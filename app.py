import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from llm_service import LLMService
from main import ocr_image_to_sorted_texts, process_pdf, segment_text
from models import AncientBookRecord, SessionLocal, init_db, serialize_record, session_scope, TextChunk, KnowledgeTriple


st.set_page_config(page_title="古籍结构化提取系统", page_icon="🏮", layout="wide")
st.session_state.setdefault("llm_api_key", os.getenv("OPENAI_API_KEY", ""))
st.session_state.setdefault("llm_base_url", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
st.session_state.setdefault("llm_model", os.getenv("LLM_MODEL", "gpt-4o-mini"))

init_db()
llm_service = LLMService(
    api_key=st.session_state.get("llm_api_key"),
    base_url=st.session_state.get("llm_base_url"),
    model=st.session_state.get("llm_model"),
)


def safe_model_dump(model_obj):
    if hasattr(model_obj, "model_dump"):
        return model_obj.model_dump()
    return model_obj.dict()


def extraction_to_rows(extraction):
    entities = getattr(extraction, "entities", []) or []
    rows = []
    for entity in entities:
        if hasattr(entity, "model_dump"):
            rows.append(entity.model_dump())
        elif hasattr(entity, "dict"):
            rows.append(entity.dict())
        else:
            rows.append(entity)
    return rows


def initialize_state():
    defaults = {
        "draft_text": "",
        "draft_source_name": "",
        "draft_source_type": "",
        "draft_tags": "",
        "draft_status": "待校对",
        "draft_extraction": None,
        "selected_record_id": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def fetch_records():
    db = SessionLocal()
    try:
        return db.query(AncientBookRecord).order_by(AncientBookRecord.created_at.desc()).all()
    finally:
        db.close()


def build_records_dataframe(records):
    rows = []
    for record in records:
        rows.append(
            {
                "ID": record.id,
                "标题": record.title or "",
                "作者": record.author or "",
                "朝代": record.dynasty or "",
                "状态": record.status or "",
                "来源": record.source_name or "",
                "标签": record.tags or "",
                "创建时间": record.created_at.strftime("%Y-%m-%d %H:%M") if record.created_at else "",
                "更新时间": record.updated_at.strftime("%Y-%m-%d %H:%M") if record.updated_at else "",
            }
        )
    return pd.DataFrame(rows)


def run_ocr_on_path(file_path: str) -> str:
    if file_path.lower().endswith(".pdf"):
        output_txt_path = process_pdf(file_path)
        with open(output_txt_path, "r", encoding="utf-8") as file:
            return file.read()
    texts = ocr_image_to_sorted_texts(file_path)
    return "\n".join(texts)


def save_uploaded_file(uploaded_file):
    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(uploaded_file.read())
        return tmp_file.name


def save_current_record(title, author, dynasty, summary, translation, tags, status):
    extraction = st.session_state.get("draft_extraction")
    structured_json = safe_model_dump(extraction) if extraction else None
    original_text = st.session_state.get("draft_text", "")
    
    with session_scope() as db:
        new_record = AncientBookRecord(
            title=title or None,
            author=author or None,
            dynasty=dynasty or None,
            summary=summary or None,
            original_text=original_text,
            structured_json=structured_json,
            modern_translation=translation or None,
            source_type=st.session_state.get("draft_source_type") or None,
            source_name=st.session_state.get("draft_source_name") or None,
            tags=tags or None,
            status=status,
            llm_model=llm_service.get_status()["model"],
        )
        db.add(new_record)
        db.flush()  # Get ID for relationships
        
        # Save chunks
        chunks = segment_text(original_text)
        for i, chunk_content in enumerate(chunks):
            db.add(TextChunk(record_id=new_record.id, content=chunk_content, chunk_index=i))
            
        # Save triples from extraction
        if extraction and hasattr(extraction, 'triples'):
            for t in extraction.triples:
                db.add(KnowledgeTriple(
                    record_id=new_record.id,
                    subject=t.subject,
                    predicate=t.predicate,
                    object=t.object,
                    context=t.context
                ))


def reset_draft():
    st.session_state["draft_text"] = ""
    st.session_state["draft_source_name"] = ""
    st.session_state["draft_source_type"] = ""
    st.session_state["draft_tags"] = ""
    st.session_state["draft_status"] = "待校对"
    st.session_state["draft_extraction"] = None


initialize_state()
records = fetch_records()
record_df = build_records_dataframe(records) if records else pd.DataFrame()
status_info = llm_service.get_status()

st.sidebar.title("🏮 古籍结构化提取系统")
st.sidebar.caption("面向历史典籍的 OCR + 大模型结构化提取 + 数据管理平台")
st.sidebar.write(f"当前模型模式：`{status_info['mode_label']}`")
st.sidebar.write(f"当前模型：`{status_info['model']}`")

tabs = st.tabs(
    [
        "1. 系统总览",
        "2. OCR 导入",
        "3. 结构化提取",
        "4. 记录检索",
        "5. 详情编辑",
        "6. 统计分析",
        "7. 数据导出",
        "8. 知识图谱",
        "9. 历史问答与分段",
        "10. 系统设置",
    ]
)

with tabs[0]:
    st.header("系统总览")
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("总记录数", len(records))
    metric_col2.metric("待校对", sum(1 for item in records if item.status == "待校对"))
    metric_col3.metric("已入库", sum(1 for item in records if item.status == "已入库"))
    metric_col4.metric("模型模式", status_info["mode_label"])

    st.subheader("业务模块设计")
    st.markdown(
        """
1. OCR 导入模块：上传图片/PDF，复用现有古籍识别能力。
2. 结构化提取模块：抽取标题、作者、朝代、实体、摘要和现代译文。
3. 校对修订模块：人工调整识别文本和大模型结果。
4. 记录检索模块：按关键词、朝代、状态和标签查询。
5. 详情编辑模块：对单条记录执行增删改查。
6. 统计分析模块：按朝代、状态、来源做基础统计。
7. 数据导出模块：导出 JSON/CSV，便于论文、汇报和二次处理。
8. 系统设置模块：管理模型接入、运行方式和部署说明。
        """
    )

    st.subheader("最近记录")
    if records:
        st.dataframe(record_df.head(10), use_container_width=True)
    else:
        st.info("当前暂无记录，可先到“2. OCR 导入”或“3. 结构化提取”模块开始处理。")

with tabs[1]:
    st.header("OCR 导入")
    left_col, right_col = st.columns([2, 3])

    with left_col:
        uploaded_file = st.file_uploader(
            "上传古籍图片或 PDF",
            type=["png", "jpg", "jpeg", "pdf"],
            key="ocr_uploader",
        )

        sample_col1, sample_col2 = st.columns(2)
        with sample_col1:
            if st.button("载入示例图片"):
                sample_path = str(Path("1.png").resolve())
                st.session_state["draft_text"] = run_ocr_on_path(sample_path)
                st.session_state["draft_source_name"] = "1.png"
                st.session_state["draft_source_type"] = "image"
                st.success("示例图片已完成 OCR。")
        with sample_col2:
            if st.button("载入示例 PDF"):
                sample_pdf = str(Path("雕菰楼《毛诗补疏》焦循.pdf").resolve())
                st.session_state["draft_text"] = run_ocr_on_path(sample_pdf)
                st.session_state["draft_source_name"] = "雕菰楼《毛诗补疏》焦循.pdf"
                st.session_state["draft_source_type"] = "pdf"
                st.success("示例 PDF 已完成 OCR。")

        if uploaded_file is not None and st.button("执行 OCR 识别", type="primary"):
            with st.spinner("正在执行 OCR，请稍候..."):
                tmp_path = save_uploaded_file(uploaded_file)
                st.session_state["draft_text"] = run_ocr_on_path(tmp_path)
                st.session_state["draft_source_name"] = uploaded_file.name
                st.session_state["draft_source_type"] = "pdf" if uploaded_file.name.lower().endswith(".pdf") else "image"
            st.success("OCR 完成，右侧可继续校对文本。")

    with right_col:
        st.text_area(
            "OCR 识别文本",
            key="draft_text",
            height=420,
            placeholder="这里会显示 OCR 识别后的古籍原文，你可以直接人工校对。",
        )
        st.text_input("来源文件名", key="draft_source_name")
        st.text_input("标签（逗号分隔）", key="draft_tags", placeholder="如：诗经,清代,序文")
        st.selectbox("记录状态", ["待校对", "待提取", "已入库", "需复核"], key="draft_status")

with tabs[2]:
    st.header("结构化提取")
    if not st.session_state.get("draft_text", "").strip():
        st.warning("请先在“2. OCR 导入”模块完成 OCR 或手动输入文本。")
    else:
        st.write(f"当前待处理来源：`{st.session_state.get('draft_source_name') or '未命名文本'}`")
        if st.button("开始结构化提取", type="primary"):
            with st.spinner("正在调用结构化提取服务..."):
                st.session_state["draft_extraction"] = llm_service.extract_and_translate(
                    st.session_state["draft_text"]
                )
            st.success("结构化提取完成。")

        extraction = st.session_state.get("draft_extraction")
        if extraction:
            extraction_data = safe_model_dump(extraction)
            meta_col1, meta_col2, meta_col3 = st.columns(3)
            with meta_col1:
                draft_title = st.text_input("标题", value=extraction_data.get("title") or "")
            with meta_col2:
                draft_author = st.text_input("作者", value=extraction_data.get("author") or "")
            with meta_col3:
                draft_dynasty = st.text_input("朝代", value=extraction_data.get("dynasty") or "")

            draft_summary = st.text_area("摘要", value=extraction_data.get("summary") or "", height=120)
            draft_translation = st.text_area(
                "现代汉语译文",
                value=extraction_data.get("modern_translation") or "",
                height=220,
            )

            st.subheader("实体结果")
            entity_rows = extraction_to_rows(extraction)
            if entity_rows:
                st.dataframe(pd.DataFrame(entity_rows), use_container_width=True)
            else:
                st.info("当前未识别到明显实体。")

            action_col1, action_col2 = st.columns(2)
            with action_col1:
                if st.button("保存为数据库记录"):
                    save_current_record(
                        draft_title,
                        draft_author,
                        draft_dynasty,
                        draft_summary,
                        draft_translation,
                        st.session_state.get("draft_tags", ""),
                        st.session_state.get("draft_status", "已入库"),
                    )
                    st.success("记录已保存。")
            with action_col2:
                if st.button("清空当前草稿"):
                    reset_draft()
                    st.rerun()

with tabs[3]:
    st.header("记录检索")
    if not records:
        st.info("暂无记录可检索。")
    else:
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            keyword = st.text_input("关键词", placeholder="检索标题、作者、原文、标签")
        with filter_col2:
            dynasties = sorted({item.dynasty for item in records if item.dynasty})
            dynasty_filter = st.selectbox("朝代筛选", ["全部"] + dynasties)
        with filter_col3:
            statuses = sorted({item.status for item in records if item.status})
            status_filter = st.selectbox("状态筛选", ["全部"] + statuses)

        filtered_records = []
        for item in records:
            keyword_hit = True
            if keyword:
                haystack = " ".join(
                    [
                        item.title or "",
                        item.author or "",
                        item.original_text or "",
                        item.tags or "",
                    ]
                )
                keyword_hit = keyword.lower() in haystack.lower()

            dynasty_hit = dynasty_filter == "全部" or item.dynasty == dynasty_filter
            status_hit = status_filter == "全部" or item.status == status_filter

            if keyword_hit and dynasty_hit and status_hit:
                filtered_records.append(item)

        st.write(f"匹配到 `{len(filtered_records)}` 条记录。")
        if filtered_records:
            filtered_df = build_records_dataframe(filtered_records)
            st.dataframe(filtered_df, use_container_width=True)
            selected_id = st.selectbox(
                "选择记录以进入详情编辑",
                options=[item.id for item in filtered_records],
                index=0,
            )
            st.session_state["selected_record_id"] = selected_id
        else:
            st.warning("没有符合条件的记录。")

with tabs[4]:
    st.header("详情编辑")
    if not records:
        st.info("暂无可编辑记录。")
    else:
        all_ids = [item.id for item in records]
        default_id = st.session_state.get("selected_record_id") or all_ids[0]
        current_id = st.selectbox(
            "选择记录 ID",
            options=all_ids,
            index=all_ids.index(default_id) if default_id in all_ids else 0,
        )

        db = SessionLocal()
        try:
            record = db.query(AncientBookRecord).filter(AncientBookRecord.id == current_id).first()
            if record:
                edit_col1, edit_col2, edit_col3 = st.columns(3)
                with edit_col1:
                    new_title = st.text_input("标题", value=record.title or "", key=f"title_{record.id}")
                with edit_col2:
                    new_author = st.text_input("作者", value=record.author or "", key=f"author_{record.id}")
                with edit_col3:
                    new_dynasty = st.text_input("朝代", value=record.dynasty or "", key=f"dynasty_{record.id}")

                new_status = st.selectbox(
                    "状态",
                    options=["待校对", "待提取", "已入库", "需复核"],
                    index=["待校对", "待提取", "已入库", "需复核"].index(record.status)
                    if record.status in ["待校对", "待提取", "已入库", "需复核"]
                    else 2,
                    key=f"status_{record.id}",
                )
                new_tags = st.text_input("标签", value=record.tags or "", key=f"tags_{record.id}")
                new_summary = st.text_area("摘要", value=record.summary or "", height=120, key=f"summary_{record.id}")
                new_original = st.text_area("原文", value=record.original_text or "", height=220, key=f"orig_{record.id}")
                new_translation = st.text_area(
                    "现代译文",
                    value=record.modern_translation or "",
                    height=220,
                    key=f"trans_{record.id}",
                )

                btn_col1, btn_col2, btn_col3 = st.columns(3)
                with btn_col1:
                    if st.button("更新记录", type="primary"):
                        record.title = new_title or None
                        record.author = new_author or None
                        record.dynasty = new_dynasty or None
                        record.status = new_status
                        record.tags = new_tags or None
                        record.summary = new_summary or None
                        record.original_text = new_original
                        record.modern_translation = new_translation or None
                        db.commit()
                        st.success("记录已更新。")
                        st.rerun()
                with btn_col2:
                    st.json(record.structured_json or {})
                with btn_col3:
                    if st.button("删除记录"):
                        db.delete(record)
                        db.commit()
                        st.warning("记录已删除。")
                        st.rerun()
        finally:
            db.close()

with tabs[5]:
    st.header("统计分析")
    if not records:
        st.info("暂无数据可统计。")
    else:
        stats_col1, stats_col2 = st.columns(2)
        with stats_col1:
            dynasty_counts = {}
            for item in records:
                key = item.dynasty or "未标注"
                dynasty_counts[key] = dynasty_counts.get(key, 0) + 1
            st.subheader("按朝代统计")
            st.bar_chart(pd.DataFrame({"数量": dynasty_counts}))

        with stats_col2:
            status_counts = {}
            for item in records:
                key = item.status or "未标注"
                status_counts[key] = status_counts.get(key, 0) + 1
            st.subheader("按状态统计")
            st.bar_chart(pd.DataFrame({"数量": status_counts}))

        st.subheader("文本长度统计")
        length_df = pd.DataFrame(
            [
                {
                    "ID": item.id,
                    "标题": item.title or f"记录{item.id}",
                    "原文长度": len(item.original_text or ""),
                    "译文长度": len(item.modern_translation or ""),
                }
                for item in records
            ]
        )
        st.dataframe(length_df, use_container_width=True)

with tabs[6]:
    st.header("数据导出")
    if not records:
        st.info("暂无数据可导出。")
    else:
        export_rows = [serialize_record(item) for item in records]
        export_json = json.dumps(export_rows, ensure_ascii=False, indent=2)
        export_csv = pd.DataFrame(export_rows).to_csv(index=False)

        st.download_button(
            "下载 JSON",
            data=export_json,
            file_name="ancient_book_records.json",
            mime="application/json",
        )
        st.download_button(
            "下载 CSV",
            data=export_csv,
            file_name="ancient_book_records.csv",
            mime="text/csv",
        )
        st.json(export_rows[:2])

with tabs[7]:
    st.header("知识图谱 (关系抽取)")
    if not records:
        st.info("暂无数据。")
    else:
        db = SessionLocal()
        all_triples = db.query(KnowledgeTriple).all()
        db.close()
        
        if not all_triples:
            st.warning("尚未从记录中提取任何知识三元组。")
            st.info("提示：在“3. 结构化提取”中保存记录时，系统会自动提取三元组。")
        else:
            st.subheader("全局知识三元组列表")
            triple_df = pd.DataFrame([
                {
                    "ID": t.id,
                    "主体 (Subject)": t.subject,
                    "关系 (Predicate)": t.predicate,
                    "客体 (Object)": t.object,
                    "记录ID": t.record_id,
                    "上下文": t.context
                } for t in all_triples
            ])
            st.dataframe(triple_df, use_container_width=True)
            
            # Simple relationship search
            st.divider()
            st.subheader("关系检索")
            search_subject = st.text_input("搜索主体 (如：鲁迅)")
            if search_subject:
                results = [t for t in all_triples if search_subject.lower() in t.subject.lower()]
                if results:
                    st.write(f"找到关于 `{search_subject}` 的 `{len(results)}` 条关系：")
                    for r in results:
                        st.info(f"**{r.subject}** --({r.predicate})--> **{r.object}**  \n*来源：{r.context or '未提供'}*")
                else:
                    st.write("未找到相关关系。")

with tabs[8]:
    st.header("历史问答与文本分段")
    if not records:
        st.info("请先导入并保存古籍数据。")
    else:
        selected_q_id = st.selectbox(
            "选择背景古籍记录",
            options=[r.id for r in records],
            format_func=lambda x: next((f"{r.title} (ID:{r.id})" for r in records if r.id == x), x)
        )
        
        db = SessionLocal()
        current_record = db.query(AncientBookRecord).filter(AncientBookRecord.id == selected_q_id).first()
        
        if current_record:
            q_col1, q_col2 = st.columns([1, 2])
            with q_col1:
                st.subheader("文本分段预览")
                chunks = current_record.chunks
                if chunks:
                    for chunk in chunks:
                        with st.expander(f"段落 {chunk.chunk_index + 1}"):
                            st.write(chunk.content)
                else:
                    st.warning("该记录尚未生成分段，可能是旧数据。")
            
            with q_col2:
                st.subheader("历史问题咨询")
                st.markdown(f"基于当前文献：**{current_record.title or '未命名'}**")
                user_question = st.text_input("请输入您想了解的问题", placeholder="例如：鲁迅在广州发生了什么？")
                
                if user_question:
                    if st.button("咨询专家 (LLM)"):
                        with st.spinner("正在分析文献并回答..."):
                            answer = llm_service.ask_historical_question(current_record.original_text, user_question)
                            st.markdown("### 专家回答")
                            st.success(answer)
        db.close()

with tabs[9]:
    st.header("系统设置")
    st.subheader("当前运行配置")
    st.write(f"模型状态：`{status_info['mode_label']}`")
    st.write(f"模型名称：`{status_info['model']}`")
    st.write(f"OPENAI API 已配置：`{'是' if status_info['api_enabled'] else '否'}`")
    st.write(f"当前工作目录：`{Path.cwd()}`")

    st.divider()
    st.subheader("大模型接入（OpenAI 兼容接口）")
    st.caption("填写后可启用“现代译文翻译 / 历史问答 / 三元组抽取”的在线大模型能力；不填则保持演示模式。")

    preset = st.selectbox(
        "选择一个 Base URL 预设",
        options=[
            "OpenAI 官方（https://api.openai.com/v1）",
            "本地 LM Studio（http://localhost:1234/v1）",
            "本地 vLLM（http://localhost:8000/v1）",
            "自定义",
        ],
        index=0,
    )
    if preset.startswith("OpenAI 官方"):
        st.session_state["llm_base_url"] = "https://api.openai.com/v1"
    elif preset.startswith("本地 LM Studio"):
        st.session_state["llm_base_url"] = "http://localhost:1234/v1"
    elif preset.startswith("本地 vLLM"):
        st.session_state["llm_base_url"] = "http://localhost:8000/v1"

    api_key_input = st.text_input(
        "API Key（不会写入代码，建议使用环境变量或 Streamlit Secrets）",
        value=st.session_state.get("llm_api_key", ""),
        type="password",
    )
    base_url_input = st.text_input(
        "Base URL（OpenAI 兼容）",
        value=st.session_state.get("llm_base_url", "https://api.openai.com/v1"),
    )
    model_input = st.text_input(
        "模型名（例如：gpt-4o-mini 或你本地部署的模型名）",
        value=st.session_state.get("llm_model", "gpt-4o-mini"),
    )

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("连通性测试"):
            tester = LLMService(api_key=api_key_input, base_url=base_url_input, model=model_input)
            result = tester.validate_connection()
            if result.get("ok"):
                st.success(result.get("message", "测试成功"))
            else:
                st.error(result.get("message", "测试失败"))

    with btn_col2:
        if st.button("应用设置并刷新"):
            st.session_state["llm_api_key"] = api_key_input
            st.session_state["llm_base_url"] = base_url_input
            st.session_state["llm_model"] = model_input
            st.rerun()

    st.subheader("部署后建议的使用流程")
    st.markdown(
        """
1. 上传图片或 PDF，执行 OCR。
2. 在识别结果区域人工校对文本。
3. 执行结构化提取，生成标题、摘要、实体和译文。
4. 保存到数据库。
5. 在检索和详情编辑模块中做增删查改。
6. 在统计和导出模块中完成成果整理。
        """
    )

    st.subheader("命令行运行方式")
    st.code("streamlit run app.py", language="bash")
