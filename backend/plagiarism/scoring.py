from plagiarism.source_metrics import evaluate_content_quality, short_page_penalty, compute_match_confidence


def combine_similarity_scores(winnowing_score: float, tfidf_score: float) -> float:
    combined = max(winnowing_score, tfidf_score) + (min(winnowing_score, tfidf_score) * 0.3)
    return round(min(combined, 100), 2)


def rank_sources(
    winnowing_results: list[dict],
    tfidf_map: dict[str, float],
    source_lookup: dict[str, dict] | None = None,
    min_tfidf_only: float = 12.0,
    limit: int = 20,
) -> list[dict]:
    ranked: list[dict] = []
    seen_urls: set[str] = set()

    for item in winnowing_results:
        w_sim = float(item.get("similarity", 0))
        t_sim = float(tfidf_map.get(item.get("url", ""), 0))
        combined = combine_similarity_scores(w_sim, t_sim)
        source_data = source_lookup.get(item.get("url", ""), {}) if source_lookup else {}
        quality_data = evaluate_content_quality(source_data.get("content", ""), source_data.get("snippet", ""))
        penalty = short_page_penalty(quality_data["word_count"])
        confidence = compute_match_confidence(w_sim, t_sim, quality_data["content_quality"], penalty)

        adjusted_similarity = combined * (0.8 + (quality_data["content_quality"] * 0.2)) * (1.0 - penalty * 0.65)
        adjusted_similarity = round(min(adjusted_similarity, 100), 2)

        if adjusted_similarity <= 0:
            continue

        ranked_item = dict(item)
        ranked_item["similarity"] = adjusted_similarity
        ranked_item["raw_similarity"] = combined
        ranked_item["match_confidence"] = confidence
        ranked_item["content_quality"] = quality_data["content_quality"]
        ranked_item["source_word_count"] = quality_data["word_count"]
        ranked_item["short_page_penalty"] = penalty
        ranked.append(ranked_item)
        seen_urls.add(item.get("url", ""))

    # Include conceptually similar sources even when exact fingerprint overlap is low.
    for url, tfidf_score in tfidf_map.items():
        if not url or url in seen_urls or tfidf_score < min_tfidf_only:
            continue

        source_data = source_lookup.get(url, {}) if source_lookup else {}
        quality_data = evaluate_content_quality(source_data.get("content", ""), source_data.get("snippet", ""))
        penalty = short_page_penalty(quality_data["word_count"])
        confidence = compute_match_confidence(0.0, float(tfidf_score), quality_data["content_quality"], penalty)
        adjusted_similarity = round(float(tfidf_score) * (0.75 + quality_data["content_quality"] * 0.25) * (1.0 - penalty * 0.65), 2)
        ranked.append(
            {
                "url": url,
                "title": source_data.get("title", url),
                "similarity": min(adjusted_similarity, 100),
                "raw_similarity": round(float(tfidf_score), 2),
                "match_confidence": confidence,
                "content_quality": quality_data["content_quality"],
                "source_word_count": quality_data["word_count"],
                "short_page_penalty": penalty,
                "matching_segments": [],
            }
        )

    ranked.sort(key=lambda x: x["similarity"], reverse=True)
    return ranked[:limit]


def build_stats(
    sources: list[dict],
    readability: dict,
    ai_detection: dict,
    word_count: int,
    similarity_threshold: float,
    sources_checked: int,
) -> dict:
    max_similarity = max((s["similarity"] for s in sources), default=0)
    threshold_pct = similarity_threshold * 100
    above_threshold = [s for s in sources if s["similarity"] > threshold_pct]

    avg_similarity = (
        round(sum(s["similarity"] for s in above_threshold) / len(above_threshold), 2)
        if above_threshold
        else 0
    )

    overall_similarity = round(max_similarity + (len(above_threshold) * 2), 2) if max_similarity > 0 else 0
    overall_similarity = min(overall_similarity, 100)

    avg_confidence = (
        round(sum(float(s.get("match_confidence", 0)) for s in sources) / len(sources), 4)
        if sources
        else 0
    )
    avg_content_quality = (
        round(sum(float(s.get("content_quality", 0)) for s in sources) / len(sources), 4)
        if sources
        else 0
    )

    return {
        "overall_similarity": overall_similarity,
        "max_similarity": max_similarity,
        "avg_similarity": avg_similarity,
        "total_sources": len(sources),
        "sources_above_threshold": len(above_threshold),
        "unique_sources": len(set(s["url"] for s in sources)),
        "avg_match_confidence": avg_confidence,
        "avg_source_content_quality": avg_content_quality,
        "readability": readability,
        "ai_detection": ai_detection,
        "word_count": word_count,
        "sources_checked": sources_checked,
    }
