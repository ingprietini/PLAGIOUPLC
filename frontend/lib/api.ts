import { cache } from "react"
import type { AnalysisResponse, AnalysisResult, CitationRequest } from "@/types"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface ApiFetchOptions extends RequestInit {
  timeoutMs?: number
}

async function apiFetch<T>(url: string, options?: ApiFetchOptions): Promise<T> {
  const { timeoutMs = 30000, ...requestOptions } = options ?? {}

  let res: Response
  try {
    res = await fetch(url, {
      ...requestOptions,
      signal: requestOptions.signal ?? AbortSignal.timeout(timeoutMs),
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === "TimeoutError") {
      throw new Error("La solicitud tardó demasiado. Intenta con un archivo más pequeño o vuelve a intentar.")
    }
    if (err instanceof Error) {
      throw new Error(err.message || "Error de conexión")
    }
    throw new Error("Error de conexión")
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error de conexión" }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }

  return res.json()
}

export async function submitAnalysis(text: string, title?: string): Promise<AnalysisResponse> {
  const formData = new FormData()
  formData.append("text", text)
  if (title) formData.append("title", title)

  return apiFetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    body: formData,
  })
}

export async function uploadFile(file: File): Promise<AnalysisResponse & { filename: string }> {
  const formData = new FormData()
  formData.append("file", file)

  return apiFetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: formData,
    timeoutMs: 180000,
  })
}

export const getAnalysis = cache(async (id: string): Promise<AnalysisResult> => {
  return apiFetch(`${API_BASE}/api/analyze/${id}`)
})

export function connectWebSocket(analysisId: string): WebSocket {
  const wsUrl = API_BASE.replace(/^http/, "ws")
  return new WebSocket(`${wsUrl}/ws/analyze/${analysisId}`)
}

export async function getCitationStyles(): Promise<Record<string, string>> {
  return apiFetch(`${API_BASE}/api/styles`)
}

export async function formatCitation(data: CitationRequest): Promise<{ citation: string; style: string }> {
  const formData = new FormData()
  for (const [key, value] of Object.entries(data)) {
    if (value) formData.append(key, value)
  }

  return apiFetch(`${API_BASE}/api/format/citation`, {
    method: "POST",
    body: formData,
  })
}

export function getAnalysisReportDocxUrl(analysisId: string): string {
  return `${API_BASE}/api/analyze/${analysisId}/report/docx`
}

export function getAnalysisReportPdfUrl(analysisId: string): string {
  return `${API_BASE}/api/analyze/${analysisId}/report/pdf`
}
