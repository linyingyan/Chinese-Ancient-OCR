from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, create_engine, text, ForeignKey, Index, event
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import datetime
from contextlib import contextmanager

Base = declarative_base()

class AncientBookRecord(Base):
    __tablename__ = 'ancient_book_records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=True)
    author = Column(String(100), nullable=True)
    dynasty = Column(String(50), nullable=True)
    original_text = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    structured_json = Column(JSON, nullable=True)
    modern_translation = Column(Text, nullable=True)
    source_type = Column(String(20), nullable=True)
    source_name = Column(String(255), nullable=True)
    tags = Column(String(255), nullable=True)
    status = Column(String(30), nullable=False, default="已入库")
    llm_model = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )
    
    # Relationships
    chunks = relationship("TextChunk", back_populates="record", cascade="all, delete-orphan")
    triples = relationship("KnowledgeTriple", back_populates="record", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AncientBookRecord(title='{self.title}', author='{self.author}')>"

class TextChunk(Base):
    """用于存储 PDF 或长文本的分段内容"""
    __tablename__ = 'text_chunks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(Integer, ForeignKey('ancient_book_records.id'))
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)  # 段落序号
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    record = relationship("AncientBookRecord", back_populates="chunks")

class KnowledgeTriple(Base):
    """用于构建知识图谱的三元组：主体-谓语-客体"""
    __tablename__ = 'knowledge_triples'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(Integer, ForeignKey('ancient_book_records.id'))
    subject = Column(String(255), nullable=False)
    predicate = Column(String(255), nullable=False)
    object = Column(String(255), nullable=False)
    context = Column(Text, nullable=True)  # 来源上下文
    
    record = relationship("AncientBookRecord", back_populates="triples")


class EventCluster(Base):
    __tablename__ = "event_clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster_key = Column(String(512), nullable=False, unique=True)
    subject = Column(String(255), nullable=True)
    action = Column(String(255), nullable=True)
    location_or_object = Column(String(255), nullable=True)
    time = Column(String(100), nullable=True)
    keywords = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    events = relationship("SpacetimeEvent", back_populates="cluster", cascade="all, delete-orphan")


class SpacetimeEvent(Base):
    __tablename__ = "spacetime_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(Integer, ForeignKey("ancient_book_records.id"), nullable=False)
    cluster_id = Column(Integer, ForeignKey("event_clusters.id"), nullable=True)
    subject = Column(String(255), nullable=False)
    action = Column(String(255), nullable=False)
    location_or_object = Column(String(255), nullable=True)
    time = Column(String(100), nullable=True)
    context = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)
    evidence = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    cluster = relationship("EventCluster", back_populates="events")


Index("idx_spacetime_events_record_id", SpacetimeEvent.record_id)
Index("idx_spacetime_events_cluster_id", SpacetimeEvent.cluster_id)

# Database setup
DATABASE_URL = "sqlite:///./ancient_books.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()

def _ensure_sqlite_columns():
    """为已存在的 SQLite 表补齐新增字段，避免手工迁移。"""
    required_columns = {
        "summary": "TEXT",
        "source_type": "VARCHAR(20)",
        "source_name": "VARCHAR(255)",
        "tags": "VARCHAR(255)",
        "status": "VARCHAR(30) DEFAULT '已入库' NOT NULL",
        "llm_model": "VARCHAR(100)",
        "updated_at": "DATETIME",
    }

    with engine.begin() as conn:
        # 检查 ancient_book_records 表
        existing = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(ancient_book_records)")).fetchall()
        }
        for column_name, ddl in required_columns.items():
            if column_name not in existing:
                conn.execute(
                    text(f"ALTER TABLE ancient_book_records ADD COLUMN {column_name} {ddl}")
                )


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


@contextmanager
def session_scope():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def serialize_record(record: AncientBookRecord) -> dict:
    return {
        "id": record.id,
        "title": record.title,
        "author": record.author,
        "dynasty": record.dynasty,
        "summary": record.summary,
        "original_text": record.original_text,
        "modern_translation": record.modern_translation,
        "structured_json": record.structured_json,
        "source_type": record.source_type,
        "source_name": record.source_name,
        "tags": record.tags,
        "status": record.status,
        "llm_model": record.llm_model,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
