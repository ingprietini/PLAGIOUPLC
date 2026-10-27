"use client"

import { Progress } from "@/components/ui/progress"

interface AnalysisProgressProps {
  progress: number
  statusMessage: string
  currentSource?: {
    index: number
    total: number
    url: string
    title: string
  }
}

export function AnalysisProgress({ progress, statusMessage, currentSource }: AnalysisProgressProps) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
      <div className="flex flex-col items-center text-center">
        <div className="mb-6">
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
              <span className="text-xl font-bold text-gray-900">{Math.round(progress)}%</span>
            </div>
          </div>
        </div>

        <Progress value={progress} className="mb-4 w-full max-w-md" />

        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-900">
            {statusMessage || "Preparando análisis..."}
          </p>
          {currentSource && (
            <div className="rounded-md border border-blue-100 bg-blue-50/70 p-3 text-left">
              <p className="text-xs font-semibold text-blue-900">
                Fuente consultada {currentSource.index}/{currentSource.total}
              </p>
              <p className="mt-1 line-clamp-1 text-xs text-blue-800">
                {currentSource.title || currentSource.url}
              </p>
              <p className="line-clamp-1 text-[11px] text-blue-700">{currentSource.url}</p>
            </div>
          )}
          <div className="flex items-center justify-center gap-1 text-xs text-gray-500">
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="inline-block h-2 w-2 rounded-full bg-primary-600 animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
            <span className="ml-2">Procesando texto de gran tamaño...</span>
          </div>
        </div>
      </div>
    </div>
  )
}
