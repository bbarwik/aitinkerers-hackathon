export type AgentKind = "friction" | "clarity" | "delight" | "quality"

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
  details?: Record<string, unknown>
}

export type TimelineEvent = {
  absolute_seconds: number
  timestamp: string
  description: string
  phase_kind: string
  significance: string
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

export type AnalysisReport = {
  overall_friction: string
  overall_engagement: string
  overall_stop_risk: string
  bug_count: number
  top_stop_risk_drivers: string[]
  top_praised_features: string[]
  top_clarity_fixes: string[]
  recommendations: string[]
  session_arc: string
}

// Batch streaming events — all scoped by video_id
export type BatchStreamEvent =
  | { type: "batch_start"; total: number }
  | { type: "video_start"; video_id: string; index: number; title: string }
  | { type: "progress"; video_id: string; phase: string; message: string }
  | { type: "timeline_chunk"; video_id: string; data: TimelineChunk }
  | { type: "insight"; video_id: string; data: { chunk_index: number; agent_kind: AgentKind; moments: Omit<InsightMoment, "id">[]; chunk_summary: string } }
  | { type: "video_report"; video_id: string; data: AnalysisReport }
  | { type: "video_error"; video_id: string; message: string }
  | { type: "done" }
