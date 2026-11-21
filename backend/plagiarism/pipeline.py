"""Análisis de plagio en varias pasadas y con varios proveedores.

Pasada 1 - Búsqueda amplia: frases repartidas por todo el documento en varios
           buscadores web (cada consulta en al menos ENGINES_PER_QUERY motores),
           más búsquedas por palabras clave en OpenAlex, Crossref y Wikipedia.
Pasada 2 - Reintento: las consultas web que fallaron se repiten con espera y
           con los motores que siguen respondiendo.
Pasada 3 - Búsqueda dirigida: las oraciones que aún no tienen fuente se buscan
           como frase exacta y por palabras clave en las fuentes académicas.
Pasada 4 - Verificación: reintento de descargas fallidas, fuentes recordadas de
           revisiones anteriores y (opcional) repositorio de documentos previos.

Consistencia: caché de búsquedas y páginas, memoria de fuentes por texto y
orden determinista (nunca depende de qué respuesta de red llega primero).
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from urllib.parse import urlsplit

from config import (
    BRAVE_API_KEY,
    ENABLE_CROSSREF,
    ENABLE_OPENALEX,
    ENABLE_REPOSITORY,
    ENABLE_WIKIPEDIA,
    ENGINE_MAX_CONSECUTIVE_FAILS,
    ENGINES_PER_QUERY,
    ANALYSIS_TIME_BUDGET,
    EXCLUDE_BIBLIOGRAPHY,
    FETCH_CALL_TIMEOUT,
    FETCH_CONCURRENCY,
    FETCH_ROUND_TIMEOUT,
    GOOGLE_API_KEY,
    GOOGLE_CSE_ID,
    MAX_API_QUERIES,
    MAX_QUERIES_PASS1,
    MAX_QUERIES_PASS3,
    MAX_RESULTS_PER_QUERY,
    MAX_SOURCES_TO_CHECK,
    REPOSITORY_MAX_DOCS,
    SEARCH_CALL_TIMEOUT,
    SEARCH_CONCURRENCY,
    SEARCH_ROUND_TIMEOUT,
    SEARCH_DELAY,
    SEARCH_WEB_ENGINES,
    SOURCE_FLAG_COVERAGE,
)
from plagiarism import cache
from plagiarism.alignment import PreparedDocument, SourceMatch, compare, prepare_document
from plagiarism.search import (
    fetch_page_text,
    normalize_url,
    search_brave_api,
    search_crossref,
    search_google_cse,
    search_openalex,
    search_web_engine,
    search_wikipedia,
)
from plagiarism.text_utils import (
    STOP_WORDS,
    count_evasion_marks,
    is_content_word,
    strip_bibliography,
    text_fingerprint,
)

logger = logging.getLogger(__name__)

ProgressFn = Callable[..., Awaitable[None]]

_ACADEMIC_PROVIDERS = {"openalex", "openalex_oa", "crossref"}
_ACADEMIC_HOST_HINTS = (
    ".edu", "scielo", "redalyc", "dialnet", "researchgate", "academia.edu", "repositorio", "repository",
    "handle.net", "doi.org", "springer", "sciencedirect", "elsevier", "core.ac.uk", "arxiv", "semanticscholar",
    "revistas", "journal", "ojs", "tesis", "thesis", "alicia.concytec", "renati", "redib", "latindex",
)
SOURCE_TYPE_LABELS = {"web": "Internet", "academico": "Publicaciones académicas", "wikipedia": "Wikipedia",
                      "repositorio": "Documentos previos"}


@dataclass
class Candidate:
    url: str
    title: str = ""
    snippet: str = ""
    hits: int = 0
    providers: set[str] = field(default_factory=set)
    provided_content: str = ""  # texto entregado por una API (resumen, artículo)
    content: str | None = None  # texto descargado; None = no descargado o fallo
    fetch_failed: bool = False

    @property
    def source_type(self) -> str:
        if self.url.startswith("repositorio:"):
            return "repositorio"
        host = urlsplit(self.url).netloc
        if host.endswith("wikipedia.org") or "wikipedia" in self.providers:
            return "wikipedia"
        if self.providers & _ACADEMIC_PROVIDERS or any(h in self.url.lower() for h in _ACADEMIC_HOST_HINTS):
            return "academico"
        return "web"

    @property
    def needs_fetch(self) -> bool:
        return not self.provided_content or "openalex_oa" in self.providers


@dataclass
class PlagiarismReport:
    sources: list[dict]
    stats: dict
    sources_checked: int
    passes: list[dict] = field(default_factory=list)


async def _noop(*_args, **_kwargs) -> None:
    return None


def _stable_rank(value: str) -> int:
    return int(hashlib.sha1(value.encode("utf-8")).hexdigest()[:8], 16)


# --------------------------------------------------------------------------- consultas

def _spread_pick(indices: list[int], k: int, score) -> list[int]:
    """Elige k elementos repartidos por todo el documento (el mejor de cada tramo)."""
    if k <= 0:
        return []
    if len(indices) <= k:
        return list(indices)
    picked = []
    total = len(indices)
    for j in range(k):
        bucket = indices[(j * total) // k:((j + 1) * total) // k]
        if bucket:
            picked.append(max(bucket, key=lambda i: (score(i), -i)))
    return picked


def _detect_language(doc: PreparedDocument) -> str:
    es = sum(1 for w in doc.tokens.words if w in ("de", "la", "que", "el", "los", "las", "del", "por", "para", "una", "con"))
    en = sum(1 for w in doc.tokens.words if w in ("the", "of", "and", "to", "is", "that", "for", "with", "are", "this"))
    return "en" if en > es else "es"


class _Analysis:
    def __init__(self, text: str, progress: ProgressFn, analysis_id: str | None):
        self.progress = progress
        self.analysis_id = analysis_id
        body, self.bibliography_excluded = strip_bibliography(text) if EXCLUDE_BIBLIOGRAPHY else (text, False)
        self.doc = prepare_document(body)
        self.text_hash = text_fingerprint(body)
        self.evasion = count_evasion_marks(body)
        self.lang = _detect_language(self.doc)
        self.region = "us-en" if self.lang == "en" else "es-es"
        self.candidates: dict[str, Candidate] = {}
        self.matches: dict[str, SourceMatch] = {}
        self.queried: set[str] = set()
        self.passes: list[dict] = []
        self.web_sem = asyncio.Semaphore(max(1, SEARCH_CONCURRENCY))
        self.api_sem = asyncio.Semaphore(4)
        # Límite por API para no provocar bloqueos por exceso de peticiones (429).
        self.provider_sems = {"openalex": asyncio.Semaphore(1), "crossref": asyncio.Semaphore(2),
                              "wikipedia": asyncio.Semaphore(2)}
        self.fetch_sem = asyncio.Semaphore(max(1, FETCH_CONCURRENCY))
        self.engine_stats: dict[str, dict[str, int]] = {e: {"ok": 0, "fail": 0, "streak": 0} for e in SEARCH_WEB_ENGINES}
        self.api_stats: dict[str, dict[str, int]] = {}
        self.web_queries_total = 0
        self.web_queries_ok = 0
        # Comparar textos usa CPU: se limita para no saturar servidores pequeños.
        self.compare_sem = asyncio.Semaphore(2)
        self.query_origin: dict[str, int] = {}
        self.current_pass = 0
        self.pct = 10
        self.deadline = time.monotonic() + ANALYSIS_TIME_BUDGET

    # ------------------------------------------------------------- utilidades
    def _sentence_ok(self, i: int) -> bool:
        s = self.doc.sentences[i]
        return s.end_token - s.start_token >= 10 and len(self.doc.sentence_stems[i]) >= 5

    def _broad_query(self, idx: int) -> str:
        s = self.doc.sentences[idx]
        end = min(s.end_token, s.start_token + 22)
        return self.doc.tokens.excerpt(self.doc.text, s.start_token, end, max_chars=220)

    def _exact_query(self, idx: int) -> str:
        s = self.doc.sentences[idx]
        length = s.end_token - s.start_token
        size = min(12, length)
        start = s.start_token + (length - size) // 2
        words = self.doc.tokens.excerpt(self.doc.text, start, start + size, max_chars=200).strip(" ,;:.")
        return f'"{words}"'

    def _keyword_query(self, idx: int) -> str:
        """Palabras con contenido de la oración, en su forma original (para APIs académicas)."""
        s = self.doc.sentences[idx]
        seen: set[str] = set()
        words: list[str] = []
        for t in range(s.start_token, s.end_token):
            norm = self.doc.tokens.words[t]
            if not is_content_word(norm) or norm in seen or norm in STOP_WORDS:
                continue
            seen.add(norm)
            a, b = self.doc.tokens.spans[t]
            words.append(self.doc.text[a:b])
            if len(words) >= 10:
                break
        return " ".join(words)

    def _sentence_coverage(self, idx: int, covered: set[int]) -> float:
        s = self.doc.sentences[idx]
        return sum(1 for p in range(s.start_token, s.end_token) if p in covered) / max(1, s.end_token - s.start_token)

    def _add_results(self, results: list[dict]) -> None:
        for r in results:
            url = normalize_url(r.get("url", ""))
            if not url:
                continue
            cand = self.candidates.get(url)
            if cand is None:
                cand = self.candidates[url] = Candidate(url=url)
            cand.hits += 1
            if r.get("provider"):
                cand.providers.add(r["provider"])
            title = (r.get("title") or "")[:220]
            if title and (not cand.title or title < cand.title):
                cand.title = title
            if len(r.get("snippet") or "") > len(cand.snippet):
                cand.snippet = r["snippet"][:1500]
            if len(r.get("content") or "") > len(cand.provided_content):
                cand.provided_content = r["content"]

    # ------------------------------------------------------------- actividad en vivo
    _ENGINE_NAMES = {"duckduckgo": "DuckDuckGo", "startpage": "Startpage", "google": "Google", "bing": "Bing",
                     "yahoo": "Yahoo", "yandex": "Yandex", "brave": "Brave", "mojeek": "Mojeek"}

    def _register_query(self, query: str, idx: int) -> str:
        """Recuerda qué oración del documento origina cada consulta (para mostrarla en vivo)."""
        if query and query not in self.query_origin:
            self.query_origin[query] = idx
        return query

    def _position(self, query: str) -> dict | None:
        idx = self.query_origin.get(query)
        if idx is None:
            return None
        s = self.doc.sentences[idx]
        start = self.doc.tokens.spans[s.start_token][0]
        end = self.doc.tokens.spans[s.end_token - 1][1]
        return {
            "start": start,
            "end": end,
            "percent": round(start * 100 / max(1, len(self.doc.text)), 1),
            "sentence": idx + 1,
            "sentences": len(self.doc.sentences),
            "text": self.doc.tokens.excerpt(self.doc.text, s.start_token, s.end_token, max_chars=260),
        }

    async def _activity(self, message: str, **activity) -> None:
        activity.setdefault("pass", self.current_pass)
        activity["found_sources"] = sum(1 for m in self.matches.values() if m.covered_words)
        await self.progress(self.pct, message, activity)

    def _remaining(self, cap: float) -> float:
        return max(1.0, min(cap, self.deadline - time.monotonic()))

    async def _gather_with_deadline(self, tasks: list[asyncio.Task], timeout: float, on_done) -> int:
        """Espera las tareas hasta `timeout` s; cancela las que no terminaron. Devuelve cuántas se cancelaron."""
        pending = set(tasks)
        end = time.monotonic() + timeout
        done_count = 0
        while pending:
            remaining = end - time.monotonic()
            if remaining <= 0:
                break
            finished, pending = await asyncio.wait(pending, timeout=min(remaining, 3.0),
                                                   return_when=asyncio.FIRST_COMPLETED)
            done_count += len(finished)
            await on_done(done_count, len(tasks))
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        return len(pending)

    # ------------------------------------------------------------- búsqueda web
    def _engine_order(self, query: str) -> list[str]:
        alive = [e for e in SEARCH_WEB_ENGINES if self.engine_stats[e]["streak"] < ENGINE_MAX_CONSECUTIVE_FAILS]
        if not alive:
            return []
        shift = _stable_rank(query) % len(alive)
        return alive[shift:] + alive[:shift]

    async def _web_query(self, query: str, strict_empty: bool) -> tuple[bool, list[dict]]:
        """Busca en varios motores hasta obtener resultados de ENGINES_PER_QUERY de ellos."""
        collected: list[dict] = []
        engines_with_results = 0
        attempts = 0
        any_response = False
        position = self._position(query)
        for engine in self._engine_order(query):
            if engines_with_results >= ENGINES_PER_QUERY or attempts >= ENGINES_PER_QUERY + 3:
                break
            if self.engine_stats[engine]["streak"] >= ENGINE_MAX_CONSECUTIVE_FAILS:
                continue
            attempts += 1
            async with self.web_sem:
                await self._activity(
                    f"Buscando en {self._ENGINE_NAMES.get(engine, engine)}...",
                    stage="search", provider=engine, fragment=query, position=position,
                    log=f"Buscando en {self._ENGINE_NAMES.get(engine, engine)}: «{query[:70]}…»",
                )
                try:
                    res = await asyncio.wait_for(
                        search_web_engine(query, engine, MAX_RESULTS_PER_QUERY, self.region), SEARCH_CALL_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    res = None
                await asyncio.sleep(SEARCH_DELAY)
            stats = self.engine_stats[engine]
            if res:
                stats["ok"] += 1
                stats["streak"] = 0
                engines_with_results += 1
                any_response = True
                collected.extend(res)
            elif res is None or strict_empty:
                stats["fail"] += 1
                stats["streak"] += 1
                if stats["streak"] == ENGINE_MAX_CONSECUTIVE_FAILS:
                    await self._activity(f"{self._ENGINE_NAMES.get(engine, engine)} no responde; se omite.", stage="search",
                                         provider=engine, log=f"{self._ENGINE_NAMES.get(engine, engine)} no responde: se deja de usar")
            else:
                any_response = True

        for name, factory in (
            ("Brave API", (lambda: search_brave_api(query, MAX_RESULTS_PER_QUERY, self.lang)) if BRAVE_API_KEY else None),
            ("Google CSE", (lambda: search_google_cse(query, MAX_RESULTS_PER_QUERY)) if GOOGLE_API_KEY and GOOGLE_CSE_ID else None),
        ):
            if factory is None:
                continue
            async with self.api_sem:
                try:
                    res = await asyncio.wait_for(factory(), SEARCH_CALL_TIMEOUT)
                except asyncio.TimeoutError:
                    res = None
            if res:
                collected.extend(res)
                any_response = True
        return any_response, collected

    async def _api_query(self, name: str, query: str, factory) -> list[dict]:
        label = {"openalex": "OpenAlex", "crossref": "Crossref", "wikipedia": "Wikipedia"}.get(name, name)
        async with self.provider_sems.get(name, self.api_sem):
            await self._activity(
                f"Consultando {label}...",
                stage="search", provider=name, fragment=query, position=self._position(query),
                log=f"Consultando {label}: {query[:70]}",
            )
            try:
                res = await asyncio.wait_for(factory(), SEARCH_CALL_TIMEOUT)
            except asyncio.TimeoutError:
                res = None
            if name == "openalex":
                await asyncio.sleep(0.25)
        stats = self.api_stats.setdefault(name, {"ok": 0, "fail": 0})
        if res is None:
            stats["fail"] += 1
            return []
        stats["ok"] += 1
        return res

    async def _search_round(
        self,
        web_queries: list[str],
        api_queries: list[str],
        lo: int,
        hi: int,
        label: str,
        strict_empty: bool,
    ) -> list[str]:
        """Ejecuta una ronda de búsquedas con tiempo máximo; devuelve las consultas web fallidas.

        Los resultados se incorporan en el orden de las consultas, no en el de llegada.
        """
        jobs: list[tuple[str, str, asyncio.Task]] = []
        for q in web_queries:
            jobs.append(("web", q, asyncio.create_task(self._web_query(q, strict_empty))))
        for q in api_queries:
            if ENABLE_OPENALEX:
                jobs.append(("api", q, asyncio.create_task(self._api_query("openalex", q, lambda q=q: search_openalex(q)))))
            if ENABLE_CROSSREF:
                jobs.append(("api", q, asyncio.create_task(self._api_query("crossref", q, lambda q=q: search_crossref(q)))))
            if ENABLE_WIKIPEDIA:
                jobs.append(("api", q, asyncio.create_task(
                    self._api_query("wikipedia", q, lambda q=q: search_wikipedia(q, self.lang)))))

        async def on_done(done: int, total: int) -> None:
            self.pct = lo + (hi - lo) * done // max(1, total)
            await self.progress(self.pct, f"{label}: {done}/{total} búsquedas completadas")

        cancelled = await self._gather_with_deadline([t for _, _, t in jobs], self._remaining(SEARCH_ROUND_TIMEOUT), on_done)
        if cancelled:
            await self._activity(f"{label}: {cancelled} búsquedas tardaron demasiado y se omitieron.", stage="search",
                                 log=f"{cancelled} búsquedas superaron el tiempo máximo")

        failed: list[str] = []
        for kind, q, task in jobs:
            ok_task = task.done() and not task.cancelled() and task.exception() is None
            result = task.result() if ok_task else None
            if kind == "web":
                self.queried.add(q)
                self.web_queries_total += 1
                ok, items = result if result else (False, [])
                if ok:
                    self.web_queries_ok += 1
                else:
                    failed.append(q)
                self._add_results(items)
            elif result:
                self._add_results(result)
        return failed

    # ------------------------------------------------------------- descarga y comparación
    async def _fetch_and_compare(self, urls: list[str], lo: int, hi: int, label: str) -> None:
        """Descarga cada fuente y la compara con el documento (en un hilo aparte para no bloquear)."""
        total = len(urls)
        counter = {"n": 0}

        async def one(url: str) -> None:
            cand = self.candidates[url]
            text: str | None = None
            if cand.needs_fetch:
                async with self.fetch_sem:
                    counter["n"] += 1
                    await self._activity(
                        f"{label}: descargando fuente {counter['n']}/{total}",
                        stage="fetch", url=url, title=cand.title or url, done=counter["n"], total=total,
                        log=f"Descargando: {cand.title or url}"[:120],
                    )
                    try:
                        text = await asyncio.wait_for(fetch_page_text(url), FETCH_CALL_TIMEOUT)
                    except (asyncio.TimeoutError, Exception):
                        text = None
            cand.content = text
            cand.fetch_failed = cand.needs_fetch and text is None
            source_text = self._source_text(cand)
            if not source_text:
                self.matches.pop(url, None)
                return
            async with self.compare_sem:
                match = await asyncio.to_thread(compare, self.doc, url, cand.title or url, source_text)
            self.matches[url] = match
            if match.covered_words:
                share = round(len(match.covered_words) * 100 / max(1, len(self.doc.tokens)), 1)
                await self._activity(
                    f"Coincidencia encontrada en {cand.title or url}",
                    stage="match", url=url, title=cand.title or url, similarity=share,
                    log=f"Coincidencia de {share}% con: {cand.title or url}"[:140],
                )

        async def on_done(done: int, total_: int) -> None:
            self.pct = lo + (hi - lo) * done // max(1, total_)
            await self.progress(self.pct, f"{label}: {done}/{total_} fuentes verificadas")

        tasks = [asyncio.create_task(one(u)) for u in urls]
        cancelled = await self._gather_with_deadline(tasks, self._remaining(FETCH_ROUND_TIMEOUT), on_done)
        if cancelled:
            # Las fuentes que no alcanzaron a verificarse se comparan con el fragmento del buscador.
            for url, task in zip(urls, tasks):
                if task.cancelled() and url not in self.matches:
                    cand = self.candidates[url]
                    cand.fetch_failed = True
                    if cand.snippet or cand.provided_content:
                        self.matches[url] = await asyncio.to_thread(
                            compare, self.doc, url, cand.title or url, self._source_text(cand))
            await self._activity(f"{label}: {cancelled} fuentes tardaron demasiado; se usó su fragmento.",
                                 stage="fetch", log=f"{cancelled} fuentes superaron el tiempo máximo")

    def _source_text(self, cand: Candidate) -> str:
        page = cand.content or ""
        parts = [page] if len(page) >= 400 else [page, cand.provided_content or cand.snippet]
        if cand.provided_content and cand.provided_content not in parts:
            parts.append(cand.provided_content)
        return "\n".join(p for p in parts if p).strip()

    def _covered(self) -> set[int]:
        covered: set[int] = set()
        for m in self.matches.values():
            covered |= m.covered_words
        return covered

    def _to_fetch(self) -> list[str]:
        ordered = sorted(self.candidates.values(), key=lambda c: (-c.hits, c.url))
        selected = [c.url for c in ordered[:MAX_SOURCES_TO_CHECK]]
        # Las fuentes con texto entregado por una API no cuestan descargas: entran todas.
        selected += [c.url for c in ordered[MAX_SOURCES_TO_CHECK:] if not c.needs_fetch]
        return [u for u in selected if u not in self.matches]

    # ------------------------------------------------------------- repositorio interno
    async def _compare_repository(self) -> int:
        try:
            from models.database import Analysis, SessionLocal
            with SessionLocal() as db:
                query = db.query(Analysis.id, Analysis.title, Analysis.original_text, Analysis.created_at).filter(
                    Analysis.status == "completed"
                )
                if self.analysis_id:
                    query = query.filter(Analysis.id != self.analysis_id)
                rows = query.order_by(Analysis.created_at.desc()).limit(REPOSITORY_MAX_DOCS).all()
        except Exception as exc:
            logger.warning("repository query failed: %s", exc)
            return 0
        checked = 0
        for row_id, title, text, created in rows:
            if time.monotonic() > self.deadline:
                break
            if not text or text_fingerprint(strip_bibliography(text)[0]) == self.text_hash:
                continue  # el mismo documento analizado antes no es plagio de sí mismo
            checked += 1
            url = f"repositorio:{row_id}"
            date = created.strftime("%d/%m/%Y") if created else ""
            cand = self.candidates.setdefault(url, Candidate(url=url))
            cand.title = f"Documento analizado previamente: {title or 'sin título'} {date}".strip()
            cand.provided_content = text
            cand.providers.add("repositorio")
            await self._activity(f"Comparando con documentos previos ({checked})", stage="repository",
                                 title=cand.title, log=f"Repositorio: {cand.title}"[:120])
            self.matches[url] = await asyncio.to_thread(compare, self.doc, url, cand.title, text)
        return checked

    # ------------------------------------------------------------- pasadas
    async def run(self) -> PlagiarismReport:
        doc = self.doc
        searchable = [i for i in range(len(doc.sentences)) if self._sentence_ok(i)]
        score = lambda i: len(doc.sentence_stems[i])  # noqa: E731

        remembered = cache.get_remembered_sources(self.text_hash)
        self._add_results(remembered)

        # Pasada 1
        self.current_pass, self.pct = 1, 10
        await self._activity("Pasada 1/4: búsqueda en buscadores web y bases académicas...", stage="pass",
                             log=f"Pasada 1: {len(searchable)} oraciones del documento se pueden investigar")
        web_q = list(dict.fromkeys(
            self._register_query(self._broad_query(i), i) for i in _spread_pick(searchable, MAX_QUERIES_PASS1, score)))
        api_picks = _spread_pick(searchable, MAX_API_QUERIES, score)
        api_q = list(dict.fromkeys(q for q in (self._register_query(self._keyword_query(i), i) for i in api_picks) if q))
        failed = await self._search_round(web_q, api_q, 10, 28, "Pasada 1/4", strict_empty=True)
        self.passes.append({"pass": 1, "web_queries": len(web_q), "api_queries": len(api_q), "failed": len(failed)})

        # Pasada 2
        self.current_pass, self.pct = 2, 28
        retried = len(failed)
        for attempt in range(1, 3):
            if not failed or self.deadline - time.monotonic() < 30:
                break
            if not self._engine_order(failed[0]):
                for st in self.engine_stats.values():  # todos caídos: se les da otra oportunidad
                    st["streak"] = 0
            await self._activity(f"Pasada 2/4: reintentando {len(failed)} búsquedas (intento {attempt})...",
                                 stage="pass", log=f"Pasada 2: reintento {attempt} de {len(failed)} búsquedas")
            await asyncio.sleep(2.0 * attempt)
            self.web_queries_total -= len(failed)  # el reintento reemplaza al intento original en las métricas
            failed = await self._search_round(failed, [], 28, 33, "Pasada 2/4", strict_empty=False)
        self.passes.append({"pass": 2, "retried": retried, "still_failed": len(failed)})

        to_fetch = self._to_fetch()
        self.pct = 33
        await self._activity(f"Verificando {len(to_fetch)} fuentes candidatas...", stage="pass",
                             log=f"Verificando {len(to_fetch)} fuentes candidatas")
        await self._fetch_and_compare(to_fetch, 33, 50, "Verificando fuentes")

        # Pasada 3: oraciones aún sin fuente.
        self.current_pass, self.pct = 3, 50
        web_q, api_q3 = [], []
        before = len(self.candidates)
        if self.deadline - time.monotonic() > 30:
            covered = self._covered()
            uncovered = [i for i in searchable if self._sentence_coverage(i, covered) < 0.3]
            picks = _spread_pick(uncovered, MAX_QUERIES_PASS3, score)
            web_q = [q for q in dict.fromkeys(self._register_query(self._exact_query(i), i) for i in picks)
                     if q not in self.queried]
            api_q3 = [q for q in dict.fromkeys(self._register_query(self._keyword_query(i), i)
                                               for i in picks[: max(0, MAX_API_QUERIES // 2)]) if q and q not in api_q]
            if web_q or api_q3:
                await self._activity("Pasada 3/4: búsqueda dirigida de frases exactas...", stage="pass",
                                     log=f"Pasada 3: {len(uncovered)} oraciones aún sin fuente")
                await self._search_round(web_q, api_q3, 50, 58, "Pasada 3/4", strict_empty=False)
                await self._fetch_and_compare(self._to_fetch(), 58, 64, "Verificando nuevas fuentes")
        else:
            await self._activity("Tiempo máximo alcanzado: se omite la pasada 3.", stage="pass",
                                 log="Pasada 3 omitida por tiempo")
        self.passes.append({"pass": 3, "web_queries": len(web_q), "api_queries": len(api_q3),
                            "new_sources": len(self.candidates) - before})

        # Pasada 4: verificación.
        self.current_pass, self.pct = 4, 64
        await self._activity("Pasada 4/4: verificación final de fuentes...", stage="pass", log="Pasada 4: verificación final")
        retry = sorted(u for u, c in self.candidates.items() if c.fetch_failed)
        if retry and self.deadline - time.monotonic() > 20:
            await asyncio.sleep(1.0)
            await self._fetch_and_compare(retry, 64, 68, "Pasada 4/4")
        repo_checked = await self._compare_repository() if ENABLE_REPOSITORY else 0
        self.passes.append({"pass": 4, "refetched": len(retry), "remembered_sources": len(remembered),
                            "repository_docs": repo_checked})
        self.pct = 70
        await self._activity("Calculando similitud global...", stage="scoring", log="Calculando similitud global")
        return self._report()

    # ------------------------------------------------------------- resultado
    def _reliability(self) -> tuple[str, str]:
        api_ok = sum(s["ok"] for s in self.api_stats.values())
        if self.web_queries_total == 0:
            ratio = 0.0
        else:
            ratio = self.web_queries_ok / self.web_queries_total
        if ratio >= 0.7:
            return "alta", "Los buscadores respondieron a la mayoría de las consultas."
        if ratio >= 0.35:
            return "media", "Algunos buscadores no respondieron; podrían faltar fuentes."
        if api_ok:
            return "baja", ("Los buscadores web no respondieron; solo se revisaron bases académicas y Wikipedia. "
                            "El porcentaje puede estar subestimado.")
        return "baja", "No se pudo consultar ninguna fuente externa. El porcentaje no es confiable."

    def _report(self) -> PlagiarismReport:
        total = max(1, len(self.doc.tokens))
        pct = lambda n: round(n * 100 / total, 2)  # noqa: E731
        ranked = sorted(
            (m for m in self.matches.values() if m.covered_words or m.quoted_words),
            key=lambda m: (-len(m.covered_words), -m.longest_run, -len(m.quoted_words), m.url),
        )

        # Atribución principal: cada palabra se asigna a la fuente mejor clasificada que la cubre,
        # así el desglose por tipo de fuente suma exactamente la similitud global.
        attributed: set[int] = set()
        by_type: dict[str, int] = {}
        sources: list[dict] = []
        exact_all: set[int] = set()
        para_all: set[int] = set()
        quoted_all: set[int] = set()
        for m in ranked:
            cand = self.candidates.get(m.url)
            stype = cand.source_type if cand else "web"
            own = m.covered_words - attributed
            attributed |= m.covered_words
            by_type[stype] = by_type.get(stype, 0) + len(own)
            exact_all |= m.exact_words
            para_all |= m.paraphrase_words
            quoted_all |= m.quoted_words
            sources.append({
                "url": m.url,
                "title": m.title,
                "similarity": pct(len(m.covered_words)),
                "snippet": cand.snippet if cand else "",
                "matching_segments": m.segments,
                "exact_similarity": pct(len(m.exact_words)),
                "paraphrase_similarity": pct(len(m.paraphrase_words)),
                "quoted_similarity": pct(len(m.quoted_words)),
                "exclusive_similarity": pct(len(own)),
                "matched_words": len(m.covered_words),
                "longest_match_words": m.longest_run,
                "source_word_count": m.source_word_count,
                "source_type": stype,
                "providers": sorted(cand.providers) if cand else [],
                "verified_full_text": bool(cand and (len(cand.content or "") >= 400 or len(cand.provided_content) >= 400)),
            })

        cache.remember_sources(
            self.text_hash,
            [{"url": s["url"], "title": s["title"], "snippet": s["snippet"]} for s in sources if not s["url"].startswith("repositorio:")],
        )

        para_all -= exact_all
        quoted_all -= exact_all | para_all
        flagged = [s for s in sources if s["similarity"] >= SOURCE_FLAG_COVERAGE]
        overall = pct(len(exact_all | para_all))
        reliability, reliability_note = self._reliability()
        stats = {
            "overall_similarity": overall,
            "originality": round(100 - overall, 2),
            "exact_similarity": pct(len(exact_all)),
            "paraphrase_similarity": pct(len(para_all)),
            "quoted_similarity": pct(len(quoted_all)),
            "similarity_by_type": {
                t: {"label": SOURCE_TYPE_LABELS[t], "similarity": pct(n)}
                for t, n in sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0])) if n
            },
            "max_similarity": sources[0]["similarity"] if sources else 0,
            "avg_similarity": round(sum(s["similarity"] for s in flagged) / len(flagged), 2) if flagged else 0,
            "total_sources": len([s for s in sources if s["matched_words"]]),
            "sources_above_threshold": len(flagged),
            "unique_sources": len(sources),
            "words_compared": len(self.doc.tokens),
            "bibliography_excluded": self.bibliography_excluded,
            "evasion": self.evasion,
            "reliability": reliability,
            "reliability_note": reliability_note,
            "search_health": {
                "web_queries": self.web_queries_total,
                "web_queries_ok": self.web_queries_ok,
                "engines": {e: {"ok": s["ok"], "fail": s["fail"]} for e, s in self.engine_stats.items()},
                "apis": self.api_stats,
                "candidates": len(self.candidates),
            },
            "search_passes": self.passes,
            "text_hash": self.text_hash,
        }
        return PlagiarismReport(sources=sources, stats=stats, sources_checked=len(self.matches), passes=self.passes)


async def run_plagiarism_check(
    text: str,
    progress: ProgressFn | None = None,
    analysis_id: str | None = None,
) -> PlagiarismReport:
    return await _Analysis(text, progress or _noop, analysis_id).run()
