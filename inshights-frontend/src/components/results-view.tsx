import { useState } from "react"
import { Streamdown } from "streamdown"
import { code } from "@streamdown/code"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { VideoCard } from "@/components/video-card"
import { TrendingUp, Clock, Sparkles, Search, ChevronDown } from "lucide-react"
import type { DiscoveryResult, DiscoveredVideo } from "@/hooks/use-discover"

function GameContext({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="overflow-hidden rounded-xl border bg-muted/20">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-3 text-sm font-medium transition-colors hover:bg-muted/40"
      >
        <Sparkles className="h-4 w-4 text-primary" />
        <span>Game context from Gemini</span>
        <ChevronDown
          className={`ml-auto h-4 w-4 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>
      {expanded && (
        <div className="border-t px-4 py-4">
          <div className="streamdown-context prose prose-sm max-w-none dark:prose-invert">
            <Streamdown plugins={{ code }}>
              {content}
            </Streamdown>
          </div>
        </div>
      )}
    </div>
  )
}

export function ResultsView({
  result,
  onAnalyzeBatch,
}: {
  result: DiscoveryResult
  onAnalyzeBatch?: (videos: DiscoveredVideo[], label: string) => void
}) {
  const [tab, setTab] = useState<"popular" | "recent">("popular")
  const videos = tab === "popular" ? result.popular : result.recent
  const tabLabel = tab === "popular" ? "Most Popular" : "Most Recent"

  return (
    <div className="space-y-6">
      {/* Header stats */}
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-heading text-xl font-semibold">
          {result.game_name}
        </h2>
        <Badge variant="secondary" className="gap-1">
          <Search className="h-3 w-3" />
          {result.total_found} videos found
        </Badge>
        {Object.entries(result.source_breakdown).map(([platform, count]) => (
          <Badge key={platform} variant="outline">
            {platform}: {count}
          </Badge>
        ))}
        {result.cached && (
          <Badge variant="outline" className="text-muted-foreground">
            cached
          </Badge>
        )}
      </div>

      {/* Game context */}
      {result.game_context && (
        <GameContext content={result.game_context} />
      )}

      {/* Generated queries */}
      {result.queries.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {result.queries.map((q, i) => (
            <Badge key={i} variant="secondary" className="text-xs font-normal">
              {q}
            </Badge>
          ))}
        </div>
      )}

      <Separator />

      {/* Tab switcher + Analyze All button */}
      <div className="flex items-center gap-3">
        <div className="flex gap-1 rounded-lg border p-1">
          <button
            onClick={() => setTab("popular")}
            className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === "popular"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <TrendingUp className="h-4 w-4" />
            Most Popular ({result.popular.length})
          </button>
          <button
            onClick={() => setTab("recent")}
            className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === "recent"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Clock className="h-4 w-4" />
            Most Recent ({result.recent.length})
          </button>
        </div>

        {onAnalyzeBatch && videos.length > 0 && (
          <button
            onClick={() => onAnalyzeBatch(videos, `${result.game_name} — ${tabLabel}`)}
            className="flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition-colors hover:bg-primary hover:text-primary-foreground"
          >
            <Sparkles className="h-4 w-4" />
            Analyze All {tabLabel} ({videos.length})
          </button>
        )}
      </div>

      {/* Video grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {videos.map((video) => (
          <VideoCard
            key={`${video.platform}-${video.video_id}`}
            video={video}
          />
        ))}
      </div>

      {videos.length === 0 && (
        <div className="text-muted-foreground py-12 text-center">
          No videos found in this category.
        </div>
      )}
    </div>
  )
}
