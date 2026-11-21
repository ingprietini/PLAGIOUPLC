"use client"

import { Progress } from "@/components/ui/progress"
import type { LiveProgress } from "@/types"

const PASSES = [
  { n: 1, label: "Búsqueda amplia" },
  { n: 2, label: "Reintentos" },
  { n: 3, label: "Frases exactas" },
  { n: 4, label: "Verificación" },
]

const PROVIDER_LABEL: Record<string, string> = {
  google: "Google",
  bing: "Bing",
  yandex: "Yandex",
  yahoo: "Yahoo",
  duckduckgo: "DuckDuckGo",
  brave: "Brave",
  mojeek: "Mojeek",
  startpage: "Startpage",
  openalex: "OpenAlex (artículos académicos)",
  crossref: "Crossref (artículos académicos)",
  wikipedia: "Wikipedia",
}

function formatElapsed(seconds = 0) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, "0")}`
}

interface AnalysisProgressProps {
  live: LiveProgress
  connection: "live" | "polling" | "connecting"
}

export function AnalysisProgress({ live, connection }: AnalysisProgressProps) {
  const { progress, message, activity, log = [], found_sources = 0, elapsed_seconds = 0 } = live
  const currentPass = activity?.pass ?? null
  const stalled = (live.seconds_since_update ?? 0) > 25
  const position = activity?.position

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
      {/* Encabezado: porcentaje, tiempo y conexión */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-3xl font-bold text-gray-900">{Math.round(progress)}%</p>
          <p className="text-sm font-medium text-gray-700">{message || "Preparando análisis..."}</p>
        </div>
        <div className="text-right text-xs text-gray-500">
          <p>
            Tiempo: <span className="font-medium text-gray-800">{formatElapsed(elapsed_seconds)}</span>
          </p>
          <p>
            Fuentes con coincidencias: <span className="font-medium text-gray-800">{found_sources}</span>
          </p>
          <p className="mt-1 inline-flex items-center gap-1">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                connection === "live" ? "bg-emerald-500" : connection === "polling" ? "bg-amber-500" : "bg-gray-400"
              }`}
            />
            {connection === "live" ? "En vivo" : connection === "polling" ? "Reconectado (actualiza cada 2 s)" : "Conectando..."}
          </p>
        </div>
      </div>

      <Progress value={progress} className="mt-4 w-full" />

      {/* Pasadas */}
      <ol className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {PASSES.map((p) => {
          const state = currentPass === null ? (progress >= 70 ? "done" : "todo") : p.n < currentPass ? "done" : p.n === currentPass ? "active" : "todo"
          return (
            <li
              key={p.n}
              className={`rounded-md border px-2 py-1.5 text-xs ${
                state === "active"
                  ? "border-blue-300 bg-blue-50 font-semibold text-blue-800"
                  : state === "done"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : "border-gray-200 text-gray-500"
              }`}
            >
              {state === "done" ? "✓ " : ""}Pasada {p.n}: {p.label}
            </li>
          )
        })}
      </ol>

      {/* Qué se está investigando ahora */}
      {activity && (activity.stage === "search" || activity.stage === "fetch" || activity.stage === "match" || activity.stage === "repository") && (
        <div className="mt-4 rounded-lg border border-blue-100 bg-blue-50/60 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-blue-900">Investigando ahora</p>

          {activity.stage === "search" && (
            <>
              <p className="mt-1 text-xs text-blue-900">
                Buscando en <b>{PROVIDER_LABEL[activity.provider ?? ""] ?? activity.provider}</b> este fragmento de tu documento:
              </p>
              <blockquote className="mt-2 border-l-4 border-blue-400 bg-white px-3 py-2 text-sm italic text-gray-800">
                {position?.text || activity.fragment}
              </blockquote>
              {position && (
                <div className="mt-2">
                  <div className="relative h-2 w-full rounded-full bg-blue-100" title="Ubicación en el documento">
                    <div
                      className="absolute top-1/2 h-3.5 w-1.5 -translate-y-1/2 rounded bg-blue-600"
                      style={{ left: `calc(${Math.min(100, position.percent)}% - 3px)` }}
                    />
                  </div>
                  <p className="mt-1 text-[11px] text-blue-800">
                    Oración {position.sentence} de {position.sentences} · {Math.round(position.percent)}% del documento
                  </p>
                </div>
              )}
            </>
          )}

          {(activity.stage === "fetch" || activity.stage === "repository") && (
            <>
              <p className="mt-1 text-xs text-blue-900">
                {activity.stage === "fetch" ? "Leyendo y comparando la fuente" : "Comparando con"}
                {activity.done && activity.total ? ` ${activity.done} de ${activity.total}` : ""}:
              </p>
              <p className="mt-1 line-clamp-1 text-sm font-medium text-gray-900">{activity.title}</p>
              {activity.url?.startsWith("http") && (
                <p className="line-clamp-1 text-[11px] text-blue-700">{activity.url}</p>
              )}
            </>
          )}

          {activity.stage === "match" && (
            <>
              <p className="mt-1 text-xs font-medium text-red-700">
                Coincidencia encontrada: {activity.similarity}% de tu texto
              </p>
              <p className="mt-1 line-clamp-1 text-sm font-medium text-gray-900">{activity.title}</p>
              {activity.url?.startsWith("http") && (
                <p className="line-clamp-1 text-[11px] text-blue-700">{activity.url}</p>
              )}
            </>
          )}
        </div>
      )}

      {stalled && (
        <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
          El servidor sigue trabajando pero va lento (lleva {live.seconds_since_update}s sin novedades). No cierres la
          página: cada búsqueda tiene un tiempo máximo y el análisis continuará solo.
        </p>
      )}

      {/* Registro de actividad */}
      {log.length > 0 && (
        <div className="mt-4">
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-500">Actividad reciente</p>
          <ul className="max-h-48 space-y-1 overflow-y-auto text-xs text-gray-600">
            {[...log].reverse().map((entry, i) => (
              <li key={`${entry.t}-${i}`} className="flex gap-2">
                <span className="w-10 shrink-0 tabular-nums text-gray-400">{formatElapsed(entry.t)}</span>
                <span className={`min-w-0 break-words ${entry.text.startsWith("Coincidencia") ? "font-medium text-red-700" : ""}`}>
                  {entry.text}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
