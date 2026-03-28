import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { AnalysisReport } from "@/types/analysis"

const STAT_COLORS: Record<string, string> = {
  rose: "bg-rose-500/10 text-rose-600 dark:text-rose-400",
  emerald: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  amber: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  orange: "bg-orange-500/10 text-orange-600 dark:text-orange-400",
}

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className={cn("rounded-lg px-3 py-2 text-center", STAT_COLORS[color])}>
      <div className="text-[10px] font-medium uppercase tracking-wide opacity-70">{label}</div>
      <div className="text-sm font-semibold capitalize">{value}</div>
    </div>
  )
}

export function ReportSummary({ report }: { report: AnalysisReport }) {
  return (
    <div className="space-y-4 rounded-xl border p-4">
      <h3 className="text-sm font-semibold">Analysis Summary</h3>

      <div className="flex flex-wrap gap-2">
        <StatCard label="Friction" value={report.overall_friction} color="rose" />
        <StatCard label="Engagement" value={report.overall_engagement} color="emerald" />
        <StatCard label="Stop Risk" value={report.overall_stop_risk} color="amber" />
        <StatCard label="Bugs" value={String(report.bug_count)} color="orange" />
      </div>

      {report.session_arc && <p className="text-sm leading-relaxed text-muted-foreground">{report.session_arc}</p>}

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
