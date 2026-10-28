import re
from .readability import analyze_readability


def _split_long_sentence(sentence: str) -> str:
    clauses = re.split(r'\b(y|pero|sin embargo|no obstante|por lo tanto|porque|ya que|puesto que|aunque|mientras|además)\b', sentence, flags=re.IGNORECASE)
    if len(clauses) >= 3:
        mid = len(clauses) // 2
        return " ".join(clauses[:mid]).strip() + ". " + " ".join(clauses[mid:]).strip() + "."
    words = sentence.split()
    mid = len(words) // 2
    return " ".join(words[:mid]) + ". " + " ".join(words[mid:]) + "."


def _join_short_sentences(sentences: list[str]) -> str:
    if len(sentences) >= 2:
        return sentences[0].strip().rstrip(".!?") + ", y " + sentences[1].strip().lower() + "."
    return " ".join(sentences)


def _passive_to_active(passive_sentence: str) -> str:
    match = re.search(r'\b(es|son|fue|fueron|era|eran|sea|sean|sido|siendo)\s+(\w+do)\b', passive_sentence, re.IGNORECASE)
    if match:
        return passive_sentence.replace(match.group(0), f"se {match.group(2)[:-1]}r").strip()
    return passive_sentence


def _add_transitions(sentences: list[str]) -> str:
    result = []
    for i, s in enumerate(sentences):
        s = s.strip()
        if i == 0:
            result.append(s)
        elif i == len(sentences) - 1:
            result.append(f"En conclusión, {s.lower()}")
        elif i % 2 == 0:
            result.append(f"Además, {s.lower()}")
        else:
            result.append(f"Por otro lado, {s.lower()}")
    return " ".join(result)


def get_improvement_suggestions(text: str) -> list:
    suggestions = []
    readability = analyze_readability(text)
    words = text.split()
    sentences = re.split(r'(?<=[.!?])\s+', text)

    def long_sentence_example(sentences: list[str]) -> str | None:
        long_sents = [s for s in sentences if len(s.split()) > 25]
        if long_sents:
            return _split_long_sentence(long_sents[0])
        return None

    def short_sentence_example(sentences: list[str]) -> str | None:
        short_pairs = []
        for i in range(len(sentences) - 1):
            if len(sentences[i].split()) < 8 and len(sentences[i+1].split()) < 8:
                short_pairs.append((sentences[i], sentences[i+1]))
                if len(short_pairs) >= 2:
                    break
        if short_pairs:
            return _join_short_sentences([short_pairs[0][0], short_pairs[0][1]])
        return None

    def passive_example(text: str) -> str | None:
        match = re.search(r'\b(es|son|fue|fueron|era|eran|sea|sean)\s+\w+do\b', text, re.IGNORECASE)
        if match:
            return _passive_to_active(match.group())
        return None

    def overused_example(text: str, overused_words: list[str]) -> str | None:
        for ow, _ in overused_words:
            idx = text.lower().find(ow)
            if idx != -1:
                start = max(0, text.rfind(".", 0, idx) + 1)
                end = text.find(".", idx)
                if end == -1:
                    end = len(text)
                sentence = text[start:end].strip()
                if len(sentence) > 20:
                    alt = sentence.replace(ow, f"**{ow}**")
                    return alt[:200]
        return None

    if readability["avg_words_per_sentence"] > 25:
        example = long_sentence_example(sentences)
        suggestions.append({
            "type": "readability",
            "severity": "medium",
            "suggestion": "Oraciones demasiado largas (promedio >25 palabras). Divídelas en oraciones más cortas para mejorar la claridad.",
            "explanation": f"Promedio actual: {readability['avg_words_per_sentence']:.0f} palabras por oración. Se recomienda 15-20 palabras.",
            "improved_example": example,
        })
    elif readability["avg_words_per_sentence"] < 10:
        example = short_sentence_example(sentences)
        suggestions.append({
            "type": "readability",
            "severity": "low",
            "suggestion": "Oraciones muy cortas. Combínalas para mejorar el flujo del texto.",
            "explanation": f"Promedio actual: {readability['avg_words_per_sentence']:.0f} palabras por oración.",
            "improved_example": example,
        })

    if readability["readability_level"] in ("Muy difícil", "Difícil"):
        suggestions.append({
            "type": "readability",
            "severity": "high",
            "suggestion": "El texto es muy complejo. Usa vocabulario más simple y oraciones más cortas.",
            "explanation": f"Nivel de legibilidad: {readability['readability_level']}. Puntaje Flesch: {readability['flesch_reading_ease']:.0f}/100.",
            "improved_example": None,
        })

    long_paragraphs = []
    current_para = []
    para_start = 0
    for i, sentence in enumerate(sentences):
        current_para.append(sentence)
        if sentence.endswith(('\n\n', '\r\n\r\n')) or i == len(sentences) - 1:
            para_text = ' '.join(current_para)
            para_words = len(para_text.split())
            if para_words > 150:
                long_paragraphs.append({
                    "start": para_start,
                    "word_count": para_words,
                    "text": para_text,
                })
            current_para = []
            para_start = i + 1

    for lp in long_paragraphs:
        paras = lp["text"].split(". ")
        mid = len(paras) // 2
        example = ". ".join(paras[:mid]) + ".\n\n" + ". ".join(paras[mid:]) + "."
        suggestions.append({
            "type": "structure",
            "severity": "medium",
            "suggestion": "Párrafo muy extenso. Divídelo en párrafos más pequeños (ideal: 50-150 palabras).",
            "explanation": f"Este párrafo tiene {lp['word_count']} palabras. Se recomienda máximo 150.",
            "improved_example": example if len(example) < 500 else example[:500] + "...",
        })

    passive_voice_matches = re.finditer(
        r'\b(es|son|fue|fueron|era|eran|sea|sean|sido|siendo)\s+\w+do\b|\b(ha|han|había|habían|habrá|habrán)\s+sido\s+\w+do\b',
        text, re.IGNORECASE
    )
    passive_count = len(list(passive_voice_matches))
    total_verbs_estimate = len(re.findall(r'\b\w+(?:ar|er|ir|ado|ido|ando|iendo|ado|ido)\b', text, re.IGNORECASE))
    if total_verbs_estimate > 0 and passive_count / total_verbs_estimate > 0.3:
        example = passive_example(text)
        suggestions.append({
            "type": "style",
            "severity": "low",
            "suggestion": "Uso excesivo de voz pasiva. Prefiere la voz activa para un texto más directo.",
            "explanation": f"Se detectaron {passive_count} construcciones en voz pasiva. Intenta usar voz activa.",
            "improved_example": example,
        })

    transition_words = [
        "sin embargo", "no obstante", "por lo tanto", "además", "por otro lado",
        "en conclusión", "por ejemplo", "en primer lugar", "finalmente", "así mismo",
        "de igual manera", "por consiguiente", "en cambio", "no obstante"
    ]
    transition_count = sum(1 for tw in transition_words if tw in text.lower())
    if transition_count < 2 and len(sentences) > 5:
        example = _add_transitions(sentences[:4])
        suggestions.append({
            "type": "structure",
            "severity": "medium",
            "suggestion": "Faltan palabras de transición. Usa conectores como 'sin embargo', 'además', 'por lo tanto' para mejorar la cohesión.",
            "explanation": f"Solo se detectaron {transition_count} palabras de transición en {len(sentences)} oraciones.",
            "improved_example": example,
        })

    repeated_words = {}
    for word in words:
        w = word.lower().strip('.,;:!?"\'()[]')
        if len(w) > 3:
            repeated_words[w] = repeated_words.get(w, 0) + 1

    overused = {w: c for w, c in repeated_words.items() if c > len(words) * 0.03 and c > 3}
    if overused:
        top_overused = sorted(overused.items(), key=lambda x: -x[1])[:3]
        example = overused_example(text, top_overused)
        suggestions.append({
            "type": "style",
            "severity": "low",
            "suggestion": f"Palabras sobreutilizadas: {', '.join(w for w, _ in top_overused)}. Usa sinónimos para variar el vocabulario.",
            "explanation": "Repetir palabras frecuentemente reduce la calidad del texto.",
            "improved_example": example,
        })

    return suggestions
