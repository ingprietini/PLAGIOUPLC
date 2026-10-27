"use client"

import { useState, useCallback, useRef } from "react"
import { submitAnalysis } from "@/lib/api"
import { useWebSocket } from "@/hooks/useWebSocket"
import type { AnalysisStats } from "@/types"

interface UseAnalysisReturn {
  analysisId: string | null
  isAnalyzing: boolean
  progress: number
  statusMessage: string
  stats: AnalysisStats | null
  error: string | null
  startAnalysis: (text: string, title?: string) => Promise<void>
  reset: () => void
}

export function useAnalysis(): UseAnalysisReturn {
  const [analysisId, setAnalysisId] = useState<string | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [stats, setStats] = useState<AnalysisStats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const wsCallbacksRef = useRef<{ onComplete?: () => void }>({})

  const handleComplete = useCallback((msg: { stats?: AnalysisStats }) => {
    setStats(msg.stats ?? null)
    setIsAnalyzing(false)
    wsCallbacksRef.current.onComplete?.()
  }, [])

  const handleError = useCallback((msg: { message?: string }) => {
    setError(msg.message ?? "Error durante el análisis")
    setIsAnalyzing(false)
  }, [])

  const { progress, statusMessage } = useWebSocket(analysisId, {
    onComplete: handleComplete,
    onError: handleError,
    enabled: isAnalyzing,
  })

  const startAnalysis = useCallback(async (text: string, title?: string) => {
    setIsAnalyzing(true)
    setError(null)
    setStats(null)

    try {
      const response = await submitAnalysis(text, title)
      setAnalysisId(response.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al iniciar el análisis")
      setIsAnalyzing(false)
    }
  }, [])

  const reset = useCallback(() => {
    setAnalysisId(null)
    setIsAnalyzing(false)
    setStats(null)
    setError(null)
  }, [])

  return {
    analysisId,
    isAnalyzing,
    progress,
    statusMessage,
    stats,
    error,
    startAnalysis,
    reset,
  }
}
