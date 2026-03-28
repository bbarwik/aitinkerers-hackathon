import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import { Trophy, Zap } from "lucide-react"
import type { HighlightReel } from "@/types/analysis"

const CATEGORY_COLORS: Record<string, string> = {
  critical_friction: "bg-rose-500/10 text-rose-500 border-rose-500/20",
  clarity_failure: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  player_delight: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  bug: "bg-orange-500/10 text-orange-500 border-orange-500/20",
  sentiment_swing: "bg-indigo-500/10 text-indigo-500 border-indigo-500/20",
  retry_loop: "bg-purple-500/10 text-purple-500 border-purple-500/20",
  player_feedback: "bg-cyan-500/10 text-cyan-500 border-cyan-500/20",
}

function formatCategory(category: string): string {
  return category.replace(/_/g, " ")
}

export function HighlightsPanel({
  highlights,
  onSeek,
}: {
  highlights: HighlightReel
  onSeek: (seconds: number) => void
}) {
  return (
    <div className="space-y-3 rounded-xl border p-4">
      <div className="flex items-center gap-2">
        <Trophy className="h-4 w-4 text-amber-500" />
        <h3 className="text-sm font-semibold">Top Moments</h3>
        <span className="text-xs text-muted-foreground">
          ({highlights.total_moments_analyzed} analyzed)
        </span>
      </div>

      {highlights.one_line_verdict && (
        <p className="text-sm font-medium leading-snug">{highlights.one_line_verdict}</p>
      )}

      <ScrollArea className="max-h-[400px]">
        <div className="space-y-2">
          {highlights.highlights.map((h) => (
            <button
              key={h.rank}
              onClick={() => onSeek(h.clip_start_seconds)}
              className="w-full rounded-lg border p-3 text-left transition-colors hover:bg-muted/50"
            >
              <div className="flex items-center gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                  {h.rank}
                </span>
                <Badge variant="outline" className={cn("text-[10px] capitalize", CATEGORY_COLORS[h.category])}>
                  {formatCategory(h.category)}
                </Badge>
                <span className="font-mono text-xs text-muted-foreground">{h.absolute_timestamp}</span>
                <div className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground">
                  <Zap className="h-3 w-3" />
                  {h.importance_score.toFixed(1)}
                </div>
              </div>
              <p className="mt-1.5 text-sm leading-snug">{h.headline}</p>
              <p className="mt-1 text-xs text-muted-foreground">{h.why_important}</p>
              {h.corroborating_agents.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {h.corroborating_agents.map((agent) => (
                    <Badge key={agent} variant="secondary" className="text-[9px]">
                      {agent}
                    </Badge>
                  ))}
                </div>
              )}
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
