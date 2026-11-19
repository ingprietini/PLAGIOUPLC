"""Utilidades de texto deterministas compartidas por todo el motor de plagio.

Todo el motor trabaja sobre tokens normalizados (minúsculas, sin tildes) pero
conserva la posición de cada token en el texto original para poder mostrar
fragmentos exactos al usuario.
"""

import hashlib
import re
import unicodedata
from dataclasses import dataclass

# Una palabra puede contener caracteres invisibles o cortarse con guion al final de línea
# ("pala-" + salto + "bra"); ambos se unen al normalizar. Son trucos habituales para evadir detectores.
_INVISIBLE = "\u200b\u200c\u200d\u2060\ufeff\u00ad"
_TOKEN_RE = re.compile(r"[^\W_]+(?:(?:[" + _INVISIBLE + r"]+|-[ \t]*\r?\n[ \t]*)[^\W_]+)*", re.UNICODE)
_INVISIBLE_RE = re.compile(r"[" + _INVISIBLE + r"]|-[ \t]*\r?\n[ \t]*")
# Letras cirílicas/griegas que se ven idénticas a las latinas.
_HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
    "ԁ": "d", "һ": "h", "ӏ": "l", "ɡ": "g", "ν": "v", "ο": "o", "α": "a", "ε": "e", "ι": "i", "κ": "k",
    "ρ": "p", "τ": "t", "υ": "u", "χ": "x",
    "А": "a", "В": "b", "Е": "e", "К": "k", "М": "m", "Н": "h", "О": "o", "Р": "p", "С": "c", "Т": "t",
    "Х": "x", "І": "i", "Ј": "j", "Ѕ": "s",
})
_LATIN_RE = re.compile(r"[a-zA-Z]")
_QUOTE_RE = re.compile(r"[\"“«„]([^\"”»“«]{40,1500}?)[\"”»]", re.DOTALL)
_SENTENCE_END_RE = re.compile(r"(?<=[.!?…])\s+|\n\s*\n+")
_BIBLIO_HEADING_RE = re.compile(
    r"^\s*(?:\d+[.)]?\s*)?(referencias(?: bibliogr[aá]ficas)?|bibliograf[ií]a|fuentes consultadas|"
    r"obras citadas|references|bibliography|works cited)\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

STOP_WORDS = frozenset([
    "a", "about", "above", "after", "again", "against", "al", "algo", "algunas", "algunos",
    "all", "am", "an", "and", "ante", "antes", "any", "are", "as", "at", "be", "because",
    "been", "before", "being", "below", "between", "both", "but", "by", "como", "con",
    "contra", "could", "cual", "cuando", "de", "del", "desde", "did", "do", "does",
    "doing", "donde", "down", "durante", "during", "e", "each", "el", "ella", "ellas",
    "ellos", "en", "entre", "era", "erais", "eran", "eras", "eres", "es", "esa", "esas",
    "ese", "eso", "esos", "esta", "estaba", "estabais", "estaban", "estabas", "estad",
    "estada", "estadas", "estado", "estados", "estamos", "estando", "estar", "estara",
    "estaran", "estaras", "estare", "estareis", "estaremos", "estaria", "estariais",
    "estariamos", "estarian", "estarias", "estas", "este", "estemos", "esto", "estos",
    "estoy", "estuve", "estuviera", "estuvierais", "estuvieramos", "estuvieran",
    "estuvieras", "estuvieron", "estuviese", "estuvieseis", "estuviesemos", "estuviesen",
    "estuvieses", "estuvimos", "estuviste", "estuvisteis", "few", "for", "from", "further",
    "ha", "habeis", "habia", "habiais", "habiamos", "habian", "habias", "habida",
    "habidas", "habido", "habidos", "habiendo", "habra", "habran", "habras", "habre",
    "habreis", "habremos", "habria", "habriais", "habriamos", "habrian", "habrias", "had",
    "han", "has", "hasta", "have", "having", "hay", "haya", "hayais", "hayamos", "hayan",
    "hayas", "he", "hemos", "her", "here", "hers", "herself", "him", "himself", "his",
    "how", "hube", "hubiera", "hubierais", "hubieramos", "hubieran", "hubieras",
    "hubieron", "hubiese", "hubieseis", "hubiesemos", "hubiesen", "hubieses", "hubimos",
    "hubiste", "hubisteis", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "la", "las", "le", "les", "lo", "los", "mas", "me", "mi", "mis", "more", "most",
    "mucho", "muchos", "muy", "my", "myself", "ni", "no", "nor", "nos", "nosotras",
    "nosotros", "not", "now", "nuestra", "nuestras", "nuestro", "nuestros", "o", "of",
    "on", "once", "only", "or", "os", "other", "otra", "otras", "otro", "otros", "our",
    "ours", "ourselves", "out", "over", "own", "para", "per", "pero", "por", "porque",
    "que", "quien", "quienes", "same", "se", "sea", "seais", "seamos", "sean", "seas",
    "ser", "sera", "seran", "seras", "sere", "sereis", "seremos", "seria", "seriais",
    "seriamos", "serian", "serias", "she", "should", "si", "sido", "siendo", "sin", "so",
    "sobre", "sois", "some", "somos", "son", "soy", "su", "such", "sus", "suya", "suyas",
    "suyo", "suyos", "tal", "tambien", "tan", "tanto", "te", "teneis", "tenemos", "tenga",
    "tengais", "tengamos", "tengan", "tengas", "tengo", "tenia", "teniais", "teniamos",
    "tenian", "tenias", "tenida", "tenidas", "tenido", "tenidos", "teniendo", "than",
    "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these",
    "they", "this", "those", "through", "ti", "tiene", "tienen", "tienes", "to", "todo",
    "todos", "too", "tu", "tus", "tuve", "tuviera", "tuvierais", "tuvieramos", "tuvieran",
    "tuvieras", "tuvieron", "tuviese", "tuvieseis", "tuviesemos", "tuviesen", "tuvieses",
    "tuvimos", "tuviste", "tuvisteis", "tuya", "tuyas", "tuyo", "tuyos", "un", "una",
    "unas", "under", "unos", "until", "up", "usted", "ustedes", "very", "vosotras",
    "vosotros", "vuestra", "vuestras", "vuestro", "vuestros", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will", "with", "would", "y",
    "ya", "yo", "you", "your", "yours", "yourself", "yourselves"
])


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def normalize_token(token: str) -> str:
    token = _INVISIBLE_RE.sub("", token)
    if _LATIN_RE.search(token):
        # Solo se traducen homoglifos en palabras mixtas: un texto realmente en ruso o griego no se altera.
        token = token.translate(_HOMOGLYPHS)
    return strip_accents(unicodedata.normalize("NFKC", token).lower())


def count_evasion_marks(text: str) -> dict:
    """Cuenta caracteres invisibles y homoglifos incrustados en palabras latinas."""
    invisible = sum(text.count(ch) for ch in _INVISIBLE if ch != "­")
    homoglyph_words = 0
    for m in _TOKEN_RE.finditer(text or ""):
        word = m.group()
        if _LATIN_RE.search(word) and word != word.translate(_HOMOGLYPHS):
            homoglyph_words += 1
    return {"invisible_chars": invisible, "homoglyph_words": homoglyph_words}


def quoted_token_ranges(text: str, tokens: "Tokens") -> list[tuple[int, int]]:
    """Rangos de tokens [inicio, fin) que están entre comillas (citas textuales)."""
    ranges: list[tuple[int, int]] = []
    starts = [s for s, _ in tokens.spans]
    import bisect
    for m in _QUOTE_RE.finditer(text or ""):
        a = bisect.bisect_left(starts, m.start(1))
        b = bisect.bisect_left(starts, m.end(1))
        if b - a >= 6:
            ranges.append((a, b))
    return ranges


@dataclass(frozen=True)
class Tokens:
    """Tokens normalizados y sus posiciones (inicio, fin) en el texto original."""

    words: list[str]
    spans: list[tuple[int, int]]

    def __len__(self) -> int:
        return len(self.words)

    def excerpt(self, text: str, start: int, end: int, context: int = 0, max_chars: int = 320) -> str:
        """Texto original entre los tokens [start, end) con `context` tokens de margen."""
        if not self.words:
            return ""
        a = max(0, start - context)
        b = min(len(self.words), end + context) - 1
        if b < a:
            return ""
        snippet = re.sub(r"\s+", " ", text[self.spans[a][0]:self.spans[b][1]]).strip()
        if len(snippet) > max_chars:
            snippet = snippet[: max_chars - 1].rstrip() + "…"
        return snippet


def tokenize(text: str) -> Tokens:
    words: list[str] = []
    spans: list[tuple[int, int]] = []
    for m in _TOKEN_RE.finditer(text or ""):
        words.append(normalize_token(m.group()))
        spans.append(m.span())
    return Tokens(words, spans)


def is_content_word(word: str) -> bool:
    return len(word) > 2 and word not in STOP_WORDS and not word.isdigit()


def content_stem(word: str) -> str:
    """Raíz aproximada (prefijo) para comparar formas flexionadas: 'educativos' ~ 'educativa'."""
    return word[:6]


@dataclass(frozen=True)
class Sentence:
    start_token: int
    end_token: int  # exclusivo


def split_sentences(text: str, tokens: Tokens) -> list[Sentence]:
    """Divide en oraciones usando la puntuación del texto original, en rangos de tokens."""
    if not tokens.words:
        return []
    boundaries = [m.end() for m in _SENTENCE_END_RE.finditer(text)]
    sentences: list[Sentence] = []
    start = 0
    b_idx = 0
    for i, (tok_start, _) in enumerate(tokens.spans):
        while b_idx < len(boundaries) and boundaries[b_idx] <= tok_start:
            if i > start:
                sentences.append(Sentence(start, i))
                start = i
            b_idx += 1
    if start < len(tokens.words):
        sentences.append(Sentence(start, len(tokens.words)))

    # Oraciones demasiado largas (p. ej. texto sin puntuación) se parten en bloques de 40 palabras.
    result: list[Sentence] = []
    for s in sentences:
        length = s.end_token - s.start_token
        if length <= 60:
            result.append(s)
            continue
        for a in range(s.start_token, s.end_token, 40):
            result.append(Sentence(a, min(a + 40, s.end_token)))
    return result


def strip_bibliography(text: str) -> tuple[str, bool]:
    """Quita la sección de referencias si aparece en el último 45% del documento.

    Las listas de referencias coinciden casi siempre con la web (son citas) y
    no constituyen plagio, así que inflaban el porcentaje.
    """
    matches = list(_BIBLIO_HEADING_RE.finditer(text or ""))
    if not matches:
        return text, False
    last = matches[-1]
    if last.start() < len(text) * 0.55:
        return text, False
    return text[: last.start()].rstrip(), True


def text_fingerprint(text: str) -> str:
    """Hash estable del contenido: ignora mayúsculas, tildes, puntuación y espacios."""
    joined = " ".join(tokenize(text).words)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
