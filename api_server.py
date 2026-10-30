import json
import hashlib
import os
import tempfile
import csv
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel 
from sqlalchemy import func
from sqlalchemy.exc import OperationalError

from llm_service import LLMService
from main import ocr_image_to_sorted_texts, process_pdf, segment_text
from models import (
    AncientBookRecord,
    EventCluster,
    KnowledgeTriple,
    SessionLocal,
    SpacetimeEvent,
    TextChunk,
    init_db,
    serialize_record,
    session_scope,
)


app = FastAPI(title="Ancient OCR API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIST_DIR = Path(__file__).resolve().parent / "frontend" / "dist"
if (FRONTEND_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")), name="assets")


def _make_llm(api_key: Optional[str], base_url: Optional[str], model: Optional[str]) -> LLMService:
    return LLMService(api_key=api_key, base_url=base_url, model=model)


def _llm_from_headers(headers: Dict[str, str]) -> LLMService:
    normalized = {str(k).lower(): v for k, v in (headers or {}).items()}
    api_key = normalized.get("x-llm-api-key")
    base_url = normalized.get("x-llm-base-url")
    model = normalized.get("x-llm-model")
    return _make_llm(api_key, base_url, model)


def _run_ocr(file_path: str) -> str:
    if file_path.lower().endswith(".pdf"):
        output_txt_path = process_pdf(file_path, dpi=250, save_page_images=False)
        return Path(output_txt_path).read_text(encoding="utf-8")
    texts = ocr_image_to_sorted_texts(file_path)
    return "\n".join(texts)


def _run_ocr_with_options(file_path: str, dpi: int, mode: str) -> str:
    if file_path.lower().endswith(".pdf"):
        effective_dpi = 200 if mode == "fast" else int(dpi)
        output_txt_path = process_pdf(file_path, dpi=effective_dpi, save_page_images=False)
        return Path(output_txt_path).read_text(encoding="utf-8")
    texts = ocr_image_to_sorted_texts(file_path)
    return "\n".join(texts)


def _write_upload_to_temp_and_hash(file: UploadFile) -> tuple[str, str]:
    suffix = Path(file.filename or "").suffix or ".bin"
    h = hashlib.sha256()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
            tmp.write(chunk)
        tmp_path = tmp.name
    return tmp_path, h.hexdigest()


def _ocr_cache_dir() -> Path:
    p = Path("output") / "cache" / "ocr"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ocr_cached_or_run(file_hash: str, runner) -> str:
    cache_file = _ocr_cache_dir() / f"{file_hash}.txt"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    text = runner()
    cache_file.write_text(text, encoding="utf-8")
    return text


def _get_db():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


class ExtractRequest(BaseModel):
    text: str
    chunk_size: Optional[int] = 1200
    max_chunks: Optional[int] = 8
    force_chunk: Optional[bool] = False


class QARequest(BaseModel):
    record_id: int
    question: str


class RecordCreateRequest(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    dynasty: Optional[str] = None
    tags: Optional[str] = None
    status: Optional[str] = "待校对"
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    original_text: str
    summary: Optional[str] = None
    modern_translation: Optional[str] = None
    structured_json: Optional[Dict[str, Any]] = None


class RecordUpdateRequest(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    dynasty: Optional[str] = None
    tags: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    modern_translation: Optional[str] = None
    original_text: Optional[str] = None
    structured_json: Optional[Dict[str, Any]] = None


class RecordExtractRequest(BaseModel):
    chunk_size: Optional[int] = 1200
    max_chunks: Optional[int] = 8
    force_chunk: Optional[bool] = False
    translation_mode: Optional[str] = "auto"


class BatchExtractRequest(BaseModel):
    record_ids: list[int]
    chunk_size: Optional[int] = 1200
    max_chunks: Optional[int] = 8
    force_chunk: Optional[bool] = False
    translation_mode: Optional[str] = "auto"

class SpacetimeBuildRequest(BaseModel):
    record_ids: Optional[list[int]] = None
    use_llm: bool = True
    rebuild_all: bool = False
    max_events_per_record: int = 20


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/api/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat()}

@app.get("/")
def serve_frontend_index():
    index_file = FRONTEND_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    raise HTTPException(status_code=404, detail="frontend not built; run `cd frontend && npm run build`")


@app.post("/api/llm/test")
def llm_test(request: Request):
    llm = _llm_from_headers(dict(request.headers))
    return llm.validate_connection()


@app.post("/api/ocr")
def ocr_file(file: UploadFile = File(...), dpi: int = 250, mode: str = "quality"):
    print(f"收到 OCR 请求: {file.filename}, DPI={dpi}, Mode={mode}", flush=True)
    tmp_path, file_hash = _write_upload_to_temp_and_hash(file)
    try:
        cache_file = _ocr_cache_dir() / f"{file_hash}.txt"
        cached_before = cache_file.exists()
        text = _ocr_cached_or_run(
            file_hash,
            lambda: _run_ocr_with_options(tmp_path, dpi=dpi, mode=mode),
        )
        return {"text": text, "filename": file.filename, "cached": cached_before}
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@app.post("/api/ocr/batch")
def ocr_batch(files: List[UploadFile] = File(...), dpi: int = 250, mode: str = "quality"):
    print(f"收到批量 OCR 请求: {len(files)} 个文件, DPI={dpi}, Mode={mode}", flush=True)
    items = []
    for f in files:
        tmp_path, file_hash = _write_upload_to_temp_and_hash(f)
        try:
            cache_file = _ocr_cache_dir() / f"{file_hash}.txt"
            cached_before = cache_file.exists()
            text = _ocr_cached_or_run(
                file_hash,
                lambda: _run_ocr_with_options(tmp_path, dpi=dpi, mode=mode),
            )
            items.append({"filename": f.filename, "text": text, "cached": cached_before})
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
    return {"items": items, "count": len(items), "dpi": 200 if mode == "fast" else int(dpi), "mode": mode}


@app.post("/api/extract")
def extract_text(payload: ExtractRequest, request: Request):
    llm = _llm_from_headers(dict(request.headers))
    text = payload.text or ""
    if payload.force_chunk or len(text) > 5000:
        extraction = llm.extract_and_translate_long(
            text,
            chunk_size=payload.chunk_size or 1200,
            max_chunks=payload.max_chunks or 8,
        )
        meta = {"chunked": True, "chunk_size": payload.chunk_size or 1200, "max_chunks": payload.max_chunks or 8}
    else:
        extraction = llm.extract_and_translate(text)
        meta = {"chunked": False}
    if hasattr(extraction, "model_dump"):
        data = extraction.model_dump()
    else:
        data = extraction.dict()
    data["_meta"] = {"llm": llm.get_status(), **meta}
    return data


@app.post("/api/records")
def create_record(payload: RecordCreateRequest, request: Request):
    llm = _llm_from_headers(dict(request.headers))
    text = (payload.original_text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="original_text 不能为空")
    try:
        with session_scope() as db:
            record = AncientBookRecord(
                title=payload.title,
                author=payload.author,
                dynasty=payload.dynasty,
                tags=payload.tags,
                status=payload.status or "待校对",
                source_type=payload.source_type,
                source_name=payload.source_name,
                original_text=text,
                summary=payload.summary,
                modern_translation=payload.modern_translation,
                structured_json=payload.structured_json,
                llm_model=llm.get_status().get("model"),
            )
            db.add(record)
            db.flush()
            chunks = segment_text(text)
            for i, chunk_content in enumerate(chunks):
                db.add(TextChunk(record_id=record.id, content=chunk_content, chunk_index=i))
            if payload.structured_json and "triples" in payload.structured_json:
                triples = payload.structured_json.get("triples") or []
                for item in triples:
                    db.add(
                        KnowledgeTriple(
                            record_id=record.id,
                            subject=item.get("subject") or "",
                            predicate=item.get("predicate") or "",
                            object=item.get("object") or "",
                            context=item.get("context"),
                        )
                    )
            return serialize_record(record)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] create_record failed: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/records")
def list_records(
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    dynasty: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
):
    db = _get_db()
    try:
        q = db.query(AncientBookRecord)
        if status and status != "全部":
            q = q.filter(AncientBookRecord.status == status)
        if dynasty and dynasty != "全部":
            q = q.filter(AncientBookRecord.dynasty == dynasty)
        if keyword:
            like = f"%{keyword}%"
            q = q.filter(
                (AncientBookRecord.title.like(like))
                | (AncientBookRecord.author.like(like))
                | (AncientBookRecord.original_text.like(like))
                | (AncientBookRecord.tags.like(like))
                | (AncientBookRecord.source_name.like(like))
            )
        total = q.count()
        items = q.order_by(AncientBookRecord.created_at.desc()).offset(skip).limit(limit).all()
        return {"total": total, "items": [serialize_record(item) for item in items]}
    finally:
        db.close()


@app.get("/api/records/{record_id}")
def get_record(record_id: int):
    db = _get_db()
    try:
        item = db.query(AncientBookRecord).filter(AncientBookRecord.id == record_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="record not found")
        return serialize_record(item)
    finally:
        db.close()


@app.put("/api/records/{record_id}")
def update_record(record_id: int, payload: RecordUpdateRequest):
    try:
        with session_scope() as db:
            record = db.query(AncientBookRecord).filter(AncientBookRecord.id == record_id).first()
            if not record:
                raise HTTPException(status_code=404, detail="record not found")
            for field in [
                "title",
                "author",
                "dynasty",
                "tags",
                "status",
                "summary",
                "modern_translation",
                "structured_json",
            ]:
                value = getattr(payload, field)
                if value is not None:
                    setattr(record, field, value)
            if payload.original_text is not None:
                record.original_text = payload.original_text
                db.query(TextChunk).filter(TextChunk.record_id == record.id).delete()
                chunks = segment_text(payload.original_text)
                for i, chunk_content in enumerate(chunks):
                    db.add(TextChunk(record_id=record.id, content=chunk_content, chunk_index=i))
            return serialize_record(record)
    except OperationalError as e:
        msg = str(e)
        if "database is locked" in msg:
            raise HTTPException(status_code=503, detail="数据库正忙（database is locked），请稍后再试")
        raise HTTPException(status_code=500, detail=msg)


@app.post("/api/records/{record_id}/extract")
def extract_record(record_id: int, payload: RecordExtractRequest, request: Request):
    llm = _llm_from_headers(dict(request.headers))
    with session_scope() as db:
        record = db.query(AncientBookRecord).filter(AncientBookRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="record not found")
        text = record.original_text or ""
        if payload.force_chunk or len(text) > 5000:
            extraction = llm.extract_and_translate_long(
                text,
                chunk_size=payload.chunk_size or 1200,
                max_chunks=payload.max_chunks or 8,
            )
        else:
            extraction = llm.extract_and_translate(text)

        data = extraction.model_dump() if hasattr(extraction, "model_dump") else extraction.dict()
        record.title = data.get("title") or record.title
        record.author = data.get("author") or record.author
        record.dynasty = data.get("dynasty") or record.dynasty
        record.summary = data.get("summary") or record.summary
        record.modern_translation = data.get("modern_translation") or record.modern_translation
        record.structured_json = data
        record.llm_model = llm.get_status()["model"]

        db.query(KnowledgeTriple).filter(KnowledgeTriple.record_id == record.id).delete()
        triples = data.get("triples") or []
        for item in triples:
            db.add(
                KnowledgeTriple(
                    record_id=record.id,
                    subject=(item.get("subject") or "").strip(),
                    predicate=(item.get("predicate") or "").strip(),
                    object=(item.get("object") or "").strip(),
                    context=item.get("context"),
                )
            )

        db.query(TextChunk).filter(TextChunk.record_id == record.id).delete()
        chunks = segment_text(text)
        for i, chunk_content in enumerate(chunks):
            db.add(TextChunk(record_id=record.id, content=chunk_content, chunk_index=i))

        result = serialize_record(record)
        result["structured_json"] = data
        return result


@app.post("/api/records/extract/batch")
def batch_extract(payload: BatchExtractRequest, request: Request):
    llm = _llm_from_headers(dict(request.headers))
    results = {"total": len(payload.record_ids), "succeeded": 0, "failed": 0, "details": []}
    with session_scope() as db:
        for rid in payload.record_ids:
            record = db.query(AncientBookRecord).filter(AncientBookRecord.id == rid).first()
            if not record:
                results["failed"] += 1
                results["details"].append({"record_id": rid, "ok": False, "error": "record not found"})
                continue
            try:
                text = record.original_text or ""
                if payload.force_chunk or len(text) > 5000:
                    extraction = llm.extract_and_translate_long(
                        text,
                        chunk_size=payload.chunk_size or 1200,
                        max_chunks=payload.max_chunks or 8,
                    )
                else:
                    extraction = llm.extract_and_translate(text)
                data = extraction.model_dump() if hasattr(extraction, "model_dump") else extraction.dict()

                record.title = data.get("title") or record.title
                record.author = data.get("author") or record.author
                record.dynasty = data.get("dynasty") or record.dynasty
                record.summary = data.get("summary") or record.summary
                record.modern_translation = data.get("modern_translation") or record.modern_translation
                record.structured_json = data
                record.llm_model = llm.get_status()["model"]

                db.query(KnowledgeTriple).filter(KnowledgeTriple.record_id == record.id).delete()
                triples = data.get("triples") or []
                for item in triples:
                    db.add(
                        KnowledgeTriple(
                            record_id=record.id,
                            subject=(item.get("subject") or "").strip(),
                            predicate=(item.get("predicate") or "").strip(),
                            object=(item.get("object") or "").strip(),
                            context=item.get("context"),
                        )
                    )

                db.query(TextChunk).filter(TextChunk.record_id == record.id).delete()
                chunks = segment_text(text)
                for i, chunk_content in enumerate(chunks):
                    db.add(TextChunk(record_id=record.id, content=chunk_content, chunk_index=i))

                results["succeeded"] += 1
                results["details"].append({"record_id": rid, "ok": True})
            except Exception as e:
                results["failed"] += 1
                results["details"].append({"record_id": rid, "ok": False, "error": str(e)})
    results["llm"] = llm.get_status()
    return results


@app.delete("/api/records/{record_id}")
def delete_record(record_id: int):
    with session_scope() as db:
        record = db.query(AncientBookRecord).filter(AncientBookRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="record not found")
        db.delete(record)
        return {"ok": True}


@app.get("/api/records/{record_id}/chunks")
def record_chunks(record_id: int):
    db = _get_db()
    try:
        chunks = (
            db.query(TextChunk)
            .filter(TextChunk.record_id == record_id)
            .order_by(TextChunk.chunk_index.asc())
            .all()
        )
        return [
            {"id": c.id, "chunk_index": c.chunk_index, "content": c.content, "created_at": c.created_at}
            for c in chunks
        ]
    finally:
        db.close()


@app.get("/api/triples")
def list_triples(subject: Optional[str] = None, skip: int = 0, limit: int = 50):
    db = _get_db()
    try:
        q = db.query(KnowledgeTriple)
        if subject:
            like = f"%{subject}%"
            q = q.filter(KnowledgeTriple.subject.like(like))
        total = q.count()
        items = q.order_by(KnowledgeTriple.id.desc()).offset(skip).limit(limit).all()
        return {
            "total": total,
            "items": [
                {
                    "id": t.id,
                    "record_id": t.record_id,
                    "subject": t.subject,
                    "predicate": t.predicate,
                    "object": t.object,
                    "context": t.context,
                }
                for t in items
            ],
        }
    finally:
        db.close()

@app.get("/api/analytics/relations")
def relation_analytics(subject: Optional[str] = None, limit: int = 20):
    db = _get_db()
    try:
        q = db.query(KnowledgeTriple)
        if subject:
            like = f"%{subject}%"
            q = q.filter(KnowledgeTriple.subject.like(like))

        total = q.count()

        top_pred = (
            db.query(KnowledgeTriple.predicate, func.count(KnowledgeTriple.id))
            .filter(KnowledgeTriple.id.in_(q.with_entities(KnowledgeTriple.id)))
            .group_by(KnowledgeTriple.predicate)
            .order_by(func.count(KnowledgeTriple.id).desc())
            .limit(limit)
            .all()
        )
        top_obj = (
            db.query(KnowledgeTriple.object, func.count(KnowledgeTriple.id))
            .filter(KnowledgeTriple.id.in_(q.with_entities(KnowledgeTriple.id)))
            .group_by(KnowledgeTriple.object)
            .order_by(func.count(KnowledgeTriple.id).desc())
            .limit(limit)
            .all()
        )
        top_rel = (
            db.query(KnowledgeTriple.predicate, KnowledgeTriple.object, func.count(KnowledgeTriple.id))
            .filter(KnowledgeTriple.id.in_(q.with_entities(KnowledgeTriple.id)))
            .group_by(KnowledgeTriple.predicate, KnowledgeTriple.object)
            .order_by(func.count(KnowledgeTriple.id).desc())
            .limit(limit)
            .all()
        )

        return {
            "total": total,
            "top_predicates": [{"predicate": p, "count": c} for p, c in top_pred],
            "top_objects": [{"object": o, "count": c} for o, c in top_obj],
            "top_relations": [{"predicate": p, "object": o, "count": c} for p, o, c in top_rel],
        }
    finally:
        db.close()


@app.get("/api/graph/person_network")
def person_network(
    subject: Optional[str] = None,
    min_weight: int = 1,
    max_nodes: int = 120,
    max_edges: int = 400,
):
    db = _get_db()
    try:
        records = db.query(AncientBookRecord.id, AncientBookRecord.structured_json).all()
        record_entities: Dict[int, Dict[str, str]] = {}
        for rid, structured in records:
            entities_map: Dict[str, str] = {}
            if isinstance(structured, dict):
                ents = structured.get("entities") or []
                if isinstance(ents, list):
                    for e in ents:
                        if not isinstance(e, dict):
                            continue
                        name = (e.get("name") or "").strip()
                        etype = (e.get("type") or "").strip()
                        if name and etype:
                            entities_map[name] = etype
            record_entities[rid] = entities_map

        triples_q = db.query(KnowledgeTriple).order_by(KnowledgeTriple.id.desc())
        if subject:
            like = f"%{subject}%"
            triples_q = triples_q.filter((KnowledgeTriple.subject.like(like)) | (KnowledgeTriple.object.like(like)))
        triples = triples_q.all()

        edge_counter: Dict[tuple[str, str], Dict[str, Any]] = {}
        node_degree: Dict[str, int] = {}

        person_name_re = re.compile(r"^[\u4e00-\u9fa5]{2,4}$")
        non_person_suffixes = ("大学", "书院", "寺", "庙", "县", "州", "府", "省", "市", "国", "朝", "年", "月", "日", "卷", "篇", "序", "传", "记")
        non_person_contains = ("公司", "集团", "银行", "委员会", "中学", "小学", "研究所", "出版社", "博物馆", "医院", "学校", "部", "司", "院")
        relation_like_predicates = ("关系", "友", "师", "弟", "兄", "父", "母", "妻", "夫", "子", "女", "君", "臣", "同门", "同学", "同僚")

        def is_person(record_id: int, name: str) -> bool:
            etype = record_entities.get(record_id, {}).get(name)
            if etype and ("人物" in etype):
                return True
            if not person_name_re.match(name):
                return False
            if any(name.endswith(s) for s in non_person_suffixes):
                return False
            if any(x in name for x in non_person_contains):
                return False
            return True

        for t in triples:
            s = (t.subject or "").strip()
            o = (t.object or "").strip()
            p = (t.predicate or "").strip()
            if not s or not o or not p:
                continue
            person_pair = is_person(t.record_id, s) and is_person(t.record_id, o)
            relation_pair = any(k in p for k in relation_like_predicates) and person_name_re.match(s) and person_name_re.match(o)
            if not (person_pair or relation_pair):
                continue
            a, b = (s, o) if s <= o else (o, s)
            key = (a, b)
            payload = edge_counter.get(key)
            if payload is None:
                payload = {"source": a, "target": b, "count": 0, "predicates": {}}
                edge_counter[key] = payload
            payload["count"] += 1
            payload["predicates"][p] = payload["predicates"].get(p, 0) + 1
            node_degree[a] = node_degree.get(a, 0) + 1
            node_degree[b] = node_degree.get(b, 0) + 1

        edges = [v for v in edge_counter.values() if v["count"] >= int(min_weight)]
        edges.sort(key=lambda x: x["count"], reverse=True)
        edges = edges[: int(max_edges)]

        nodes_set = set()
        for e in edges:
            nodes_set.add(e["source"])
            nodes_set.add(e["target"])

        nodes = [{"id": n, "name": n, "value": node_degree.get(n, 0)} for n in nodes_set]
        nodes.sort(key=lambda x: x["value"], reverse=True)
        nodes = nodes[: int(max_nodes)]
        keep = {n["id"] for n in nodes}

        links = []
        for e in edges:
            if e["source"] not in keep or e["target"] not in keep:
                continue
            preds = sorted(e["predicates"].items(), key=lambda kv: kv[1], reverse=True)[:3]
            label = " / ".join(f"{k}({v})" for k, v in preds)
            links.append(
                {
                    "source": e["source"],
                    "target": e["target"],
                    "value": e["count"],
                    "label": label,
                }
            )

        return {
            "nodes": nodes,
            "links": links,
            "meta": {"nodes": len(nodes), "links": len(links), "min_weight": min_weight, "subject": subject or ""},
        }
    finally:
        db.close()


@app.get("/api/export/records")
def export_records(
    format: str = "json",
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    dynasty: Optional[str] = None,
):
    db = _get_db()
    try:
        q = db.query(AncientBookRecord)
        if status and status != "全部":
            q = q.filter(AncientBookRecord.status == status)
        if dynasty and dynasty != "全部":
            q = q.filter(AncientBookRecord.dynasty == dynasty)
        if keyword:
            like = f"%{keyword}%"
            q = q.filter(
                (AncientBookRecord.title.like(like))
                | (AncientBookRecord.author.like(like))
                | (AncientBookRecord.original_text.like(like))
                | (AncientBookRecord.tags.like(like))
                | (AncientBookRecord.source_name.like(like))
            )
        items = q.order_by(AncientBookRecord.created_at.desc()).all()
        rows = [serialize_record(item) for item in items]

        if format.lower() == "csv":
            output = io.StringIO()
            fieldnames = [
                "id",
                "title",
                "author",
                "dynasty",
                "status",
                "tags",
                "source_type",
                "source_name",
                "summary",
                "modern_translation",
                "created_at",
                "updated_at",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k) for k in fieldnames})
            content = output.getvalue().encode("utf-8-sig")
            return Response(
                content=content,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=records.csv"},
            )

        content = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=records.json"},
        )
    finally:
        db.close()


@app.get("/api/export/triples")
def export_triples(format: str = "json", subject: Optional[str] = None):
    db = _get_db()
    try:
        q = db.query(KnowledgeTriple)
        if subject:
            like = f"%{subject}%"
            q = q.filter(KnowledgeTriple.subject.like(like))
        items = q.order_by(KnowledgeTriple.id.desc()).all()
        rows = [
            {"id": t.id, "record_id": t.record_id, "subject": t.subject, "predicate": t.predicate, "object": t.object, "context": t.context}
            for t in items
        ]
        if format.lower() == "csv":
            output = io.StringIO()
            fieldnames = ["id", "record_id", "subject", "predicate", "object", "context"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k) for k in fieldnames})
            content = output.getvalue().encode("utf-8-sig")
            return Response(
                content=content,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=triples.csv"},
            )
        content = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=triples.json"},
        )
    finally:
        db.close()


@app.get("/api/spacetime/events")
def spacetime_events(subject: Optional[str] = None, skip: int = 0, limit: int = 200):
    return spacetime_timeline(subject=subject, skip=skip, limit=limit)


def _extract_keywords_from_record(record: AncientBookRecord, limit: int = 20) -> list[str]:
    text = (record.original_text or "").strip()
    keywords: Dict[str, int] = {}

    structured = record.structured_json if isinstance(record.structured_json, dict) else {}
    ents = structured.get("entities") or []
    if isinstance(ents, list):
        for e in ents:
            if not isinstance(e, dict):
                continue
            name = (e.get("name") or "").strip()
            etype = (e.get("type") or "").strip()
            if not name:
                continue
            if etype and ("时间" in etype or "数字" in etype):
                continue
            keywords[name] = keywords.get(name, 0) + 3

    triples = structured.get("triples") or []
    if isinstance(triples, list):
        for t in triples:
            if not isinstance(t, dict):
                continue
            for k in ("subject", "object"):
                v = (t.get(k) or "").strip()
                if v and 1 < len(v) <= 10:
                    keywords[v] = keywords.get(v, 0) + 1

    stop = {
        "因此",
        "于是",
        "其",
        "之",
        "者",
        "也",
        "曰",
        "云",
        "乃",
        "不",
        "无",
        "有",
        "为",
        "以",
        "于",
        "而",
        "与",
        "及",
        "等",
    }
    for m in re.findall(r"[\u4e00-\u9fa5]{2,4}", text):
        if m in stop:
            continue
        if m.endswith(("年", "月", "日")):
            continue
        keywords[m] = keywords.get(m, 0) + 1

    ranked = sorted(keywords.items(), key=lambda kv: kv[1], reverse=True)
    return [k for k, _ in ranked[:limit]]


def _find_time_candidates(text: str) -> list[str]:
    time_patterns = [
        r"\d{3,4}年(?:\d{1,2}月(?:\d{1,2}日)?)?",
        r"春秋",
        r"战国",
        r"秦",
        r"西汉",
        r"东汉",
        r"汉",
        r"三国",
        r"晋",
        r"隋",
        r"唐",
        r"宋",
        r"元",
        r"明",
        r"清",
        r"民国",
    ]
    time_re = re.compile("|".join(f"(?:{p})" for p in time_patterns))
    return list(dict.fromkeys(time_re.findall(text or "")))


def _event_action_normalize(action: str) -> str:
    a = (action or "").strip()
    mapping = {
        "到达": "到达",
        "抵达": "到达",
        "在": "在",
        "居住": "在",
        "居住在": "在",
        "任": "任职",
        "任教于": "任职",
        "拜": "任职",
        "任命": "任职",
        "擔任": "任职",
        "担任": "任职",
        "封": "封",
        "册立": "册立",
        "遷": "迁",
        "迁居": "迁",
        "迁": "迁",
        "徙": "迁",
    }
    return mapping.get(a, a)


def _extract_events_from_triples(record: AncientBookRecord, triples: list[KnowledgeTriple], max_events: int = 20) -> list[dict]:
    text = record.original_text or ""
    times = _find_time_candidates(text)
    def _prefer_time() -> str:
        for t in times:
            if re.search(r"\d{3,4}年", t):
                return t
        if record.dynasty:
            return record.dynasty
        return times[0] if times else ""

    default_time = _prefer_time()
    loc_predicates = {"在", "于", "於", "到达", "抵达", "至", "到", "居住", "居住在", "任", "任教于", "拜", "任命", "担任", "擔任", "迁", "迁居", "遷", "徙", "赴", "入", "出", "定都于", "定都於"}
    action_keywords = (
        "在",
        "于",
        "於",
        "到",
        "至",
        "入",
        "出",
        "赴",
        "迁",
        "遷",
        "徙",
        "居",
        "任",
        "拜",
        "封",
        "册立",
        "定都",
        "攻",
        "破",
        "击",
        "擊",
        "败",
        "敗",
        "降",
        "杀",
        "殺",
        "诛",
        "誅",
        "坑",
        "斩",
        "斬",
        "俘",
        "擒",
        "生",
        "出生",
    )

    place_suffixes = (
        "城",
        "邑",
        "郡",
        "县",
        "縣",
        "州",
        "府",
        "国",
        "國",
        "京",
        "都",
        "关",
        "關",
        "门",
        "門",
        "宮",
        "宫",
        "山",
        "河",
        "江",
        "湖",
        "海",
        "泽",
        "澤",
        "岭",
        "嶺",
        "道",
        "路",
    )

    def looks_like_place(v: str) -> bool:
        s = (v or "").strip()
        if not s:
            return False
        if "地點" in s or "地点" in s:
            return True
        if len(s) <= 10 and re.match(r"^[\u4e00-\u9fa5]{2,}$", s) and any(s.endswith(x) for x in place_suffixes):
            return True
        if len(s) <= 6 and re.match(r"^[\u4e00-\u9fa5]{2,}$", s):
            return True
        return False

    out = []
    for t in triples:
        predicate = (t.predicate or "").strip()
        subject = (t.subject or "").strip()
        obj = (t.object or "").strip()
        if not predicate or not subject or not obj:
            continue
        is_eventish = predicate in loc_predicates or any(k in predicate for k in action_keywords)
        if not is_eventish:
            continue
        if not looks_like_place(obj) and not any(k in predicate for k in ("在", "于", "於", "到", "至", "入", "出", "赴", "迁", "遷", "徙", "定都", "出生", "生")):
            continue
        out.append(
            {
                "time": default_time,
                "subject": subject,
                "action": _event_action_normalize(predicate),
                "location_or_object": obj,
                "context": (t.context or "").strip(),
                "evidence": (t.context or "").strip(),
            }
        )
        if len(out) >= max_events:
            break
    return out


def _cluster_key(subject: str, action: str, location_or_object: str, time_value: str) -> str:
    s = (subject or "").strip()
    a = (action or "").strip()
    o = (location_or_object or "").strip()
    t = (time_value or "").strip()
    return f"{s}|{a}|{o}|{t}"


@app.post("/api/spacetime/build")
def spacetime_build(payload: SpacetimeBuildRequest, request: Request):
    llm = _llm_from_headers(dict(request.headers))
    try:
        with session_scope() as db:
            if payload.rebuild_all and not payload.record_ids:
                db.query(SpacetimeEvent).delete()
                db.query(EventCluster).delete()

            if payload.record_ids:
                db.query(SpacetimeEvent).filter(SpacetimeEvent.record_id.in_(payload.record_ids)).delete()

            q = db.query(AncientBookRecord.id).order_by(AncientBookRecord.id.asc())
            if payload.record_ids:
                q = q.filter(AncientBookRecord.id.in_(payload.record_ids))
            elif not payload.rebuild_all:
                existing_ids = {rid for (rid,) in db.query(SpacetimeEvent.record_id).distinct().all()}
                if existing_ids:
                    q = q.filter(~AncientBookRecord.id.in_(existing_ids))
            record_ids = [rid for (rid,) in q.all()]

            existed = db.query(EventCluster).all()
            cluster_id_by_key: Dict[str, int] = {c.cluster_key: c.id for c in existed}
            cluster_kw_by_key: Dict[str, list] = {c.cluster_key: (c.keywords if isinstance(c.keywords, list) else []) for c in existed}

        built_events = 0

        for rid in record_ids:
            db = SessionLocal()
            try:
                r = db.query(AncientBookRecord).filter(AncientBookRecord.id == rid).first()
                if not r:
                    db.close()
                    continue
                keywords = _extract_keywords_from_record(r, limit=24)
                triples = db.query(KnowledgeTriple).filter(KnowledgeTriple.record_id == rid).order_by(KnowledgeTriple.id.desc()).all()

                if payload.use_llm and llm.api_enabled:
                    events = llm.extract_spacetime_events(r.original_text or "", keywords=keywords, max_events=payload.max_events_per_record)
                else:
                    events = _extract_events_from_triples(r, triples, max_events=payload.max_events_per_record)

                for e in events:
                    time_value = (e.get("time") or r.dynasty or "").strip()
                    subject = (e.get("subject") or "").strip()
                    action = _event_action_normalize(e.get("action") or "")
                    obj = (e.get("location_or_object") or "").strip()
                    if not subject or not action:
                        continue

                    key = _cluster_key(subject, action, obj, time_value)
                    cluster_id = cluster_id_by_key.get(key)
                    if cluster_id is None:
                        cluster = EventCluster(
                            cluster_key=key,
                            subject=subject,
                            action=action,
                            location_or_object=obj,
                            time=time_value,
                            keywords=list(dict.fromkeys(keywords))[:20],
                        )
                        db.add(cluster)
                        db.flush()
                        cluster_id = cluster.id
                        cluster_id_by_key[key] = cluster_id
                        cluster_kw_by_key[key] = list(dict.fromkeys(keywords))[:30]
                    else:
                        old_kw = cluster_kw_by_key.get(key) or []
                        merged = list(dict.fromkeys((old_kw or []) + keywords))[:30]
                        if merged != old_kw:
                            cluster_kw_by_key[key] = merged
                            db.query(EventCluster).filter(EventCluster.id == cluster_id).update({"keywords": merged})

                    db.add(
                        SpacetimeEvent(
                            record_id=rid,
                            cluster_id=cluster_id,
                            subject=subject,
                            action=action,
                            location_or_object=obj,
                            time=time_value,
                            context=(e.get("context") or "")[:800],
                            evidence=(e.get("evidence") or "")[:800],
                            keywords=list(dict.fromkeys(keywords))[:20],
                        )
                    )
                    built_events += 1

                db.commit()
            except OperationalError as e:
                db.rollback()
                msg = str(e)
                if "database is locked" in msg:
                    raise HTTPException(status_code=503, detail="数据库正忙（database is locked），请稍后再试")
                raise
            finally:
                db.close()

        db = SessionLocal()
        try:
            used_cluster_ids = {
                cid
                for (cid,) in db.query(SpacetimeEvent.cluster_id)
                .filter(SpacetimeEvent.cluster_id.isnot(None))
                .distinct()
                .all()
            }
            if used_cluster_ids:
                db.query(EventCluster).filter(~EventCluster.id.in_(used_cluster_ids)).delete(synchronize_session=False)
            else:
                db.query(EventCluster).delete()
            db.commit()
        finally:
            db.close()

        if payload.use_llm and llm.api_enabled:
            db = SessionLocal()
            try:
                cluster_ids = [cid for (cid,) in db.query(EventCluster.id).filter((EventCluster.summary == None) | (EventCluster.summary == "")).all()]
            finally:
                db.close()

            for cid in cluster_ids:
                db = SessionLocal()
                try:
                    c = db.query(EventCluster).filter(EventCluster.id == cid).first()
                    if not c or c.summary:
                        db.close()
                        continue
                    evs = (
                        db.query(SpacetimeEvent)
                        .filter(SpacetimeEvent.cluster_id == cid)
                        .order_by(SpacetimeEvent.id.desc())
                        .limit(10)
                        .all()
                    )
                    contexts = [x.context or "" for x in evs if (x.context or "").strip()]
                    if not contexts:
                        db.close()
                        continue
                    summary = llm.summarize_spacetime_cluster(contexts, keywords=c.keywords if isinstance(c.keywords, list) else [])
                    c.summary = (summary.get("summary") or "").strip()[:2000] if isinstance(summary, dict) else None
                    db.commit()
                finally:
                    db.close()

        return {"ok": True, "records": len(record_ids), "events": built_events, "clusters": len(cluster_id_by_key), "llm": llm.get_status()}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] spacetime_build failed: {e}", flush=True)
        raise


@app.get("/api/spacetime/clusters")
def spacetime_clusters(subject: Optional[str] = None, skip: int = 0, limit: int = 50):
    db = _get_db()
    try:
        q = db.query(EventCluster)
        if subject:
            like = f"%{subject}%"
            q = q.filter(EventCluster.subject.like(like))
        total = q.count()
        clusters = q.order_by(EventCluster.updated_at.desc()).offset(skip).limit(limit).all()
        items = []
        for c in clusters:
            count = db.query(func.count(SpacetimeEvent.id)).filter(SpacetimeEvent.cluster_id == c.id).scalar() or 0
            if count <= 0:
                continue
            items.append(
                {
                    "id": c.id,
                    "subject": c.subject,
                    "action": c.action,
                    "location_or_object": c.location_or_object,
                    "time": c.time,
                    "keywords": c.keywords or [],
                    "summary": c.summary,
                    "count": count,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
            )
        return {"total": total, "items": items}
    finally:
        db.close()


@app.get("/api/spacetime/clusters/{cluster_id}")
def spacetime_cluster_detail(cluster_id: int):
    db = _get_db()
    try:
        c = db.query(EventCluster).filter(EventCluster.id == cluster_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="cluster not found")
        evs = (
            db.query(SpacetimeEvent)
            .filter(SpacetimeEvent.cluster_id == c.id)
            .order_by(SpacetimeEvent.id.desc())
            .limit(200)
            .all()
        )
        events = []
        for e in evs:
            r = db.query(AncientBookRecord).filter(AncientBookRecord.id == e.record_id).first()
            events.append(
                {
                    "id": e.id,
                    "record_id": e.record_id,
                    "title": r.title if r else None,
                    "dynasty": r.dynasty if r else None,
                    "time": e.time,
                    "subject": e.subject,
                    "action": e.action,
                    "location_or_object": e.location_or_object,
                    "context": e.context or "",
                    "evidence": e.evidence or "",
                    "keywords": e.keywords or [],
                }
            )
        return {
            "cluster": {
                "id": c.id,
                "subject": c.subject,
                "action": c.action,
                "location_or_object": c.location_or_object,
                "time": c.time,
                "keywords": c.keywords or [],
                "summary": c.summary,
            },
            "events": events,
        }
    finally:
        db.close()


@app.get("/api/spacetime/timeline")
def spacetime_timeline(subject: Optional[str] = None, skip: int = 0, limit: int = 200):
    db = _get_db()
    try:
        q = db.query(EventCluster)
        if subject:
            like = f"%{subject}%"
            q = q.filter(EventCluster.subject.like(like))
        clusters = q.all()

        dynasty_year = {
            "春秋": -770,
            "战国": -475,
            "秦": -221,
            "西汉": -206,
            "东汉": 25,
            "汉": -206,
            "三国": 220,
            "晋": 265,
            "西晋": 265,
            "东晋": 317,
            "隋": 581,
            "唐": 618,
            "五代": 907,
            "宋": 960,
            "北宋": 960,
            "南宋": 1127,
            "元": 1271,
            "明": 1368,
            "清": 1644,
            "民国": 1912,
            "中华民国": 1912,
            "现代": 2000,
        }

        def time_key(t: str):
            s = (t or "").strip()
            if not s:
                return (10**9, 1, s)
            m = re.search(r"(\d{3,4})年", s)
            base = None
            if m:
                base = int(m.group(1))
            else:
                for k, v in dynasty_year.items():
                    if k in s:
                        base = v
                        break
            if base is None:
                base = 10**8
            secondary = 0 if m else 1
            return (base, secondary, s)

        items = []
        for c in clusters:
            count = db.query(func.count(SpacetimeEvent.id)).filter(SpacetimeEvent.cluster_id == c.id).scalar() or 0
            if count <= 0:
                continue
            items.append(
                {
                    "cluster_id": c.id,
                    "time": c.time,
                    "subject": c.subject,
                    "action": c.action,
                    "location_or_object": c.location_or_object,
                    "count": count,
                    "summary": c.summary,
                    "keywords": c.keywords or [],
                }
            )
        items.sort(key=lambda x: time_key(x.get("time") or ""))
        total = len(items)
        sliced = items[skip : skip + limit]
        return {"total": total, "items": sliced}
    finally:
        db.close()


@app.post("/api/qa")
def qa(payload: QARequest, request: Request):
    llm = _llm_from_headers(dict(request.headers))
    db = _get_db()
    try:
        record = db.query(AncientBookRecord).filter(AncientBookRecord.id == payload.record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="record not found")
        answer = llm.ask_historical_question(record.original_text, payload.question)
        return {"answer": answer}
    finally:
        db.close()


@app.get("/{path:path}")
def serve_frontend_spa(path: str):
    if path.startswith("api/") or path == "api":
        raise HTTPException(status_code=404, detail="not found")
    target = FRONTEND_DIST_DIR / path
    if target.exists() and target.is_file():
        return FileResponse(str(target))
    index_file = FRONTEND_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    raise HTTPException(status_code=404, detail="frontend not built; run `cd frontend && npm run build`")
