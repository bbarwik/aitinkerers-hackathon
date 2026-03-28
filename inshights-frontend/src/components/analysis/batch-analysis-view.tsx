import { useState } from "react"
import { ArrowLeft, Loader2, CheckCircle2, AlertCircle, Clock, Eye, BarChart3 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { ProgressLog } from "@/components/progress-log"
import { VideoAnalysisView } from "./video-analysis-view"
import { StudyView } from "./study-view"
import { useBatchAnalysis, type VideoAnalysisEntry } from "@/hooks/use-batch-analysis"
import { useStudy } from "@/hooks/use-study"
import { cn } from "@/lib/utils"
import type { DiscoveredVideo } from "@/hooks/use-discover"

function formatDuration(seconds: number | null): string {
  if (!seconds) return ""
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
  return `${m}:${s.toString().padStart(2, "0")}`
}

const STATUS_ICON = {
  pending: <Clock className="h-4 w-4 text-muted-foreground" />,
  processing: <Loader2 className="h-4 w-4 animate-spin text-primary" />,
  done: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
  error: <AlertCircle className="h-4 w-4 text-destructive" />,
}

const STATUS_LABEL = {
  pending: "Queued",
  processing: "Analyzing...",
  done: "Complete",
  error: "Failed",
}

function BatchVideoCard({
  entry,
  onClick,
}: {
  entry: VideoAnalysisEntry
  onClick: () => void
}) {
  const { video, status, insights, report } = entry
  const thumbnailUrl = video.thumbnail_url || `https://img.youtube.com/vi/${video.video_id}/mqdefault.jpg`

  return (
    <Card
      className={cn(
        "overflow-hidden transition-all",
        status === "done" && "cursor-pointer hover:shadow-lg hover:border-primary/50",
        status === "processing" && "border-primary/30",
      )}
      onClick={status === "done" ? onClick : undefined}
    >
      <div className="relative aspect-video overflow-hidden bg-muted">
        <img src={thumbnailUrl} alt={video.title} className="h-full w-full object-cover" loading="lazy" />
        {video.duration_seconds && (
          <span className="absolute right-2 bottom-2 rounded bg-black/80 px-1.5 py-0.5 font-mono text-xs text-white">
            {formatDuration(video.duration_seconds)}
          </span>
        )}
        {status === "processing" && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/40">
            <Loader2 className="h-8 w-8 animate-spin text-white" />
          </div>
        )}
        {status === "done" && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 transition-opacity hover:opacity-100">
            <div className="flex items-center gap-2 rounded-lg bg-white/90 px-4 py-2 text-sm font-medium text-black">
              <Eye className="h-4 w-4" />
              View Analysis
            </div>
          </div>
        )}
      </div>
      <CardContent className="p-3">
        <h3 className="line-clamp-2 text-sm font-medium leading-snug">{video.title}</h3>
        <div className="mt-2 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs">
            {STATUS_ICON[status]}
            <span className={cn("font-medium", status === "done" && "text-emerald-500", status === "error" && "text-destructive")}>
              {STATUS_LABEL[status]}
            </span>
          </div>
          {status === "done" && insights.length > 0 && (
            <Badge variant="secondary" className="text-[10px]">
              {insights.length} insights
            </Badge>
          )}
          {report?.executive && (
            <Badge variant="outline" className="text-[10px]">
              Health: {report.executive.session_health_score}
            </Badge>
          )}
        </div>
        {entry.error && <p className="mt-1 text-xs text-destructive">{entry.error}</p>}
      </CardContent>
    </Card>
  )
}

export function BatchAnalysisView({
  videos,
  batchLabel,
  onBack,
}: {
  videos: DiscoveredVideo[]
  batchLabel: string
  onBack: () => void
}) {
  const { status, entries, completedCount, totalCount, error, startBatch } = useBatchAnalysis()
  const study = useStudy()
  const [selectedEntry, setSelectedEntry] = useState<VideoAnalysisEntry | null>(null)

  const handleStart = () => startBatch(videos)

  // Derive game_key from first completed report
  const gameKey = entries.find((e) => e.report?.game_key)?.report?.game_key ?? null
  const batchDone = status === "done"
  const completedEntries = entries.filter((e) => e.status === "done")

  const handleStudy = () => {
    if (gameKey) study.analyze(gameKey)
  }

  // Drill into individual video analysis
  if (selectedEntry) {
    const latest = entries.find((e) => e.video.video_id === selectedEntry.video.video_id) ?? selectedEntry
    return (
      <VideoAnalysisView
        video={latest.video}
        insights={latest.insights}
        report={latest.report}
        onBack={() => setSelectedEntry(null)}
      />
    )
  }

  // Collect progress from all currently processing videos
  const activeProgress = entries
    .filter((e) => e.status === "processing")
    .flatMap((e) => e.progress.slice(-3).map((msg) => `[${e.video.title.slice(0, 30)}] ${msg}`))

  return (
    <div className="flex h-[calc(100vh-57px)] flex-col overflow-y-auto">
      {/* Top bar */}
      <div className="flex items-center gap-3 border-b px-6 py-3">
        <Button variant="ghost" size="sm" onClick={onBack} className="gap-1.5">
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        <div className="flex-1">
          <h2 className="text-sm font-medium">Batch Analysis — {batchLabel}</h2>
          <p className="text-xs text-muted-foreground">{totalCount} videos</p>
        </div>

        {status === "idle" && (
          <Button onClick={handleStart} className="gap-2">
            Analyze All ({videos.length})
          </Button>
        )}
        {status === "loading" && (
          <div className="flex items-center gap-2 text-sm">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <span className="font-medium">{completedCount}/{totalCount}</span>
            <span className="text-muted-foreground">complete</span>
          </div>
        )}
        {batchDone && (
          <>
            <Badge variant="secondary" className="gap-1 text-emerald-600">
              <CheckCircle2 className="h-3 w-3" />
              All complete
            </Badge>
            {gameKey && completedEntries.length >= 2 && !study.report && (
              <Button onClick={handleStudy} disabled={study.status === "loading"} className="gap-2">
                {study.status === "loading" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <BarChart3 className="h-4 w-4" />
                )}
                Cross-Video Study
              </Button>
            )}
          </>
        )}
      </div>

      <div className="mx-auto w-full max-w-7xl space-y-6 p-6">
        {/* Progress bar */}
        {status === "loading" && totalCount > 0 && (
          <div className="space-y-2">
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-[width] duration-500"
                style={{ width: `${(completedCount / totalCount) * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Error */}
        {(error || study.error) && (
          <div className="flex items-center gap-3 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error || study.error}
          </div>
        )}

        {/* Active progress log */}
        {activeProgress.length > 0 && (
          <ProgressLog messages={activeProgress} loading={status === "loading"} />
        )}

        {/* Study results */}
        {study.report && <StudyView study={study.report} />}

        {/* Study loading */}
        {study.status === "loading" && (
          <div className="flex items-center justify-center gap-2 rounded-xl border p-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Generating cross-video study analysis...
          </div>
        )}

        {/* Video grid */}
        {entries.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {entries.map((entry) => (
              <BatchVideoCard
                key={entry.video.video_id}
                entry={entry}
                onClick={() => setSelectedEntry(entry)}
              />
            ))}
          </div>
        ) : (
          /* Pre-start: show the videos that will be analyzed */
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {videos.map((video) => (
              <Card key={video.video_id} className="overflow-hidden opacity-70">
                <div className="relative aspect-video bg-muted">
                  <img
                    src={video.thumbnail_url || `https://img.youtube.com/vi/${video.video_id}/mqdefault.jpg`}
                    alt={video.title}
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                </div>
                <CardContent className="p-3">
                  <h3 className="line-clamp-2 text-sm font-medium leading-snug">{video.title}</h3>
                  <p className="mt-1 text-xs text-muted-foreground">{video.channel_name}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
