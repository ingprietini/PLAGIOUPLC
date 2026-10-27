"use client"

import { useEffect, useState, useCallback, memo } from "react"
import { useParams, useRouter } from "next/navigation"
import dynamic from "next/dynamic"
import { getAnalysis, getAnalysisReportDocxUrl, getAnalysisReportPdfUrl } from "@/lib/api"
import { ResultsDashboard } from "@/components/ResultsDashboard"
import { CardSkeleton, StatsSkeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import type { AnalysisResult } from "@/types"

const ApaFormatter = dynamic(() => import("@/components/ApaFormatter").then((m) => m.ApaFormatter), {
  loading: () => <div className="h-64 skeleton-pulse rounded-xl bg-gray-100" />,
})

const ExecutiveSummary = memo(function ExecutiveSummary({
  result,
}: {
  result: AnalysisResult
}) {
  const sources = result.sources || []
  const suggestions = result.suggestions || []

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h3 className="mb-4 font-semibold text-gray-900">Resumen ejecutivo</h3>
      <div className="space-y-4 text-sm text-gray-600">
        <p>
          Se analizaron <strong>{result.word_count.toLocaleString()}</strong> palabras
          comparándolas con <strong>{result.stats?.sources_checked || 0}</strong> posibles
          fuentes en internet.
        </p>
        <p>
          Se encontraron <strong>{sources.length}</strong> fuentes con coincidencias
          {result.stats && result.stats.sources_above_threshold > 0 && (
            <>, <strong>{result.stats.sources_above_threshold}</strong> superan el umbral de plagio</>
          )}.
          {result.stats && result.stats.overall_similarity > 0 && (
            <>
              {" "}La similitud global es del{" "}
              <strong>{result.stats.overall_similarity}%</strong>{" "}
              (pico: {result.stats.max_similarity}%).
            </>
          )}
        </p>
        <p>
          Se generaron <strong>{suggestions.length}</strong> sugerencias de mejora para
          el texto analizado.
        </p>
        {result.stats?.ai_detection && (
          <p>
            La detección de IA arrojó una probabilidad del{" "}
            <strong>{result.stats.ai_detection.ai_probability}%</strong>{" "}
            ({result.stats.ai_detection.verdict}).
          </p>
        )}
        {sources.length > 0 && (
          <p>
            <span className="font-medium text-yellow-700">Recomendación:</span>{" "}
            Revisa las fuentes detectadas y asegúrate de citarlas correctamente usando
            el formato APA, MLA o Chicago disponible en esta página.
          </p>
        )}
      </div>
    </div>
  )
})

function SkeletonBlock({ className }: { className: string }) {
  return <div className={`skeleton-pulse rounded bg-gray-200 ${className}`} />
}

function LoadingView() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8">
        <div className="mb-2">
          <SkeletonBlock className="h-8 w-64" />
        </div>
        <SkeletonBlock className="h-4 w-96" />
      </div>
      <StatsSkeleton />
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <CardSkeleton />
        <CardSkeleton />
      </div>
      <div className="mt-6">
        <CardSkeleton />
      </div>
    </div>
  )
}

function ErrorView({ error, router }: { error: string; router: ReturnType<typeof useRouter> }) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
      <div className="text-center">
        <div className="mb-4 inline-flex items-center justify-center rounded-full bg-red-50 p-3">
          <svg className="h-6 w-6 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-gray-900">Error al cargar resultados</h2>
        <p className="mt-2 text-sm text-gray-500">{error}</p>
        <div className="mt-6 flex items-center justify-center gap-4">
          <Button onClick={() => router.push("/analyze")}>Volver al análisis</Button>
          <Button variant="secondary" onClick={() => window.location.reload()}>
            Reintentar
          </Button>
        </div>
      </div>
    </div>
  )
}

function ProcessingView({ progress }: { progress: number }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-8 text-center shadow-sm">
      <div className="mb-4">
        <div className="relative mx-auto h-20 w-20">
          <svg className="h-20 w-20 -rotate-90" viewBox="0 0 80 80">
            <circle cx="40" cy="40" r="34" fill="none" stroke="#e5e7eb" strokeWidth="6" />
            <circle
              cx="40"
              cy="40"
              r="34"
              fill="none"
              stroke="#2563eb"
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={`${2 * Math.PI * 34}`}
              strokeDashoffset={`${2 * Math.PI * 34 * (1 - progress / 100)}`}
              className="transition-all duration-500 ease-out"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xl font-bold text-gray-900">{progress}%</span>
          </div>
        </div>
      </div>
      <p className="text-sm font-medium text-gray-700">Análisis en progreso...</p>
      <p className="mt-1 text-xs text-gray-500">Los resultados se actualizarán automáticamente.</p>
    </div>
  )
}

function FailedView({ error, router }: { error?: string; router: ReturnType<typeof useRouter> }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
      <h2 className="text-lg font-semibold text-red-700">El análisis falló</h2>
      <p className="mt-2 text-sm text-red-600">{error || "Error desconocido"}</p>
      <Button variant="secondary" className="mt-4" onClick={() => router.push("/analyze")}>
        Intentar de nuevo
      </Button>
    </div>
  )
}

export default function ResultsPage() {
  const params = useParams()
  const router = useRouter()
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchResults = useCallback(async (id: string) => {
    try {
      const data = await getAnalysis(id)
      setResult(data)
      setLoading(false)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar resultados")
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const id = params.id as string
    if (!id) return

    fetchResults(id)

    const interval = setInterval(() => {
      fetchResults(id)
    }, 3000)

    return () => clearInterval(interval)
  }, [params.id, fetchResults])

  if (loading && !result) return <LoadingView />
  if (error && !result) return <ErrorView error={error} router={router} />
  if (!result) return null

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Resultados del análisis</h1>
          <p className="mt-1 text-sm text-gray-500">
            {result.title} &middot;{" "}
            {result.completed_at
              ? new Date(result.completed_at).toLocaleString()
              : "En progreso..."}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            onClick={() => window.open(getAnalysisReportPdfUrl(result.id), "_blank", "noopener,noreferrer")}
            disabled={result.status !== "completed"}
          >
            Descargar informe PDF
          </Button>
          <Button
            variant="secondary"
            onClick={() => window.open(getAnalysisReportDocxUrl(result.id), "_blank", "noopener,noreferrer")}
            disabled={result.status !== "completed"}
          >
            Descargar informe DOCX
          </Button>
          <Button variant="secondary" onClick={() => router.push("/analyze")}>
            Nuevo análisis
          </Button>
        </div>
      </div>

      {(result.status === "processing" || result.status === "pending") && (
        <ProcessingView progress={result.progress || 0} />
      )}

      {result.status === "failed" && <FailedView error={result.error} router={router} />}

      {result.status === "completed" && (
        <div className="space-y-8">
          <ResultsDashboard result={result} />

          <div className="grid gap-6 lg:grid-cols-2">
            <ApaFormatter />
            <ExecutiveSummary result={result} />
          </div>
        </div>
      )}
    </div>
  )
}
