"""Búsqueda web y descarga de fuentes.

Diferencias clave con la versión anterior:
- Distingue "sin resultados" (respuesta válida, se guarda en caché) de "falló"
  (bloqueo/timeout, devuelve None y se reintenta en otra pasada).
- Permite reintentar con motores alternativos de ddgs.
- Descarga el texto completo de páginas HTML y PDF, con caché.
"""

import asyncio
import logging
import re
from html import unescape
from urllib.parse import urlsplit, urlunsplit

import httpx

from config import (
    FETCH_TIMEOUT,
    GOOGLE_API_KEY,
    GOOGLE_CSE_ID,
    MAX_PAGE_BYTES,
    MAX_PAGE_CHARS,
    SEARCH_ENGINE,
)
from plagiarism import cache

logger = logging.getLogger(__name__)

_shared_client: httpx.AsyncClient | None = None

_SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".mp4", ".mp3", ".zip", ".rar",
    ".ppt", ".pptx", ".xls", ".xlsx", ".exe",
)
_BLOCK_TAGS_RE = re.compile(
    r"<(script|style|noscript|svg|nav|footer|header|form|aside|iframe)\b.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_BREAK_TAGS_RE = re.compile(r"<(?:br|/p|/div|/li|/h[1-6]|/tr|/section|/article)\b[^>]*>", re.IGNORECASE)


async def get_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(FETCH_TIMEOUT, connect=8.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.5",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            },
        )
    return _shared_client


async def close_client():
    global _shared_client
    if _shared_client:
        await _shared_client.aclose()
        _shared_client = None


def normalize_url(url: str) -> str:
    """URL canónica para deduplicar: sin fragmento, host en minúsculas, sin "/" final."""
    try:
        parsed = urlsplit((url or "").strip())
    except Exception:
        return ""
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


# --------------------------------------------------------------------------- búsqueda

def default_engine() -> str:
    if SEARCH_ENGINE:
        return SEARCH_ENGINE
    return "google" if GOOGLE_API_KEY and GOOGLE_CSE_ID else "duckduckgo"


async def search_web(query: str, num_results: int, backend: str | None = None) -> list[dict] | None:
    """Devuelve la lista de resultados, [] si no hubo, o None si la búsqueda falló.

    Las respuestas válidas se guardan en caché por (motor, consulta).
    """
    engine = default_engine()
    cache_engine = f"{engine}:{backend or 'auto'}:{num_results}"

    cached = cache.get_search(cache_engine, query)
    if cached is not None:
        return cached

    if engine == "google":
        results = await _search_google(query, num_results)
    elif engine == "duckduckgo":
        results = await _search_ddgs(query, num_results, backend)
    else:
        results = []

    if results is not None:
        cache.put_search(cache_engine, query, results)
    return results


async def _search_google(query: str, num_results: int) -> list[dict] | None:
    client = await get_client()
    try:
        response = await client.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": query, "num": min(num_results, 10)},
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.info("google search failed: %s", exc)
        return None
    return [
        {"url": item.get("link", ""), "title": item.get("title", ""), "snippet": item.get("snippet", "")}
        for item in data.get("items", [])
    ]


async def _search_ddgs(query: str, num_results: int, backend: str | None) -> list[dict] | None:
    def _sync() -> list[dict] | None:
        try:
            from ddgs import DDGS
        except ImportError:
            return None
        kwargs = {"max_results": num_results}
        if backend:
            kwargs["backend"] = backend
        try:
            raw = DDGS().text(query, **kwargs) or []
        except TypeError:
            # Versión de ddgs sin parámetro backend.
            try:
                raw = DDGS().text(query, max_results=num_results) or []
            except Exception as exc:
                logger.info("ddgs search failed: %s", exc)
                return None
        except Exception as exc:
            message = str(exc).lower()
            if "no results" in message:
                return []
            logger.info("ddgs search failed (%s): %s", backend or "auto", exc)
            return None
        return [
            {"url": r.get("href", ""), "title": r.get("title", ""), "snippet": r.get("body", "")}
            for r in raw[:num_results]
        ]

    return await asyncio.to_thread(_sync)


# --------------------------------------------------------------------------- descarga

def extract_text_from_html(html: str) -> str:
    html = _BLOCK_TAGS_RE.sub(" ", html)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    html = _BREAK_TAGS_RE.sub("\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.split("\n")]
    # Las líneas muy cortas suelen ser menús, botones o pies de página.
    lines = [line for line in lines if len(line) >= 25]
    return "\n".join(lines)[:MAX_PAGE_CHARS]


def _extract_pdf_bytes(content: bytes) -> str:
    try:
        from parser import _extract_pdf
        return _extract_pdf(content)[:MAX_PAGE_CHARS]
    except Exception as exc:
        logger.info("pdf extraction failed: %s", exc)
        return ""


async def fetch_page_text(url: str) -> str | None:
    """Texto de la página (con caché). None si no se pudo descargar (se reintentará)."""
    cached = cache.get_page(url)
    if cached is not None:
        return cached

    if urlsplit(url).path.lower().endswith(_SKIP_EXTENSIONS):
        return ""

    client = await get_client()
    try:
        async with client.stream("GET", url) as response:
            status = response.status_code
            if 400 <= status < 500 and status not in (408, 425, 429):
                # Error permanente (404, 403, 410...): no se reintenta; se usa el fragmento del buscador.
                cache.put_page(url, "")
                return ""
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_PAGE_BYTES:
                    break
                chunks.append(chunk)
            body = b"".join(chunks)
            encoding = response.encoding or "utf-8"
    except Exception as exc:
        logger.debug("fetch failed %s: %s", url, exc)
        return None

    if "pdf" in content_type or body[:5] == b"%PDF-":
        text = await asyncio.to_thread(_extract_pdf_bytes, body)
    elif "html" in content_type or "xml" in content_type or "text/plain" in content_type or not content_type:
        try:
            decoded = body.decode(encoding, errors="replace")
        except LookupError:
            decoded = body.decode("utf-8", errors="replace")
        text = decoded[:MAX_PAGE_CHARS] if "text/plain" in content_type else await asyncio.to_thread(extract_text_from_html, decoded)
    else:
        text = ""

    cache.put_page(url, text)
    return text
