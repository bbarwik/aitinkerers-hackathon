import { useMemo, useRef, useState } from "react"
import { ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { VideoPlayer, type VideoPlayerHandle } from "./video-player"
import { TimelineBar } from "./timeline-bar"
import { InsightsPanel } from "./insights-panel"
import { ReportSummary } from "./report-summary"
import { HighlightsPanel } from "./highlights-panel"
import { ExecutiveSummaryView } from "./executive-summary"
import type { DiscoveredVideo } from "@/hooks/use-discover"
import type { InsightMoment, AnalysisReport } from "@/types/analysis"

export function VideoAnalysisView({
  video,
  insights,
  report,
  onBack,
}: {
  video: DiscoveredVideo
  insights: InsightMoment[]
  report: AnalysisReport | null
  onBack: () => void
}) {
  const playerRef = useRef<VideoPlayerHandle>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(video.duration_seconds ?? 0)

  const activeInsight = useMemo(() => {
    if (!insights.length) return null
    const sorted = [...insights].sort((a, b) => a.absolute_seconds - b.absolute_seconds)
    for (let i = sorted.length - 1; i >= 0; i--) {
      const diff = currentTime - sorted[i].absolute_seconds
      if (diff >= 0 && diff < 3) return sorted[i]
    }
    return null
  }, [insights, currentTime])

  const handleSeek = (seconds: number) => {
    playerRef.current?.seekTo(seconds)
    playerRef.current?.play()
  }

  return (
    <div className="flex h-[calc(100vh-57px)] flex-col">
      {/* Top bar */}
      <div className="flex items-center gap-3 border-b px-4 py-2">
        <Button variant="ghost" size="sm" onClick={onBack} className="gap-1.5">
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm font-medium">{video.title}</h2>
          {video.channel_name && <p className="truncate text-xs text-muted-foreground">{video.channel_name}</p>}
        </div>
        {insights.length > 0 && (
          <span className="text-xs text-muted-foreground">{insights.length} insights</span>
        )}
      </div>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Insights sidebar */}
        <div className="w-[380px] shrink-0 border-r">
          <InsightsPanel
            insights={insights}
            activeInsightId={activeInsight?.id ?? null}
            onInsightClick={(insight) => handleSeek(insight.absolute_seconds)}
          />
        </div>

        {/* Right: Player + timeline + report */}
        <div className="flex-1 overflow-y-auto">
          <div className="sticky top-0 z-10 space-y-2 bg-background p-4 pb-2 shadow-sm">
            <VideoPlayer
              ref={playerRef}
              url={video.url}
              onTimeUpdate={setCurrentTime}
              onDuration={setDuration}
            />
            <TimelineBar
              duration={duration}
              currentTime={currentTime}
              insights={insights}
              onSeek={handleSeek}
            />
          </div>

          <div className="space-y-4 p-4 pt-2">
            {report?.executive && <ExecutiveSummaryView summary={report.executive} />}
            {report?.highlights && <HighlightsPanel highlights={report.highlights} onSeek={handleSeek} />}
            {report && <ReportSummary report={report} />}

            {insights.length === 0 && !report && (
              <div className="py-12 text-center text-sm text-muted-foreground">
                No analysis data yet. Process this video to see insights.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
