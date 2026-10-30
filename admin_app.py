import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from llm_service import LLMService
from main import ocr_image_to_sorted_texts, process_pdf, segment_text
from models import AncientBookRecord, KnowledgeTriple, SessionLocal, TextChunk, init_db, serialize_record, session_scope


st.set_page_config(page_title="历史典籍内容结构化提取系统", page_icon="典", layout="wide")

st.markdown(
    """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stApp {background: #f3efe6;}
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #8b4a15 0%, #6a3c12 100%);
        border-right: 1px solid rgba(255,255,255,0.08);
        width: 270px;
    }
    [data-testid="stSidebar"] > div:first-child {padding-top: 10px;}
    [data-testid="stSidebar"] * {color: #ffffff;}
    [data-testid="stSidebar"] a {color: #ffffff; text-decoration: none;}

    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] {gap: 6px;}
    [data-testid="stSidebar"] .stRadio label {
        border-radius: 10px;
        padding: 10px 10px;
        margin: 0px;
        background: rgba(255,255,255,0.00);
        border: 1px solid rgba(255,255,255,0.06);
        transition: all 120ms ease-in-out;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(255,255,255,0.10);
        border-color: rgba(255,255,255,0.10);
        transform: translateX(1px);
    }
    [data-testid="stSidebar"] .stRadio label > div {width: 100%;}
    [data-testid="stSidebar"] .stRadio label > input {opacity: 0; position: absolute;}
    [data-testid="stSidebar"] .stRadio label > input:checked + div {
        background: rgba(255,255,255,0.14);
        border-radius: 10px;
        padding: 10px 10px;
        margin: -10px -10px;
        border: 1px solid rgba(255,255,255,0.16);
        box-shadow: 0 8px 18px rgba(0,0,0,0.16);
    }
    [data-testid="stSidebar"] .stRadio p {margin: 0; font-weight: 600; letter-spacing: 0.2px;}

    .logo-wrap {
        display:flex;
        align-items:center;
        gap:10px;
        padding: 10px 8px 4px 8px;
    }
    .logo-badge{
        width: 34px;
        height: 34px;
        border-radius: 10px;
        background: rgba(255,255,255,0.16);
        display:flex;
        align-items:center;
        justify-content:center;
        font-weight: 800;
        border: 1px solid rgba(255,255,255,0.18);
    }
    .logo-title{font-size: 14px; font-weight: 800; line-height: 1.1;}
    .logo-sub{font-size: 11px; opacity: 0.85; margin-top: 2px;}

    .topbar {
        background: #ffffff;
        border-bottom: 1px solid #eee;
        padding: 10px 14px;
        border-radius: 10px;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 1px 6px rgba(0,0,0,0.06);
    }
    .topbar-title {font-size: 16px; font-weight: 700; color: #333;}
    .topbar-sub {font-size: 12px; color: #888; margin-top: 2px;}
    .userpill {
        background: #f7f7f7;
        border: 1px solid #eee;
        padding: 6px 10px;
        border-radius: 999px;
        color: #333;
        font-size: 12px;
    }
    .card {
        background: #ffffff;
        border: 1px solid #eee;
        border-radius: 12px;
        padding: 12px 14px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.04);
    }
</style>
""",
    unsafe_allow_html=True,
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


def fetch_records():
    db = SessionLocal()
    try:
        return db.query(AncientBookRecord).order_by(AncientBookRecord.created_at.desc()).all()
    finally:
        db.close()


def build_records_dataframe(records):
    return pd.DataFrame(
        [
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
            for record in records
        ]
    )


def save_uploaded_file(uploaded_file):
    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(uploaded_file.read())
        return tmp_file.name


def run_ocr_on_path(file_path: str) -> str:
    if file_path.lower().endswith(".pdf"):
        output_txt_path = process_pdf(file_path)
        with open(output_txt_path, "r", encoding="utf-8") as file:
            return file.read()
    texts = ocr_image_to_sorted_texts(file_path)
    return "\n".join(texts)


def render_topbar(title: str, subtitle: str):
    st.markdown(
        f"""
<div class="topbar">
  <div>
    <div class="topbar-title">{title}</div>
    <div class="topbar-sub">{subtitle}</div>
  </div>
  <div class="userpill">Admin User</div>
</div>
""",
        unsafe_allow_html=True,
    )


def ensure_state():
    st.session_state.setdefault("draft_text", "")
    st.session_state.setdefault("draft_source_name", "")
    st.session_state.setdefault("draft_source_type", "")
    st.session_state.setdefault("draft_tags", "")
    st.session_state.setdefault("draft_status", "待校对")
    st.session_state.setdefault("draft_extraction", None)
    st.session_state.setdefault("selected_record_id", None)
    st.session_state.setdefault("llm_api_key", os.getenv("OPENAI_API_KEY", ""))
    st.session_state.setdefault("llm_base_url", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    st.session_state.setdefault("llm_model", os.getenv("LLM_MODEL", "gpt-4o-mini"))


def make_llm():
    return LLMService(
        api_key=st.session_state.get("llm_api_key"),
        base_url=st.session_state.get("llm_base_url"),
        model=st.session_state.get("llm_model"),
    )


def save_current_record(llm_service: LLMService, title, author, dynasty, summary, translation, tags, status):
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
        db.flush()
        chunks = segment_text(original_text)
        for i, chunk_content in enumerate(chunks):
            db.add(TextChunk(record_id=new_record.id, content=chunk_content, chunk_index=i))
        if extraction and hasattr(extraction, "triples"):
            for t in extraction.triples:
                db.add(
                    KnowledgeTriple(
                        record_id=new_record.id,
                        subject=t.subject,
                        predicate=t.predicate,
                        object=t.object,
                        context=t.context,
                    )
                )


def reset_draft():
    st.session_state["draft_text"] = ""
    st.session_state["draft_source_name"] = ""
    st.session_state["draft_source_type"] = ""
    st.session_state["draft_tags"] = ""
    st.session_state["draft_status"] = "待校对"
    st.session_state["draft_extraction"] = None


init_db()
ensure_state()
llm_service = make_llm()
status_info = llm_service.get_status()
records = fetch_records()

st.sidebar.markdown(
    """
<div class="logo-wrap">
  <div class="logo-badge">典</div>
  <div>
    <div class="logo-title">古籍智能系统</div>
    <div class="logo-sub">历史典籍结构化提取平台</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")
st.sidebar.write(f"模型：`{status_info['model']}`")
st.sidebar.write(f"模式：`{status_info['mode_label']}`")
st.sidebar.markdown("---")

nav_items = [
    ("🏠 首页", "首页"),
    ("🧾 OCR校对", "OCR校对"),
    ("🧠 结构化提取", "结构化提取"),
    ("📚 文献管理", "文献管理"),
    ("🕸️ 知识图谱展示", "知识图谱展示"),
    ("💬 历史问题咨询", "历史问题咨询"),
    ("⚙️ 系统设置", "系统设置"),
]
nav_labels = [item[0] for item in nav_items]
nav_label_to_key = {label: key for label, key in nav_items}
page_label = st.sidebar.radio("导航", options=nav_labels, label_visibility="collapsed")
page = nav_label_to_key.get(page_label, "首页")


if page == "首页":
    render_topbar("历史典籍内容结构化提取系统", "首页 / 系统概览")
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("总记录数", len(records))
    metric_col2.metric("待校对", sum(1 for item in records if item.status == "待校对"))
    metric_col3.metric("已入库", sum(1 for item in records if item.status == "已入库"))
    metric_col4.metric("模型模式", status_info["mode_label"])
    st.subheader("最近记录")
    if records:
        st.dataframe(build_records_dataframe(records).head(10), use_container_width=True, hide_index=True)
    else:
        st.info("当前暂无记录，请先进行 OCR 导入或结构化提取。")


elif page == "OCR校对":
    render_topbar("OCR校对", "首页 / OCR校对")
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        keyword = st.text_input("关键字", placeholder="输入标题/来源/标签/原文关键字")
    with col2:
        type_filter = st.selectbox("类型", options=["全部", "图片", "PDF"])
    with col3:
        status_filter = st.selectbox("OCR状态", options=["全部", "待校对", "待提取", "已入库", "需复核"])
    with col4:
        query = st.button("查询", type="primary")

    filtered_records = records
    if query or keyword or type_filter != "全部" or status_filter != "全部":
        filtered_records = []
        for item in records:
            haystack = " ".join([item.title or "", item.source_name or "", item.tags or "", item.original_text or ""])
            keyword_hit = True if not keyword else (keyword.lower() in haystack.lower())
            type_hit = True
            if type_filter == "图片":
                type_hit = (item.source_type or "image") != "pdf"
            elif type_filter == "PDF":
                type_hit = (item.source_type or "") == "pdf"
            status_hit = True if status_filter == "全部" else (item.status == status_filter)
            if keyword_hit and type_hit and status_hit:
                filtered_records.append(item)

    if filtered_records:
        table_df = pd.DataFrame(
            [
                {
                    "页面": item.id,
                    "图片": item.source_name or "",
                    "类型": "PDF" if (item.source_type or "") == "pdf" else "图片",
                    "朝代": item.dynasty or "",
                    "OCR状态": item.status or "",
                    "更新时间": item.updated_at.strftime("%Y-%m-%d %H:%M") if item.updated_at else "",
                }
                for item in filtered_records
            ]
        )
        page_size = st.selectbox("每页", options=[10, 20, 50], index=0)
        total = len(table_df)
        total_pages = max(1, (total + page_size - 1) // page_size)
        current = st.number_input("页码", min_value=1, max_value=total_pages, value=1, step=1)
        start = (current - 1) * page_size
        end = start + page_size
        st.dataframe(table_df.iloc[start:end], use_container_width=True, hide_index=True)
        st.caption(f"共 {total} 条，当前第 {current}/{total_pages} 页")
    else:
        st.info("暂无数据")

    st.divider()
    st.subheader("导入新文件并OCR")
    left_col, right_col = st.columns([2, 3])
    with left_col:
        uploaded_file = st.file_uploader("上传古籍图片或 PDF", type=["png", "jpg", "jpeg", "pdf"])
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
            st.success("OCR 完成，请在右侧校对文本。")
    with right_col:
        st.text_area("OCR 识别文本", key="draft_text", height=320)
        st.text_input("来源文件名", key="draft_source_name")
        st.text_input("标签（逗号分隔）", key="draft_tags")
        st.selectbox("记录状态", ["待校对", "待提取", "已入库", "需复核"], key="draft_status")


elif page == "结构化提取":
    render_topbar("结构化提取", "首页 / 结构化提取")
    if not st.session_state.get("draft_text", "").strip():
        st.warning("请先在“OCR校对”页面完成 OCR，或直接粘贴原文。")
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
            draft_translation = st.text_area("现代汉语译文", value=extraction_data.get("modern_translation") or "", height=220)
            st.subheader("实体结果")
            entity_rows = extraction_to_rows(extraction)
            if entity_rows:
                st.dataframe(pd.DataFrame(entity_rows), use_container_width=True, hide_index=True)
            else:
                st.info("当前未识别到明显实体。")
            action_col1, action_col2 = st.columns(2)
            with action_col1:
                if st.button("保存为数据库记录"):
                    save_current_record(
                        llm_service,
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


elif page == "文献管理":
    render_topbar("文献管理", "首页 / 文献管理")
    if not records:
        st.info("暂无可管理记录。")
    else:
        left, right = st.columns([2, 3])
        with left:
            keyword = st.text_input("关键词", placeholder="检索标题、作者、原文、标签")
            dynasties = sorted({item.dynasty for item in records if item.dynasty})
            dynasty_filter = st.selectbox("朝代筛选", ["全部"] + dynasties)
            statuses = sorted({item.status for item in records if item.status})
            status_filter = st.selectbox("状态筛选", ["全部"] + statuses)
            filtered = []
            for item in records:
                haystack = " ".join([item.title or "", item.author or "", item.original_text or "", item.tags or ""])
                keyword_hit = True if not keyword else (keyword.lower() in haystack.lower())
                dynasty_hit = dynasty_filter == "全部" or item.dynasty == dynasty_filter
                status_hit = status_filter == "全部" or item.status == status_filter
                if keyword_hit and dynasty_hit and status_hit:
                    filtered.append(item)
            st.write(f"匹配到 `{len(filtered)}` 条记录。")
            st.dataframe(build_records_dataframe(filtered), use_container_width=True, hide_index=True)
            selected_id = st.selectbox("选择记录", options=[item.id for item in filtered] if filtered else [records[0].id])
            st.session_state["selected_record_id"] = selected_id
        with right:
            current_id = st.session_state.get("selected_record_id") or records[0].id
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
                    new_translation = st.text_area("现代译文", value=record.modern_translation or "", height=220, key=f"trans_{record.id}")
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


elif page == "知识图谱展示":
    render_topbar("知识图谱展示", "首页 / 知识图谱展示")
    db = SessionLocal()
    all_triples = db.query(KnowledgeTriple).all()
    db.close()
    if not all_triples:
        st.warning("尚未从记录中提取任何知识三元组。")
    else:
        col1, col2 = st.columns([2, 1])
        with col2:
            search_subject = st.text_input("主体检索", placeholder="如：鲁迅")
        if search_subject:
            all_triples = [t for t in all_triples if search_subject.lower() in (t.subject or "").lower()]
        triple_df = pd.DataFrame(
            [
                {
                    "主体": t.subject,
                    "关系": t.predicate,
                    "客体": t.object,
                    "记录ID": t.record_id,
                    "上下文": t.context or "",
                }
                for t in all_triples
            ]
        )
        st.dataframe(triple_df, use_container_width=True, hide_index=True)


elif page == "历史问题咨询":
    render_topbar("历史问题咨询", "首页 / 历史问题咨询")
    if not records:
        st.info("请先导入并保存古籍数据。")
    else:
        selected_q_id = st.selectbox(
            "选择背景古籍记录",
            options=[r.id for r in records],
            format_func=lambda x: next((f"{r.title} (ID:{r.id})" for r in records if r.id == x), str(x)),
        )
        db = SessionLocal()
        try:
            current_record = db.query(AncientBookRecord).filter(AncientBookRecord.id == selected_q_id).first()
            if current_record:
                q_col1, q_col2 = st.columns([1, 2])
                with q_col1:
                    st.subheader("文本分段")
                    chunks = current_record.chunks
                    if chunks:
                        for chunk in chunks:
                            with st.expander(f"段落 {chunk.chunk_index + 1}"):
                                st.write(chunk.content)
                    else:
                        st.warning("该记录尚未生成分段。")
                with q_col2:
                    st.subheader("提问")
                    st.markdown(f"文献：**{current_record.title or '未命名'}**")
                    user_question = st.text_input("请输入问题", placeholder="例如：鲁迅在广州发生了什么？")
                    if user_question and st.button("咨询专家 (LLM)", type="primary"):
                        with st.spinner("正在分析并回答..."):
                            answer = llm_service.ask_historical_question(current_record.original_text, user_question)
                            st.success(answer)
        finally:
            db.close()


elif page == "系统设置":
    render_topbar("系统设置", "首页 / 系统设置")
    st.subheader("当前运行配置")
    st.write(f"模型状态：`{status_info['mode_label']}`")
    st.write(f"模型名称：`{status_info['model']}`")
    st.write(f"OPENAI API 已配置：`{'是' if status_info['api_enabled'] else '否'}`")
    st.write(f"当前工作目录：`{Path.cwd()}`")
    st.divider()
    st.subheader("大模型接入（OpenAI 兼容接口）")
    preset = st.selectbox(
        "Base URL 预设",
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
    api_key_input = st.text_input("API Key", value=st.session_state.get("llm_api_key", ""), type="password")
    base_url_input = st.text_input("Base URL", value=st.session_state.get("llm_base_url", "https://api.openai.com/v1"))
    model_input = st.text_input("模型名", value=st.session_state.get("llm_model", "gpt-4o-mini"))
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
        if st.button("应用并刷新"):
            st.session_state["llm_api_key"] = api_key_input
            st.session_state["llm_base_url"] = base_url_input
            st.session_state["llm_model"] = model_input
            st.rerun()
    st.divider()
    st.subheader("数据导出")
    export_rows = [serialize_record(item) for item in records]
    export_json = json.dumps(export_rows, ensure_ascii=False, indent=2)
    export_csv = pd.DataFrame(export_rows).to_csv(index=False)
    st.download_button("下载 JSON", data=export_json, file_name="ancient_book_records.json", mime="application/json")
    st.download_button("下载 CSV", data=export_csv, file_name="ancient_book_records.csv", mime="text/csv")
