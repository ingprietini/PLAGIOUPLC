"use client"

import { useState } from "react"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

export function TextImprover() {
  const [text, setText] = useState("")
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const analyzeText = () => {
    if (!text.trim()) return
    setIsAnalyzing(true)

    const words = text.split(/\s+/)
    const sentences = text.split(/[.!?]+/).filter(Boolean)
    const avgWordsPerSentence = words.length / sentences.length

    const newSuggestions: string[] = []

    if (avgWordsPerSentence > 25) {
      newSuggestions.push(
        "Oraciones muy largas (promedio >25 palabras). Divídelas para mejorar claridad."
      )
    }

    if (avgWordsPerSentence < 8) {
      newSuggestions.push(
        "Oraciones muy cortas. Combínalas para mejorar el flujo del texto."
      )
    }

    const passiveCount = (text.match(
      /\b(es|son|fue|fueron|era|eran|sea|sean|sido|siendo)\s+\w+do\b/gi
    ) || []).length
    if (passiveCount > 3) {
      newSuggestions.push(
        `Uso excesivo de voz pasiva (${passiveCount} casos). Prefiere voz activa.`
      )
    }

    const paragraphs = text.split(/\n\s*\n/)
    const longParas = paragraphs.filter((p) => p.split(/\s+/).length > 150)
    if (longParas.length > 0) {
      newSuggestions.push(
        `${longParas.length} párrafo(s) muy extenso(s). Divídelos en secciones más pequeñas.`
      )
    }

    const transitionWords = [
      "sin embargo", "no obstante", "por lo tanto", "además",
      "por otro lado", "en conclusión", "por ejemplo",
    ]
    const transitionCount = transitionWords.filter((tw) =>
      text.toLowerCase().includes(tw)
    ).length
    if (transitionCount < 2 && sentences.length > 5) {
      newSuggestions.push(
        "Faltan palabras de transición. Usa conectores como 'sin embargo', 'además', 'por lo tanto'."
      )
    }

    const wordFreq: Record<string, number> = {}
    words.forEach((w) => {
      const clean = w.toLowerCase().replace(/[^a-záéíóúüñ]/g, "")
      if (clean.length > 3) wordFreq[clean] = (wordFreq[clean] || 0) + 1
    })
    const overused = Object.entries(wordFreq)
      .filter(([, count]) => count > words.length * 0.03 && count > 3)
      .map(([word]) => word)
    if (overused.length > 0) {
      newSuggestions.push(
        `Palabras sobreutilizadas: ${overused.slice(0, 3).join(", ")}. Usa sinónimos.`
      )
    }

    if (newSuggestions.length === 0) {
      newSuggestions.push("El texto tiene buena estructura y legibilidad general.")
    }

    setSuggestions(newSuggestions)
    setIsAnalyzing(false)
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Mejorar texto</h3>
          <Button onClick={analyzeText} disabled={!text.trim()} loading={isAnalyzing} size="sm">
            Analizar
          </Button>
        </div>
        <p className="text-sm text-gray-500">
          Pega tu texto para obtener sugerencias de mejora de estilo y estructura.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Pega aquí tu texto para analizar..."
          rows={8}
          className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 resize-y"
        />

        {suggestions.length > 0 && (
          <div className="space-y-3">
            <p className="text-sm font-medium text-gray-700">
              Sugerencias ({suggestions.length})
            </p>
            {suggestions.map((sg, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded-lg border border-gray-100 bg-gray-50 p-3"
              >
                <Badge variant={sg.includes("extenso") || sg.includes("excesivo") ? "warning" : "info"}>
                  {i + 1}
                </Badge>
                <p className="text-sm text-gray-700">{sg}</p>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
