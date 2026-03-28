import { useMemo } from "react"
import { cn } from "@/lib/utils"
import type { AgentKind, InsightMoment } from "@/types/analysis"

const AGENT_KINDS: AgentKind[] = ["friction", "clarity", "delight", "quality", "sentiment", "retry", "verbal"]

const MARKER_COLORS: Record<AgentKind, string> = {
  friction: "bg-rose-500",
  clarity: "bg-amber-500",
  delight: "bg-emerald-500",
  quality: "bg-orange-500",
  sentiment: "bg-indigo-500",
  retry: "bg-purple-500",
  verbal: "bg-cyan-500",
}

function seededRandom(seed: number): () => number {
  let s = seed
  return () => {
    s = (s * 16807 + 0) % 2147483647
    return s / 2147483647
  }
}

type PlaceholderMarker = { seconds: number; agent_kind: AgentKind }

function generatePlaceholders(fromSeconds: number, toSeconds: number, count: number): PlaceholderMarker[] {
  const rng = seededRandom(42)
  const span = toSeconds - fromSeconds
  if (span <= 0) return []
  const markers: PlaceholderMarker[] = []
  for (let i = 0; i < count; i++) {
    markers.push({
      seconds: fromSeconds + rng() * span,
      agent_kind: AGENT_KINDS[Math.floor(rng() * AGENT_KINDS.length)],
    })
  }
  return markers.sort((a, b) => a.seconds - b.seconds)
}

export function TimelineBar({
  duration,
  currentTime,
  insights,
  onSeek,
  analyzedSeconds,
}: {
  duration: number
  currentTime: number
  insights: InsightMoment[]
  onSeek: (seconds: number) => void
  analyzedSeconds?: number
}) {
  if (!duration) return null

  const pct = (seconds: number) => `${(seconds / duration) * 100}%`
  const analyzed = analyzedSeconds ?? duration
  const hasUnanalyzed = analyzed < duration

  const placeholders = useMemo(
    () => {
      if (!hasUnanalyzed) return []
      return generatePlaceholders(analyzed, duration, Math.round((duration - analyzed) / 6))
    },
    [analyzed, duration, hasUnanalyzed],
  )

  return (
    <div className="relative h-8">
      {/* Track background */}
      <div className="absolute top-1/2 w-full h-1.5 -translate-y-1/2 rounded-full bg-muted overflow-hidden">
        {/* Playback progress */}
        <div
          className="absolute inset-y-0 left-0 bg-primary/30 transition-[width] duration-200"
          style={{ width: pct(currentTime) }}
        />
      </div>

      {/* Playhead */}
      <div
        className="absolute top-1/2 -translate-y-1/2 w-0.5 h-4 rounded-full bg-primary pointer-events-none transition-[left] duration-200"
        style={{ left: pct(currentTime) }}
      />

      {/* Real markers (clickable) */}
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

      {/* Placeholder markers for unanalyzed region (not clickable) */}
      {placeholders.map((m, i) => (
        <div
          key={`ph-${i}`}
          className={cn(
            "absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-2.5 h-2.5 rounded-full",
            "border-2 border-background opacity-40 pointer-events-none",
            MARKER_COLORS[m.agent_kind],
          )}
          style={{ left: pct(m.seconds) }}
        />
      ))}
    </div>
  )
}
