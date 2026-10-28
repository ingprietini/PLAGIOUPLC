from dataclasses import asdict, is_dataclass
import re


def _serialize(obj):
    if is_dataclass(obj):
        return asdict(obj)
    return obj


def _boost_probability(prob: float, features: dict) -> float:
    boosted = prob

    if features.get("burstiness", 1) < 0.1:
        boosted += 8
    if features.get("sentence_length_variance", 1) < 0.2:
        boosted += 6
    if features.get("char_entropy", 10) < 4.0:
        boosted += 5
    if features.get("vocabulary_richness", 1) < 0.3:
        boosted += 5
    if features.get("conjunction_start_ratio", 0) > 0.3:
        boosted += 4
    if features.get("hedging_density", 0) > 0.05:
        boosted += 4
    if features.get("punctuation_entropy", 1) < 1.5:
        boosted += 3
    if features.get("bigram_repetition", 0) > 0.05:
        boosted += 3

    if boosted > 0.1:
        boosted = boosted * 1.25 + 5

    return min(boosted, 100)


def _boosted_verdict(boosted_prob: float) -> str:
    if boosted_prob >= 25:
        return "AI-generated"
    if boosted_prob >= 15:
        return "Posiblemente IA"
    return "Human-written"


def _boosted_confidence(boosted_prob: float) -> str:
    if boosted_prob >= 60:
        return "high"
    if boosted_prob >= 30:
        return "medium"
    return "low"


def _extra_flags(features: dict) -> list:
    flags = []
    if features.get("burstiness", 1) < 0.05:
        flags.append("Burstiness extremadamente baja — patrón típico de IA")
    if features.get("sentence_length_variance", 1) < 0.1:
        flags.append("Longitud de oraciones casi idéntica — poco natural")
    if features.get("bigram_repetition", 0) > 0.08:
        flags.append("Repetición excesiva de bigramas — característico de IA")
    if features.get("conjunction_start_ratio", 0) > 0.35:
        flags.append("Muchas oraciones comienzan con conjunciones — patrón de IA")
    if features.get("trigram_repetition", 0) > 0.03:
        flags.append("Repetición de trigramas — texto generado por IA")
    if features.get("punctuation_entropy", 1) < 1.0:
        flags.append("Uso de puntuación muy uniforme — poco humano")
    if features.get("vocabulary_richness", 1) < 0.25:
        flags.append("Vocabulario poco diverso — indicador de IA")
    if features.get("chatbot_marker_score", 0) > 0.1:
        flags.append("Presencia de marcadores de chatbot")
    return flags


def detect_ai_text(text: str) -> dict | None:
    try:
        from lmscan import scan

        result = scan(text)
        features = asdict(result.features)
        raw_prob = result.ai_probability * 100
        boosted_prob = _boost_probability(raw_prob, features)

        extra = _extra_flags(features)
        all_flags = list(result.flags) + extra

        return {
            "ai_probability": round(boosted_prob, 1),
            "raw_probability": round(raw_prob, 1),
            "verdict": _boosted_verdict(boosted_prob),
            "confidence": _boosted_confidence(boosted_prob),
            "flags": all_flags,
            "scan_time_ms": round(result.scan_time_s * 1000, 1),
            "features": features,
            "sentence_count": result.features.sentence_count,
            "model_attribution": [_serialize(m) for m in result.model_attribution],
        }
    except Exception:
        return None
