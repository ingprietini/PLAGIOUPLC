import os

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/antiplagio.db")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")
MAX_WORD_LIMIT = 100000
MAX_UPLOAD_SIZE = 50 * 1024 * 1024
CHUNK_SIZE = 500


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


# --- Búsqueda web ---
SEARCH_ENGINE = os.getenv("SEARCH_ENGINE", "duckduckgo")
SEARCH_DELAY = _float("SEARCH_DELAY", 0.6)
SEARCH_CONCURRENCY = _int("SEARCH_CONCURRENCY", 3)
MAX_RESULTS_PER_QUERY = _int("MAX_RESULTS_PER_QUERY", 6)
# Pasada 1: consultas repartidas uniformemente por todo el documento.
MAX_QUERIES_PASS1 = _int("MAX_QUERIES_PASS1", 40)
# Pasada 3: consultas dirigidas a oraciones que aún no tienen fuente.
MAX_QUERIES_PASS3 = _int("MAX_QUERIES_PASS3", 20)
# Motores alternativos de ddgs para reintentar consultas fallidas (pasada 2).
SEARCH_FALLBACK_BACKENDS = [b.strip() for b in os.getenv("SEARCH_FALLBACK_BACKENDS", "bing,brave,mojeek").split(",") if b.strip()]

# --- Descarga de páginas ---
MAX_SOURCES_TO_CHECK = _int("MAX_SOURCES_TO_CHECK", 60)
FETCH_CONCURRENCY = _int("FETCH_CONCURRENCY", 6)
FETCH_TIMEOUT = _float("FETCH_TIMEOUT", 15.0)
MAX_PAGE_BYTES = _int("MAX_PAGE_BYTES", 6 * 1024 * 1024)
MAX_PAGE_CHARS = _int("MAX_PAGE_CHARS", 150000)

# --- Comparación ---
SHINGLE_SIZE = _int("SHINGLE_SIZE", 5)          # palabras por huella
MIN_MATCH_WORDS = _int("MIN_MATCH_WORDS", 8)     # longitud mínima de un tramo copiado
MATCH_GAP_WORDS = _int("MATCH_GAP_WORDS", 3)     # palabras cambiadas toleradas dentro de un tramo
PARAPHRASE_THRESHOLD = _float("PARAPHRASE_THRESHOLD", 0.72)
# Una fuente "supera el umbral" si cubre al menos este % del documento.
SOURCE_FLAG_COVERAGE = _float("SOURCE_FLAG_COVERAGE", 1.0)
SIMILARITY_THRESHOLD = SOURCE_FLAG_COVERAGE / 100
EXCLUDE_BIBLIOGRAPHY = os.getenv("EXCLUDE_BIBLIOGRAPHY", "true").lower() != "false"

# --- Consistencia ---
# Días que se reutilizan búsquedas y páginas descargadas. Mismo texto => mismo resultado.
CACHE_TTL_DAYS = _int("CACHE_TTL_DAYS", 30)
