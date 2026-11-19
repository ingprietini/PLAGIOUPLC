import uuid
import os
from datetime import datetime
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, Column, String, Text, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.pool import NullPool
from config import DATABASE_URL

_db_url = DATABASE_URL
if _db_url.startswith("postgres://"):
    # Render/Heroku entregan "postgres://", SQLAlchemy necesita "postgresql://".
    _db_url = "postgresql://" + _db_url[len("postgres://"):]
_is_sqlite = _db_url.startswith("sqlite")

if _is_sqlite:
    db_dir = os.path.dirname(_db_url.replace("sqlite:///", ""))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

engine = create_engine(
    _db_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    poolclass=NullPool,
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=True)
    original_text = Column(Text, nullable=False)
    word_count = Column(Integer, default=0)
    status = Column(String, default="pending")
    progress = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    stats = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    sources = relationship("Source", back_populates="analysis", cascade="all, delete-orphan")
    suggestions = relationship("Suggestion", back_populates="analysis", cascade="all, delete-orphan")


class Source(Base):
    __tablename__ = "sources"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id = Column(String, ForeignKey("analyses.id"), nullable=False)
    url = Column(Text, nullable=False)
    title = Column(String, nullable=True)
    similarity = Column(Float, default=0.0)
    matched_text = Column(Text, nullable=True)
    source_snippet = Column(Text, nullable=True)

    analysis = relationship("Analysis", back_populates="sources")


class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id = Column(String, ForeignKey("analyses.id"), nullable=False)
    type = Column(String, nullable=False)
    severity = Column(String, default="medium")
    original_text = Column(Text, nullable=True)
    suggestion_text = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    improved_example = Column(Text, nullable=True)
    position_start = Column(Integer, nullable=True)
    position_end = Column(Integer, nullable=True)

    analysis = relationship("Analysis", back_populates="suggestions")


class SearchCache(Base):
    """Resultados de búsqueda web por consulta: mismo texto => mismas consultas => mismas fuentes."""

    __tablename__ = "search_cache"

    key = Column(String(64), primary_key=True)  # sha256(motor + consulta normalizada)
    query = Column(Text, nullable=False)
    results = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PageCache(Base):
    """Texto extraído de cada página/PDF descargado."""

    __tablename__ = "page_cache"

    key = Column(String(64), primary_key=True)  # sha256(url)
    url = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TextSourceMemory(Base):
    """Fuentes ya encontradas para un mismo texto; se vuelven a verificar en revisiones futuras."""

    __tablename__ = "text_source_memory"

    text_hash = Column(String(64), primary_key=True)
    urls = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def dispose_engine():
    engine.dispose()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
