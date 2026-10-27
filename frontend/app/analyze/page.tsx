"use client"

import { useRouter } from "next/navigation"
import { useState, useCallback, useRef, useEffect } from "react"
import dynamic from "next/dynamic"
import { TextUpload } from "@/components/TextUpload"
import { AnalysisProgress } from "@/components/AnalysisProgress"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { submitAnalysis, uploadFile, connectWebSocket } from "@/lib/api"
import type { WSMessage } from "@/types"

const SOURCE_DISPLAY_INTERVAL_MS = 550

const TextImprover = dynamic(() => import("@/components/TextImprover").then((m) => m.TextImprover), {
  loading: () => <div className="h-48 skeleton-pulse rounded-xl bg-gray-100" />,
})

const ApaFormatter = dynamic(() => import("@/components/ApaFormatter").then((m) => m.ApaFormatter), {
  loading: () => <div className="h-48 skeleton-pulse rounded-xl bg-gray-100" />,
})

export default function AnalyzePage() {
  const router = useRouter()
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusMessage, setStatusMessage] = useState("")
  const [currentSource, setCurrentSource] = useState<WSMessage["source"]>()
  const [error, setError] = useState<string | null>(null)
  const sourceQueueRef = useRef<NonNullable<WSMessage["source"]>[]>([])
  const sourceTickerRef = useRef<number | null>(null)

  const dismissError = useCallback(() => setError(null), [])

  const stopSourceTicker = useCallback(() => {
    if (sourceTickerRef.current !== null) {
      window.clearInterval(sourceTickerRef.current)
      sourceTickerRef.current = null
    }
  }, [])

  const startSourceTicker = useCallback(() => {
    stopSourceTicker()
    sourceTickerRef.current = window.setInterval(() => {
      const nextSource = sourceQueueRef.current.shift()
      if (nextSource) {
        setCurrentSource(nextSource)
      }
    }, SOURCE_DISPLAY_INTERVAL_MS)
  }, [stopSourceTicker])

  useEffect(() => {
    return () => {
      stopSourceTicker()
    }
  }, [stopSourceTicker])

  const startAnalysis = useCallback(async (analysisId: string) => {
    setIsAnalyzing(true)
    setProgress(0)
    setError(null)
    setCurrentSource(undefined)
    setStatusMessage("Iniciando análisis...")
    sourceQueueRef.current = []
    startSourceTicker()

    const ws = connectWebSocket(analysisId)

    ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data)

      if (msg.type === "progress") {
        setProgress(msg.progress ?? 0)
        setStatusMessage(msg.message ?? "")
      } else if (msg.type === "source_checking") {
        setProgress(msg.progress ?? 0)
        setStatusMessage(msg.message ?? "")
        if (msg.source) {
          sourceQueueRef.current.push(msg.source)
        }
      } else if (msg.type === "complete") {
        setProgress(100)
        setStatusMessage("Análisis completado")
        sourceQueueRef.current = []
        stopSourceTicker()
        setCurrentSource(undefined)
        setIsAnalyzing(false)
        ws.close()
        router.push(`/results/${analysisId}`)
      } else if (msg.type === "error") {
        sourceQueueRef.current = []
        stopSourceTicker()
        setError(msg.message ?? "Error durante el análisis")
        setIsAnalyzing(false)
        ws.close()
      }
    }

    ws.onerror = () => {
      sourceQueueRef.current = []
      stopSourceTicker()
      setError("Error de conexión con el servidor")
      setIsAnalyzing(false)
    }
  }, [router, startSourceTicker, stopSourceTicker])

  const handleAnalyze = useCallback(async (text: string, title?: string) => {
    setError(null)
    try {
      const response = await submitAnalysis(text, title)
      await startAnalysis(response.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al iniciar el análisis")
      setIsAnalyzing(false)
    }
  }, [startAnalysis])

  const handleFileUpload = useCallback(async (analysisId: string, title?: string) => {
    setError(null)
    await startAnalysis(analysisId)
  }, [startAnalysis])

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Analizar texto</h1>
        <p className="mt-1 text-sm text-gray-500">
          Sube un archivo o pega tu texto para detectar posible plagio y obtener sugerencias de mejora.
        </p>
      </div>

      <div className="space-y-8">
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
            <button className="ml-2 font-medium underline hover:no-underline" onClick={dismissError}>
              Cerrar
            </button>
          </div>
        )}

        <Card>
          <CardHeader>
            <h2 className="font-semibold text-gray-900">
              {isAnalyzing ? "Análisis en progreso" : "Subir texto"}
            </h2>
            <p className="text-sm text-gray-500">
              Mínimo 50 palabras. Soporta hasta 100,000 palabras.
            </p>
          </CardHeader>
          <CardContent>
            {isAnalyzing ? (
              <AnalysisProgress progress={progress} statusMessage={statusMessage} currentSource={currentSource} />
            ) : (
              <TextUpload onAnalyze={handleAnalyze} onFileUpload={handleFileUpload} isAnalyzing={isAnalyzing} />
            )}
          </CardContent>
        </Card>

        <div className="grid gap-6 lg:grid-cols-2">
          <TextImprover />
          <ApaFormatter />
        </div>
      </div>
    </div>
  )
}
