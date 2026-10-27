"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import type { WSMessage } from "@/types"

interface UseWebSocketOptions {
  onMessage?: (msg: WSMessage) => void
  onComplete?: (msg: WSMessage) => void
  onError?: (msg: WSMessage) => void
  enabled?: boolean
}

export function useWebSocket(analysisId: string | null, options: UseWebSocketOptions = {}) {
  const [isConnected, setIsConnected] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusMessage, setStatusMessage] = useState("")
  const [currentSource, setCurrentSource] = useState<WSMessage["source"]>()
  const wsRef = useRef<WebSocket | null>(null)
  const optionsRef = useRef(options)
  optionsRef.current = options

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
      setIsConnected(false)
    }
  }, [])

  useEffect(() => {
    if (!analysisId || !options.enabled) return

    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"}/ws/analyze/${analysisId}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => setIsConnected(true)

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)
        const current = optionsRef.current
        current.onMessage?.(msg)

        switch (msg.type) {
          case "progress":
            setProgress(msg.progress ?? 0)
            setStatusMessage(msg.message ?? "")
            break
          case "source_checking":
            setProgress(msg.progress ?? 0)
            setStatusMessage(msg.message ?? "")
            setCurrentSource(msg.source)
            break
          case "status":
            setStatusMessage(msg.message ?? "")
            break
          case "complete":
            setProgress(100)
            setStatusMessage("Análisis completado")
            setCurrentSource(undefined)
            current.onComplete?.(msg)
            break
          case "error":
            current.onError?.(msg)
            break
        }
      } catch {
        // ignore parse errors
      }
    }

    ws.onerror = () => {
      optionsRef.current.onError?.({ type: "error", message: "Error de conexión WebSocket" })
    }

    ws.onclose = () => {
      setIsConnected(false)
    }

    return () => {
      ws.close()
    }
  }, [analysisId, options.enabled])

  return { isConnected, progress, statusMessage, currentSource, disconnect }
}
