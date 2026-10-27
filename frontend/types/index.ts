export interface AnalysisResponse {
  id: string
  status: string
  word_count: number
}

export interface ReadabilityStats {
  word_count: number
  sentence_count: number
  avg_words_per_sentence: number
  avg_chars_per_word: number
  total_syllables: number
  flesch_reading_ease: number
  flesch_kincaid_grade: number
  coleman_liau_index: number
  readability_level: string
}

export interface ModelMatch {
  model: string
  confidence: number
  evidence: string[]
  marker_count: number
}

export interface AiDetectionResult {
  ai_probability: number
  raw_probability: number
  verdict: string
  confidence: string
  flags: string[]
  scan_time_ms: number
  sentence_count: number
  model_attribution: ModelMatch[]
  features?: Record<string, number>
}

export interface AnalysisStats {
  overall_similarity: number
  max_similarity: number
  avg_similarity: number
  total_sources: number
  sources_above_threshold: number
  unique_sources: number
  readability: ReadabilityStats
  ai_detection: AiDetectionResult | null
  word_count: number
  sources_checked: number
}

export interface SourceResult {
  id: string
  url: string
  title: string
  similarity: number
  matched_text: Array<{
    matched_phrase?: string
    source_excerpt?: string
    text_excerpt?: string
    text_pos_start?: number
    text_pos_end?: number
    source_pos_start?: number
    source_pos_end?: number
  } | string>
  source_snippet: string
}

export interface SuggestionResult {
  id: string
  type: string
  severity: string
  suggestion: string
  explanation: string
  improved_example?: string
  original_text?: string
  position_start?: number
  position_end?: number
}

export interface AnalysisResult {
  id: string
  title: string
  word_count: number
  status: string
  progress: number
  error?: string
  stats: AnalysisStats
  sources: SourceResult[]
  suggestions: SuggestionResult[]
  created_at: string
  completed_at: string
}

export interface WSMessage {
  type: "status" | "progress" | "source_checking" | "complete" | "error"
  status?: string
  progress?: number
  message?: string
  source?: {
    index: number
    total: number
    url: string
    title: string
  }
  stats?: AnalysisStats
  sources_count?: number
  suggestions_count?: number
}

export interface CitationRequest {
  style: string
  source_type: string
  author?: string
  title?: string
  year?: string
  url?: string
  publisher?: string
  journal?: string
  volume?: string
  issue?: string
  pages?: string
  doi?: string
  site_name?: string
}
