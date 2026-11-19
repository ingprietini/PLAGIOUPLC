"""Análisis de plagio en varias pasadas.

Pasada 1 - Búsqueda amplia: una consulta por cada tramo del documento,
           repartidas uniformemente (no solo el principio).
Pasada 2 - Reintento: las consultas que fallaron (bloqueo, timeout) se repiten
           con espera progresiva y motores de búsqueda alternativos.
Pasada 3 - Búsqueda dirigida: las oraciones que todavía no tienen fuente se
           buscan como frase exacta entre comillas.
Pasada 4 - Verificación: se reintentan las descargas fallidas, se vuelven a
           comprobar las fuentes encontradas en revisiones anteriores del mismo
           texto y se recalculan todas las coincidencias.

Consistencia: búsquedas y páginas se guardan en caché, las fuentes con
coincidencias se recuerdan por texto, y todo el orden es determinista
(nunca depende de qué respuesta de red llega primero).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from config import (
    EXCLUDE_BIBLIOGRAPHY,
    FETCH_CONCURRENCY,
    MAX_QUERIES_PASS1,
    MAX_QUERIES_PASS3,
    MAX_RESULTS_PER_QUERY,
    MAX_SOURCES_TO_CHECK,
    SEARCH_CONCURRENCY,
    SEARCH_DELAY,
    SEARCH_FALLBACK_BACKENDS,
    SOURCE_FLAG_COVERAGE,
)
from plagiarism import cache
from plagiarism.alignment import PreparedDocument, SourceMatch, compare, prepare_document
from plagiarism.search import fetch_page_text, normalize_url, search_web
from plagiarism.text_utils import strip_bibliography, text_fingerprint

logger = logging.getLogger(__name__)

ProgressFn = Callable[[int, str], Awaitable[None]]


@dataclass
class Candidate:
    url: str
    title: str = ""
    snippet: str = ""
    hits: int = 0
    content: str | None = None  # None = aún no descargada o descarga fallida
    fetch_failed: bool = False


@dataclass
class PlagiarismReport:
    sources: list[dict]
    stats: dict
    sources_checked: int
    passes: list[dict] = field(default_factory=list)


async def _noop(_: int, __: str) -> None:
    return None


# --------------------------------------------------------------------------- consultas

def _spread_pick(indices: list[int], k: int, score) -> list[int]:
    """Elige k elementos repartidos por todo el documento (el mejor de cada tramo)."""
    if len(indices) <= k:
        return list(indices)
    picked = []
    total = len(indices)
    for j in range(k):
        bucket = indices[(j * total) // k:((j + 1) * total) // k]
        if bucket:
            picked.append(max(bucket, key=lambda i: (score(i), -i)))
    return picked


def _searchable_sentences(doc: PreparedDocument) -> list[int]:
    return [
        i for i, s in enumerate(doc.sentences)
        if s.end_token - s.start_token >= 10 and len(doc.sentence_stems[i]) >= 5
    ]


def _broad_query(doc: PreparedDocument, idx: int) -> str:
    s = doc.sentences[idx]
    end = min(s.end_token, s.start_token + 22)
    return doc.tokens.excerpt(doc.text, s.start_token, end, max_chars=220)


def _exact_query(doc: PreparedDocument, idx: int) -> str:
    s = doc.sentences[idx]
    length = s.end_token - s.start_token
    size = min(12, length)
    start = s.start_token + (length - size) // 2
    words = doc.tokens.excerpt(doc.text, start, start + size, max_chars=200).strip(" ,;:.")
    return f'"{words}"'


# --------------------------------------------------------------------------- análisis

class _Analysis:
    def __init__(self, text: str, progress: ProgressFn):
        self.progress = progress
        body, self.bibliography_excluded = strip_bibliography(text) if EXCLUDE_BIBLIOGRAPHY else (text, False)
        self.doc = prepare_document(body)
        self.text_hash = text_fingerprint(body)
        self.candidates: dict[str, Candidate] = {}
        self.matches: dict[str, SourceMatch] = {}
        self.queried: set[str] = set()
        self.failed_queries: list[str] = []
        self.passes: list[dict] = []
        self.search_sem = asyncio.Semaphore(max(1, SEARCH_CONCURRENCY))
        self.fetch_sem = asyncio.Semaphore(max(1, FETCH_CONCURRENCY))

    # -- búsqueda
    def _add_results(self, results: list[dict]) -> int:
        added = 0
        for r in results:
            url = normalize_url(r.get("url", ""))
            if not url:
                continue
            cand = self.candidates.get(url)
            if cand is None:
                cand = self.candidates[url] = Candidate(url=url)
                added += 1
            cand.hits += 1
            if not cand.title and r.get("title"):
                cand.title = r["title"][:220]
            if len(r.get("snippet") or "") > len(cand.snippet):
                cand.snippet = r["snippet"][:1500]
        return added

    async def _run_queries(self, queries: list[str], backend: str | None, lo: int, hi: int, label: str) -> list[str]:
        """Ejecuta consultas en paralelo limitado; devuelve las que fallaron.

        Los resultados se incorporan en el orden de las consultas, no en el de llegada.
        """
        async def one(q: str):
            async with self.search_sem:
                res = await search_web(q, MAX_RESULTS_PER_QUERY, backend=backend)
                await asyncio.sleep(SEARCH_DELAY)
                return res

        tasks = [asyncio.create_task(one(q)) for q in queries]
        done = 0
        for fut in asyncio.as_completed(tasks):
            try:
                await fut
            except Exception:
                pass
            done += 1
            if done == len(tasks) or done % 5 == 0:
                await self.progress(lo + (hi - lo) * done // max(1, len(tasks)), f"{label}: {done}/{len(tasks)} consultas")

        failed: list[str] = []
        for q, task in zip(queries, tasks):
            result = None if task.exception() else task.result()
            self.queried.add(q)
            if result is None:
                failed.append(q)
            else:
                self._add_results(result)
        return failed

    # -- descarga y comparación
    async def _fetch_and_compare(self, urls: list[str], lo: int, hi: int, label: str) -> None:
        async def one(url: str):
            async with self.fetch_sem:
                return await fetch_page_text(url)

        tasks = [asyncio.create_task(one(u)) for u in urls]
        done = 0
        for fut in asyncio.as_completed(tasks):
            try:
                await fut
            except Exception:
                pass
            done += 1
            if done == len(tasks) or done % 5 == 0:
                await self.progress(lo + (hi - lo) * done // max(1, len(tasks)), f"{label}: {done}/{len(tasks)} páginas")

        for url, task in zip(urls, tasks):
            cand = self.candidates[url]
            text = None if task.exception() else task.result()
            cand.fetch_failed = text is None
            cand.content = text
            self._compare(cand)

    def _compare(self, cand: Candidate) -> None:
        page = cand.content or ""
        # Si la página no se pudo leer (o es casi vacía) se usa al menos el fragmento del buscador.
        source_text = page if len(page) >= 400 else f"{page}\n{cand.snippet}".strip()
        if not source_text:
            self.matches.pop(cand.url, None)
            return
        self.matches[cand.url] = compare(self.doc, cand.url, cand.title or cand.url, source_text)

    def _covered(self) -> set[int]:
        covered: set[int] = set()
        for m in self.matches.values():
            covered |= m.covered_words
        return covered

    def _to_fetch(self) -> list[str]:
        ordered = sorted(self.candidates.values(), key=lambda c: (-c.hits, c.url))
        return [c.url for c in ordered[:MAX_SOURCES_TO_CHECK] if c.url not in self.matches]

    # -- pasadas
    async def run(self) -> PlagiarismReport:
        doc = self.doc
        searchable = _searchable_sentences(doc)

        # Fuentes que ya coincidieron en revisiones anteriores de este mismo texto.
        remembered = cache.get_remembered_sources(self.text_hash)
        for r in remembered:
            self._add_results([r])

        # Pasada 1
        await self.progress(10, "Pasada 1/4: búsqueda amplia en la web...")
        picks = _spread_pick(searchable, MAX_QUERIES_PASS1, lambda i: len(doc.sentence_stems[i]))
        queries = list(dict.fromkeys(_broad_query(doc, i) for i in picks))
        self.failed_queries = await self._run_queries(queries, None, 10, 28, "Pasada 1/4")
        self.passes.append({"pass": 1, "queries": len(queries), "failed": len(self.failed_queries)})

        # Pasada 2
        retried = len(self.failed_queries)
        for attempt, backend in enumerate(SEARCH_FALLBACK_BACKENDS[:3], start=1):
            if not self.failed_queries:
                break
            await self.progress(28, f"Pasada 2/4: reintentando {len(self.failed_queries)} búsquedas ({backend})...")
            await asyncio.sleep(1.5 * attempt)
            self.failed_queries = await self._run_queries(self.failed_queries, backend, 28, 33, "Pasada 2/4")
        self.passes.append({"pass": 2, "retried": retried, "still_failed": len(self.failed_queries)})

        await self.progress(33, f"Descargando {min(len(self.candidates), MAX_SOURCES_TO_CHECK)} fuentes candidatas...")
        await self._fetch_and_compare(self._to_fetch(), 33, 50, "Verificando fuentes")

        # Pasada 3: oraciones aún sin fuente, como frase exacta.
        covered = self._covered()
        uncovered = [
            i for i in searchable
            if sum(1 for p in range(doc.sentences[i].start_token, doc.sentences[i].end_token) if p in covered)
            / (doc.sentences[i].end_token - doc.sentences[i].start_token) < 0.3
        ]
        picks = _spread_pick(uncovered, MAX_QUERIES_PASS3, lambda i: len(doc.sentence_stems[i]))
        queries = [q for q in dict.fromkeys(_exact_query(doc, i) for i in picks) if q not in self.queried]
        before = len(self.candidates)
        if queries:
            await self.progress(50, "Pasada 3/4: búsqueda dirigida de frases exactas...")
            failed = await self._run_queries(queries, None, 50, 58, "Pasada 3/4")
            if failed and SEARCH_FALLBACK_BACKENDS:
                failed = await self._run_queries(failed, SEARCH_FALLBACK_BACKENDS[0], 58, 60, "Pasada 3/4 (reintento)")
            await self._fetch_and_compare(self._to_fetch(), 60, 64, "Verificando nuevas fuentes")
        self.passes.append({"pass": 3, "queries": len(queries), "new_sources": len(self.candidates) - before})

        # Pasada 4: verificación.
        await self.progress(64, "Pasada 4/4: verificación final de fuentes...")
        retry = sorted(u for u, c in self.candidates.items() if c.fetch_failed)
        if retry:
            await asyncio.sleep(1.0)
            await self._fetch_and_compare(retry, 64, 70, "Pasada 4/4")
        self.passes.append({"pass": 4, "refetched": len(retry), "remembered_sources": len(remembered)})

        return self._report()

    def _report(self) -> PlagiarismReport:
        total = max(1, len(self.doc.tokens))
        ranked = sorted(
            (m for m in self.matches.values() if m.covered_words),
            key=lambda m: (-len(m.covered_words), -m.longest_run, m.url),
        )

        sources: list[dict] = []
        for m in ranked:
            cand = self.candidates.get(m.url)
            coverage = round(len(m.covered_words) * 100 / total, 2)
            sources.append({
                "url": m.url,
                "title": m.title,
                "similarity": coverage,
                "snippet": cand.snippet if cand else "",
                "matching_segments": m.segments,
                "exact_similarity": round(len(m.exact_words) * 100 / total, 2),
                "paraphrase_similarity": round(len(m.paraphrase_words) * 100 / total, 2),
                "matched_words": len(m.covered_words),
                "longest_match_words": m.longest_run,
                "source_word_count": m.source_word_count,
                "verified_full_text": bool(cand and cand.content and len(cand.content) >= 400),
            })

        cache.remember_sources(self.text_hash, [{"url": s["url"], "title": s["title"], "snippet": s["snippet"]} for s in sources])

        exact_all: set[int] = set()
        para_all: set[int] = set()
        for m in ranked:
            exact_all |= m.exact_words
            para_all |= m.paraphrase_words
        para_all -= exact_all

        flagged = [s for s in sources if s["similarity"] >= SOURCE_FLAG_COVERAGE]
        stats = {
            "overall_similarity": round(len(exact_all | para_all) * 100 / total, 2),
            "exact_similarity": round(len(exact_all) * 100 / total, 2),
            "paraphrase_similarity": round(len(para_all) * 100 / total, 2),
            "max_similarity": sources[0]["similarity"] if sources else 0,
            "avg_similarity": round(sum(s["similarity"] for s in flagged) / len(flagged), 2) if flagged else 0,
            "total_sources": len(sources),
            "sources_above_threshold": len(flagged),
            "unique_sources": len(sources),
            "words_compared": len(self.doc.tokens),
            "bibliography_excluded": self.bibliography_excluded,
            "search_passes": self.passes,
            "text_hash": self.text_hash,
        }
        return PlagiarismReport(
            sources=sources,
            stats=stats,
            sources_checked=len(self.matches),
            passes=self.passes,
        )


async def run_plagiarism_check(text: str, progress: ProgressFn | None = None) -> PlagiarismReport:
    return await _Analysis(text, progress or _noop).run()
