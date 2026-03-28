import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { BarChart3, AlertTriangle, Lightbulb, ListChecks, MessageSquareQuote, TrendingDown } from "lucide-react"
import type { StudyReport, SegmentFingerprint, StopRiskCohort, CrossVideoInsight } from "@/types/analysis"

function pct(value: number | null): string {
  if (value == null) return "—"
  return `${(value * 100).toFixed(0)}%`
}

function num(value: number | null, decimals = 1): string {
  if (value == null) return "—"
  return value.toFixed(decimals)
}

function sentimentColor(value: number | null): string {
  if (value == null) return "text-muted-foreground"
  if (value >= 3) return "text-emerald-600"
  if (value >= 0) return "text-lime-600"
  if (value >= -3) return "text-amber-600"
  return "text-rose-600"
}

const CONFIDENCE_COLORS: Record<string, string> = {
  strong: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
  moderate: "bg-amber-500/10 text-amber-600 border-amber-500/20",
  suggestive: "bg-blue-500/10 text-blue-600 border-blue-500/20",
}

function SegmentTable({ fingerprints }: { fingerprints: SegmentFingerprint[] }) {
  if (fingerprints.length === 0) return null

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-2 text-left font-medium">Segment</th>
            <th className="px-2 py-2 text-right font-medium">Sessions</th>
            <th className="px-2 py-2 text-right font-medium">Friction</th>
            <th className="px-2 py-2 text-right font-medium">Delight</th>
            <th className="px-2 py-2 text-right font-medium">Sentiment</th>
            <th className="px-2 py-2 text-right font-medium">1st Fail</th>
            <th className="px-2 py-2 text-right font-medium">Avg Retries</th>
            <th className="px-2 py-2 text-right font-medium">Quit Rate</th>
          </tr>
        </thead>
        <tbody>
          {fingerprints.map((fp) => (
            <tr key={fp.segment_label} className="border-b last:border-0 hover:bg-muted/30">
              <td className="px-3 py-2 font-mono font-medium">{fp.segment_label.replace(/_/g, " ")}</td>
              <td className="px-2 py-2 text-right">{fp.sessions_encountered}</td>
              <td className={cn("px-2 py-2 text-right", fp.friction_rate >= 0.5 ? "font-medium text-rose-600" : "")}>
                {pct(fp.friction_rate)}
              </td>
              <td className={cn("px-2 py-2 text-right", fp.delight_rate >= 0.7 ? "font-medium text-emerald-600" : "")}>
                {pct(fp.delight_rate)}
              </td>
              <td className={cn("px-2 py-2 text-right font-mono", sentimentColor(fp.avg_sentiment))}>
                {fp.avg_sentiment != null ? (fp.avg_sentiment > 0 ? "+" : "") + num(fp.avg_sentiment) : "—"}
              </td>
              <td className={cn("px-2 py-2 text-right", (fp.first_attempt_failure_rate ?? 0) >= 0.5 ? "font-medium text-rose-600" : "")}>
                {pct(fp.first_attempt_failure_rate)}
              </td>
              <td className="px-2 py-2 text-right">{num(fp.avg_retry_attempts)}</td>
              <td className={cn("px-2 py-2 text-right", (fp.quit_signal_rate ?? 0) >= 0.1 ? "font-medium text-rose-600" : "")}>
                {pct(fp.quit_signal_rate)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function StopRiskSection({ cohorts }: { cohorts: StopRiskCohort[] }) {
  if (cohorts.length === 0) return null

  return (
    <div>
      <div className="mb-2 flex items-center gap-1.5">
        <TrendingDown className="h-3.5 w-3.5 text-rose-500" />
        <h4 className="text-xs font-medium text-muted-foreground">Stop-Risk Cohorts</h4>
      </div>
      <div className="space-y-2">
        {cohorts.map((c) => (
          <div key={c.trigger_segment} className="rounded-lg border border-rose-200 bg-rose-50/50 p-3 dark:border-rose-900 dark:bg-rose-950/30">
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-medium">{c.trigger_segment.replace(/_/g, " ")}</span>
              <Badge variant="destructive" className="text-[10px]">
                {c.percentage.toFixed(0)}% of sessions
              </Badge>
              <span className="text-xs text-muted-foreground">
                ({c.sessions_affected}/{c.total_sessions})
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{c.common_pattern}</p>
            {c.representative_quotes.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {c.representative_quotes.slice(0, 3).map((q, i) => (
                  <span key={i} className="rounded bg-background px-2 py-0.5 text-[10px] italic">&ldquo;{q}&rdquo;</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function InsightsSection({ insights }: { insights: CrossVideoInsight[] }) {
  if (insights.length === 0) return null

  return (
    <div>
      <div className="mb-2 flex items-center gap-1.5">
        <Lightbulb className="h-3.5 w-3.5 text-primary" />
        <h4 className="text-xs font-medium text-muted-foreground">Cross-Video Insights</h4>
      </div>
      <div className="space-y-3">
        {insights.map((insight, i) => (
          <div key={i} className="rounded-lg border p-4">
            <div className="flex items-center gap-2">
              <h5 className="text-sm font-semibold">{insight.title}</h5>
              <Badge variant="outline" className={cn("text-[10px] capitalize", CONFIDENCE_COLORS[insight.confidence])}>
                {insight.confidence}
              </Badge>
              <span className="text-[10px] text-muted-foreground">{insight.sessions_supporting} sessions</span>
            </div>
            <p className="mt-2 text-sm leading-relaxed">{insight.insight}</p>
            <p className="mt-1.5 text-xs text-muted-foreground">{insight.evidence_summary}</p>
            <p className="mt-1.5 text-xs font-medium text-primary">{insight.recommended_action}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

export function StudyView({ study }: { study: StudyReport }) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <BarChart3 className="h-5 w-5 text-primary" />
        <div>
          <h2 className="text-lg font-semibold">{study.game_title} — Cross-Video Study</h2>
          <p className="text-xs text-muted-foreground">
            {study.total_sessions} sessions &middot; {study.total_duration_minutes.toFixed(0)} min total
          </p>
        </div>
      </div>

      {/* Executive summary */}
      {study.executive_summary && (
        <div className="space-y-2 rounded-xl border p-4 text-sm leading-relaxed text-muted-foreground">
          {study.executive_summary.split("\n\n").map((para, i) => (
            <p key={i}>{para}</p>
          ))}
        </div>
      )}

      {/* Top priorities */}
      {study.top_priorities.length > 0 && (
        <div className="rounded-xl border p-4">
          <div className="mb-2 flex items-center gap-1.5">
            <ListChecks className="h-3.5 w-3.5 text-primary" />
            <h4 className="text-xs font-medium text-muted-foreground">Top Priorities</h4>
          </div>
          <ol className="space-y-1 text-sm">
            {study.top_priorities.map((action, i) => (
              <li key={i} className="flex gap-2">
                <span className="shrink-0 font-mono text-xs text-muted-foreground">{i + 1}.</span>
                {action}
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Segment fingerprints */}
      {study.segment_fingerprints.length > 0 && (
        <div>
          <div className="mb-2 flex items-center gap-1.5">
            <MessageSquareQuote className="h-3.5 w-3.5 text-muted-foreground" />
            <h4 className="text-xs font-medium text-muted-foreground">
              Segment Analysis ({study.segment_fingerprints.length} segments)
            </h4>
          </div>
          <SegmentTable fingerprints={study.segment_fingerprints} />
        </div>
      )}

      <StopRiskSection cohorts={study.stop_risk_cohorts} />
      <InsightsSection insights={study.insights} />
    </div>
  )
}
