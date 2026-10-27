"use client"

import { memo, useState } from "react"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { PlagiarismStats } from "@/components/PlagiarismStats"
import { SourceCard } from "@/components/SourceCard"
import { AiDetectionCard } from "@/components/AiDetectionCard"
import type { AnalysisResult, SuggestionResult } from "@/types"

const severityConfig = {
  high: { variant: "danger" as const, label: "Importante" },
  medium: { variant: "warning" as const, label: "Recomendado" },
  low: { variant: "info" as const, label: "Sugerencia" },
} as const

const typeLabels: Record<string, string> = {
  readability: "Legibilidad",
  structure: "Estructura",
  style: "Estilo",
}

function hasVerifiedTextualMatch(source: AnalysisResult["sources"][number]) {
  return (source.matched_text || []).some((segment) => {
    if (typeof segment === "string") {
      return false
    }
    return Boolean(segment.source_excerpt && (segment.matched_phrase || segment.text_excerpt))
  })
}

function SuggestionCard({ suggestion }: { suggestion: SuggestionResult }) {
  const config = severityConfig[suggestion.severity as keyof typeof severityConfig] || severityConfig.low
  const [showExample, setShowExample] = useState(false)
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
      <div className="mb-1 flex items-center gap-2">
        <Badge variant={config.variant}>{config.label}</Badge>
        <span className="text-xs font-medium text-gray-500 capitalize">
          {typeLabels[suggestion.type] || suggestion.type}
        </span>
      </div>
      <p className="text-sm text-gray-700">{suggestion.suggestion}</p>
      {suggestion.explanation && (
        <p className="mt-1 text-xs text-gray-500">{suggestion.explanation}</p>
      )}
      {suggestion.improved_example && (
        <div className="mt-2">
          <button
            onClick={() => setShowExample(!showExample)}
            className="text-xs font-medium text-primary-600 hover:text-primary-500"
          >
            {showExample ? "Ocultar ejemplo" : "Ver ejemplo mejorado"}
          </button>
          {showExample && (
            <div className="mt-1 rounded border border-green-200 bg-green-50 p-2 text-xs text-green-800">
              {suggestion.improved_example}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const SourcesSection = memo(function SourcesSection({
  sources,
}: {
  sources: AnalysisResult["sources"]
}) {
  if (sources.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No se encontraron fuentes con coincidencias significativas.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {sources.map((source, i) => (
        <SourceCard key={source.id} source={source} index={i} />
      ))}
    </div>
  )
})

const SuggestionsSection = memo(function SuggestionsSection({
  suggestions,
}: {
  suggestions: AnalysisResult["suggestions"]
}) {
  if (suggestions.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No hay sugerencias disponibles para este texto.
      </p>
    )
  }

  return (
    <div className="space-y-4">
      {suggestions.map((sg) => (
        <SuggestionCard key={sg.id} suggestion={sg} />
      ))}
    </div>
  )
})

export const ResultsDashboard = memo(function ResultsDashboard({
  result,
}: {
  result: AnalysisResult
}) {
  const { stats, sources, suggestions } = result
  const verifiedSources = sources.filter(hasVerifiedTextualMatch)
  const relatedSources = sources.filter((source) => !hasVerifiedTextualMatch(source))

  return (
    <div className="space-y-8">
      <div>
        <div className="mb-2 flex items-center gap-3">
          <h2 className="text-xl font-semibold text-gray-900">Resumen de resultados</h2>
          <Badge variant={stats.overall_similarity > 20 ? "danger" : "success"}>
            {stats.overall_similarity > 20
              ? "Posible plagio detectado"
              : "Originalidad aceptable"}
          </Badge>
        </div>
        <p className="text-sm text-gray-500">
          {result.title} &middot; {result.word_count.toLocaleString()} palabras &middot;{" "}
          {result.completed_at
            ? new Date(result.completed_at).toLocaleDateString()
            : ""}
        </p>
      </div>

      <PlagiarismStats stats={stats} />

      {stats.ai_detection && (
        <AiDetectionCard result={stats.ai_detection} />
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <h3 className="font-semibold text-gray-900">
              Fuentes con cita textual verificable ({verifiedSources.length})
            </h3>
          </CardHeader>
          <CardContent>
            <SourcesSection sources={verifiedSources} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="font-semibold text-gray-900">
              Sugerencias de mejora ({suggestions.length})
            </h3>
          </CardHeader>
          <CardContent>
            <SuggestionsSection suggestions={suggestions} />
          </CardContent>
        </Card>
      </div>

      {relatedSources.length > 0 && (
        <Card>
          <CardHeader>
            <h3 className="font-semibold text-gray-900">
              Fuentes relacionadas por similitud temática ({relatedSources.length})
            </h3>
            <p className="text-xs text-gray-500">
              Estas fuentes no tienen cita textual verificable con tu documento.
            </p>
          </CardHeader>
          <CardContent>
            <SourcesSection sources={relatedSources} />
          </CardContent>
        </Card>
      )}

      {stats.readability && (
        <Card>
          <CardHeader>
            <h3 className="font-semibold text-gray-900">Estadísticas de legibilidad</h3>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <p className="text-xs text-gray-500">Nivel de legibilidad</p>
                <p className="text-lg font-semibold">{stats.readability.readability_level}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Índice Flesch</p>
                <p className="text-lg font-semibold">{stats.readability.flesch_reading_ease}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Palabras por oración</p>
                <p className="text-lg font-semibold">{stats.readability.avg_words_per_sentence}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Grado Flesch-Kincaid</p>
                <p className="text-lg font-semibold">{stats.readability.flesch_kincaid_grade}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
})
