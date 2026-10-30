from models import init_db, SessionLocal, AncientBookRecord, TextChunk, KnowledgeTriple
import datetime
import json

def seed_data():
    init_db()
    db = SessionLocal()
    
    # Check if we already have data
    if db.query(AncientBookRecord).count() > 2: # Keep original samples but allow re-seeding
        print("Database already contains enough data. Skipping seeding.")
        db.close()
        return

    sample_records = [
        {
            "title": "鲁迅广州行踪录",
            "author": "历史研究者",
            "dynasty": "民国/现代",
            "original_text": "1927年，鲁迅抵达广州。他在中山大学任教，期间与许广平关系密切。在广州，鲁迅发表了多篇演讲，并完成了《野草》的出版。",
            "summary": "记录了鲁迅在广州期间的教学、生活和创作情况。",
            "modern_translation": "1927年，鲁迅来到广州。他在中山大学担任教职...",
            "source_type": "manual",
            "source_name": "research_note",
            "tags": "鲁迅,广州,现代文学",
            "status": "已入库",
            "structured_json": {
                "entities": [
                    {"name": "鲁迅", "type": "人物", "context": "文学家"},
                    {"name": "广州", "type": "地点", "context": "主要活动地"},
                    {"name": "中山大学", "type": "机构", "context": "任教单位"}
                ]
            }
        }
    ]

    for data in sample_records:
        record = AncientBookRecord(**data)
        db.add(record)
        db.flush()
        
        # Add chunks
        db.add(TextChunk(record_id=record.id, content=record.original_text, chunk_index=0))
        
        # Add triples
        triples = [
            ("鲁迅", "抵达", "广州"),
            ("鲁迅", "任教于", "中山大学"),
            ("鲁迅", "出版", "《野草》"),
            ("鲁迅", "关系密切", "许广平")
        ]
        for s, p, o in triples:
            db.add(KnowledgeTriple(record_id=record.id, subject=s, predicate=p, object=o, context="文中明确记载"))
    
    db.commit()
    db.close()
    print("New historical sample data seeded successfully.")

if __name__ == "__main__":
    seed_data()
