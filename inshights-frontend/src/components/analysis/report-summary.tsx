import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { AnalysisReport } from "@/types/analysis"

const STAT_COLORS: Record<string, string> = {
  rose: "bg-rose-500/10 text-rose-600 dark:text-rose-400",
  emerald: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  amber: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  orange: "bg-orange-500/10 text-orange-600 dark:text-orange-400",
  indigo: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  purple: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
  cyan: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400",
}

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className={cn("rounded-lg px-3 py-2 text-center", STAT_COLORS[color])}>
      <div className="text-[10px] font-medium uppercase tracking-wide opacity-70">{label}</div>
      <div className="text-sm font-semibold capitalize">{value}</div>
    </div>
  )
}

function SentimentBar({ label, value }: { label: string; value: number }) {
  const pct = ((value + 10) / 20) * 100 // -10..+10 → 0..100%
  const isPositive = value > 0
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-28 truncate text-muted-foreground">{label}</span>
      <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-muted">
        <div className="absolute left-1/2 top-0 h-full w-px bg-border" />
        <div
          className={cn("absolute top-0 h-full rounded-full", isPositive ? "bg-emerald-500" : "bg-rose-500")}
          style={
            isPositive
              ? { left: "50%", width: `${(value / 10) * 50}%` }
              : { right: "50%", width: `${(Math.abs(value) / 10) * 50}%` }
          }
        />
      </div>
      <span className={cn("w-8 text-right font-mono font-medium", isPositive ? "text-emerald-600" : "text-rose-600")}>
        {value > 0 ? "+" : ""}{value.toFixed(1)}
      </span>
    </div>
  )
}

export function ReportSummary({ report }: { report: AnalysisReport }) {
  const hasSegmentSentiment = Object.keys(report.sentiment_by_segment).length > 0

  return (
    <div className="space-y-4 rounded-xl border p-4">
      <h3 className="text-sm font-semibold">Analysis Summary</h3>

      {/* Core stats */}
      <div className="flex flex-wrap gap-2">
        <StatCard label="Friction" value={report.overall_friction} color="rose" />
        <StatCard label="Engagement" value={report.overall_engagement} color="emerald" />
        <StatCard label="Stop Risk" value={report.overall_stop_risk} color="amber" />
        <StatCard label="Bugs" value={String(report.bug_count)} color="orange" />
        {report.avg_sentiment != null && (
          <StatCard
            label="Avg Sentiment"
            value={`${report.avg_sentiment > 0 ? "+" : ""}${report.avg_sentiment.toFixed(1)}`}
            color="indigo"
          />
        )}
        {report.total_retry_sequences > 0 && (
          <StatCard label="Retry Loops" value={String(report.total_retry_sequences)} color="purple" />
        )}
        {report.first_attempt_failure_count > 0 && (
          <StatCard label="1st-Try Fails" value={String(report.first_attempt_failure_count)} color="purple" />
        )}
      </div>

      {report.session_arc && <p className="text-sm leading-relaxed text-muted-foreground">{report.session_arc}</p>}

      {/* Sentiment by segment */}
      {hasSegmentSentiment && (
        <div>
          <h4 className="mb-2 text-xs font-medium text-muted-foreground">Sentiment by Segment</h4>
          <div className="space-y-1.5">
            {Object.entries(report.sentiment_by_segment)
              .sort(([, a], [, b]) => a - b)
              .map(([segment, value]) => (
                <SentimentBar key={segment} label={segment.replace(/_/g, " ")} value={value} />
              ))}
          </div>
        </div>
      )}

      {/* Notable quotes */}
      {report.notable_quotes.length > 0 && (
        <div>
          <h4 className="mb-1.5 text-xs font-medium text-muted-foreground">Notable Player Quotes</h4>
          <ul className="space-y-1">
            {report.notable_quotes.map((quote, i) => (
              <li key={i} className="flex gap-2 text-sm italic text-cyan-600 dark:text-cyan-400">
                <span className="shrink-0">&ldquo;</span>
                <span>{quote}&rdquo;</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Recommendations */}
      {report.recommendations.length > 0 && (
        <div>
          <h4 className="mb-1.5 text-xs font-medium text-muted-foreground">Recommendations</h4>
          <ul className="space-y-1">
            {report.recommendations.map((rec, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="shrink-0 text-muted-foreground">-</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Tags */}
      <div className="flex flex-wrap gap-4">
        {report.top_praised_features.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted-foreground">Praised:</span>
            {report.top_praised_features.map((f) => (
              <Badge key={f} variant="secondary" className="bg-emerald-500/10 text-[10px] text-emerald-600">
                {f}
              </Badge>
            ))}
          </div>
        )}
        {report.top_stop_risk_drivers.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted-foreground">Stop risks:</span>
            {report.top_stop_risk_drivers.map((f) => (
              <Badge key={f} variant="secondary" className="bg-rose-500/10 text-[10px] text-rose-600">
                {f}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
