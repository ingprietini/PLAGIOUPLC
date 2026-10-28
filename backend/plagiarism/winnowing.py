import re
import hashlib
from config import WINNOWING_K, WINNOWING_W

WORD_RE = re.compile(r"[a-záéíóúüñ0-9]+", re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-záéíóúüñA-Z0-9\s]', '', text)
    text = re.sub(r'\s+', '', text)
    return text


def hash_gram(gram: str) -> int:
    return int(hashlib.md5(gram.encode('utf-8')).hexdigest(), 16)


def generate_fingerprint(text: str, k: int = WINNOWING_K, w: int = WINNOWING_W) -> set:
    normalized = normalize_text(text)
    if len(normalized) < k:
        return set()

    hashes = []
    for i in range(len(normalized) - k + 1):
        gram = normalized[i:i + k]
        hashes.append(hash_gram(gram))

    fingerprint = set()
    for i in range(len(hashes) - w + 1):
        window = hashes[i:i + w]
        min_hash = min(window)
        fingerprint.add(min_hash)

    return fingerprint


def compare_fingerprints(fp1: set, fp2: set) -> float:
    if not fp1 or not fp2:
        return 0.0
    intersection = fp1 & fp2
    union = fp1 | fp2
    return len(intersection) / len(union)


def _tokenize_words(text: str) -> list[str]:
    return WORD_RE.findall((text or "").lower())


def _build_ngram_index(words: list[str], ngram_size: int) -> dict[tuple[str, ...], int]:
    index: dict[tuple[str, ...], int] = {}
    if len(words) < ngram_size:
        return index

    for i in range(len(words) - ngram_size + 1):
        gram = tuple(words[i:i + ngram_size])
        if gram not in index:
            index[gram] = i
    return index


def _clean_excerpt(text: str, max_chars: int = 280) -> str:
    compact = re.sub(r"\s+", " ", (text or "")).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "..."


def find_matching_segments(
    text: str,
    source_text: str,
    ngram_size: int = 10,
    max_matches: int = 5,
    context_words: int = 24,
    text_ngram_index: dict[tuple[str, ...], int] | None = None,
) -> list[dict]:
    text_words = _tokenize_words(text)
    source_words = _tokenize_words(source_text)

    if len(text_words) < ngram_size or len(source_words) < ngram_size:
        return []

    if text_ngram_index is None:
        text_ngram_index = _build_ngram_index(text_words, ngram_size)

    matches: list[dict] = []
    seen_phrases: set[str] = set()

    for i in range(len(source_words) - ngram_size + 1):
        gram = tuple(source_words[i:i + ngram_size])
        text_pos = text_ngram_index.get(gram)
        if text_pos is None:
            continue

        phrase = " ".join(gram)
        if phrase in seen_phrases:
            continue
        seen_phrases.add(phrase)

        s_start = max(0, i - context_words // 2)
        s_end = min(len(source_words), i + ngram_size + context_words // 2)
        t_start = max(0, text_pos - context_words // 2)
        t_end = min(len(text_words), text_pos + ngram_size + context_words // 2)

        matches.append(
            {
                "matched_phrase": phrase,
                "source_excerpt": _clean_excerpt(" ".join(source_words[s_start:s_end])),
                "text_excerpt": _clean_excerpt(" ".join(text_words[t_start:t_end])),
            }
        )

        if len(matches) >= max_matches:
            break

    return matches


async def analyze_plagiarism(text: str, sources: list, progress_callback=None) -> dict:
    text_fp = generate_fingerprint(text)
    if not text_fp:
        return {"results": [], "total_sources_checked": len(sources)}

    text_words = _tokenize_words(text)
    text_ngram_index = _build_ngram_index(text_words, ngram_size=10)

    results = []

    total = len(sources)
    for index, source in enumerate(sources, start=1):
        if progress_callback:
            await progress_callback(source, index, total)

        source_text = source.get("content", "")
        source_fp = generate_fingerprint(source_text)
        similarity = compare_fingerprints(text_fp, source_fp)

        if similarity > 0:
            segments = find_matching_segments(
                text,
                source_text,
                ngram_size=10,
                max_matches=5,
                context_words=24,
                text_ngram_index=text_ngram_index,
            )
            results.append({
                "url": source.get("url", ""),
                "title": source.get("title", ""),
                "similarity": round(similarity * 100, 2),
                "matching_segments": segments
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return {"results": results, "total_sources_checked": len(sources)}
