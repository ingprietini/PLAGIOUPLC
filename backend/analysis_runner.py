"""Ejecución de análisis en segundo plano con estado en vivo.

El análisis ya no vive dentro del WebSocket: si la conexión se corta (Render
cierra conexiones, el usuario cambia de pestaña, la red falla) el análisis
continúa, y el navegador puede reconectarse o consultar el progreso por HTTP.

LIVE[analysis_id] guarda en memoria el estado actual (porcentaje, etapa, el
fragmento del documento que se está buscando, la fuente que se está
verificando y un registro de las últimas actividades).
"""

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime

from models.database import Analysis, SessionLocal, Source, Suggestion

logger = logging.getLogger(__name__)

LIVE: dict[str, dict] = {}
TASKS: dict[str, asyncio.Task] = {}
_LOG_SIZE = 12


def _state(analysis_id: str) -> dict:
    state = LIVE.get(analysis_id)
    if state is None:
        state = LIVE[analysis_id] = {
            "status": "processing",
            "progress": 0,
            "message": "Iniciando análisis...",
            "stage": "start",
            "activity": None,
            "log": deque(maxlen=_LOG_SIZE),
            "found_sources": 0,
            "started_at": time.time(),
            "updated_at": time.time(),
            "version": 0,
            "error": None,
            "stats": None,
        }
    return state


def snapshot(analysis_id: str) -> dict | None:
    state = LIVE.get(analysis_id)
    if state is None:
        return None
    now = time.time()
    return {
        "status": state["status"],
        "progress": state["progress"],
        "message": state["message"],
        "stage": state["stage"],
        "activity": state["activity"],
        "log": list(state["log"]),
        "found_sources": state["found_sources"],
        "elapsed_seconds": int(now - state["started_at"]),
        "seconds_since_update": int(now - state["updated_at"]),
        "version": state["version"],
        "error": state["error"],
    }


async def emit(analysis_id: str, progress: int, message: str, activity: dict | None = None) -> None:
    """Actualiza el estado en vivo. Nunca bloquea ni falla."""
    state = _state(analysis_id)
    state["progress"] = max(state["progress"], int(progress))
    state["message"] = message
    if activity:
        state["activity"] = activity
        state["stage"] = activity.get("stage", state["stage"])
        if activity.get("found_sources") is not None:
            state["found_sources"] = activity["found_sources"]
        label = activity.get("log")
        if label:
            state["log"].append({"t": int(time.time() - state["started_at"]), "text": label})
    state["updated_at"] = time.time()
    state["version"] += 1


def is_running(analysis_id: str) -> bool:
    task = TASKS.get(analysis_id)
    return task is not None and not task.done()


def ensure_started(analysis_id: str) -> None:
    """Lanza el análisis si no está corriendo (idempotente)."""
    if is_running(analysis_id):
        return
    state = LIVE.get(analysis_id)
    if state and state["status"] in ("completed", "failed"):
        return
    _state(analysis_id)
    TASKS[analysis_id] = asyncio.create_task(_run(analysis_id))


def _set_db_status(analysis_id: str, **fields) -> None:
    try:
        with SessionLocal() as db:
            analysis = db.get(Analysis, analysis_id)
            if analysis:
                for k, v in fields.items():
                    setattr(analysis, k, v)
                db.commit()
    except Exception as exc:
        logger.warning("could not update analysis status: %s", exc)


async def _run(analysis_id: str) -> None:
    # Importes diferidos: evitan ciclos y cargan módulos pesados solo cuando hace falta.
    from ai_detector.detector import detect_ai_text
    from nlp.readability import analyze_readability
    from nlp.suggestions import get_improvement_suggestions
    from plagiarism.pipeline import run_plagiarism_check
    from plagiarism.scoring import build_stats

    state = _state(analysis_id)

    async def progress(pct: int, message: str, activity: dict | None = None) -> None:
        await emit(analysis_id, pct, message, activity)

    try:
        with SessionLocal() as db:
            analysis = db.get(Analysis, analysis_id)
            if not analysis:
                raise ValueError("Análisis no encontrado")
            text = analysis.original_text
            word_count = analysis.word_count
            # Reanudación tras un reinicio: se borran resultados parciales anteriores.
            db.query(Source).filter(Source.analysis_id == analysis_id).delete()
            db.query(Suggestion).filter(Suggestion.analysis_id == analysis_id).delete()
            analysis.status = "processing"
            analysis.progress = 0
            analysis.error = None
            db.commit()

        await progress(3, "Analizando legibilidad del texto...", {"stage": "readability", "log": "Legibilidad del texto"})
        readability = await asyncio.to_thread(analyze_readability, text)

        await progress(6, "Detectando texto generado por IA...", {"stage": "ai", "log": "Detección de IA"})
        ai_detection = await asyncio.to_thread(detect_ai_text, text)

        report = await run_plagiarism_check(text, progress=progress, analysis_id=analysis_id)

        await progress(75, "Generando sugerencias de mejora...", {"stage": "suggestions", "log": "Sugerencias de mejora"})
        suggestions = await asyncio.to_thread(get_improvement_suggestions, text)

        await progress(88, "Guardando resultados...", {"stage": "saving", "log": "Guardando resultados"})
        stats = build_stats(
            plagiarism_stats=report.stats,
            readability=readability,
            ai_detection=ai_detection,
            word_count=word_count,
            sources_checked=report.sources_checked,
        )
        with SessionLocal() as db:
            analysis = db.get(Analysis, analysis_id)
            for src in report.sources:
                payload = {
                    "segments": src.get("matching_segments", []),
                    "metrics": {k: src[k] for k in (
                        "exact_similarity", "paraphrase_similarity", "matched_words", "longest_match_words",
                        "source_word_count", "verified_full_text", "quoted_similarity", "exclusive_similarity",
                        "source_type", "providers",
                    )},
                }
                db.add(Source(
                    analysis_id=analysis_id,
                    url=src["url"],
                    title=src["title"],
                    similarity=src["similarity"],
                    matched_text=json.dumps(payload),
                    source_snippet=(src.get("snippet") or "")[:500],
                ))
            for sug in suggestions:
                db.add(Suggestion(
                    analysis_id=analysis_id,
                    type=sug["type"],
                    severity=sug["severity"],
                    suggestion_text=sug["suggestion"],
                    explanation=sug.get("explanation", ""),
                    improved_example=sug.get("improved_example"),
                ))
            analysis.stats = stats
            analysis.status = "completed"
            analysis.progress = 100
            analysis.completed_at = datetime.utcnow()
            db.commit()

        state["stats"] = stats
        state["status"] = "completed"
        await progress(100, "Análisis completado", {"stage": "done", "log": "Análisis completado"})
    except Exception as exc:
        logger.exception("analysis %s failed", analysis_id)
        state["status"] = "failed"
        state["error"] = str(exc) or "Error durante el análisis"
        _set_db_status(analysis_id, status="failed", error=state["error"])
        await progress(state["progress"], "El análisis falló", {"stage": "error", "log": f"Error: {state['error']}"})
    finally:
        TASKS.pop(analysis_id, None)
        # Limpieza diferida del estado en vivo para no acumular memoria.
        asyncio.get_running_loop().call_later(900, LIVE.pop, analysis_id, None)
