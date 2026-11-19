"use client"

import { memo } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { AnalysisStats } from "@/types"

const RELIABILITY = {
  alta: { variant: "success", label: "Confiabilidad alta" },
  media: { variant: "warning", label: "Confiabilidad media" },
  baja: { variant: "danger", label: "Confiabilidad baja" },
} as const

const TYPE_COLORS: Record<string, string> = {
  web: "bg-rose-500",
  academico: "bg-violet-500",
  wikipedia: "bg-sky-500",
  repositorio: "bg-orange-500",
}

function Segment({ value, className, title }: { value: number; className: string; title: string }) {
  if (value <= 0) return null
  return <div className={className} style={{ width: `${Math.min(100, value)}%` }} title={title} />
}

export const PlagiarismStats = memo(function PlagiarismStats({
  stats,
}: {
  stats: AnalysisStats
}) {
  const similarityColor =
    stats.overall_similarity > 40 ? "danger" : stats.overall_similarity > 15 ? "warning" : "success"

  const similarityLabel =
    stats.overall_similarity > 30 ? "Alta" : stats.overall_similarity > 10 ? "Media" : "Baja"

  const hasBreakdown = stats.exact_similarity != null
  const exact = stats.exact_similarity ?? 0
  const paraphrase = stats.paraphrase_similarity ?? 0
  const quoted = stats.quoted_similarity ?? 0
  const original = Math.max(0, 100 - exact - paraphrase - quoted)
  const byType = Object.entries(stats.similarity_by_type ?? {})
  const reliability = stats.reliability ? RELIABILITY[stats.reliability] : null
  const evasion = stats.evasion
  const evasionDetected = !!evasion && (evasion.homoglyph_words > 0 || evasion.invisible_chars > 0)
  const health = stats.search_health
  const enginesOk = health
    ? Object.entries(health.engines).filter(([, s]) => s.ok > 0).map(([name]) => name)
    : []
  const apisOk = health
    ? Object.entries(health.apis).filter(([, s]) => s.ok > 0).map(([name]) => name)
    : []

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">Similitud global</p>
              <Badge variant={similarityColor}>{similarityLabel}</Badge>
            </div>
            <p className="mt-2 text-2xl font-bold">{stats.overall_similarity}%</p>
            <p className="text-xs text-gray-500">
              {hasBreakdown
                ? `originalidad: ${stats.originality ?? Math.max(0, 100 - stats.overall_similarity)}%`
                : `pico: ${stats.max_similarity}% · prom: ${stats.avg_similarity}%`}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-gray-500">Fuentes detectadas</p>
            <p className="mt-2 text-2xl font-bold">{stats.total_sources}</p>
            <p className="text-xs text-gray-500">de {stats.sources_checked} revisadas</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-gray-500">Fuentes con plagio</p>
            <p className="mt-2 text-2xl font-bold">{stats.sources_above_threshold}</p>
            <p className="text-xs text-gray-500">aportan al menos el 1% del texto</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-gray-500">Palabras analizadas</p>
            <p className="mt-2 text-2xl font-bold">{stats.word_count.toLocaleString()}</p>
            <p className="text-xs text-gray-500">
              {stats.bibliography_excluded ? "referencias bibliográficas excluidas" : "texto procesado"}
            </p>
          </CardContent>
        </Card>
      </div>

      {hasBreakdown && (
        <Card>
          <CardContent className="space-y-5 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-gray-900">Composición del texto</p>
              {reliability && <Badge variant={reliability.variant}>{reliability.label}</Badge>}
            </div>

            <div>
              <div className="flex h-3 w-full overflow-hidden rounded-full bg-gray-100">
                <Segment value={exact} className="bg-red-500" title={`Copia literal ${exact}%`} />
                <Segment value={paraphrase} className="bg-amber-400" title={`Paráfrasis ${paraphrase}%`} />
                <Segment value={quoted} className="bg-blue-300" title={`Citas ${quoted}%`} />
                <Segment value={original} className="bg-emerald-400" title={`Original ${original.toFixed(2)}%`} />
              </div>
              <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600 sm:grid-cols-4">
                <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-red-500" />Copia literal: <b>{exact}%</b></span>
                <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-amber-400" />Paráfrasis: <b>{paraphrase}%</b></span>
                <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-blue-300" />Citas entre comillas: <b>{quoted}%</b></span>
                <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-emerald-400" />Original: <b>{original.toFixed(2)}%</b></span>
              </div>
              {quoted > 0 && (
                <p className="mt-1 text-[11px] text-gray-500">
                  Las citas entre comillas se muestran aparte y no suman a la similitud global.
                </p>
              )}
            </div>

            {byType.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">Similitud por origen</p>
                <div className="space-y-1.5">
                  {byType.map(([type, info]) => (
                    <div key={type} className="flex items-center gap-3 text-xs">
                      <span className="w-40 shrink-0 text-gray-700">{info.label}</span>
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
                        <div
                          className={`h-full ${TYPE_COLORS[type] ?? "bg-gray-400"}`}
                          style={{ width: `${Math.min(100, info.similarity)}%` }}
                        />
                      </div>
                      <span className="w-14 text-right font-medium text-gray-900">{info.similarity}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {evasionDetected && (
              <p className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-800">
                Posible intento de evasión: se encontraron {evasion!.homoglyph_words} palabras con letras de otros
                alfabetos que imitan a las latinas y {evasion!.invisible_chars} caracteres invisibles. Se normalizaron
                antes de comparar.
              </p>
            )}

            {stats.reliability_note && stats.reliability !== "alta" && (
              <p className="rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
                {stats.reliability_note}
              </p>
            )}

            {health && (
              <p className="text-[11px] text-gray-500">
                Consultas web respondidas: {health.web_queries_ok}/{health.web_queries}
                {enginesOk.length > 0 && ` · buscadores: ${enginesOk.join(", ")}`}
                {apisOk.length > 0 && ` · bases: ${apisOk.join(", ")}`}
                {` · ${health.candidates} fuentes candidatas`}
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
})
