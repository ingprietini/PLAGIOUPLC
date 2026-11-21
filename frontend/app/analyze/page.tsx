"use client"

import { useRouter } from "next/navigation"
import { useState, useCallback, useRef, useEffect } from "react"
import dynamic from "next/dynamic"
import { TextUpload } from "@/components/TextUpload"
import { AnalysisProgress } from "@/components/AnalysisProgress"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { submitAnalysis, connectWebSocket, getAnalysisProgress } from "@/lib/api"
import type { LiveProgress, WSMessage } from "@/types"

const POLL_INTERVAL_MS = 2000
const INITIAL_LIVE: LiveProgress = { status: "processing", progress: 0, message: "Iniciando análisis..." }

const TextImprover = dynamic(() => import("@/components/TextImprover").then((m) => m.TextImprover), {
  loading: () => <div className="h-48 skeleton-pulse rounded-xl bg-gray-100" />,
})

const ApaFormatter = dynamic(() => import("@/components/ApaFormatter").then((m) => m.ApaFormatter), {
  loading: () => <div className="h-48 skeleton-pulse rounded-xl bg-gray-100" />,
})

export default function AnalyzePage() {
  const router = useRouter()
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [live, setLive] = useState<LiveProgress>(INITIAL_LIVE)
  const [connection, setConnection] = useState<"live" | "polling" | "connecting">("connecting")
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<number | null>(null)
  const finishedRef = useRef(false)

  const dismissError = useCallback(() => setError(null), [])

  const cleanup = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  useEffect(() => cleanup, [cleanup])

  const finish = useCallback(
    (analysisId: string, failure?: string) => {
      if (finishedRef.current) return
      finishedRef.current = true
      cleanup()
      if (failure) {
        setError(failure)
        setIsAnalyzing(false)
        return
      }
      setLive((prev) => ({ ...prev, progress: 100, message: "Análisis completado" }))
      router.push(`/results/${analysisId}`)
    },
    [cleanup, router]
  )

  // Respaldo: si el WebSocket se cae, se consulta el progreso por HTTP. El análisis sigue en el servidor.
  const startPolling = useCallback(
    (analysisId: string) => {
      if (pollRef.current !== null || finishedRef.current) return
      setConnection("polling")
      const tick = async () => {
        try {
          const snap = await getAnalysisProgress(analysisId)
          setLive(snap)
          if (snap.status === "completed") finish(analysisId)
          else if (snap.status === "failed") finish(analysisId, snap.error || "El análisis falló en el servidor")
        } catch {
          // Error transitorio de red: se reintenta en el siguiente ciclo.
        }
      }
      void tick()
      pollRef.current = window.setInterval(tick, POLL_INTERVAL_MS)
    },
    [finish]
  )

  const startAnalysis = useCallback(
    async (analysisId: string) => {
      cleanup()
      finishedRef.current = false
      setIsAnalyzing(true)
      setError(null)
      setLive(INITIAL_LIVE)
      setConnection("connecting")

      let ws: WebSocket
      try {
        ws = connectWebSocket(analysisId)
      } catch {
        startPolling(analysisId)
        return
      }
      wsRef.current = ws

      ws.onopen = () => setConnection("live")

      ws.onmessage = (event) => {
        let msg: WSMessage
        try {
          msg = JSON.parse(event.data)
        } catch {
          return
        }
        if (msg.type === "progress" || msg.type === "status") {
          setLive((prev) => ({
            ...prev,
            ...msg,
            status: msg.status ?? prev.status,
            progress: msg.progress ?? prev.progress,
            message: msg.message ?? prev.message,
          }))
        } else if (msg.type === "complete") {
          finish(analysisId)
        } else if (msg.type === "error") {
          finish(analysisId, msg.message ?? "Error durante el análisis")
        }
      }

      // Cierre o error de la conexión sin haber terminado: pasar a consultar por HTTP.
      ws.onerror = () => startPolling(analysisId)
      ws.onclose = () => {
        wsRef.current = null
        if (!finishedRef.current) startPolling(analysisId)
      }
    },
    [cleanup, finish, startPolling]
  )

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
              <AnalysisProgress live={live} connection={connection} />
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
