def build_stats(
    plagiarism_stats: dict,
    readability: dict,
    ai_detection: dict | None,
    word_count: int,
    sources_checked: int,
) -> dict:
    """Estadísticas finales del análisis (formato que consume el frontend)."""
    stats = dict(plagiarism_stats)
    stats.update({
        "readability": readability,
        "ai_detection": ai_detection,
        "word_count": word_count,
        "sources_checked": sources_checked,
    })
    return stats
