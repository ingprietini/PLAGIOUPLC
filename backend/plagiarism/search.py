import re
import httpx
import asyncio
from html import unescape
from config import (
    GOOGLE_API_KEY,
    GOOGLE_CSE_ID,
    SEARCH_DELAY,
    SEARCH_ENGINE,
    CHUNK_SIZE,
    MAX_SOURCES_TO_CHECK,
    MAX_CHUNKS_TO_SEARCH,
    MAX_KEY_PHRASES_PER_CHUNK,
    MAX_RESULTS_PER_QUERY,
)

_shared_client: httpx.AsyncClient | None = None

_BOILERPLATE_RE = re.compile(
    r"\b(cookie|privacy|pol[ií]tica|accept|suscrib|newsletter|advertis|terms|login|registr|copyright)\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_CLAUSE_SPLIT_RE = re.compile(r"(?<=[,;:])\s+")


async def get_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None:
        _shared_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_keepalive_connections=8),
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            },
        )
    return _shared_client


async def close_client():
    global _shared_client
    if _shared_client:
        await _shared_client.aclose()
        _shared_client = None


async def search_web(query: str, num_results: int = 5, retries: int = 2) -> list:
    engine = SEARCH_ENGINE or ("google" if GOOGLE_API_KEY and GOOGLE_CSE_ID else "duckduckgo")

    if engine == "duckduckgo":
        return await _search_duckduckgo(query, num_results)
    if engine == "google":
        return await _search_google(query, num_results, retries)

    return _mock_search(query, num_results)


async def _search_google(query: str, num_results: int, retries: int) -> list:
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": min(num_results, 10),
    }

    client = await get_client()

    for attempt in range(retries + 1):
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return [
                {
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "content": item.get("snippet", ""),
                }
                for item in data.get("items", [])
            ]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < retries:
                await asyncio.sleep(2 ** attempt)
                continue
            return []
        except Exception:
            if attempt < retries:
                await asyncio.sleep(2 ** attempt)
                continue
            return []

    return []


async def _search_duckduckgo(query: str, num_results: int = 5) -> list:
    def _sync_search() -> list:
        try:
            from ddgs import DDGS
            results = []
            with DDGS() as ddgs:
                for i, r in enumerate(ddgs.text(query, max_results=num_results)):
                    if i >= num_results:
                        break
                    results.append({
                        "url": r.get("href", ""),
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "content": r.get("body", ""),
                    })
            return results
        except Exception:
            return []

    return await asyncio.to_thread(_sync_search)


def _pick_chunk_indices(total_chunks: int, max_chunks: int) -> list[int]:
    if total_chunks <= max_chunks:
        return list(range(total_chunks))

    indices = {0, total_chunks - 1}
    middle = max_chunks - 2
    if middle > 0:
        step = (total_chunks - 1) / (middle + 1)
        for i in range(1, middle + 1):
            indices.add(round(step * i))
    return sorted(indices)


def _split_into_sentence_chunks(text: str, chunk_size_words: int) -> list[str]:
    # Prefer splitting at sentence boundaries ('.', '!', '?') so queries are shorter and cleaner.
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if not sentences:
        words = text.split()
        return [" ".join(words[i:i + chunk_size_words]) for i in range(0, len(words), chunk_size_words)]

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = sentence.split()
        sentence_len = len(sentence_words)

        # Flush current chunk before adding a sentence that would exceed the target size.
        if current_sentences and (current_words + sentence_len > chunk_size_words):
            chunks.append(" ".join(current_sentences).strip())
            current_sentences = []
            current_words = 0

        # If a sentence is too long, split it by words as fallback.
        if sentence_len > chunk_size_words:
            if current_sentences:
                chunks.append(" ".join(current_sentences).strip())
                current_sentences = []
                current_words = 0

            for i in range(0, sentence_len, chunk_size_words):
                piece = " ".join(sentence_words[i:i + chunk_size_words]).strip()
                if piece:
                    chunks.append(piece)
            continue

        current_sentences.append(sentence)
        current_words += sentence_len

    if current_sentences:
        chunks.append(" ".join(current_sentences).strip())

    return [chunk for chunk in chunks if chunk]


def _split_into_clause_chunks(text: str, chunk_size_words: int) -> list[str]:
    clauses = [c.strip() for c in _CLAUSE_SPLIT_RE.split(text) if c.strip()]
    if not clauses:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for clause in clauses:
        clause_words = clause.split()
        clause_len = len(clause_words)

        if current and (current_words + clause_len > chunk_size_words):
            chunks.append(" ".join(current).strip())
            current = []
            current_words = 0

        if clause_len > chunk_size_words:
            for i in range(0, clause_len, chunk_size_words):
                piece = " ".join(clause_words[i:i + chunk_size_words]).strip()
                if piece:
                    chunks.append(piece)
            continue

        current.append(clause)
        current_words += clause_len

    if current:
        chunks.append(" ".join(current).strip())

    return [chunk for chunk in chunks if chunk]


def _split_into_sliding_chunks(text: str, window_words: int = 90, stride_words: int = 45) -> list[str]:
    words = text.split()
    if len(words) <= window_words:
        return [" ".join(words)] if words else []

    chunks: list[str] = []
    i = 0
    while i < len(words):
        piece = " ".join(words[i:i + window_words]).strip()
        if piece:
            chunks.append(piece)
        if i + window_words >= len(words):
            break
        i += max(1, stride_words)
    return chunks


def _sample_chunks(chunks: list[str], max_chunks: int) -> list[str]:
    if len(chunks) <= max_chunks:
        return chunks
    return [chunks[i] for i in _pick_chunk_indices(len(chunks), max_chunks)]


def _exact_phrase_queries(text: str, max_queries: int = 4) -> list[str]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    queries: list[str] = []
    for sentence in sentences:
        words = sentence.split()
        if len(words) < 7:
            continue
        size = min(14, len(words))
        phrase = _quote_window(words, size=size)
        queries.append(f'"{phrase}"')
        if len(queries) >= max_queries:
            break
    return queries


def _build_queries_from_chunks(chunks: list[str], max_phrases: int) -> list[str]:
    queries: list[str] = []
    for chunk in chunks:
        queries.extend(extract_key_phrases(chunk, max_phrases=max_phrases))
    return queries


async def search_chunks(text: str, chunk_size: int = CHUNK_SIZE, progress_callback=None) -> list:
    max_chunks = max(1, MAX_CHUNKS_TO_SEARCH)
    sentence_chunks = _sample_chunks(_split_into_sentence_chunks(text, chunk_size), max_chunks)
    clause_chunks = _sample_chunks(_split_into_clause_chunks(text, max(40, chunk_size // 2)), max_chunks)
    sliding_chunks = _sample_chunks(_split_into_sliding_chunks(text, window_words=max(60, chunk_size // 2), stride_words=max(25, chunk_size // 4)), max_chunks)

    queries = []
    queries.extend(_build_queries_from_chunks(sentence_chunks, max_phrases=max(1, MAX_KEY_PHRASES_PER_CHUNK)))
    queries.extend(_build_queries_from_chunks(clause_chunks, max_phrases=max(1, min(3, MAX_KEY_PHRASES_PER_CHUNK))))
    queries.extend(_build_queries_from_chunks(sliding_chunks, max_phrases=max(1, min(2, MAX_KEY_PHRASES_PER_CHUNK))))
    queries.extend(_exact_phrase_queries(text, max_queries=max(2, MAX_KEY_PHRASES_PER_CHUNK)))

    deduped_queries: list[str] = []
    seen_queries: set[str] = set()
    for q in queries:
        normalized = " ".join((q or "").split()).strip().lower()
        if not normalized or normalized in seen_queries:
            continue
        seen_queries.add(normalized)
        deduped_queries.append(q)

    semaphore = asyncio.Semaphore(5)

    async def search_phrase(phrase: str) -> list:
        async with semaphore:
            results = await search_web(phrase, num_results=max(1, MAX_RESULTS_PER_QUERY))
            await asyncio.sleep(SEARCH_DELAY)
            return results

    all_tasks = []
    total_phrases = 0
    for phrase in deduped_queries:
        all_tasks.append(search_phrase(phrase))
        total_phrases += 1

    if progress_callback:
        await progress_callback(f"Buscando en {total_phrases} fragmentos...")

    chunk_results = []
    for i, task in enumerate(asyncio.as_completed(all_tasks)):
        try:
            result = await asyncio.wait_for(task, timeout=15)
        except asyncio.TimeoutError:
            if progress_callback:
                await progress_callback(f"Búsqueda web: {i + 1}/{total_phrases} (timeout)")
            continue
        if isinstance(result, list):
            chunk_results.extend(result)
        if progress_callback and (i + 1) % min(5, max(1, total_phrases // 5)) == 0:
            await progress_callback(f"Búsqueda web: {i + 1}/{total_phrases}")

    seen = set()
    unique = []
    for r in chunk_results:
        url = r.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(r)

    return unique[:MAX_SOURCES_TO_CHECK]


def _extract_text_from_html(html: str, max_chars: int = 12000) -> str:
    html = re.sub(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return ""

    # Drop lines likely to be cookie/UX boilerplate to improve similarity quality.
    chunks = re.split(r"(?<=[.!?])\s+", text)
    chunks = [c for c in chunks if len(c) >= 40 and not _BOILERPLATE_RE.search(c)]
    cleaned = " ".join(chunks)
    return cleaned[:max_chars]


async def _fetch_source_content(source: dict) -> dict:
    url = source.get("url", "")
    if not url:
        return source

    client = await get_client()
    try:
        response = await client.get(url)
        response.raise_for_status()
    except Exception:
        return source

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        return source

    extracted = _extract_text_from_html(response.text)
    if not extracted:
        return source

    enriched = dict(source)
    enriched["content"] = extracted
    return enriched


async def hydrate_sources_content(sources: list[dict], max_fetch: int = 15, progress_callback=None) -> list[dict]:
    if not sources:
        return []

    target = sources[: max(1, max_fetch)]
    rest = sources[max_fetch:]

    semaphore = asyncio.Semaphore(5)

    async def bounded_fetch(source: dict) -> dict:
        async with semaphore:
            return await _fetch_source_content(source)

    tasks = [bounded_fetch(source) for source in target]
    hydrated: list[dict] = []
    total = len(tasks)

    for i, task in enumerate(asyncio.as_completed(tasks), start=1):
        try:
            item = await asyncio.wait_for(task, timeout=12)
        except asyncio.TimeoutError:
            continue
        hydrated.append(item)
        if progress_callback and i % max(1, total // 5) == 0:
            await progress_callback(f"Verificando contenido de páginas: {i}/{total}")

    return hydrated + rest


def _quote_window(words: list[str], size: int = 12) -> str:
    if len(words) <= size:
        return " ".join(words)
    start = (len(words) - size) // 2
    return " ".join(words[start:start + size])


def extract_key_phrases(text: str, max_phrases: int = 3) -> list:
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    if not sentences:
        words = text.split()
        return [" ".join(words[i:i + 15]) for i in range(0, len(words), 15)][:max_phrases]

    sentences.sort(key=lambda s: (len(s.split()), len(s)), reverse=True)

    key_phrases = []
    seen_ngrams = set()
    for s in sentences:
        words = s.split()
        ngrams = set(tuple(words[i:i + 3]) for i in range(max(0, len(words) - 2)))
        if len(words) >= 6 and not ngrams & seen_ngrams:
            compact = s[:300]
            key_phrases.append(compact)
            key_phrases.append(f'"{_quote_window(words, size=min(12, len(words)))}"')
            seen_ngrams.update(ngrams)
        if len(key_phrases) >= max_phrases:
            break

    # Remove duplicates preserving order.
    unique_phrases = []
    seen = set()
    for phrase in key_phrases:
        if phrase not in seen:
            seen.add(phrase)
            unique_phrases.append(phrase)

    return unique_phrases[:max_phrases] or [s[:300] for s in sentences[:max_phrases]]


def _mock_search(query: str, num_results: int = 5) -> list:
    return [
        {
            "url": f"https://ejemplo.com/resultado-{i}",
            "title": f"Resultado simulado para: {query[:50]}...",
            "snippet": f"Fragmento de texto relacionado con la consulta. {query[:100]}",
            "content": f"Fragmento de texto relacionado con la consulta. {query[:100]}",
        }
        for i in range(min(num_results, 3))
    ]
