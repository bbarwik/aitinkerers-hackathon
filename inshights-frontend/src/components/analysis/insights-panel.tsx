import { useState, useRef, useEffect } from "react"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import type { AgentKind, InsightMoment } from "@/types/analysis"

const AGENT_TABS: { value: AgentKind | "all"; label: string; color: string }[] = [
  { value: "all", label: "All", color: "" },
  { value: "friction", label: "Friction", color: "text-rose-500" },
  { value: "clarity", label: "Clarity", color: "text-amber-500" },
  { value: "delight", label: "Delight", color: "text-emerald-500" },
  { value: "quality", label: "Quality", color: "text-orange-500" },
]

const BADGE_COLORS: Record<AgentKind, string> = {
  friction: "bg-rose-500/10 text-rose-500 border-rose-500/20",
  clarity: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  delight: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  quality: "bg-orange-500/10 text-orange-500 border-orange-500/20",
}

export function InsightsPanel({
  insights,
  activeInsightId,
  onInsightClick,
}: {
  insights: InsightMoment[]
  activeInsightId: string | null
  onInsightClick: (insight: InsightMoment) => void
}) {
  const [filter, setFilter] = useState<AgentKind | "all">("all")
  const activeRef = useRef<HTMLButtonElement>(null)

  const filtered = filter === "all" ? insights : insights.filter((i) => i.agent_kind === filter)
  const sorted = [...filtered].sort((a, b) => a.absolute_seconds - b.absolute_seconds)

  useEffect(() => {
    if (activeInsightId && activeRef.current) {
      activeRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" })
    }
  }, [activeInsightId])

  return (
    <div className="flex h-full flex-col">
      {/* Filter tabs */}
      <div className="flex flex-wrap gap-1 border-b px-3 py-2">
        {AGENT_TABS.map((tab) => {
          const count = tab.value === "all" ? insights.length : insights.filter((i) => i.agent_kind === tab.value).length
          return (
            <button
              key={tab.value}
              onClick={() => setFilter(tab.value)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                filter === tab.value
                  ? "bg-primary text-primary-foreground"
                  : `text-muted-foreground hover:text-foreground ${tab.color}`,
              )}
            >
              {tab.label}
              <span className="ml-1 opacity-60">({count})</span>
            </button>
          )
        })}
      </div>

      {/* Insight cards */}
      <ScrollArea className="flex-1">
        <div className="space-y-2 p-3">
          {sorted.map((insight) => (
            <button
              key={insight.id}
              ref={activeInsightId === insight.id ? activeRef : undefined}
              onClick={() => onInsightClick(insight)}
              className={cn(
                "w-full rounded-lg border p-3 text-left transition-colors",
                activeInsightId === insight.id ? "border-primary bg-primary/5 shadow-sm" : "hover:bg-muted/50",
              )}
            >
              <div className="flex items-center gap-2">
                <Badge variant="outline" className={cn("text-[10px] capitalize", BADGE_COLORS[insight.agent_kind])}>
                  {insight.agent_kind}
                </Badge>
                <span className="font-mono text-xs text-muted-foreground">{insight.timestamp}</span>
                {insight.severity_numeric >= 7 && (
                  <Badge variant="destructive" className="text-[10px]">
                    severe
                  </Badge>
                )}
              </div>
              <p className="mt-1.5 text-sm leading-snug">{insight.summary}</p>
              {insight.evidence.length > 0 && (
                <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{insight.evidence.join(" · ")}</p>
              )}
              {insight.game_context && (
                <p className="mt-1 text-xs italic text-muted-foreground/70">{insight.game_context}</p>
              )}
            </button>
          ))}

          {sorted.length === 0 && (
            <div className="py-12 text-center text-sm text-muted-foreground">
              {insights.length === 0 ? "Waiting for insights..." : "No insights for this filter."}
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
