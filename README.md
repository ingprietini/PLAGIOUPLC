# AntiPlagio

Detector de plagio inteligente para textos largos (hasta 100,000 palabras). Analiza similitudes, busca fuentes en web, detecta texto generado por IA, genera estadísticas de legibilidad y produce citas en formato APA/MLA/Chicago.

---

## Tabla de contenidos

- [Stack tecnológico](#stack-tecnológico)
- [Quick start](#quick-start)
- [Arquitectura](#arquitectura)
- [Uso](#uso)
- [API REST](#api-rest)
- [Descarga de informes](#descarga-de-informes)
- [WebSocket](#websocket--progreso-en-tiempo-real)
- [Motores de análisis](#motores-de-análisis)
- [Configuración](#configuración)
- [Solución de problemas](#solución-de-problemas)
- [Estructura del proyecto](#estructura-del-proyecto)

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Frontend | Next.js 14 (App Router, React, TypeScript, Tailwind CSS) |
| Backend | Python 3.14+ — FastAPI, SQLAlchemy, scikit-learn |
| Base de datos | SQLite |
| Búsqueda web | DuckDuckGo (gratis, sin API key) o Google Custom Search |
| Detección de IA | lmscan — análisis estadístico offline (25 features, 9 LLMs) |
| Archivos | pdfplumber (PDF), python-docx (DOCX/DOC), zipfile+xml (ODT) |

---

## Quick start

```bash
# Instalar dependencias del frontend
pnpm --dir frontend install

# Instalar dependencias del backend
python -m pip install -r backend/requirements.txt
```

Inicia el backend desde la carpeta `backend`:

```powershell
cd backend
python -m uvicorn main:app --reload --port 8000
```

En otra terminal inicia el frontend:

```powershell
cd frontend
pnpm dev
```

Abre [http://localhost:3000](http://localhost:3000). La API queda disponible en
[http://localhost:8000](http://localhost:8000).

También hay scripts en el `package.json` raíz: `pnpm frontend`, `pnpm backend`,
`pnpm dev` y `pnpm build`. Para desarrollo en Windows se recomienda ejecutar frontend
y backend en terminales separadas con los comandos anteriores.

---

## Arquitectura

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js :3000)                                        │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌───────────┐  │
│  │ Upload   │  │ Analysis     │  │ Results    │  │ Citas     │  │
│  │ + Text   │  │ Progress     │  │ Dashboard  │  │ APA/MLA/  │  │
│  │          │  │ (WebSocket)  │  │            │  │ Chicago   │  │
│  └────┬─────┘  └──────┬───────┘  └─────┬──────┘  └─────┬─────┘  │
│       └───────────────┴────────────────┴───────────────┘         │
│                           │ REST + WS                           │
└───────────────────────────┼──────────────────────────────────────┘
                            │
┌───────────────────────────┼──────────────────────────────────────┐
│  Backend (FastAPI :8000)  ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  POST /api/analyze  │  POST /api/upload                  │   │
│  │  GET  /api/analyze/{id}  │  WS /ws/analyze/{id}         │   │
│  │  POST /api/format/citation  │  GET /api/styles           │   │
│  │  GET .../report/pdf|docx                                  │   │
│  │  GET  /api/health                                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────┴──────────────────────────────────┐  │
│  │  Procesamiento                                             │  │
│  │  ┌──────────┐  ┌──────────┐  ┌────────┐  ┌───────────┐   │  │
│  │  │Lectura   │  │Detección │  │Motores │  │Generación │   │  │
│  │  │archivos  │  │de IA     │  │plagio  │  │citas      │   │  │
│  │  │(txt/pdf/ │  │(lmscan)  │  │(Winnow │  │(APA/MLA/  │   │  │
│  │  │ docx/odt)│  │          │  │+TF-IDF)│  │ Chicago)  │   │  │
│  │  └──────────┘  └──────────┘  └────────┘  └───────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                           │                                      │
│  ┌────────────────────────┴──────────────────────────────────┐  │
│  │  Búsqueda web (DuckDuckGo / Google)                       │  │
│  │  → consulta por fragmentos, normalización de URLs,       │  │
│  │    hidratación HTML, límite de concurrencia y timeouts     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                           │                                      │
│  ┌────────────────────────┴──────────────────────────────────┐  │
│  │  SQLite (SQLAlchemy)                                      │  │
│  │  analyses │ sources │ suggestions                         │  │
│  └───────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Uso

1. **Subir archivo** — arrastrá o seleccioná `.txt`, `.pdf`, `.docx`, `.doc` u `.odt`
2. **Pegar texto** — escribí o pegá el texto (mín. 50 palabras, máx. 100k)
3. **Analizar** — el backend procesa en tiempo real con WebSocket (legibilidad → detección IA → búsqueda web → winnowing → TF-IDF → sugerencias)
4. **Resultados** — similitud global, métricas de legibilidad, detección estadística de IA, fuentes separadas entre coincidencias textuales verificadas y similitud temática, y sugerencias con ejemplos.
5. **Exportar** — descarga el informe completo como PDF o DOCX desde la página de resultados.
6. **Citas y mejora** — usa el generador de citas APA 7.ª, MLA 9.ª o Chicago 17.ª, y el mejorador de texto independiente.

---

## API REST

### `POST /api/analyze`

Enviar texto para análisis.

**Request** (`multipart/form-data`):

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `text` | string | sí | Texto a analizar (50–100k palabras) |
| `title` | string | no | Título opcional del análisis |

**Response** `200`:

```json
{
  "status": "ok",
  "id": "uuid-del-analisis",
  "word_count": 1234
}
```

**Errors**: `400` si el texto excede 100k palabras o tiene menos de 50.

---

### `POST /api/upload`

Subir archivo para análisis. El backend extrae el texto y lo almacena.

**Request** (`multipart/form-data`):

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `file` | file | sí | `.txt`, `.pdf`, `.docx`, `.doc`, `.odt` (máx. 50 MB) |

**Response** `200`:

```json
{
  "status": "ok",
  "id": "uuid-del-analisis",
  "word_count": 1234,
  "filename": "documento.pdf"
}
```

---

### `GET /api/analyze/{id}`

Obtener resultados completos de un análisis.

**Response** `200`:

```json
{
  "id": "uuid",
  "title": "Título del análisis",
  "word_count": 1234,
  "status": "completed",
  "progress": 100,
  "error": null,
  "stats": {
    "overall_similarity": 15.3,
    "max_similarity": 24.1,
    "avg_similarity": 8.2,
    "sources_above_threshold": 3,
    "total_sources": 12,
    "unique_sources": 8,
    "sources_checked": 34,
    "word_count": 1234,
    "readability": { "...": "..." },
    "ai_detection": { "...": "..." }
  },
  "sources": [
    {
      "id": "uuid",
      "url": "https://ejemplo.com",
      "title": "Página encontrada",
      "similarity": 24.1,
      "matched_text": [
        {
          "matched_phrase": "frase coincidente",
          "source_excerpt": "Fragmento de la página de origen",
          "text_excerpt": "Fragmento correspondiente del texto analizado"
        }
      ],
      "source_snippet": "Resumen devuelto por el buscador",
      "match_confidence": 0.72,
      "content_quality": 0.81,
      "short_page_penalty": 0,
      "source_word_count": 420
    }
  ],
  "suggestions": [
    {
      "id": "uuid",
      "type": "readability",
      "severity": "medium",
      "suggestion": "Oraciones demasiado largas...",
      "explanation": "Promedio actual: 28 palabras...",
      "improved_example": "Esta es una oración más corta. Y esta es otra."
    }
  ],
  "created_at": "2026-06-20T12:00:00",
  "completed_at": "2026-06-20T12:01:30"
}
```

**Campos de `status`**:

| Valor | Significado |
|---|---|
| `pending` | Creado, no ha comenzado |
| `processing` | En curso (consultar WebSocket para progreso) |
| `completed` | Finalizado correctamente |
| `failed` | Error durante el análisis (`error` contiene el detalle) |

**Campos de `stats`**:

| Campo | Tipo | Descripción |
|---|---|---|
| `overall_similarity` | number | Score compuesto: pico máximo + 2% por cada fuente sobre umbral |
| `max_similarity` | number | Mayor coincidencia individual encontrada |
| `avg_similarity` | number | Promedio de fuentes que superan el umbral de plagio |
| `sources_above_threshold` | number | Fuentes que superan el umbral mínimo de similitud |
| `total_sources` | number | Total de fuentes con cualquier coincidencia |
| `unique_sources` | number | Cantidad de URLs únicas |
| `sources_checked` | number | Fuentes normalizadas incluidas en la comparación |
| `avg_match_confidence` | number | Confianza promedio por fuente, en escala 0–1 |
| `avg_source_content_quality` | number | Calidad promedio del contenido de las fuentes, en escala 0–1 |
| `readability` | object | Métricas Flesch y Coleman-Liau |
| `ai_detection` | object o `null` | Resultado estadístico de detección de IA |

Los registros antiguos siguen siendo compatibles: `matched_text` se devuelve como
una lista de segmentos incluso si el registro guardado usaba el formato legado. Los
campos de métricas de fuente pueden ser `null` en análisis previos a su incorporación.

---

## Descarga de informes

Ambas rutas requieren un análisis existente. La interfaz solo habilita las descargas
cuando el estado es `completed`.

### `GET /api/analyze/{id}/report/pdf`

Descarga un informe PDF con el resumen de métricas, fuentes encontradas, hallazgos y
sugerencias, detalle de coincidencias y el texto original con anotaciones de
coincidencias textuales verificables cuando están disponibles.

**Response**: archivo `application/pdf`.

### `GET /api/analyze/{id}/report/docx`

Descarga un documento Word con el resumen, las fuentes, sugerencias, detalle de
coincidencias y el texto original.

**Response**: archivo
`application/vnd.openxmlformats-officedocument.wordprocessingml.document`.

Las dos rutas devuelven `404` si no existe el identificador. La generación de PDF
requiere `reportlab`, incluido en `backend/requirements.txt`.

---

### `POST /api/format/citation`

Generar una cita en APA, MLA o Chicago.

**Request** (`multipart/form-data`):

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `style` | string | sí | `apa`, `mla` o `chicago` |
| `source_type` | string | sí | `web`, `book` o `journal` |
| `author` | string | no | Autor(es) |
| `title` | string | no | Título |
| `year` | string | no | Año |
| `url` | string | no | URL |
| `publisher` | string | no | Editorial |
| `journal` | string | no | Revista |
| `volume` / `issue` / `pages` | string | no | Datos de publicación |
| `doi` | string | no | DOI |
| `site_name` | string | no | Sitio web |

**Response** `200`:

```json
{
  "status": "ok",
  "citation": "Apellido, A. (2024). Título del artículo...",
  "style": "apa"
}
```

---

### `GET /api/styles`

```json
{
  "status": "ok",
  "styles": {
    "apa": "APA 7ª edición",
    "mla": "MLA 9ª edición",
    "chicago": "Chicago 17ª edición",
    "ieee": "IEEE"
  }
}
```

`GET /api/styles` actualmente también anuncia `ieee`, pero `POST /api/format/citation`
y el selector de la interfaz solo generan APA, MLA y Chicago.

### `GET /api/health`

```json
{
  "status": "ok",
  "timestamp": "2026-06-20T12:00:00"
}
```

---

## WebSocket — Progreso en tiempo real

### `WS /ws/analyze/{id}`

Conectarse después de crear un análisis (`POST /api/analyze` o `POST /api/upload`). El servidor envía mensajes JSON durante todo el proceso.

| Tipo | Cuándo | Contenido |
|---|---|---|
| `status` | Inicio | `{ "type": "status", "status": "processing", "progress": 0, "message": "..." }` |
| `progress` | Cada paso | `{ "type": "progress", "progress": 30, "message": "..." }` |
| `source_checking` | Al comparar cada fuente | `{ "type": "source_checking", "progress": 45, "message": "...", "source": { "index": 1, "total": 10, "url": "...", "title": "..." } }` |
| `complete` | Fin exitoso | `{ "type": "complete", "stats": {...}, "sources_count": N, "suggestions_count": N }` |
| `error` | Error | `{ "type": "error", "message": "..." }` |

**Flujo de progreso**:

```
  0% ── Inicio
  5% ── Legibilidad (Flesch, Coleman-Liau)
  8% ── Detección de IA (lmscan)
 10-24% ─ Búsqueda web e hidratación del contenido de páginas
 30-60% ─ Winnowing (fingerprinting + Jaccard)
 60-75% ─ TF-IDF (similitud coseno)
 75-85% ─ Sugerencias de mejora (con ejemplos)
 85-100% ─ Guardado en base de datos
```

---

## Motores de análisis

### Detección de plagio

| Algoritmo | Técnica | Detecta |
|---|---|---|
| **Winnowing** | Fingerprinting con k-gramas (k=30, w=75) + similitud Jaccard | Copias textuales y casi textuales |
| **TF-IDF** | Vectorización (1-3 gramas) + similitud coseno | Coincidencias conceptuales y parafraseo |
| **Scoring combinado** | `max(winnowing, tfidf) + min(winnowing, tfidf) * 0.3` | Base de similitud; luego se ajusta por calidad del contenido y extensión de la página |

- **Búsqueda web**: genera consultas a partir de fragmentos de oraciones, cláusulas y ventanas deslizantes, y agrega consultas de frases exactas. Por defecto se muestrean hasta 50 fragmentos por estrategia; la concurrencia es de 5 solicitudes, con timeout de 15 segundos por consulta.
- **Normalización de fuentes**: elimina parámetros de consulta y fragmentos de la URL para deduplicar resultados; limpia y limita snippets y contenido.
- **Contenido web**: intenta recuperar y extraer texto HTML de hasta 500 fuentes (configurable); elimina scripts, estilos y texto de boilerplate. Si no se obtiene el HTML, conserva el contenido/snippet del buscador.
- **Verificación**: compara el contenido enriquecido con Winnowing y TF-IDF, incluyendo fuentes con similitud TF-IDF suficiente aunque no tengan coincidencias textuales verificables.
- **Métricas por fuente**: `raw_similarity`, `match_confidence` (0–1), `content_quality` (0–1), `short_page_penalty` (0–0.45) y `source_word_count`. La similitud mostrada se ajusta por calidad y longitud; una similitud temática no implica una coincidencia textual.
- **Stop words**: selección heurística entre español e inglés para TF-IDF.

### Detección de texto generado por IA

Usa **lmscan** — biblioteca open-source Apache 2.0 que evalúa 25 features estadísticos:

- Burstiness (variación en longitud de oraciones)
- Entropía del texto y entropía de caracteres
- Desviación de la ley de Zipf
- Densidad de "slop words" y marcadores de chatbot
- Diversidad de vocabulario (hapax legomena, lexical density)
- Repetición de n-gramas (bigramas, trigramas, long n-gramas)
- Ratio de voz pasiva, conectores, hedging, contracciones
- Densidad de patrones de lista y diversidad de aperturas de oraciones

Atribuye el texto a modelos/familias cuando la biblioteca proporciona esa información. El resultado incluye probabilidad base y ajustada, veredicto, confianza, indicadores, tiempo de análisis y atribución por modelo.

> **Limitación**: es detección estadística, no un clasificador neuronal. Textos académicos formales o muy estructurados pueden generar falsos positivos.

### Sugerencias de mejora

Cada sugerencia incluye un **ejemplo mejorado** generado automáticamente a partir del texto real del usuario:

| Problema | Ejemplo generado |
|---|---|
| Oraciones >25 palabras | Divide la primera oración larga por su conjunción central |
| Oraciones <10 palabras | Combina 2 oraciones cortas consecutivas con ", y" |
| Voz pasiva excesiva | Convierte "fue realizado" → "se realizó" |
| Párrafo >150 palabras | Parte el párrafo por la mitad |
| Faltan transiciones | Re-escribe añadiendo "Además", "Por otro lado", "En conclusión" |
| Palabras sobreutilizadas | Muestra la palabra repetida en contexto |

---

## Configuración

### Variables de entorno

Crear `backend/.env` (opcional, todo tiene defaults):

```
# Motor de búsqueda (default: duckduckgo)
SEARCH_ENGINE=google
GOOGLE_API_KEY=tu_api_key
GOOGLE_CSE_ID=tu_cse_id

# Base de datos
DATABASE_URL=sqlite:///./data/antiplagio.db
```

| Variable | Default | Descripción |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/antiplagio.db` | Ruta de la base de datos SQLite |
| `SEARCH_ENGINE` | `duckduckgo` | Motor: `duckduckgo` o `google` |
| `GOOGLE_API_KEY` | — | API key de Google Custom Search |
| `GOOGLE_CSE_ID` | — | ID del motor de Google |
| `MAX_SOURCES_TO_CHECK` | `500` | Límite superior para resultados del buscador y páginas a hidratar; la normalización limita actualmente la lista a 50 fuentes |
| `MAX_CHUNKS_TO_SEARCH` | `50` | Máximo de fragmentos muestreados por estrategia de búsqueda |
| `MAX_KEY_PHRASES_PER_CHUNK` | `4` | Máximo de frases clave por fragmento |
| `MAX_RESULTS_PER_QUERY` | `5` | Resultados pedidos al buscador por consulta |

`SEARCH_ENGINE`, `GOOGLE_API_KEY` y `GOOGLE_CSE_ID` pueden definirse en
`backend/.env` o en el entorno del proceso. Google Custom Search requiere credenciales;
DuckDuckGo es el valor predeterminado.

### Parámetros de detección (en `config.py`)

| Parámetro | Default | Efecto |
|---|---|---|
| `WINNOWING_K` | 30 | Tamaño del k-grama (menor = más sensible) |
| `WINNOWING_W` | 75 | Ventana de selección de fingerprints (menor = más fingerprints) |
| `SIMILARITY_THRESHOLD` | 0.15 | Umbral mínimo para considerar plagio |
| `CHUNK_SIZE` | 500 | Tamaño de fragmento para búsqueda web |
| `MAX_WORD_LIMIT` | 100000 | Límite máximo de palabras por análisis |
| `MAX_UPLOAD_SIZE` | 50 MB | Tamaño máximo del archivo cargado |
| `SEARCH_DELAY` | 0.5 s | Pausa entre solicitudes de búsqueda |

---

## Solución de problemas

| Problema | Causa | Solución |
|---|---|---|
| `table X has no column named Y` | La DB fue creada con un esquema anterior | Verifica qué base de datos está usando `DATABASE_URL` y aplica la migración correspondiente antes de borrar datos. Las métricas nuevas de fuente se guardan en el campo JSON existente, sin requerir columnas nuevas. |
| `PendingRollbackError` | Una transacción falló y no se hizo rollback | El servidor ya maneja esto automáticamente con `db.rollback()` |
| Búsqueda web lenta | DuckDuckGo puede rate-limit | Esperar unos minutos, o configurar Google Custom Search |
| WebSocket se cierra sin mensajes | Timeout en búsqueda web | Cada consulta tiene timeout de 15s; las que exceden se saltan |
| `uvicorn` no encontrado | Python Scripts no está en PATH | Usar `$env:PATH = "...;$env:PATH"` o la ruta absoluta |
| Detección de IA da falso positivo | Texto académico formal | Es esperado; la card muestra una advertencia al usuario |
| No aparece una coincidencia textual en una fuente | La fuente fue incluida por similitud temática o el buscador no proporcionó texto verificable | Revisa la tarjeta como fuente relacionada; no se presenta como cita textual comprobada |
| No se descarga el PDF | `reportlab` no está instalado o el análisis aún no terminó | Instala `backend/requirements.txt` y descarga cuando el estado sea `completed` |

---

## Estructura del proyecto

```
PageAntiplagio/
├── frontend/                    # Next.js 14
│   ├── app/
│   │   ├── analyze/page.tsx     # Página de análisis
│   │   └── results/[id]/page.tsx # Resultados
│   ├── components/
│   │   ├── AiDetectionCard.tsx
│   │   ├── AnalysisProgress.tsx
│   │   ├── ApaFormatter.tsx
│   │   ├── PlagiarismStats.tsx
│   │   ├── ResultsDashboard.tsx
│   │   ├── SourceCard.tsx
│   │   ├── TextImprover.tsx
│   │   ├── TextUpload.tsx
│   │   └── ui/                  # Componentes base (Button, Card, Badge...)
│   ├── lib/
│   │   └── api.ts               # Cliente HTTP, WebSocket y URL de informes
│   └── types/index.ts
├── backend/
│   ├── main.py                  # FastAPI (rutas + WebSocket)
│   ├── config.py                # Parámetros de configuración
│   ├── models/database.py       # SQLAlchemy (Analysis, Source, Suggestion)
│   ├── parser.py                # Extracción de texto (pdf, docx, odt)
│   ├── plagiarism/
│   │   ├── winnowing.py         # Fingerprinting, Jaccard y segmentos coincidentes
│   │   ├── tfidf.py             # TF-IDF + coseno + detección de idioma
│   │   ├── search.py            # Búsqueda, extracción HTML y muestreo
│   │   ├── source_normalizer.py # Limpieza y deduplicación de fuentes
│   │   ├── source_metrics.py    # Calidad, penalización y confianza
│   │   └── scoring.py           # Ranking de fuentes y estadísticas
│   ├── nlp/
│   │   ├── readability.py       # Flesch, Coleman-Liau
│   │   └── suggestions.py       # Sugerencias con ejemplos mejorados
│   ├── ai_detector/
│   │   └── detector.py          # Wrapper de lmscan
│   └── apa/
│       └── formatter.py         # APA/MLA/Chicago
├── data/
│   └── antiplagio.db             # Base de datos SQLite (si se usa esta ruta)
└── README.md
```

La base de datos por defecto se configura en `backend/config.py` como
`sqlite:///./data/antiplagio.db`; la ruta relativa se resuelve desde el directorio
de ejecución del backend.

---

## Licencia

MIT
