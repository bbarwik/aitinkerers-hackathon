import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { Activity, AlertTriangle, Lightbulb, ListChecks } from "lucide-react"
import type { ExecutiveSummary as ExecutiveSummaryType } from "@/types/analysis"

function HealthGauge({ score }: { score: number }) {
  const color =
    score >= 90 ? "text-emerald-500" :
    score >= 70 ? "text-lime-500" :
    score >= 50 ? "text-amber-500" :
    score >= 30 ? "text-orange-500" :
    "text-rose-500"

  const bgColor =
    score >= 90 ? "bg-emerald-500" :
    score >= 70 ? "bg-lime-500" :
    score >= 50 ? "bg-amber-500" :
    score >= 30 ? "bg-orange-500" :
    "bg-rose-500"

  return (
    <div className="flex items-center gap-3">
      <div className="relative h-16 w-16">
        <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90">
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="currentColor" strokeWidth="3" className="text-muted" />
          <circle
            cx="18" cy="18" r="15.5" fill="none" stroke="currentColor" strokeWidth="3"
            strokeDasharray={`${score * 0.974} 100`}
            strokeLinecap="round"
            className={color}
          />
        </svg>
        <span className={cn("absolute inset-0 flex items-center justify-center text-lg font-bold", color)}>
          {score}
        </span>
      </div>
      <div>
        <div className="text-xs font-medium text-muted-foreground">Session Health</div>
        <div className="flex items-center gap-1.5">
          <div className={cn("h-2 w-2 rounded-full", bgColor)} />
          <span className="text-sm font-medium">
            {score >= 90 ? "Excellent" : score >= 70 ? "Good" : score >= 50 ? "Issues Found" : score >= 30 ? "Significant Issues" : "Critical"}
          </span>
        </div>
      </div>
    </div>
  )
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-rose-500/10 text-rose-600 border-rose-500/20",
  important: "bg-amber-500/10 text-amber-600 border-amber-500/20",
  notable: "bg-blue-500/10 text-blue-600 border-blue-500/20",
}

export function ExecutiveSummaryView({ summary }: { summary: ExecutiveSummaryType }) {
  return (
    <div className="space-y-5 rounded-xl border p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold">Executive Summary</h3>
        </div>
        <HealthGauge score={summary.session_health_score} />
      </div>

      {/* 3-paragraph summary */}
      <div className="space-y-2 text-sm leading-relaxed text-muted-foreground">
        {summary.executive_summary.split("\n\n").map((para, i) => (
          <p key={i}>{para}</p>
        ))}
      </div>

      {/* Key findings */}
      {summary.key_findings.length > 0 && (
        <div>
          <div className="mb-2 flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
            <h4 className="text-xs font-medium text-muted-foreground">Key Findings</h4>
          </div>
          <div className="space-y-2">
            {summary.key_findings.map((finding, i) => (
              <div key={i} className="rounded-lg border p-3">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className={cn("text-[10px] capitalize", SEVERITY_COLORS[finding.severity])}>
                    {finding.severity}
                  </Badge>
                  {finding.affected_timestamps.length > 0 && (
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {finding.affected_timestamps.slice(0, 3).join(", ")}
                    </span>
                  )}
                </div>
                <p className="mt-1.5 text-sm font-medium">{finding.finding}</p>
                <p className="mt-1 text-xs text-muted-foreground">{finding.evidence_summary}</p>
                <p className="mt-1 text-xs text-primary">{finding.recommended_action}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Priority actions */}
      {summary.priority_actions.length > 0 && (
        <div>
          <div className="mb-1.5 flex items-center gap-1.5">
            <ListChecks className="h-3.5 w-3.5 text-primary" />
            <h4 className="text-xs font-medium text-muted-foreground">Priority Actions</h4>
          </div>
          <ol className="space-y-1 text-sm">
            {summary.priority_actions.map((action, i) => (
              <li key={i} className="flex gap-2">
                <span className="shrink-0 font-mono text-xs text-muted-foreground">{i + 1}.</span>
                {action}
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Cross-dimensional insight */}
      {summary.cross_dimensional_insight && (
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
          <div className="mb-1 flex items-center gap-1.5">
            <Lightbulb className="h-3.5 w-3.5 text-primary" />
            <span className="text-xs font-medium text-primary">Cross-Dimensional Insight</span>
          </div>
          <p className="text-sm leading-relaxed">{summary.cross_dimensional_insight}</p>
        </div>
      )}
    </div>
  )
}
