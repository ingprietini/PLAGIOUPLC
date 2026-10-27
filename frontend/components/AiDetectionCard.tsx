"use client"

import { memo } from "react"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { AiDetectionResult } from "@/types"

const confidenceColors: Record<string, "danger" | "warning" | "success" | "info"> = {
  high: "danger",
  medium: "warning",
  low: "info",
}

function getProbabilityColor(prob: number): string {
  if (prob >= 30) return "text-red-600"
  if (prob >= 15) return "text-yellow-600"
  return "text-green-600"
}

function getVerdictBadge(verdict: string, prob: number) {
  if (verdict === "AI-generated" || prob >= 25) {
    return <Badge variant="danger">Posible IA</Badge>
  }
  if (verdict === "Posiblemente IA" || prob >= 15) {
    return <Badge variant="warning">Sospechoso</Badge>
  }
  return <Badge variant="success">Parece humano</Badge>
}

export const AiDetectionCard = memo(function AiDetectionCard({
  result,
}: {
  result: AiDetectionResult
}) {
  const confidence = result.confidence as keyof typeof confidenceColors

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Detección de IA</h3>
          {getVerdictBadge(result.verdict, result.ai_probability)}
        </div>
        <p className="text-xs text-gray-500">
          Análisis estadístico completado en {result.scan_time_ms}ms
        </p>
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex items-baseline gap-2">
          <span className={`text-3xl font-bold ${getProbabilityColor(result.ai_probability)}`}>
            {result.ai_probability}%
          </span>
          <span className="text-sm text-gray-500">probabilidad de IA</span>
          <Badge variant={confidenceColors[confidence] || "info"}>
            confianza {result.confidence}
          </Badge>
        </div>
        {result.raw_probability < result.ai_probability && (
          <p className="mb-3 text-xs text-gray-400">
            Probabilidad base: {result.raw_probability}% · Ajuste por severidad: +{((result.ai_probability / result.raw_probability - 1) * 100).toFixed(0)}%
          </p>
        )}

        {result.flags.length > 0 && (
          <div className="mb-4 space-y-1">
            <p className="text-xs font-medium text-gray-500">Indicadores detectados:</p>
            <ul className="space-y-0.5">
              {result.flags.map((flag, i) => (
                <li key={i} className="flex items-start gap-1.5 text-xs text-gray-600">
                  <span className="mt-0.5 block h-1.5 w-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                  {flag}
                </li>
              ))}
            </ul>
          </div>
        )}

        {result.model_attribution && result.model_attribution.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500">Atribución por modelo:</p>
            <div className="mt-1 space-y-0.5">
              {result.model_attribution.map((m, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-gray-600">
                  <span className="w-32 truncate">{m.model}</span>
                  <div className="h-1.5 flex-1 rounded-full bg-gray-100">
                    <div
                      className="h-1.5 rounded-full bg-blue-400"
                      style={{ width: `${Math.round(m.confidence * 100)}%` }}
                    />
                  </div>
                  <span className="w-8 text-right tabular-nums text-gray-400">
                    {Math.round(m.confidence * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <p className="mt-3 text-xs text-gray-400">
          * Detección estadística — puede tener falsos positivos en textos formales o académicos.
        </p>
      </CardContent>
    </Card>
  )
})
