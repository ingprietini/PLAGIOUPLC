"""Caché persistente de búsquedas, páginas y fuentes por texto.

Es la base de la consistencia: si se analiza el mismo texto otra vez, se
reutilizan exactamente las mismas respuestas de búsqueda y el mismo contenido
de las páginas, así que el resultado es idéntico. Los fallos (errores de red,
bloqueos del buscador) nunca se guardan, para poder reintentarlos.
"""

import hashlib
import logging
from datetime import datetime, timedelta

from config import CACHE_TTL_DAYS
from models.database import PageCache, SearchCache, SessionLocal, TextSourceMemory

logger = logging.getLogger(__name__)


def _key(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _fresh(created_at: datetime | None) -> bool:
    return created_at is not None and datetime.utcnow() - created_at < timedelta(days=CACHE_TTL_DAYS)


def _normalize_query(query: str) -> str:
    return " ".join((query or "").lower().split())


def get_search(engine: str, query: str) -> list[dict] | None:
    try:
        with SessionLocal() as db:
            row = db.get(SearchCache, _key(engine, _normalize_query(query)))
            if row and _fresh(row.created_at):
                return list(row.results or [])
    except Exception as exc:  # la caché nunca debe romper el análisis
        logger.warning("search cache read failed: %s", exc)
    return None


def put_search(engine: str, query: str, results: list[dict]) -> None:
    try:
        with SessionLocal() as db:
            db.merge(SearchCache(
                key=_key(engine, _normalize_query(query)),
                query=query[:2000],
                results=results,
                created_at=datetime.utcnow(),
            ))
            db.commit()
    except Exception as exc:
        logger.warning("search cache write failed: %s", exc)


def get_page(url: str) -> str | None:
    try:
        with SessionLocal() as db:
            row = db.get(PageCache, _key(url))
            if row and _fresh(row.created_at):
                return row.content
    except Exception as exc:
        logger.warning("page cache read failed: %s", exc)
    return None


def put_page(url: str, content: str) -> None:
    try:
        with SessionLocal() as db:
            db.merge(PageCache(key=_key(url), url=url, content=content, created_at=datetime.utcnow()))
            db.commit()
    except Exception as exc:
        logger.warning("page cache write failed: %s", exc)


def get_remembered_sources(text_hash: str) -> list[dict]:
    try:
        with SessionLocal() as db:
            row = db.get(TextSourceMemory, text_hash)
            if row and _fresh(row.updated_at):
                return [s for s in (row.urls or []) if isinstance(s, dict) and s.get("url")]
    except Exception as exc:
        logger.warning("source memory read failed: %s", exc)
    return []


def remember_sources(text_hash: str, sources: list[dict]) -> None:
    """Une las fuentes con coincidencias a las ya recordadas (nunca se pierden entre revisiones)."""
    try:
        with SessionLocal() as db:
            row = db.get(TextSourceMemory, text_hash)
            merged: dict[str, dict] = {}
            if row and _fresh(row.updated_at):
                for s in row.urls or []:
                    if isinstance(s, dict) and s.get("url"):
                        merged[s["url"]] = s
            for s in sources:
                merged[s["url"]] = {"url": s["url"], "title": s.get("title", ""), "snippet": s.get("snippet", "")}
            db.merge(TextSourceMemory(
                text_hash=text_hash,
                urls=[merged[u] for u in sorted(merged)],
                updated_at=datetime.utcnow(),
            ))
            db.commit()
    except Exception as exc:
        logger.warning("source memory write failed: %s", exc)
