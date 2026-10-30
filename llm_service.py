import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from pydantic import BaseModel, Field

load_dotenv()

# 定义结构化提取的数据模型
class AncientBookEntity(BaseModel):
    name: str = Field(description="实体名称，如人物名、地名、官职名等")
    type: str = Field(description="实体类型，如 人物, 地点, 官职, 时间, 书名")
    context: str = Field(description="实体在文中的上下文含义")

class KnowledgeTripleModel(BaseModel):
    """三元组模型"""
    subject: str = Field(description="主体，通常是一个实体")
    predicate: str = Field(description="谓语/关系，描述主体和客体之间的联系")
    object: str = Field(description="客体，通常是另一个实体或属性")
    context: Optional[str] = Field(default=None, description="三元组发生的简短上下文")

class StructuredExtraction(BaseModel):
    title: Optional[str] = Field(default=None, description="书籍或篇章标题")
    author: Optional[str] = Field(default=None, description="作者")
    dynasty: Optional[str] = Field(default=None, description="朝代")
    entities: List[AncientBookEntity] = Field(default_factory=list, description="从文中提取的关键实体")
    triples: List[KnowledgeTripleModel] = Field(default_factory=list, description="从文中提取的知识三元组（用于知识图谱）")
    summary: str = Field(description="原文的简短摘要")
    modern_translation: str = Field(description="原文的现代汉语翻译")

class LLMService:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        base_url = base_url if base_url is not None else os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model if model is not None else os.getenv("LLM_MODEL", "gpt-4o-mini")

        api_key = (api_key or "").strip()
        base_url = (base_url or "").strip()
        model = (self.model or "").strip()

        enable_by_key = bool(api_key) and api_key != "your_openai_api_key_here"
        enable_by_local = (base_url.startswith("http://localhost") or base_url.startswith("http://127.0.0.1")) and bool(model)
        self.api_enabled = HAS_OPENAI and bool(base_url) and bool(model) and (enable_by_key or enable_by_local)

        effective_key = api_key if enable_by_key else ("sk-local" if enable_by_local else "")
        self.client = OpenAI(api_key=effective_key, base_url=base_url) if self.api_enabled else None
        self._base_url = base_url

    def get_status(self) -> dict:
        if not HAS_OPENAI:
            mode_label = "未安装 openai SDK（已自动降级）"
        else:
            mode_label = "在线大模型" if self.api_enabled else "未配置大模型（演示模式）"
        return {
            "api_enabled": self.api_enabled,
            "model": self.model,
            "mode_label": mode_label,
            "base_url": self._base_url,
            "sdk_ready": HAS_OPENAI,
        }

    def validate_connection(self) -> dict:
        if not self.api_enabled or self.client is None:
            return {
                "ok": False,
                "message": "未启用大模型：请先配置 API Key / Base URL / Model。",
                "base_url": self._base_url,
                "model": self.model,
                "sdk_ready": HAS_OPENAI,
                "api_enabled": self.api_enabled,
            }
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
            )
            content = response.choices[0].message.content
            return {
                "ok": True,
                "message": f"连通性测试成功：{(content or 'ok')[:80]}",
                "base_url": self._base_url,
                "model": self.model,
                "sdk_ready": HAS_OPENAI,
                "api_enabled": self.api_enabled,
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"连通性测试失败：{e}",
                "base_url": self._base_url,
                "model": self.model,
                "sdk_ready": HAS_OPENAI,
                "api_enabled": self.api_enabled,
            }

    def _extract_title(self, text: str) -> Optional[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return None
        first_line = lines[0]
        return first_line[:60]

    def _extract_dynasty(self, text: str) -> Optional[str]:
        candidates = ["先秦", "秦", "汉", "魏", "晋", "南北朝", "隋", "唐", "宋", "元", "明", "清", "民国"]
        for dynasty in candidates:
            if dynasty in text:
                return dynasty
        return None

    def _extract_entities_fallback(self, text: str) -> List[AncientBookEntity]:
        entities: List[AncientBookEntity] = []
        seen = set()

        book_names = re.findall(r"《([^》]{1,20})》", text)
        for name in book_names[:10]:
            if ("书名", name) not in seen:
                entities.append(
                    AncientBookEntity(name=name, type="书名", context=f"文中提及书名《{name}》")
                )
                seen.add(("书名", name))

        people_like = re.findall(r"[\u4e00-\u9fa5]{2,4}(?:子|公|王|帝|君|卿)", text)
        for name in people_like[:10]:
            if ("人物", name) not in seen:
                entities.append(
                    AncientBookEntity(name=name, type="人物", context=f"文中可能涉及人物“{name}”")
                )
                seen.add(("人物", name))

        places = re.findall(r"[\u4e00-\u9fa5]{2,8}(?:州|郡|县|山|江|河|宫|门)", text)
        for name in places[:10]:
            if ("地点", name) not in seen:
                entities.append(
                    AncientBookEntity(name=name, type="地点", context=f"文中可能涉及地点“{name}”")
                )
                seen.add(("地点", name))

        return entities[:15]

    def _extract_triples_fallback(self, text: str) -> List[KnowledgeTripleModel]:
        triples: List[KnowledgeTripleModel] = []
        seen = set()

        clean = (text or "").strip()
        if not clean:
            return []

        candidates = []
        try:
            candidates = [e.name for e in self._extract_entities_fallback(clean)]
        except Exception:
            candidates = []

        for m in re.findall(r"[\u4e00-\u9fa5]{2,4}", clean):
            candidates.append(m)
        candidates = [c.strip() for c in candidates if isinstance(c, str) and c.strip()]
        candidates = list(dict.fromkeys(candidates))
        candidates.sort(key=len, reverse=True)

        def find_nearest_subject(pos: int, window: int = 80) -> str:
            best_name = ""
            best_pos = -1
            left = max(0, pos - window)
            segment = clean[left:pos]
            for name in candidates:
                idx = segment.rfind(name)
                if idx == -1:
                    continue
                abs_idx = left + idx
                if abs_idx > best_pos:
                    best_pos = abs_idx
                    best_name = name
            return best_name

        def add(subject: str, predicate: str, obj: str):
            subject = (subject or "").strip()
            predicate = (predicate or "").strip()
            obj = (obj or "").strip()
            if not subject or not predicate or not obj:
                return
            if subject == obj:
                return
            key = (subject, predicate, obj)
            if key in seen:
                return
            seen.add(key)
            triples.append(KnowledgeTripleModel(subject=subject, predicate=predicate, object=obj, context=None))

        direct_patterns = [
            (r"([\u4e00-\u9fa5]{2,6})在([\u4e00-\u9fa5]{2,10})", "在"),
            (r"([\u4e00-\u9fa5]{2,6})任([\u4e00-\u9fa5]{2,12})", "任"),
            (r"([\u4e00-\u9fa5]{2,6})(?:到达|抵达|至)([\u4e00-\u9fa5]{2,10})", "到达"),
            (r"([\u4e00-\u9fa5]{2,6})赴([\u4e00-\u9fa5]{2,10})", "赴"),
            (r"([\u4e00-\u9fa5]{2,6})入([\u4e00-\u9fa5]{2,10})", "入"),
            (r"([\u4e00-\u9fa5]{2,6})出([\u4e00-\u9fa5]{2,10})", "出"),
            (r"([\u4e00-\u9fa5]{2,6})(?:迁|徙)([\u4e00-\u9fa5]{2,10})", "迁"),
            (r"([\u4e00-\u9fa5]{2,6})(?:殺|杀)([\u4e00-\u9fa5]{2,6})", "杀"),
            (r"([\u4e00-\u9fa5]{2,6})(?:見|见)([\u4e00-\u9fa5]{2,6})", "会见"),
        ]
        for pattern, predicate in direct_patterns:
            for subject, obj in re.findall(pattern, clean):
                add(subject, predicate, obj)
                if len(triples) >= 20:
                    return triples

        verb_pattern = re.compile(
            r"(到达|抵达|至|在|任|赴|入|出|迁|徙|殺|杀|見|见)([\u4e00-\u9fa5]{2,12})"
        )
        predicate_map = {
            "抵达": "到达",
            "到达": "到达",
            "至": "到达",
            "徙": "迁",
            "迁": "迁",
            "殺": "杀",
            "杀": "杀",
            "見": "会见",
            "见": "会见",
        }
        for m in verb_pattern.finditer(clean):
            verb = m.group(1)
            obj = m.group(2)
            subject = find_nearest_subject(m.start(0))
            predicate = predicate_map.get(verb, verb)
            add(subject, predicate, obj)
            if len(triples) >= 20:
                return triples

        return triples

    def _segment_text_smart(self, text: str, chunk_size: int) -> List[str]:
        clean = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not clean:
            return []
        parts = [p.strip() for p in clean.split("\n") if p.strip()]
        if len(parts) <= 1:
            parts = re.split(r"(?<=[。！？；])", clean)
            parts = [p.strip() for p in parts if p.strip()]

        chunks: List[str] = []
        buf: List[str] = []
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

    def _dedup_entities(self, entities: List[AncientBookEntity]) -> List[AncientBookEntity]:
        out: List[AncientBookEntity] = []
        seen = set()
        for e in entities or []:
            name = (e.name or "").strip()
            etype = (e.type or "").strip()
            if not name or not etype:
                continue
            key = (etype, name)
            if key in seen:
                continue
            seen.add(key)
            out.append(e)
        return out

    def _dedup_triples(self, triples: List[KnowledgeTripleModel]) -> List[KnowledgeTripleModel]:
        out: List[KnowledgeTripleModel] = []
        seen = set()
        for t in triples or []:
            s = (t.subject or "").strip()
            p = (t.predicate or "").strip()
            o = (t.object or "").strip()
            if not s or not p or not o:
                continue
            key = (s, p, o)
            if key in seen:
                continue
            seen.add(key)
            out.append(t)
        return out

    def extract_and_translate_fallback(self, text: str) -> StructuredExtraction:
        clean_text = text.strip()
        if not clean_text:
            return StructuredExtraction(
                title=None,
                author=None,
                dynasty=None,
                entities=[],
                triples=[],
                summary="原文为空",
                modern_translation="原文为空，无法翻译。",
            )
        summary = clean_text[:120] + ("..." if len(clean_text) > 120 else "")
        translation = clean_text[:300]
        if translation:
            translation = "【兜底模式】以下为原文保留，请后续接入真实大模型后生成现代汉语译文：\n" + translation
        else:
            translation = "【兜底模式】暂无可翻译内容。"

        return StructuredExtraction(
            title=self._extract_title(clean_text),
            author=None,
            dynasty=self._extract_dynasty(clean_text),
            entities=self._extract_entities_fallback(clean_text),
            triples=self._extract_triples_fallback(clean_text),
            summary=summary or "暂无摘要",
            modern_translation=translation,
        )

    def _normalize_extraction_dict(self, data: dict) -> dict:
        if not isinstance(data, dict):
            data = {}
        normalized = dict(data)
        normalized.setdefault("title", None)
        normalized.setdefault("author", None)
        normalized.setdefault("dynasty", None)
        normalized.setdefault("entities", [])
        normalized.setdefault("triples", [])
        normalized.setdefault("summary", "")
        normalized.setdefault("modern_translation", "")
        if normalized["summary"] is None:
            normalized["summary"] = ""
        if normalized["modern_translation"] is None:
            normalized["modern_translation"] = ""
        if not isinstance(normalized.get("entities"), list):
            normalized["entities"] = []
        if not isinstance(normalized.get("triples"), list):
            normalized["triples"] = []
        return normalized

    def _extract_json_from_text(self, text: str) -> dict:
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return {}
        return {}

    def _call_extract_once(self, text: str, translation_mode: str = "auto") -> StructuredExtraction:
        if not self.api_enabled or self.client is None:
            return self.extract_and_translate_fallback(text)

        long_text = len(text) > 3500
        if translation_mode == "auto":
            translation_mode = "condensed" if long_text else "full"

        translation_requirement = (
            "给出尽量完整的现代汉语译文"
            if translation_mode == "full"
            else "不需要翻译，modern_translation 返回空字符串"
            if translation_mode == "none"
            else "给出浓缩版现代汉语译文（控制在 800 字以内）"
        )

        prompt = f"""你是一个精通中国古籍研究的专家。请对以下古籍文本进行结构化处理。
任务要求：
1. 识别标题、作者和朝代（如果文中包含或能推断出）。
2. 提取文中的关键实体（人物、地点、官职、时间、书名等），实体需包含 name/type/context。
3. 提取知识三元组（subject/predicate/object/context），用于构建知识图谱，要求尽量具体可检索。
4. 提供原文的简要摘要（200 字以内）。
5. {translation_requirement}。

返回格式必须为 JSON 对象，且只包含以下字段：
title, author, dynasty, summary, modern_translation, entities, triples

待处理文本：
{text}
"""

        try:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "只输出合法 JSON，不要输出其它文字。"},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                result_json = json.loads(response.choices[0].message.content)
            except Exception:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "只输出合法 JSON，不要输出其它文字。"},
                        {"role": "user", "content": prompt},
                    ],
                )
                result_json = self._extract_json_from_text(response.choices[0].message.content or "")
            result_json = self._normalize_extraction_dict(result_json)
            if not result_json.get("summary"):
                result_json["summary"] = (text.strip()[:200] + ("..." if len(text) > 200 else "")) if text.strip() else ""
            if not result_json.get("modern_translation"):
                result_json["modern_translation"] = ""
            return StructuredExtraction(**result_json)
        except Exception:
            return self.extract_and_translate_fallback(text)

    def extract_and_translate_long(
        self,
        text: str,
        chunk_size: int = 1200,
        max_chunks: int = 8,
    ) -> StructuredExtraction:
        clean = (text or "").strip()
        if not clean:
            return self.extract_and_translate(clean)

        chunks = self._segment_text_smart(clean, chunk_size=chunk_size)
        chunks = [c for c in chunks if c]
        if max_chunks and len(chunks) > max_chunks:
            chunks = chunks[:max_chunks]

        merged_entities: List[AncientBookEntity] = []
        merged_triples: List[KnowledgeTripleModel] = []

        if self.api_enabled:
            for chunk in chunks:
                partial = self._call_extract_once(chunk, translation_mode="none")
                merged_entities.extend(partial.entities or [])
                merged_triples.extend(partial.triples or [])
            head = clean[:4000]
            base = self._call_extract_once(head, translation_mode="condensed")
        else:
            base = self.extract_and_translate_fallback(clean)

        base.entities = self._dedup_entities(merged_entities) if merged_entities else base.entities
        base.triples = self._dedup_triples(merged_triples) if merged_triples else base.triples
        if not base.summary:
            base.summary = clean[:200] + ("..." if len(clean) > 200 else "")
        if not base.modern_translation:
            base.modern_translation = ""
        return base

    def extract_and_translate_with_api(self, text: str) -> StructuredExtraction:
        if len(text) > 5000:
            return self.extract_and_translate_long(text)
        return self._call_extract_once(text, translation_mode="auto")

    def extract_and_translate(self, text: str) -> StructuredExtraction:
        """使用大模型对古籍文本进行结构化提取和翻译"""
        if not text.strip():
            return StructuredExtraction(
                title=None,
                author=None,
                dynasty=None,
                entities=[],
                triples=[],
                summary="原文为空",
                modern_translation="原文为空，无法翻译。",
            )
        if self.api_enabled:
            return self.extract_and_translate_with_api(text)
        return self.extract_and_translate_fallback(text)

    def extract_spacetime_events(self, text: str, keywords: Optional[List[str]] = None, max_events: int = 20) -> List[Dict[str, Any]]:
        clean = (text or "").strip()
        if not clean:
            return []
        if not self.api_enabled or self.client is None:
            return []

        kw = [k for k in (keywords or []) if isinstance(k, str) and k.strip()][:30]
        prompt = f"""你是古籍史料整理专家。请从给定文本中抽取“时空事件”，用于构建时空演变与事件聚类。

要求：
1) 输出必须是 JSON 对象，且只包含字段：events
2) events 是数组，每条 event 只包含字段：
   time, subject, action, location_or_object, context, evidence, keywords
3) time 尽量规范（如“1927年3月”或“民国十六年”），找不到则可为空字符串
4) subject 尽量为人物/机构/群体；location_or_object 为地点或事件涉及对象
5) action 用短语表达（如“抵达/任职/会见/迁居/出任/赴任/战/签订”等）
6) context 与 evidence 都给出能在原文中找到的短句片段（50~120 字）
7) keywords 给出与该事件最相关的 3~8 个关键词（优先从提示关键词中挑选）
8) 最多输出 {max_events} 条，按时间先后或叙事顺序排序

提示关键词（可为空）：{kw}

待处理文本：
{clean[:12000]}
"""
        try:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "只输出合法 JSON，不要输出其它文字。"},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                data = json.loads(response.choices[0].message.content or "{}")
            except Exception:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "只输出合法 JSON，不要输出其它文字。"},
                        {"role": "user", "content": prompt},
                    ],
                )
                raw = (response.choices[0].message.content or "").strip()
                start = raw.find("{")
                end = raw.rfind("}")
                data = json.loads(raw[start : end + 1]) if start != -1 and end != -1 and end > start else {}
            events = data.get("events") if isinstance(data, dict) else None
            if not isinstance(events, list):
                return []
            out: List[Dict[str, Any]] = []
            for e in events[: max_events or 20]:
                if not isinstance(e, dict):
                    continue
                out.append(
                    {
                        "time": (e.get("time") or "").strip(),
                        "subject": (e.get("subject") or "").strip(),
                        "action": (e.get("action") or "").strip(),
                        "location_or_object": (e.get("location_or_object") or "").strip(),
                        "context": (e.get("context") or "").strip(),
                        "evidence": (e.get("evidence") or "").strip(),
                        "keywords": e.get("keywords") if isinstance(e.get("keywords"), list) else [],
                    }
                )
            return out
        except Exception:
            return []

    def summarize_spacetime_cluster(self, contexts: List[str], keywords: Optional[List[str]] = None) -> Dict[str, Any]:
        if not self.api_enabled or self.client is None:
            return {}
        ctx = [c.strip() for c in (contexts or []) if isinstance(c, str) and c.strip()]
        if not ctx:
            return {}
        kw = [k for k in (keywords or []) if isinstance(k, str) and k.strip()][:30]
        prompt = f"""你是古籍事件整理专家。下面给出同一类“时空事件”的多个上下文片段（来自不同文献/不同段落），请输出一个聚类摘要，方便在时空演变页面展示。

要求：
1) 输出必须是 JSON 对象，且只包含字段：summary, key_points, keywords
2) summary：200~350 字，写清楚“谁在何时何地做了什么/发生了什么”，不要编造
3) key_points：3~6 条要点，每条 20~50 字
4) keywords：5~12 个关键词（优先从提示关键词里选）

提示关键词：{kw}

上下文片段：
{chr(10).join([f"- {c[:260]}" for c in ctx[:12]])}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "只输出合法 JSON，不要输出其它文字。"},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content or "{}")
            if not isinstance(data, dict):
                return {}
            return {
                "summary": (data.get("summary") or "").strip(),
                "key_points": data.get("key_points") if isinstance(data.get("key_points"), list) else [],
                "keywords": data.get("keywords") if isinstance(data.get("keywords"), list) else [],
            }
        except Exception:
            return {}

    def ask_historical_question(self, context: str, question: str) -> str:
        """针对特定古籍背景回答历史问题"""
        if not self.api_enabled:
            return "未配置或未启用大模型，当前为演示模式：请在“系统设置”里配置可用的 OpenAI 兼容接口（API Key / Base URL / Model）后再试。"
        
        prompt = f"""基于以下古籍背景，请回答用户的问题。
背景内容：
{context}

用户问题：
{question}

请用简洁且学术化的语言回答。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个古籍历史研究专家。"},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"问答服务出错: {e}"
