import { cn } from "@/lib/utils"
import type { AgentKind, InsightMoment } from "@/types/analysis"

const MARKER_COLORS: Record<AgentKind, string> = {
  friction: "bg-rose-500",
  clarity: "bg-amber-500",
  delight: "bg-emerald-500",
  quality: "bg-orange-500",
}

export function TimelineBar({
  duration,
  currentTime,
  insights,
  onSeek,
}: {
  duration: number
  currentTime: number
  insights: InsightMoment[]
  onSeek: (seconds: number) => void
}) {
  if (!duration) return null

  const pct = (seconds: number) => `${(seconds / duration) * 100}%`

  return (
    <div className="relative h-8">
      {/* Track */}
      <div className="absolute top-1/2 w-full h-1.5 -translate-y-1/2 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full bg-primary/30 transition-[width] duration-200"
          style={{ width: pct(currentTime) }}
        />
      </div>

      {/* Playhead */}
      <div
        className="absolute top-1/2 -translate-y-1/2 w-0.5 h-4 rounded-full bg-primary pointer-events-none transition-[left] duration-200"
        style={{ left: pct(currentTime) }}
      />

      {/* Markers */}
      {insights.map((insight) => (
        <button
          key={insight.id}
          type="button"
          onClick={() => onSeek(insight.absolute_seconds)}
          title={`${insight.summary} (${insight.timestamp})`}
          className={cn(
            "absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full",
            "border-2 border-background shadow-sm",
            "hover:scale-150 transition-transform cursor-pointer",
            MARKER_COLORS[insight.agent_kind],
            Math.abs(currentTime - insight.absolute_seconds) < 2 &&
              "ring-2 ring-primary ring-offset-1 ring-offset-background scale-125",
          )}
          style={{ left: pct(insight.absolute_seconds) }}
        />
      ))}
    </div>
  )
}
