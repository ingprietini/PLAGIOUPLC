import re


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def evaluate_content_quality(content: str, snippet: str = "") -> dict:
    text = (content or snippet or "").strip()
    if not text:
        return {
            "content_quality": 0.0,
            "word_count": 0,
            "sentence_count": 0,
            "lexical_diversity": 0.0,
        }

    words = re.findall(r"\b\w+\b", text.lower())
    word_count = len(words)
    sentence_count = max(1, len(re.findall(r"[.!?]", text)))
    unique_words = len(set(words))

    lexical_diversity = (unique_words / word_count) if word_count else 0.0

    length_score = _clamp(word_count / 450.0, 0.0, 1.0)
    sentence_score = _clamp(sentence_count / 24.0, 0.0, 1.0)
    diversity_score = _clamp(lexical_diversity / 0.55, 0.0, 1.0)

    quality = (length_score * 0.5) + (sentence_score * 0.2) + (diversity_score * 0.3)

    return {
        "content_quality": round(_clamp(quality, 0.0, 1.0), 4),
        "word_count": word_count,
        "sentence_count": sentence_count,
        "lexical_diversity": round(lexical_diversity, 4),
    }


def short_page_penalty(word_count: int) -> float:
    if word_count >= 180:
        return 0.0
    if word_count <= 30:
        return 0.45

    # Linear penalty from 30 to 180 words.
    penalty = (180 - word_count) / 150 * 0.45
    return round(_clamp(penalty, 0.0, 0.45), 4)


def compute_match_confidence(
    winnowing_score: float,
    tfidf_score: float,
    content_quality: float,
    penalty: float,
) -> float:
    w = _clamp(winnowing_score / 100.0, 0.0, 1.0)
    t = _clamp(tfidf_score / 100.0, 0.0, 1.0)

    if w > 0 and t > 0:
        agreement = 1.0 - abs(w - t)
    else:
        agreement = 0.35

    base = (max(w, t) * 0.55) + (min(w, t) * 0.25) + (_clamp(agreement, 0.0, 1.0) * 0.2)
    confidence = base * _clamp(content_quality, 0.0, 1.0) * (1.0 - _clamp(penalty, 0.0, 0.6))

    return round(_clamp(confidence, 0.0, 1.0), 4)
