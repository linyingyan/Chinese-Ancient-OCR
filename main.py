from paddleocr import PaddleOCR
from pathlib import Path
import fitz  # PyMuPDF
import numpy as np
import re
import tempfile


# 初始化 OCR 模型（全局单例）
ocr = PaddleOCR(
    device="cpu",  # 启用GPU加速
    # ocr_version="PP-OCRv5",  # 使用v5模型（最新版本）
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    enable_mkldnn=False,  # 禁用 MKL-DNN 以避免 ONEDNN 错误
)


def _to_list(x):
    """将任意序列（含 numpy 数组）转为 list，None 保持 None"""
    if x is None:
        return None
    if isinstance(x, list):
        return x
    if hasattr(x, "tolist"):
        try:
            return x.tolist()
        except Exception:
            pass
    try:
        return list(x)
    except Exception:
        return None


def ocr_image_to_sorted_texts(img_path: str, save_vis: bool = False, save_json: bool = False) -> list:
    """
    对单张图片执行 OCR，返回按"从右到左、从上到下"排序的文本列表。
    :param img_path: 图片路径
    :param save_vis: 是否保存可视化结果图
    :param save_json: 是否保存 JSON 结果
    :return: 排序后的文本列表
    """
    # PaddleOCR v3 (PaddleX backend) usage
    result = ocr.predict(img_path)
    collected_items = []  # (cx, cy, text, box)

    for res in result:
        # 可选保存可视化/JSON
        if save_vis or save_json:
            try:
                if save_vis:
                    res.save_to_img("output")
                if save_json:
                    res.save_to_json("output")
            except Exception as e:
                print(f"保存结果失败: {e}")

        # 获取文本和边界框
        # PaddleOCR v3 result object behaves like a dict
        try:
            texts = res['rec_texts']
            boxes = res['rec_boxes']
            polys = res['dt_polys']
        except Exception:
            # 尝试通过 json 属性访问 (兼容性兜底)
            try:
                texts = res.json['res']['rec_texts']
                boxes = res.json['res']['rec_boxes']
                polys = res.json['res']['dt_polys']
            except Exception:
                texts = None
                boxes = None
                polys = None

        texts_list = _to_list(texts)
        boxes_list = _to_list(boxes)

        if texts_list and boxes_list and len(texts_list) > 0 and len(boxes_list) > 0:
            for t, b in zip(texts_list, boxes_list):
                # 检查 box 格式
                if len(b) == 4 and isinstance(b[0], (int, float, np.number)):
                    # [xmin, ymin, xmax, ymax] 格式
                    xmin, ymin, xmax, ymax = b
                elif len(b) == 4 and isinstance(b[0], (list, tuple, np.ndarray)):
                    # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] 格式 (polygon)
                    xs = [p[0] for p in b]
                    ys = [p[1] for p in b]
                    xmin, xmax = min(xs), max(xs)
                    ymin, ymax = min(ys), max(ys)
                else:
                    continue

                cx = (xmin + xmax) / 2.0
                cy = (ymin + ymax) / 2.0
                collected_items.append((cx, cy, t, b))

    if not collected_items:
        return []

    # 按列分组：x 坐标接近的文本框归为同一列
    # 先按 cx 从右到左排序
    collected_items.sort(key=lambda item: -item[0])

    columns = []
    column_x_threshold = 30  # x 坐标差异阈值（像素），可根据实际调整

    for item in collected_items:
        cx, cy, text, box = item
        # 查找是否有现有列与当前 cx 接近
        found_column = False
        for col in columns:
            col_cx_avg = sum(it[0] for it in col) / len(col)
            if abs(cx - col_cx_avg) < column_x_threshold:
                col.append(item)
                found_column = True
                break
        if not found_column:
            columns.append([item])

    # 每列内按 y 从上到下排序，然后合并文本
    ordered_texts = []
    for col in columns:
        col.sort(key=lambda item: item[1])  # 按 cy 排序
        col_text = "".join(item[2] for item in col)  # 同列文本合并
        ordered_texts.append(col_text)

    return ordered_texts


def process_pdf(pdf_path: str, dpi: int = 300, save_page_images: bool = True) -> Path:
    """
    处理 PDF：分页渲染成图片 → 逐页 OCR → 每页独立 txt + 整本合并 txt
    :param pdf_path: PDF 文件路径
    :param dpi: 渲染 DPI（越高越清晰，推荐 200-300）
    :param save_page_images: 是否保留分页图片（默认保留）
    :return: 整本合并 txt 的路径
    """
    pdf_stem = Path(pdf_path).stem
    base_out = Path("output") / pdf_stem
    images_dir = base_out / "images"
    page_txt_dir = base_out / "page_txt"
    errors_log = base_out / "errors.log"

    if save_page_images:
        images_dir.mkdir(parents=True, exist_ok=True)
    page_txt_dir.mkdir(parents=True, exist_ok=True)

    all_texts = []
    with open(errors_log, "w", encoding="utf-8") as errf:
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            errf.write(f"打开 PDF 失败: {e}\n")
            print(f"打开 PDF 失败: {e}")
            return base_out / f"{pdf_stem}.txt"

        total_pages = len(doc)
        print(f"开始处理 PDF：{pdf_path}，共 {total_pages} 页")

        for page_index in range(total_pages):
            page_num = page_index + 1
            try:
                # 渲染为高分辨率图片
                page = doc[page_index]
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                if save_page_images:
                    img_path = images_dir / f"page_{page_num:03d}.png"
                    pix.save(str(img_path))
                    img_path_str = str(img_path)
                else:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
                        tmp_path = tmp_img.name
                    pix.save(tmp_path)
                    img_path_str = tmp_path

                # OCR 识别并排序
                ordered = ocr_image_to_sorted_texts(img_path_str, save_vis=False, save_json=False)

                # 保存当前页 txt
                page_txt_file = page_txt_dir / f"page_{page_num:03d}.txt"
                with open(page_txt_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(ordered))

                all_texts.extend(ordered)
                print(f"[OK] 第 {page_num}/{total_pages} 页完成", flush=True)
                if not save_page_images:
                    try:
                        Path(img_path_str).unlink(missing_ok=True)
                    except Exception:
                        pass

            except Exception as e:
                errf.write(f"第 {page_num} 页失败: {e}\n")
                print(f"[FAIL] 第 {page_num}/{total_pages} 页失败: {e}", flush=True)

        doc.close()

    # 合并整本 txt
    merged_txt = base_out / f"{pdf_stem}.txt"
    with open(merged_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(all_texts))

    print(f"\n整本合并完成: {merged_txt}")
    print(f"每页 txt 保存在: {page_txt_dir}")
    if save_page_images:
        print(f"分页图片保存在: {images_dir}")

    return merged_txt


def segment_text(text: str, chunk_size: int = 500) -> list:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    parts = [p.strip() for p in text.split("\n") if p.strip()]
    if len(parts) <= 1:
        parts = re.split(r"(?<=[。！？；])", text)
        parts = [p.strip() for p in parts if p.strip()]

    chunks = []
    buf = []
    buf_len = 0
    for p in parts:
        p_len = len(p)
        if buf_len + p_len + 1 <= chunk_size:
            buf.append(p)
            buf_len += p_len + 1
            continue
        if buf:
            chunks.append("\n".join(buf).strip())
        buf = [p]
        buf_len = p_len
    if buf:
        chunks.append("\n".join(buf).strip())
    return chunks

# ==================== 主入口 ====================
if __name__ == "__main__":
    # 输入路径：可修改为图片或 PDF
    input_path = "./1.png"  # 或 "./1.png"

    if str(input_path).lower().endswith(".pdf"):
        # PDF 批量处理
        process_pdf(input_path, dpi=300, save_page_images=True)
    else:
        # 单图处理
        ordered = ocr_image_to_sorted_texts(input_path, save_vis=True, save_json=True)
        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{Path(input_path).stem}.txt"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n".join(ordered))
        print(f"已按从右到左、从上到下排序写入: {out_file}")
