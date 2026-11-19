"""Proveedores de búsqueda y descarga de fuentes.

Proveedores:
- web:<motor>  Buscadores web consultados de forma explícita y separada mediante
               ddgs (google, yahoo, yandex, duckduckgo, bing, brave, mojeek...).
               Antes se usaba el modo "auto" de ddgs, que prioriza Wikipedia y
               Grokipedia (solo devuelven un título) y elige el resto al azar:
               resultados irrelevantes y no deterministas.
- brave_api    Brave Search API oficial (opcional, requiere BRAVE_API_KEY).
- google_cse   Google Custom Search API (opcional, requiere claves).
- openalex     Artículos académicos con su resumen (API abierta).
- crossref     Metadatos y resúmenes de artículos con DOI (API abierta).
- wikipedia    Búsqueda y texto completo de artículos (API oficial).

Cada proveedor devuelve una lista de resultados, [] si no hubo, o None si
falló (bloqueo, timeout); los fallos nunca se guardan en caché.
"""

import asyncio
import logging
import re
from html import unescape
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import httpx

from config import (
    API_USER_AGENT,
    BRAVE_API_KEY,
    FETCH_TIMEOUT,
    GOOGLE_API_KEY,
    GOOGLE_CSE_ID,
    MAX_PAGE_BYTES,
    MAX_PAGE_CHARS,
    OPENALEX_API_KEY,
)
from plagiarism import cache

logger = logging.getLogger(__name__)

_shared_client: httpx.AsyncClient | None = None
_api_client: httpx.AsyncClient | None = None

_SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".mp4", ".mp3", ".zip", ".rar",
    ".ppt", ".pptx", ".xls", ".xlsx", ".exe",
)
_BLOCK_TAGS_RE = re.compile(
    r"<(script|style|noscript|svg|nav|footer|header|form|aside|iframe)\b.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_BREAK_TAGS_RE = re.compile(r"<(?:br|/p|/div|/li|/h[1-6]|/tr|/section|/article)\b[^>]*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WIKI_HOST_RE = re.compile(r"^([a-z\-]+)(?:\.m)?\.wikipedia\.org$")


async def get_client() -> httpx.AsyncClient:
    """Cliente con apariencia de navegador para descargar páginas web."""
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


async def get_api_client() -> httpx.AsyncClient:
    """Cliente identificado como bot para APIs públicas (Wikipedia lo exige)."""
    global _api_client
    if _api_client is None:
        _api_client = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=8.0),
            follow_redirects=True,
            headers={"User-Agent": API_USER_AGENT, "Accept": "application/json"},
        )
    return _api_client


async def close_client():
    global _shared_client, _api_client
    for client in (_shared_client, _api_client):
        if client:
            await client.aclose()
    _shared_client = None
    _api_client = None


def normalize_url(url: str) -> str:
    """URL canónica para deduplicar: sin fragmento, host en minúsculas, sin "/" final."""
    try:
        parsed = urlsplit((url or "").strip())
    except Exception:
        return ""
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    netloc = parsed.netloc.lower()
    if netloc.endswith(".m.wikipedia.org"):
        netloc = netloc.replace(".m.wikipedia.org", ".wikipedia.org")
    path = parsed.path.rstrip("/")
    return urlunsplit(("https" if parsed.scheme.lower() == "https" else "http", netloc, path, parsed.query, ""))


def _clean_markup(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG_RE.sub(" ", value or ""))).strip()


async def _get_json(url: str, params: dict, headers: dict | None = None, retries: int = 2) -> dict:
    """GET a una API pública con reintentos ante límites de velocidad (429) o errores 5xx."""
    client = await get_api_client()
    for attempt in range(retries + 1):
        r = await client.get(url, params=params, headers=headers)
        if (r.status_code == 429 or r.status_code >= 500) and attempt < retries:
            retry_after = r.headers.get("retry-after", "")
            wait = float(retry_after) if retry_after.isdigit() else 1.5 * (attempt + 1)
            await asyncio.sleep(min(wait, 8.0))
            continue
        r.raise_for_status()
        return r.json()
    return {}


async def _cached(provider: str, query: str, fetch, cache_empty: bool) -> list[dict] | None:
    cached = cache.get_search(provider, query)
    if cached is not None:
        return cached
    results = await fetch()
    if results is not None and (results or cache_empty):
        cache.put_search(provider, query, results)
    return results


# --------------------------------------------------------------------------- web

async def search_web_engine(query: str, engine: str, num_results: int, region: str) -> list[dict] | None:
    """Un buscador concreto vía ddgs. Las respuestas vacías no se guardan: en servidores
    compartidos un "sin resultados" suele ser un bloqueo encubierto."""

    def _sync() -> list[dict] | None:
        try:
            from ddgs import DDGS
            raw = DDGS(timeout=10).text(query, max_results=num_results, backend=engine, region=region) or []
        except Exception as exc:
            if "no results" in str(exc).lower():
                return []
            logger.info("web search failed (%s): %s", engine, exc)
            return None
        return [
            {"url": r.get("href", ""), "title": r.get("title", ""), "snippet": r.get("body", ""), "provider": f"web:{engine}"}
            for r in raw[:num_results]
        ]

    async def fetch():
        return await asyncio.to_thread(_sync)

    return await _cached(f"web:{engine}:{region}:{num_results}", query, fetch, cache_empty=False)


async def search_brave_api(query: str, num_results: int, lang: str) -> list[dict] | None:
    if not BRAVE_API_KEY:
        return None

    async def fetch():
        try:
            data = await _get_json(
                "https://api.search.brave.com/res/v1/web/search",
                {"q": query, "count": min(num_results, 20), "search_lang": lang},
                headers={"X-Subscription-Token": BRAVE_API_KEY},
            )
            items = data.get("web", {}).get("results", [])
        except Exception as exc:
            logger.info("brave api failed: %s", exc)
            return None
        return [
            {"url": i.get("url", ""), "title": i.get("title", ""), "snippet": _clean_markup(i.get("description", "")), "provider": "brave_api"}
            for i in items
        ]

    return await _cached(f"brave_api:{lang}:{num_results}", query, fetch, cache_empty=True)


async def search_google_cse(query: str, num_results: int) -> list[dict] | None:
    if not (GOOGLE_API_KEY and GOOGLE_CSE_ID):
        return None

    async def fetch():
        try:
            data = await _get_json(
                "https://www.googleapis.com/customsearch/v1",
                {"key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": query, "num": min(num_results, 10)},
            )
            items = data.get("items", [])
        except Exception as exc:
            logger.info("google cse failed: %s", exc)
            return None
        return [
            {"url": i.get("link", ""), "title": i.get("title", ""), "snippet": i.get("snippet", ""), "provider": "google_cse"}
            for i in items
        ]

    return await _cached(f"google_cse:{num_results}", query, fetch, cache_empty=True)


# --------------------------------------------------------------------------- académico

def _openalex_abstract(inverted: dict | None) -> str:
    if not inverted:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)


async def search_openalex(query: str, num_results: int = 5) -> list[dict] | None:
    async def fetch():
        try:
            data = await _get_json(
                "https://api.openalex.org/works",
                {
                    "search": query,
                    "per-page": num_results,
                    "select": "id,doi,title,abstract_inverted_index,primary_location,open_access",
                    **({"api_key": OPENALEX_API_KEY} if OPENALEX_API_KEY else {}),
                },
            )
            works = data.get("results", [])
        except Exception as exc:
            logger.info("openalex failed: %s", exc)
            return None
        results = []
        for w in works:
            abstract = _openalex_abstract(w.get("abstract_inverted_index"))
            title = w.get("title") or ""
            landing = ((w.get("primary_location") or {}).get("landing_page_url")) or w.get("doi") or w.get("id") or ""
            if abstract:
                results.append({
                    "url": landing, "title": title, "snippet": abstract[:300],
                    "content": f"{title}. {abstract}", "provider": "openalex",
                })
            oa_url = (w.get("open_access") or {}).get("oa_url")
            if oa_url and oa_url != landing:
                # Versión de acceso abierto: se descarga el texto completo (a menudo PDF).
                results.append({"url": oa_url, "title": title, "snippet": abstract[:300], "provider": "openalex_oa"})
        return results

    return await _cached(f"openalex:{num_results}", query, fetch, cache_empty=True)


async def search_crossref(query: str, num_results: int = 5) -> list[dict] | None:
    async def fetch():
        try:
            data = await _get_json(
                "https://api.crossref.org/works",
                {"query.bibliographic": query, "rows": num_results, "select": "DOI,title,abstract,URL"},
            )
            items = data.get("message", {}).get("items", [])
        except Exception as exc:
            logger.info("crossref failed: %s", exc)
            return None
        results = []
        for item in items:
            abstract = _clean_markup(item.get("abstract", ""))
            if not abstract:
                continue
            title = (item.get("title") or [""])[0]
            results.append({
                "url": item.get("URL") or f"https://doi.org/{item.get('DOI', '')}",
                "title": title, "snippet": abstract[:300],
                "content": f"{title}. {abstract}", "provider": "crossref",
            })
        return results

    return await _cached(f"crossref:{num_results}", query, fetch, cache_empty=True)


# --------------------------------------------------------------------------- wikipedia

async def wikipedia_article_text(lang: str, title: str) -> str | None:
    url = f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
    cached = cache.get_page(url)
    if cached is not None:
        return cached
    try:
        data = await _get_json(
            f"https://{lang}.wikipedia.org/w/api.php",
            {"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
                    "titles": title, "format": "json", "formatversion": 2},
        )
        pages = data.get("query", {}).get("pages", [])
    except Exception as exc:
        logger.info("wikipedia extract failed: %s", exc)
        return None
    text = (pages[0].get("extract") or "")[:MAX_PAGE_CHARS] if pages else ""
    cache.put_page(url, text)
    return text


async def search_wikipedia(query: str, lang: str, num_results: int = 3) -> list[dict] | None:
    async def fetch():
        try:
            data = await _get_json(
                f"https://{lang}.wikipedia.org/w/api.php",
                {"action": "query", "list": "search", "srsearch": query, "srlimit": num_results,
                        "format": "json", "formatversion": 2},
            )
            hits = data.get("query", {}).get("search", [])
        except Exception as exc:
            logger.info("wikipedia search failed: %s", exc)
            return None
        return [
            {
                "url": f"https://{lang}.wikipedia.org/wiki/{quote(h['title'].replace(' ', '_'))}",
                "title": f"{h['title']} - Wikipedia",
                "snippet": _clean_markup(h.get("snippet", "")),
                "provider": "wikipedia",
            }
            for h in hits
        ]

    return await _cached(f"wikipedia:{lang}:{num_results}", query, fetch, cache_empty=True)


# --------------------------------------------------------------------------- descarga

def extract_text_from_html(html: str) -> str:
    html = _BLOCK_TAGS_RE.sub(" ", html)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    html = _BREAK_TAGS_RE.sub("\n", html)
    text = unescape(_TAG_RE.sub(" ", html))
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
    parsed = urlsplit(url)
    wiki = _WIKI_HOST_RE.match(parsed.netloc)
    if wiki and parsed.path.startswith("/wiki/"):
        # Wikipedia bloquea navegadores simulados; se usa su API oficial.
        return await wikipedia_article_text(wiki.group(1), unquote(parsed.path[len("/wiki/"):]).replace("_", " "))

    cached = cache.get_page(url)
    if cached is not None:
        return cached

    if parsed.path.lower().endswith(_SKIP_EXTENSIONS):
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
        if "text/plain" in content_type:
            text = decoded[:MAX_PAGE_CHARS]
        else:
            text = await asyncio.to_thread(extract_text_from_html, decoded)
    else:
        text = ""

    cache.put_page(url, text)
    return text
