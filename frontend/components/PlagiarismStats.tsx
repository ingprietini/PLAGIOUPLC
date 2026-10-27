"use client"

import { memo } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { AnalysisStats } from "@/types"

export const PlagiarismStats = memo(function PlagiarismStats({
  stats,
}: {
  stats: AnalysisStats
}) {
  const similarityColor =
    stats.overall_similarity > 40 ? "danger" : stats.overall_similarity > 15 ? "warning" : "success"

  const similarityLabel =
    stats.overall_similarity > 30 ? "Alta" : stats.overall_similarity > 10 ? "Media" : "Baja"

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">Similitud global</p>
            <Badge variant={similarityColor}>{similarityLabel}</Badge>
          </div>
          <p className="mt-2 text-2xl font-bold">{stats.overall_similarity}%</p>
          <p className="text-xs text-gray-500">
            pico: {stats.max_similarity}% · prom: {stats.avg_similarity}%
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
          <p className="text-xs text-gray-500">superan el umbral mínimo</p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <p className="text-sm text-gray-500">Palabras analizadas</p>
          <p className="mt-2 text-2xl font-bold">{stats.word_count.toLocaleString()}</p>
          <p className="text-xs text-gray-500">texto procesado</p>
        </CardContent>
      </Card>
    </div>
  )
})
