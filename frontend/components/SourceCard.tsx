"use client"

import { memo } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { SourceResult } from "@/types"

export const SourceCard = memo(function SourceCard({
  source,
  index,
}: {
  source: SourceResult
  index: number
}) {
  const matchingTexts = (source.matched_text || [])
    .map((segment) =>
      typeof segment === "string"
        ? { source_excerpt: segment, text_excerpt: "", matched_phrase: "" }
        : {
            matched_phrase: segment.matched_phrase,
            source_excerpt: segment.source_excerpt,
            text_excerpt: segment.text_excerpt,
          }
    )
    .filter((segment) => segment.source_excerpt && (segment.matched_phrase || segment.text_excerpt))
    .slice(0, 3)

  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gray-100 text-xs font-medium text-gray-600">
                {index + 1}
              </span>
              <p className="truncate text-sm font-medium text-gray-900">
                {source.title || "Sin título"}
              </p>
            </div>
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 block truncate text-xs text-primary-600 hover:underline"
            >
              {source.url}
            </a>
            {source.source_snippet && (
              <p className="mt-2 text-xs text-gray-600 line-clamp-2">
                {source.source_snippet}
              </p>
            )}

            {matchingTexts.length > 0 && (
              <div className="mt-3 space-y-2 rounded-md border border-amber-100 bg-amber-50/60 p-2">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-800">
                  Coincidencias textuales verificadas
                </p>
                {matchingTexts.map((segment, matchIndex) => (
                  <div key={`${source.id}-match-${matchIndex}`} className="rounded border border-amber-200 bg-white p-2">
                    {segment.matched_phrase && (
                      <p className="mb-1 text-[11px] font-medium text-amber-700">
                        Coincidencia clave: "{segment.matched_phrase}"
                      </p>
                    )}
                    <p className="text-xs text-gray-700">"{segment.source_excerpt}"</p>
                    {segment.text_excerpt && (
                      <p className="mt-1 text-[11px] text-gray-500">
                        Similar en tu texto: "{segment.text_excerpt}"
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}

            {matchingTexts.length === 0 && (
              <p className="mt-3 text-[11px] text-gray-500">
                Sin cita textual verificable en esta fuente; se muestra por similitud temática.
              </p>
            )}
          </div>
          <Badge
            variant={
              source.similarity > 50 ? "danger" : source.similarity > 20 ? "warning" : "info"
            }
          >
            {source.similarity}%
          </Badge>
        </div>
      </CardContent>
    </Card>
  )
})
