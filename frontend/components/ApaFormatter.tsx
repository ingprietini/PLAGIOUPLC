"use client"

import { useState } from "react"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

const STYLES = [
  { value: "apa", label: "APA 7ª edición" },
  { value: "mla", label: "MLA 9ª edición" },
  { value: "chicago", label: "Chicago 17ª edición" },
]

const SOURCE_TYPES = [
  { value: "web", label: "Sitio web" },
  { value: "book", label: "Libro" },
  { value: "journal", label: "Artículo de revista" },
]

interface FormData {
  style: string
  source_type: string
  author: string
  title: string
  year: string
  url: string
  publisher: string
  journal: string
  volume: string
  issue: string
  pages: string
  doi: string
  site_name: string
}

const initialForm: FormData = {
  style: "apa",
  source_type: "web",
  author: "",
  title: "",
  year: new Date().getFullYear().toString(),
  url: "",
  publisher: "",
  journal: "",
  volume: "",
  issue: "",
  pages: "",
  doi: "",
  site_name: "",
}

export function ApaFormatter() {
  const [form, setForm] = useState<FormData>(initialForm)
  const [citation, setCitation] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)

  const handleChange = (field: keyof FormData, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const generateCitation = async () => {
    setIsGenerating(true)
    setCitation("")

    const params = new URLSearchParams()
    Object.entries(form).forEach(([key, value]) => {
      if (value) params.append(key, value)
    })

    try {
      const res = await fetch("http://localhost:8000/api/format/citation", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: params,
      })

      if (res.ok) {
        const data = await res.json()
        setCitation(data.citation)
      } else {
        setCitation(generateLocalCitation(form))
      }
    } catch {
      setCitation(generateLocalCitation(form))
    }

    setIsGenerating(false)
  }

  return (
    <Card>
      <CardHeader>
        <h3 className="font-semibold text-gray-900">Generar citas APA/MLA/Chicago</h3>
        <p className="text-sm text-gray-500">
          Completa los datos de la fuente para generar una cita en el formato deseado.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Estilo</label>
            <select
              value={form.style}
              onChange={(e) => handleChange("style", e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
            >
              {STYLES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Tipo de fuente</label>
            <select
              value={form.source_type}
              onChange={(e) => handleChange("source_type", e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
            >
              {SOURCE_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Autor</label>
          <input
            type="text"
            value={form.author}
            onChange={(e) => handleChange("author", e.target.value)}
            placeholder="Apellido, Nombre"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Título</label>
          <input
            type="text"
            value={form.title}
            onChange={(e) => handleChange("title", e.target.value)}
            placeholder="Título del artículo/libro/página"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Año</label>
            <input
              type="text"
              value={form.year}
              onChange={(e) => handleChange("year", e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">URL</label>
            <input
              type="text"
              value={form.url}
              onChange={(e) => handleChange("url", e.target.value)}
              placeholder="https://..."
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
            />
          </div>
        </div>

        {form.source_type === "book" && (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Editorial</label>
            <input
              type="text"
              value={form.publisher}
              onChange={(e) => handleChange("publisher", e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
            />
          </div>
        )}

        {form.source_type === "journal" && (
          <div className="grid gap-4 sm:grid-cols-4">
            <div className="sm:col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">Revista</label>
              <input
                type="text"
                value={form.journal}
                onChange={(e) => handleChange("journal", e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Volumen</label>
              <input
                type="text"
                value={form.volume}
                onChange={(e) => handleChange("volume", e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Número</label>
              <input
                type="text"
                value={form.issue}
                onChange={(e) => handleChange("issue", e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Páginas</label>
              <input
                type="text"
                value={form.pages}
                onChange={(e) => handleChange("pages", e.target.value)}
                placeholder="123-145"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">DOI</label>
              <input
                type="text"
                value={form.doi}
                onChange={(e) => handleChange("doi", e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              />
            </div>
          </div>
        )}

        <Button onClick={generateCitation} loading={isGenerating} className="w-full">
          Generar cita
        </Button>

        {citation && (
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
            <div className="mb-2 flex items-center gap-2">
              <Badge variant="info">
                {STYLES.find((s) => s.value === form.style)?.label || form.style.toUpperCase()}
              </Badge>
              <span className="text-xs text-gray-500">Cita generada</span>
            </div>
            <p className="text-sm text-gray-800 italic">{citation}</p>
            <Button
              variant="ghost"
              size="sm"
              className="mt-2"
              onClick={() => navigator.clipboard.writeText(citation)}
            >
              Copiar
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function generateLocalCitation(form: FormData): string {
  const { style, source_type, author, title, year, url, publisher, journal, volume, issue, pages, doi, site_name } = form

  if (style === "apa") {
    if (source_type === "web") {
      return `${author || "Autor desconocido"} (${year || "s.f."}). ${title || "Título"}. ${site_name || "Sitio web"}. URL: ${url}`
    }
    if (source_type === "book") {
      return `${author || "Autor desconocido"} (${year || "s.f."}). ${title || "Título"}. ${publisher || "Editorial"}.`
    }
    if (source_type === "journal") {
      return `${author || "Autor desconocido"} (${year || "s.f."}). ${title || "Título"}. ${journal || "Revista"}${volume ? `, ${volume}` : ""}${issue ? `(${issue})` : ""}${pages ? `, ${pages}` : ""}.${doi ? ` https://doi.org/${doi}` : ""}`
    }
  }

  if (style === "mla") {
    if (source_type === "web") {
      return `${author || "Autor desconocido"}. "${title || "Título"}." ${site_name || "Sitio web"}, ${year || "s.f."}, ${url}.`
    }
    if (source_type === "book") {
      return `${author || "Autor desconocido"}. ${title || "Título"}. ${publisher || "Editorial"}, ${year || "s.f."}.`
    }
    if (source_type === "journal") {
      return `${author || "Autor desconocido"}. "${title || "Título"}." ${journal || "Revista"}, vol. ${volume || "?"}, no. ${issue || "?"}, ${year || "s.f."}, pp. ${pages || "?"}.`
    }
  }

  if (style === "chicago") {
    if (source_type === "web") {
      return `${author || "Autor desconocido"}. "${title || "Título"}." Último acceso. ${url}.`
    }
  }

  return `${author || "Autor"}. (${year || "s.f."}). ${title || "Título"}.`
}
