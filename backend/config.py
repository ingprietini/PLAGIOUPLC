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
SEARCH_ENGINE = os.getenv("SEARCH_ENGINE", "multi")  # multi | google (API de Google CSE)
SEARCH_DELAY = _float("SEARCH_DELAY", 0.6)
SEARCH_CONCURRENCY = _int("SEARCH_CONCURRENCY", 3)
MAX_RESULTS_PER_QUERY = _int("MAX_RESULTS_PER_QUERY", 6)
# Pasada 1: consultas repartidas uniformemente por todo el documento.
MAX_QUERIES_PASS1 = _int("MAX_QUERIES_PASS1", 40)
# Pasada 3: consultas dirigidas a oraciones que aún no tienen fuente.
MAX_QUERIES_PASS3 = _int("MAX_QUERIES_PASS3", 20)
# Buscadores web consultados uno por uno (en orden rotativo por consulta).
SEARCH_WEB_ENGINES = [b.strip() for b in os.getenv(
    "SEARCH_WEB_ENGINES", "google,yahoo,yandex,duckduckgo,bing,brave,mojeek,startpage"
).split(",") if b.strip()]
ENGINES_PER_QUERY = _int("ENGINES_PER_QUERY", 2)       # buscadores con resultados que se exigen por consulta
ENGINE_MAX_CONSECUTIVE_FAILS = _int("ENGINE_MAX_CONSECUTIVE_FAILS", 4)
# Fuentes académicas y enciclopédicas (APIs abiertas, no bloquean servidores).
ENABLE_OPENALEX = os.getenv("ENABLE_OPENALEX", "true").lower() != "false"
ENABLE_CROSSREF = os.getenv("ENABLE_CROSSREF", "true").lower() != "false"
ENABLE_WIKIPEDIA = os.getenv("ENABLE_WIKIPEDIA", "true").lower() != "false"
# Compara contra documentos analizados antes (copia entre estudiantes). Desactivado por defecto:
# si alguien vuelve a subir una versión editada de su propio trabajo, aparecería como coincidencia.
ENABLE_REPOSITORY = os.getenv("ENABLE_REPOSITORY", "false").lower() == "true"
MAX_API_QUERIES = _int("MAX_API_QUERIES", 15)
API_USER_AGENT = os.getenv("API_USER_AGENT", "AntiPlagioBot/1.0 (+https://www.mediawiki.org/wiki/API:Etiquette)")
# Brave Search API opcional (plan gratuito: https://brave.com/search/api/).
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
# Clave gratuita de OpenAlex (https://openalex.org/settings/api); sin ella limita mucho a servidores compartidos.
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY", "")
REPOSITORY_MAX_DOCS = _int("REPOSITORY_MAX_DOCS", 300)

# --- Descarga de páginas ---
MAX_SOURCES_TO_CHECK = _int("MAX_SOURCES_TO_CHECK", 60)
FETCH_CONCURRENCY = _int("FETCH_CONCURRENCY", 6)
FETCH_TIMEOUT = _float("FETCH_TIMEOUT", 15.0)
MAX_PAGE_BYTES = _int("MAX_PAGE_BYTES", 6 * 1024 * 1024)
MAX_PAGE_CHARS = _int("MAX_PAGE_CHARS", 150000)

# --- Tiempos máximos (evitan que el análisis se quede trabado) ---
SEARCH_CALL_TIMEOUT = _float("SEARCH_CALL_TIMEOUT", 20.0)     # una búsqueda en un motor/API
FETCH_CALL_TIMEOUT = _float("FETCH_CALL_TIMEOUT", 30.0)       # descargar y extraer una página/PDF
SEARCH_ROUND_TIMEOUT = _float("SEARCH_ROUND_TIMEOUT", 180.0)  # una ronda completa de búsquedas
FETCH_ROUND_TIMEOUT = _float("FETCH_ROUND_TIMEOUT", 150.0)    # una ronda completa de verificación
ANALYSIS_TIME_BUDGET = _float("ANALYSIS_TIME_BUDGET", 540.0)  # todo el análisis de plagio
MAX_PDF_PAGES = _int("MAX_PDF_PAGES", 80)

# --- Comparación ---
SHINGLE_SIZE = _int("SHINGLE_SIZE", 5)          # palabras por huella
MIN_MATCH_WORDS = _int("MIN_MATCH_WORDS", 8)     # longitud mínima de un tramo copiado
MATCH_GAP_WORDS = _int("MATCH_GAP_WORDS", 3)     # palabras cambiadas toleradas dentro de un tramo
PARAPHRASE_THRESHOLD = _float("PARAPHRASE_THRESHOLD", 0.72)
# Una fuente "supera el umbral" si cubre al menos este % del documento.
SOURCE_FLAG_COVERAGE = _float("SOURCE_FLAG_COVERAGE", 1.0)
SIMILARITY_THRESHOLD = SOURCE_FLAG_COVERAGE / 100
EXCLUDE_BIBLIOGRAPHY = os.getenv("EXCLUDE_BIBLIOGRAPHY", "true").lower() != "false"
# Las coincidencias dentro de comillas se reportan como "citas" y no suman a la similitud global.
EXCLUDE_QUOTES = os.getenv("EXCLUDE_QUOTES", "true").lower() != "false"

# --- Consistencia ---
# Días que se reutilizan búsquedas y páginas descargadas. Mismo texto => mismo resultado.
CACHE_TTL_DAYS = _int("CACHE_TTL_DAYS", 30)
