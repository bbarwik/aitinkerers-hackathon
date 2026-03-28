import { useMemo, useRef, useState } from "react"
import { ArrowLeft, MessageSquareText, Activity, Trophy, BarChart3 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { VideoPlayer, type VideoPlayerHandle } from "./video-player"
import { TimelineBar } from "./timeline-bar"
import { InsightsPanel } from "./insights-panel"
import { ReportSummary } from "./report-summary"
import { HighlightsPanel } from "./highlights-panel"
import { ExecutiveSummaryView } from "./executive-summary"
import { cn } from "@/lib/utils"
import type { DiscoveredVideo } from "@/hooks/use-discover"
import type { InsightMoment, AnalysisReport } from "@/types/analysis"

type Tab = "insights" | "summary" | "highlights" | "report"

const TABS: { value: Tab; label: string; icon: React.ReactNode }[] = [
  { value: "insights", label: "Insights", icon: <MessageSquareText className="h-4 w-4" /> },
  { value: "summary", label: "Summary", icon: <Activity className="h-4 w-4" /> },
  { value: "highlights", label: "Highlights", icon: <Trophy className="h-4 w-4" /> },
  { value: "report", label: "Report", icon: <BarChart3 className="h-4 w-4" /> },
]

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
  const [tab, setTab] = useState<Tab>("insights")

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
    <div className="flex h-[calc(100vh-57px)] flex-col overflow-hidden">
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

      {/* Video + timeline (compact) */}
      <div className="shrink-0 space-y-1.5 border-b bg-background px-4 py-2">
        <div className="mx-auto max-w-2xl">
          <VideoPlayer
            ref={playerRef}
            url={video.url}
            onTimeUpdate={setCurrentTime}
            onDuration={setDuration}
          />
        </div>
        <TimelineBar
          duration={duration}
          currentTime={currentTime}
          insights={insights}
          onSeek={handleSeek}
          analyzedSeconds={report?.duration_seconds}
        />
      </div>

      {/* Tab bar */}
      <div className="flex shrink-0 gap-1 border-b px-4 py-1.5">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              tab === t.value
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
            )}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {tab === "insights" && (
          <InsightsPanel
            insights={insights}
            activeInsightId={activeInsight?.id ?? null}
            onInsightClick={(insight) => handleSeek(insight.absolute_seconds)}
          />
        )}

        {tab === "summary" && (
          <div className="space-y-4 p-4">
            {report?.executive ? (
              <ExecutiveSummaryView summary={report.executive} />
            ) : (
              <div className="py-12 text-center text-sm text-muted-foreground">
                No executive summary available.
              </div>
            )}
          </div>
        )}

        {tab === "highlights" && (
          <div className="space-y-4 p-4">
            {report?.highlights ? (
              <HighlightsPanel highlights={report.highlights} onSeek={handleSeek} />
            ) : (
              <div className="py-12 text-center text-sm text-muted-foreground">
                No highlights available.
              </div>
            )}
          </div>
        )}

        {tab === "report" && (
          <div className="space-y-4 p-4">
            {report ? (
              <ReportSummary report={report} />
            ) : (
              <div className="py-12 text-center text-sm text-muted-foreground">
                No report data available.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
