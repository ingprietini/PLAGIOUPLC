import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" })

export const metadata: Metadata = {
  title: "AntiPlagio - Detector de Plagio Inteligente",
  description:
    "Analiza textos largos, detecta plagio, obtén estadísticas, fuentes y sugerencias para mejorar tu escritura con formato APA/MLA.",
  keywords: ["plagio", "detector de plagio", "antiplagio", "apa", "formato apa", "originalidad"],
  openGraph: {
    title: "AntiPlagio - Detector de Plagio Inteligente",
    description:
      "Analiza textos de hasta 100,000 palabras. Detecta plagio, encuentra fuentes, mejora tu escritura.",
    type: "website",
  },
}

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "AntiPlagio",
  applicationCategory: "EducationalApplication",
  operatingSystem: "Web",
  description:
    "Detector de plagio inteligente con análisis de similitud, búsqueda web, sugerencias de mejora y formato APA/MLA.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={inter.variable}>
      <body className="font-sans antialiased">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <nav className="border-b border-gray-200 bg-white">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="flex h-16 items-center justify-between">
              <a href="/" className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600 text-white text-sm font-bold">
                  AP
                </div>
                <span className="text-xl font-bold text-gray-900">AntiPlagio</span>
              </a>
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <a href="/" className="hover:text-gray-900">Inicio</a>
                <a href="/analyze" className="hover:text-gray-900">Analizar</a>
              </div>
            </div>
          </div>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  )
}
