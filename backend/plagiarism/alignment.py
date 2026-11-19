"""Comparación documento ↔ fuente.

Reemplaza al Winnowing con Jaccard y al TF-IDF global anteriores, que daban
porcentajes cercanos a 0 aunque hubiera párrafos copiados (Jaccard divide por el
tamaño de ambos textos) y cambiaban según qué otras fuentes aparecieran.

Ahora, para cada fuente se calcula qué palabras del documento proceden de ella:

1. Coincidencia literal: huellas de N palabras normalizadas (sin tildes ni
   mayúsculas). Se ignoran huellas formadas solo por palabras vacías.
2. Tramos: las coincidencias se unen tolerando unas pocas palabras cambiadas
   (copia con retoques) y se descartan tramos más cortos que MIN_MATCH_WORDS.
3. Paráfrasis: oraciones no copiadas literalmente se comparan con las de la
   fuente mediante TF-IDF de n-gramas de caracteres (insensible al orden de las
   palabras), ajustado SOLO con ese par documento-fuente. Se acepta si:
   a) la similitud supera PARAPHRASE_THRESHOLD y comparten la mitad de las
      palabras con contenido, o
   b) la similitud es algo menor pero comparten ≥60% de raíces (Jaccard) y al
      menos 6: oraciones reordenadas con algún sinónimo.
4. Citas: tramos literales que están entre comillas se reportan como "cita" y
   no suman a la similitud global (EXCLUDE_QUOTES).

El resultado es determinista: mismo documento + misma fuente => mismo valor.
"""

from dataclasses import dataclass, field

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import EXCLUDE_QUOTES, MATCH_GAP_WORDS, MIN_MATCH_WORDS, PARAPHRASE_THRESHOLD, SHINGLE_SIZE
from plagiarism.text_utils import (
    Sentence,
    Tokens,
    content_stem,
    is_content_word,
    quoted_token_ranges,
    split_sentences,
    tokenize,
)


@dataclass
class PreparedDocument:
    text: str
    tokens: Tokens
    sentences: list[Sentence]
    shingle_positions: dict[tuple[str, ...], list[int]]
    sentence_texts: list[str]
    sentence_stems: list[frozenset[str]]
    quoted: frozenset[int] = frozenset()


@dataclass
class SourceMatch:
    url: str
    title: str
    exact_words: set[int] = field(default_factory=set)
    paraphrase_words: set[int] = field(default_factory=set)
    quoted_words: set[int] = field(default_factory=set)
    segments: list[dict] = field(default_factory=list)
    source_word_count: int = 0
    longest_run: int = 0

    @property
    def covered_words(self) -> set[int]:
        return self.exact_words | self.paraphrase_words


def _informative(gram: tuple[str, ...]) -> bool:
    return sum(1 for w in gram if is_content_word(w)) >= 2


def _shingles(words: list[str], n: int):
    for i in range(len(words) - n + 1):
        gram = tuple(words[i:i + n])
        if _informative(gram):
            yield i, gram


def prepare_document(text: str) -> PreparedDocument:
    tokens = tokenize(text)
    sentences = split_sentences(text, tokens)
    positions: dict[tuple[str, ...], list[int]] = {}
    for i, gram in _shingles(tokens.words, SHINGLE_SIZE):
        positions.setdefault(gram, []).append(i)
    sentence_texts = [" ".join(tokens.words[s.start_token:s.end_token]) for s in sentences]
    sentence_stems = [
        frozenset(content_stem(w) for w in tokens.words[s.start_token:s.end_token] if is_content_word(w))
        for s in sentences
    ]
    quoted: set[int] = set()
    if EXCLUDE_QUOTES:
        for a, b in quoted_token_ranges(text, tokens):
            quoted.update(range(a, b))
    return PreparedDocument(text, tokens, sentences, positions, sentence_texts, sentence_stems, frozenset(quoted))


def _runs(indices: set[int], gap: int) -> list[tuple[int, int]]:
    """Agrupa índices en tramos [inicio, fin) permitiendo huecos de hasta `gap` palabras."""
    if not indices:
        return []
    ordered = sorted(indices)
    runs: list[tuple[int, int]] = []
    start = prev = ordered[0]
    for idx in ordered[1:]:
        if idx - prev - 1 > gap:
            runs.append((start, prev + 1))
            start = idx
        prev = idx
    runs.append((start, prev + 1))
    return runs


def _exact_matches(doc: PreparedDocument, src_tokens: Tokens) -> tuple[list[tuple[int, int]], dict[int, int]]:
    """Tramos del documento copiados de la fuente y, para cada tramo, una posición en la fuente."""
    n = SHINGLE_SIZE
    src_positions: dict[tuple[str, ...], int] = {}
    for i, gram in _shingles(src_tokens.words, n):
        src_positions.setdefault(gram, i)

    covered: set[int] = set()
    anchor: dict[int, int] = {}
    for gram, doc_positions in doc.shingle_positions.items():
        src_pos = src_positions.get(gram)
        if src_pos is None:
            continue
        for p in doc_positions:
            covered.update(range(p, p + n))
            anchor.setdefault(p, src_pos)

    runs = [(a, b) for a, b in _runs(covered, MATCH_GAP_WORDS) if b - a >= MIN_MATCH_WORDS]
    run_anchor: dict[int, int] = {}
    for a, b in runs:
        for p in range(a, b):
            if p in anchor:
                run_anchor[a] = anchor[p] - (p - a)
                break
    return runs, run_anchor


def _paraphrase_matches(
    doc: PreparedDocument,
    src_text: str,
    src_tokens: Tokens,
    exact_words: set[int],
) -> list[tuple[int, int, int, float]]:
    """(oración_doc, inicio_tok_fuente, fin_tok_fuente, similitud) para oraciones parafraseadas."""
    candidates: list[int] = []
    for idx, s in enumerate(doc.sentences):
        length = s.end_token - s.start_token
        if length < 8 or len(doc.sentence_stems[idx]) < 4:
            continue
        already = sum(1 for p in range(s.start_token, s.end_token) if p in exact_words)
        if already / length >= 0.5:
            continue
        candidates.append(idx)
    if not candidates:
        return []

    src_sentences = [
        s for s in split_sentences(src_text, src_tokens)
        if s.end_token - s.start_token >= 6
    ]
    if not src_sentences:
        return []

    # Prefiltro barato: la fuente debe compartir palabras con contenido con la oración.
    src_vocab = frozenset(content_stem(w) for w in src_tokens.words if is_content_word(w))
    candidates = [i for i in candidates if len(doc.sentence_stems[i] & src_vocab) / len(doc.sentence_stems[i]) >= 0.6]
    if not candidates:
        return []

    src_texts = [" ".join(src_tokens.words[s.start_token:s.end_token]) for s in src_sentences]
    src_stems = [
        frozenset(content_stem(w) for w in src_tokens.words[s.start_token:s.end_token] if is_content_word(w))
        for s in src_sentences
    ]
    doc_texts = [doc.sentence_texts[i] for i in candidates]

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, dtype=np.float64)
    try:
        matrix = vectorizer.fit_transform(doc_texts + src_texts)
    except ValueError:
        return []
    sims = cosine_similarity(matrix[: len(doc_texts)], matrix[len(doc_texts):])

    found = []
    relaxed = PARAPHRASE_THRESHOLD - 0.12
    for row, doc_idx in enumerate(candidates):
        doc_stems = doc.sentence_stems[doc_idx]
        top = sims[row].argsort()[::-1][:5]
        for best in top:
            best = int(best)
            score = float(sims[row, best])
            if score < relaxed:
                break
            shared = len(doc_stems & src_stems[best])
            overlap = shared / max(1, len(doc_stems))
            jaccard = shared / max(1, len(doc_stems | src_stems[best]))
            if (score >= PARAPHRASE_THRESHOLD and overlap >= 0.5) or (jaccard >= 0.6 and shared >= 6):
                s = src_sentences[best]
                found.append((doc_idx, s.start_token, s.end_token, round(score, 4)))
                break
    return found


def compare(doc: PreparedDocument, url: str, title: str, src_text: str, max_segments: int = 8) -> SourceMatch:
    src_tokens = tokenize(src_text)
    match = SourceMatch(url=url, title=title, source_word_count=len(src_tokens))
    if len(src_tokens) < SHINGLE_SIZE or not doc.tokens.words:
        return match

    runs, run_anchor = _exact_matches(doc, src_tokens)
    segments: list[tuple[int, dict]] = []
    for a, b in runs:
        run_words = set(range(a, b))
        is_quote = bool(doc.quoted) and len(run_words & doc.quoted) >= 0.8 * len(run_words)
        if is_quote:
            match.quoted_words.update(run_words)
        else:
            match.exact_words.update(run_words)
            match.longest_run = max(match.longest_run, b - a)
        src_start = max(0, run_anchor.get(a, 0))
        src_end = min(len(src_tokens), src_start + (b - a))
        segments.append(((b - a) * (0.3 if is_quote else 1.0), {
            "match_type": "quote" if is_quote else "exact",
            "matched_words": b - a,
            "matched_phrase": doc.tokens.excerpt(doc.text, a, min(b, a + 14), max_chars=160),
            "text_excerpt": doc.tokens.excerpt(doc.text, a, b, context=6),
            "source_excerpt": src_tokens.excerpt(src_text, src_start, src_end, context=6),
            "text_pos_start": doc.tokens.spans[a][0],
            "text_pos_end": doc.tokens.spans[b - 1][1],
        }))

    for doc_idx, s_start, s_end, score in _paraphrase_matches(doc, src_text, src_tokens, match.exact_words | match.quoted_words):
        s = doc.sentences[doc_idx]
        words = set(range(s.start_token, s.end_token)) - match.exact_words - match.quoted_words
        if len(words) < 4:
            continue
        match.paraphrase_words.update(words)
        segments.append((len(words) * 0.8, {
            "match_type": "paraphrase",
            "matched_words": len(words),
            "similarity": round(score * 100, 1),
            "matched_phrase": "",
            "text_excerpt": doc.tokens.excerpt(doc.text, s.start_token, s.end_token),
            "source_excerpt": src_tokens.excerpt(src_text, s_start, s_end),
            "text_pos_start": doc.tokens.spans[s.start_token][0],
            "text_pos_end": doc.tokens.spans[s.end_token - 1][1],
        }))

    # Segmentos más largos primero; desempate por posición en el texto (determinista).
    segments.sort(key=lambda item: (-item[0], item[1]["text_pos_start"]))
    match.segments = [seg for _, seg in segments[:max_segments]]
    return match
