export type AgentKind = "friction" | "clarity" | "delight" | "quality" | "sentiment" | "retry" | "verbal"

// --- Per-video moment types ---

export type InsightMoment = {
  id: string
  absolute_seconds: number
  timestamp: string
  agent_kind: AgentKind
  summary: string
  game_context: string
  evidence: string[]
  severity_numeric: number
  source_chunk_index: number
  segment_label: string | null
  confidence_score: number
  corroborating_agents: string[]
  // sentiment-specific
  sentiment_raw_score: number | null
  // retry-specific
  retry_total_attempts: number | null
  retry_quit_signal: boolean | null
  retry_final_outcome: string | null
  // verbal-specific
  verbal_is_actionable: boolean | null
  verbal_quote: string | null
}

export type TimelineEvent = {
  absolute_seconds: number
  timestamp: string
  description: string
  phase_kind: string
  significance: string
  segment_label: string
}

export type TimelineChunk = {
  chunk_index: number
  chunk_start_seconds: number
  chunk_end_seconds: number
  chunk_summary: string
  events: TimelineEvent[]
}

export type VideoInfo = {
  video_id: string
  title: string
  url: string
  duration_seconds: number
  chunk_count: number
  platform: "youtube" | "local"
}

// --- Highlights ---

export type HighlightMoment = {
  rank: number
  absolute_timestamp: string
  absolute_seconds: number
  clip_start_seconds: number
  clip_end_seconds: number
  category: string
  headline: string
  why_important: string
  evidence: string[]
  importance_score: number
  corroborating_agents: string[]
}

export type HighlightReel = {
  video_id: string
  total_moments_analyzed: number
  highlights: HighlightMoment[]
  one_line_verdict: string
}

// --- Executive Summary ---

export type KeyFinding = {
  evidence_summary: string
  affected_timestamps: string[]
  finding: string
  recommended_action: string
  severity: string
}

export type ExecutiveSummary = {
  executive_summary: string
  key_findings: KeyFinding[]
  priority_actions: string[]
  cross_dimensional_insight: string
  session_health_score: number
}

// --- Per-chunk agent coverage ---

export type ChunkAgentCoverage = {
  chunk_index: number
  friction: boolean
  clarity: boolean
  delight: boolean
  quality: boolean
  sentiment: boolean
  retry: boolean
  verbal: boolean
}

// --- Video Report (full PLAN_v2 shape) ---

export type AnalysisReport = {
  video_id: string
  filename: string
  duration_seconds: number
  chunk_count: number
  game_title: string
  game_key: string
  session_arc: string
  // moment lists
  friction_moments: InsightMoment[]
  clarity_moments: InsightMoment[]
  delight_moments: InsightMoment[]
  quality_issues: InsightMoment[]
  sentiment_moments: InsightMoment[]
  retry_moments: InsightMoment[]
  verbal_moments: InsightMoment[]
  // original aggregation
  overall_friction: string
  overall_engagement: string
  overall_stop_risk: string
  bug_count: number
  top_stop_risk_drivers: string[]
  top_praised_features: string[]
  top_clarity_fixes: string[]
  recommendations: string[]
  // new aggregation
  avg_sentiment: number | null
  sentiment_by_segment: Record<string, number>
  total_retry_sequences: number
  first_attempt_failure_count: number
  notable_quotes: string[]
  // enriched outputs
  highlights: HighlightReel | null
  executive: ExecutiveSummary | null
  agent_coverage: ChunkAgentCoverage[]
}

// --- Cross-Video Study types ---

export type SegmentFingerprint = {
  segment_label: string
  sessions_encountered: number
  sessions_with_friction: number
  friction_rate: number
  avg_friction_severity: number
  sessions_with_delight: number
  delight_rate: number
  dominant_friction_source: string | null
  dominant_delight_driver: string | null
  avg_sentiment: number | null
  positive_sentiment_rate: number | null
  first_attempt_failure_rate: number | null
  avg_retry_attempts: number | null
  quit_signal_rate: number | null
  representative_quotes: string[]
}

export type StopRiskCohort = {
  trigger_segment: string
  sessions_affected: number
  total_sessions: number
  percentage: number
  common_pattern: string
  representative_quotes: string[]
}

export type CrossVideoInsight = {
  title: string
  insight: string
  evidence_summary: string
  sessions_supporting: number
  confidence: "strong" | "moderate" | "suggestive"
  recommended_action: string
}

export type StudyReport = {
  game_key: string
  game_title: string
  total_sessions: number
  total_duration_minutes: number
  segment_fingerprints: SegmentFingerprint[]
  stop_risk_cohorts: StopRiskCohort[]
  insights: CrossVideoInsight[]
  top_priorities: string[]
  executive_summary: string
}

// --- Batch streaming events (all scoped by video_id) ---

export type BatchStreamEvent =
  | { type: "batch_start"; total: number }
  | { type: "video_start"; video_id: string; index: number; title: string }
  | { type: "progress"; video_id: string; phase: string; message: string }
  | { type: "timeline_chunk"; video_id: string; data: TimelineChunk }
  | { type: "insight"; video_id: string; data: { chunk_index: number; agent_kind: AgentKind; moments: Omit<InsightMoment, "id">[]; chunk_summary: string } }
  | { type: "video_report"; video_id: string; data: AnalysisReport }
  | { type: "video_error"; video_id: string; message: string }
  | { type: "done" }
