import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_SPANISH_STOP_WORDS = [
    "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como", "con", "contra",
    "cual", "cuando", "de", "del", "desde", "donde", "durante", "e", "el", "ella",
    "ellas", "ellos", "en", "entre", "era", "erais", "eran", "eras", "eres", "es",
    "esa", "esas", "ese", "eso", "esos", "esta", "estaba", "estabais", "estaban",
    "estabas", "estad", "estada", "estadas", "estado", "estados", "estamos",
    "estando", "estar", "estaremos", "estará", "estarán", "estarás", "estaré",
    "estaréis", "estaría", "estaríais", "estaríamos", "estarían", "estarías",
    "estas", "este", "estemos", "esto", "estos", "estoy", "estuve", "estuviera",
    "estuvierais", "estuvieran", "estuvieras", "estuvieron", "estuviese",
    "estuvieseis", "estuviesen", "estuvieses", "estuvimos", "estuviste",
    "estuvisteis", "estuviéramos", "estuviésemos", "ha", "habida", "habidas",
    "habido", "habidos", "habiendo", "habremos", "habrá", "habrán", "habrás",
    "habré", "habréis", "habría", "habríais", "habríamos", "habrían", "habrías",
    "habéis", "había", "habíais", "habíamos", "habían", "habías", "han", "has",
    "hasta", "hay", "haya", "hayamos", "hayan", "hayas", "hayáis", "he", "hemos",
    "hube", "hubiera", "hubierais", "hubieran", "hubieras", "hubieron", "hubiese",
    "hubieseis", "hubiesen", "hubieses", "hubimos", "hubiste", "hubisteis",
    "hubiéramos", "hubiésemos", "la", "las", "le", "les", "lo", "los", "me",
    "mi", "mis", "mucho", "muchos", "muy", "más", "ni", "no", "nos", "nosotras",
    "nosotros", "nuestra", "nuestras", "nuestro", "nuestros", "o", "os", "otra",
    "otras", "otro", "otros", "para", "pero", "por", "porque", "que", "quien",
    "quienes", "qué", "se", "sea", "seamos", "sean", "seas", "ser", "seremos",
    "será", "serán", "serás", "seré", "seréis", "sería", "seríais", "seríamos",
    "serían", "serías", "seáis", "si", "sido", "siendo", "sin", "sobre", "sois",
    "somos", "son", "soy", "su", "sus", "suya", "suyas", "suyo", "suyos", "sí",
    "tal", "también", "tan", "tanto", "te", "tenemos", "tenga", "tengamos",
    "tengan", "tengas", "tengo", "tengáis", "tenida", "tenidas", "tenido",
    "tenidos", "teniendo", "tenéis", "tenía", "teníais", "teníamos", "tenían",
    "tenías", "ti", "tiene", "tienen", "tienes", "todo", "todos", "tu", "tus",
    "tuve", "tuviera", "tuvierais", "tuvieran", "tuvieras", "tuvieron", "tuviese",
    "tuvieseis", "tuviesen", "tuvieses", "tuvimos", "tuviste", "tuvisteis",
    "tuviéramos", "tuviésemos", "tuya", "tuyas", "tuyo", "tuyos", "tú", "un",
    "una", "unas", "unos", "usted", "ustedes", "vosotras", "vosotros", "vuestra",
    "vuestras", "vuestro", "vuestros", "y", "ya", "yo", "él", "ésta", "éstas",
    "éste", "éstos",
]

_ENGLISH_STOP_WORDS = [
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "could", "did", "do", "does", "doing", "down",
    "during", "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me",
    "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "on", "once",
    "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own",
    "per", "same", "she", "should", "so", "some", "such", "than", "that", "the",
    "their", "theirs", "them", "themselves", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up", "very",
    "was", "we", "were", "what", "when", "where", "which", "while", "who",
    "whom", "why", "will", "with", "would", "you", "your", "yours", "yourself",
    "yourselves",
]


def _detect_language(text: str) -> str:
    text_lower = text.lower()
    es_score = sum(1 for w in ["de", "la", "que", "el", "en", "y", "los", "se", "del", "las", "por", "para", "con", "una", "su", "al", "como", "más", "pero", "sus", "era", "entre", "porque", "este", "esta", "muy", "sin", "sobre", "también", "vez", "podría", "dijo", "cada", "ser", "tiene", "todo", "esa", "eso", "son"] if w in text_lower)
    en_score = sum(1 for w in ["the", "and", "that", "have", "for", "not", "with", "you", "this", "but", "his", "from", "they", "say", "her", "she", "will", "one", "all", "would", "there", "their", "what", "out", "about", "who", "get", "which", "when", "make", "can", "like", "time", "just", "him", "know", "take", "people", "into", "year", "your", "good", "some", "could", "them", "see", "other", "than", "then", "now", "look", "only", "come", "its", "over", "think", "also", "back", "after", "use", "two", "how", "our", "work", "first", "well", "way", "even", "new", "want", "because"] if w in text_lower)
    return "es" if es_score > en_score else "en"


def _get_stop_words(text: str) -> list[str]:
    lang = _detect_language(text)
    return _SPANISH_STOP_WORDS if lang == "es" else _ENGLISH_STOP_WORDS


def preprocess(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def compute_similarity(original: str, sources: list) -> list:
    if not sources:
        return []

    preprocessed_original = preprocess(original)
    preprocessed_sources = [preprocess(s.get("content", "")) for s in sources]
    if not preprocessed_original or not any(preprocessed_sources):
        return [
            {
                "url": source.get("url", ""),
                "title": source.get("title", ""),
                "similarity": 0.0,
            }
            for source in sources
        ]

    documents = [preprocessed_original] + preprocessed_sources
    vectorizer = TfidfVectorizer(
        max_features=10000,
        ngram_range=(1, 3),
        stop_words=_get_stop_words(original),
        max_df=0.7,
        min_df=1
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(documents)
    except ValueError:
        # All terms were filtered (e.g., only stop words). Return safe zero scores.
        return [
            {
                "url": source.get("url", ""),
                "title": source.get("title", ""),
                "similarity": 0.0,
            }
            for source in sources
        ]
    similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

    results = []
    for i, source in enumerate(sources):
        results.append({
            "url": source.get("url", ""),
            "title": source.get("title", ""),
            "similarity": round(float(similarities[i]) * 100, 2)
        })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results
