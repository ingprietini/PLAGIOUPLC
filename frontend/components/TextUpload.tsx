"use client"

import { useState, useRef, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { uploadFile, submitAnalysis } from "@/lib/api"

const ACCEPTED_FORMATS = ".txt,.pdf,.docx,.doc,.odt"

const FORMAT_LABELS: Record<string, string> = {
  ".txt": "Texto",
  ".pdf": "PDF",
  ".docx": "Word",
  ".doc": "Word (antiguo)",
  ".odt": "OpenDocument",
}

interface TextUploadProps {
  onAnalyze: (text: string, title?: string) => void
  onFileUpload: (analysisId: string, title?: string) => void
  isAnalyzing: boolean
}

export function TextUpload({ onAnalyze, onFileUpload, isAnalyzing }: TextUploadProps) {
  const [text, setText] = useState("")
  const [title, setTitle] = useState("")
  const [fileName, setFileName] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFileProcess(file)
  }, [])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFileProcess(file)
  }

  const handleFileProcess = async (file: File) => {
    setUploadError(null)
    const ext = "." + file.name.split(".").pop()?.toLowerCase()

    if (ext === ".txt") {
      const reader = new FileReader()
      reader.onload = (ev) => {
        const content = ev.target?.result as string
        setText(content)
        setFileName(file.name)
        setTitle(file.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()))
      }
      reader.readAsText(file)
      return
    }

    try {
      const result = await uploadFile(file)
      setFileName(file.name)
      const derivedTitle = title || file.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
      onFileUpload(result.id, derivedTitle)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Error al subir archivo")
    }
  }

  const handleSubmit = () => {
    if (!text.trim()) return
    if (wordCount < 50) {
      setUploadError("El texto debe tener al menos 50 palabras para analizar.")
      return
    }
    onAnalyze(text.trim(), title.trim() || undefined)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-1">
          Título del documento (opcional)
        </label>
        <input
          id="title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Ej: Tesis de grado, Artículo científico..."
          className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
      </div>

      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
          isDragging
            ? "border-primary-500 bg-primary-50"
            : "border-gray-300 hover:border-gray-400"
        }`}
      >
        <div className="flex flex-col items-center gap-3">
          <div className="rounded-full bg-primary-50 p-3">
            <svg className="h-6 w-6 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <div>
            <p className="text-sm text-gray-600">
              Arrastra un archivo aquí o{" "}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="font-medium text-primary-600 hover:text-primary-500"
              >
                selecciona un archivo
              </button>
            </p>
            <div className="mt-1 flex flex-wrap justify-center gap-1.5">
              {Object.entries(FORMAT_LABELS).map(([ext, label]) => (
                <span key={ext} className="inline-flex items-center rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                  {label}
                </span>
              ))}
            </div>
          </div>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_FORMATS}
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>

      {fileName && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700">
          Archivo cargado: <strong>{fileName}</strong>
        </div>
      )}

      {uploadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {uploadError}
        </div>
      )}

      <div>
        <textarea
          value={text}
          onChange={(e) => { setText(e.target.value); setFileName(null) }}
          placeholder="Pega aquí tu texto para analizar (mínimo 50 palabras)..."
          rows={10}
          className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 resize-y min-h-[180px]"
        />
      </div>

      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-500">
          {fileName ? (
            <span>
              <strong>{fileName}</strong> — {wordCount.toLocaleString()} palabras
            </span>
          ) : wordCount > 0 ? (
            <span>
              <strong>{wordCount.toLocaleString()}</strong> palabras
              {wordCount < 50 ? (
                <span className="ml-2 text-red-500">(mínimo 50 palabras)</span>
              ) : wordCount > 50000 ? (
                <span className="ml-2 text-yellow-600">
                  (texto muy extenso — se muestrearán fragmentos para la búsqueda web)
                </span>
              ) : wordCount > 10000 ? (
                <span className="ml-2 text-yellow-600">
                  (texto extenso, puede tomar más tiempo)
                </span>
              ) : null}
            </span>
          ) : (
            <span>Sin texto ingresado</span>
          )}
        </div>
        <Button
          onClick={handleSubmit}
          disabled={!text.trim() || wordCount < 50}
          loading={isAnalyzing}
          size="lg"
          title={
            !text.trim()
              ? "Pega un texto para analizar"
              : wordCount < 50
              ? `Se necesitan al menos 50 palabras (${wordCount}/50)`
              : "Iniciar análisis"
          }
        >
          {isAnalyzing ? "Analizando..." : "Analizar texto"}
        </Button>
      </div>
    </div>
  )
}
