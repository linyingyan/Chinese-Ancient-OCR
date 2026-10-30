# 古籍 OCR 提取器

基于 PaddleOCR 的古籍文字识别工具，支持竖排文字的自动识别与排序。

## 功能特点

- **智能文字排序**：自动识别竖排古籍文字，按"从右到左、从上到下"正确排序
- **单图识别**：支持对单张图片进行 OCR 识别
- **PDF 批量处理**：自动分页渲染并逐页识别，生成独立和合并文本
- **高分辨率渲染**：支持自定义 DPI，提升识别精度
- **多格式输出**：支持 TXT、JSON、可视化标注图片

## 环境要求

- Python 3.8+
- Windows / Linux / macOS

## 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- `paddleocr` - OCR 识别引擎
- `PyMuPDF` - PDF 处理
- `paddlepaddle` - 深度学习框架
- `opencv-python` - 图像处理
- `Pillow` - 图像操作
- `numpy` - 数值计算

## 使用方法

### 1. 单图片识别

```python
python main.py
```

修改 `main.py` 中的输入路径：

```python
input_path = "./your_image.png"  # 指定图片路径
```

### 2. PDF 批量识别

```python
input_path = "./古籍文档.pdf"  # 指定 PDF 路径
```

运行后自动完成：
- 分页渲染为高清图片
- 逐页 OCR 识别
- 生成每页独立 TXT
- 合并为整本 TXT

## 输出结构

```
output/
├── [图片名].txt              # 单图识别结果
├── [图片名]_res.json         # 单图 JSON 结果
├── [图片名]_ocr_res_img.png  # 单图可视化标注
└── [PDF名]/
    ├── images/              # 分页图片
    │   ├── page_001.png
    │   ├── page_002.png
    │   └── ...
    ├── page_txt/            # 每页文本
    │   ├── page_001.txt
    │   ├── page_002.txt
    │   └── ...
    ├── [PDF名].txt          # 整本合并文本
    └── errors.log           # 错误日志
```

## 参数配置

### OCR 初始化参数

```python
ocr = PaddleOCR(
    device="cpu",                        # 设备：cpu/gpu
    use_doc_orientation_classify=False,  # 文档方向分类
    use_doc_unwarping=False,             # 文档矫正
    use_textline_orientation=False,      # 文本行方向
)
```

### PDF 处理参数

```python
process_pdf(
    pdf_path="./文档.pdf",    # PDF 路径
    dpi=300,                  # 渲染分辨率
    save_page_images=True     # 是否保留分页图片
)
```

### 单图识别参数

```python
ocr_image_to_sorted_texts(
    img_path="./图片.png",    # 图片路径
    save_vis=True,            # 保存可视化结果
    save_json=True            # 保存 JSON 结果
)
```

### 列分组阈值调整

如果文字列识别错误，可调整 `column_x_threshold` 参数（默认 30 像素）：

```python
column_x_threshold = 30  # 增大值：列合并更宽松；减小值：列分割更严格
```

## 工作原理

1. **图片预处理**：PDF 按指定 DPI 渲染为高清图片
2. **OCR 识别**：使用 PaddleOCR 检测文字区域和识别文本
3. **坐标计算**：提取每个文字框的中心坐标 (cx, cy)
4. **列分组**：按 x 坐标将文字框分组为列（从右到左）
5. **列内排序**：每列内按 y 坐标排序（从上到下）
6. **文本合并**：合并同列文字，输出排序结果

## 常见问题

### Q: 识别精度不高？
A: 尝试提高 PDF 渲染 DPI（300-500），或调整 OCR 参数

### Q: 文字列顺序错乱？
A: 调整 `column_x_threshold` 参数，适应不同古籍排版

### Q: 处理速度慢？
A: 使用 GPU 加速，将 `device="cpu"` 改为 `device="gpu"`

### Q: 内存不足？
A: 降低 DPI 或分批处理 PDF

## 技术栈

- **PaddleOCR**：百度飞桨 OCR 引擎
- **PyMuPDF (fitz)**：PDF 高性能渲染
- **OpenCV**：图像处理
- **NumPy**：数值计算

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request

