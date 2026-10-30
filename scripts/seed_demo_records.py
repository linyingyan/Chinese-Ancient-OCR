import time
from typing import Any, Dict, List, Optional

import requests


BASE = "http://127.0.0.1:8000"


def get_records(keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
    r = requests.get(f"{BASE}/api/records", params={"skip": 0, "limit": limit, "keyword": keyword})
    r.raise_for_status()
    return (r.json() or {}).get("items") or []


def find_record_id_by_title(title: str) -> Optional[int]:
    items = get_records(title, limit=50)
    for it in items:
        if (it.get("title") or "").strip() == title.strip():
            return it.get("id")
    return None


def create_record(payload: Dict[str, Any]) -> int:
    r = requests.post(f"{BASE}/api/records", json=payload, timeout=30)
    r.raise_for_status()
    return int(r.json()["id"])


def extract_record(record_id: int) -> None:
    r = requests.post(
        f"{BASE}/api/records/{record_id}/extract",
        json={"chunk_size": 1200, "max_chunks": 6, "force_chunk": False},
        timeout=120,
    )
    r.raise_for_status()


def build_spacetime_for_records(record_ids: List[int]) -> Dict[str, Any]:
    r = requests.post(
        f"{BASE}/api/spacetime/build",
        json={
            "record_ids": record_ids,
            "use_llm": False,
            "rebuild_all": False,
            "max_events_per_record": 20,
        },
        timeout=180,
    )
    r.raise_for_status()
    return r.json()


def main() -> None:
    records = [
        {
            "title": "史记·项羽本纪（鸿门之前）节选",
            "author": "司马迁",
            "dynasty": "汉",
            "source_type": "web",
            "source_name": "https://ctext.org/shiji/xiang-yu-ben-ji",
            "tags": "史记,楚汉,鸿门宴",
            "status": "已入库",
            "original_text": "行略定秦地。函谷關有兵守關，不得入。又聞沛公已破咸陽，項羽大怒，使當陽君等擊關。項羽遂入，至于戲西。沛公軍霸上。當是時，項羽兵四十萬，在新豐鴻門，沛公兵十萬，在霸上。",
        },
        {
            "title": "史记·项羽本纪（鸿门宴）节选",
            "author": "司马迁",
            "dynasty": "汉",
            "source_type": "web",
            "source_name": "https://ctext.org/shiji/xiang-yu-ben-ji",
            "tags": "史记,鸿门宴",
            "status": "已入库",
            "original_text": "沛公旦日從百餘騎來見項王，至鴻門，謝曰：「臣與將軍戮力而攻秦……今者有小人之言，令將軍與臣有郤。」項王曰：「此沛公左司馬曹無傷言之；不然，籍何以至此。」",
        },
        {
            "title": "史记·项羽本纪（诛宋义）节选A",
            "author": "司马迁",
            "dynasty": "汉",
            "source_type": "web",
            "source_name": "https://ctext.org/shiji/xiang-yu-ben-ji",
            "tags": "史记,巨鹿,楚汉",
            "status": "已入库",
            "original_text": "行至安陽，留四十六日不進。天寒大雨，士卒凍饑。項羽晨朝上將軍宋義，即其帳中斬宋義頭，出令軍中曰：「宋義與齊謀反楚，楚王陰令羽誅之。」",
        },
        {
            "title": "史记·项羽本纪（诛宋义）节选B",
            "author": "司马迁",
            "dynasty": "汉",
            "source_type": "web",
            "source_name": "https://ctext.org/shiji/xiang-yu-ben-ji",
            "tags": "史记,巨鹿,楚汉",
            "status": "已入库",
            "original_text": "項羽晨朝上將軍宋義，即其帳中斬宋義頭。使人追宋義子，及之齊，殺之。懷王因使項羽為上將軍。",
        },
        {
            "title": "史记·项羽本纪（长史欣至咸阳）节选",
            "author": "司马迁",
            "dynasty": "汉",
            "source_type": "web",
            "source_name": "https://ctext.org/shiji/xiang-yu-ben-ji",
            "tags": "史记,秦末",
            "status": "已入库",
            "original_text": "章邯恐，使長史欣請事。至咸陽，留司馬門三日，趙高不見，有不信之心。欣恐，還走其軍。",
        },
        {
            "title": "史记·项羽本纪（至彭城）节选",
            "author": "司马迁",
            "dynasty": "汉",
            "source_type": "web",
            "source_name": "https://ctext.org/shiji/xiang-yu-ben-ji",
            "tags": "史记,彭城之战",
            "status": "已入库",
            "original_text": "項王乃西從蕭，晨擊漢軍而東，至彭城，日中，大破漢軍。漢軍皆走。",
        },
    ]

    record_ids: List[int] = []
    for rec in records:
        rid = find_record_id_by_title(rec["title"])
        if rid is None:
            rid = create_record(rec)
        record_ids.append(rid)

    for rid in record_ids:
        extract_record(rid)
        time.sleep(0.2)

    build_result = build_spacetime_for_records(record_ids)
    print({"record_ids": record_ids, "spacetime_build": build_result})


if __name__ == "__main__":
    main()

