import re
from urllib.parse import urlsplit, urlunsplit


def _clean_text(value: str, limit: int = 2000) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned[:limit]


def normalize_url(url: str) -> str:
    if not url:
        return ""

    try:
        parsed = urlsplit(url.strip())
    except Exception:
        return ""

    if not parsed.scheme or not parsed.netloc:
        return ""

    # Canonical URL for deduplication: no query/fragment and no trailing slash.
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def normalize_sources(raw_sources: list[dict], max_sources: int = 50) -> list[dict]:
    deduped: list[dict] = []
    seen_urls: set[str] = set()

    for source in raw_sources:
        url = normalize_url(source.get("url", ""))
        if not url or url in seen_urls:
            continue

        title = _clean_text(source.get("title", ""), limit=220)
        snippet = _clean_text(source.get("snippet", ""), limit=1200)
        content = _clean_text(source.get("content", "") or snippet, limit=4000)
        if not content:
            continue

        deduped.append(
            {
                "url": url,
                "title": title or url,
                "snippet": snippet,
                "content": content,
            }
        )
        seen_urls.add(url)

        if len(deduped) >= max_sources:
            break

    return deduped
