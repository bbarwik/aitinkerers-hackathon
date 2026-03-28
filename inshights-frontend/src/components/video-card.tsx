import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { ExternalLink, Eye, Clock } from "lucide-react"
import type { DiscoveredVideo } from "@/hooks/use-discover"

function formatDuration(seconds: number | null): string {
  if (!seconds) return ""
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
  return `${m}:${s.toString().padStart(2, "0")}`
}

function formatViews(count: number | null): string {
  if (!count) return ""
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`
  return count.toString()
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return ""
  const date = new Date(dateStr)
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function YtIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current">
      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
    </svg>
  )
}

function TwitchIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current">
      <path d="M11.64 5.93H13.07V10.21H11.64M15.57 5.93H17V10.21H15.57M7 2L3.43 5.57V18.43H7.71V22L11.29 18.43H14.14L20.57 12V2M19.14 11.29L16.29 14.14H13.43L10.93 16.64V14.14H7.71V3.43H19.14Z" />
    </svg>
  )
}

const PLATFORM_ICON = {
  youtube: YtIcon,
  twitch: TwitchIcon,
}

export function VideoCard({ video }: { video: DiscoveredVideo }) {
  const PlatformIcon = PLATFORM_ICON[video.platform]
  const thumbnailUrl =
    video.thumbnail_url ||
    `https://img.youtube.com/vi/${video.video_id}/mqdefault.jpg`

  return (
    <Card className="group overflow-hidden transition-shadow hover:shadow-lg">
      <a
        href={video.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block"
      >
        <div className="bg-muted relative aspect-video overflow-hidden">
          <img
            src={thumbnailUrl}
            alt={video.title}
            className="h-full w-full object-cover transition-transform group-hover:scale-105"
            loading="lazy"
          />
          {video.duration_seconds && (
            <span className="absolute right-2 bottom-2 rounded bg-black/80 px-1.5 py-0.5 font-mono text-xs text-white">
              {formatDuration(video.duration_seconds)}
            </span>
          )}
          <div className="bg-primary/90 text-primary-foreground absolute top-2 left-2 flex items-center gap-1 rounded px-1.5 py-0.5 text-xs">
            <PlatformIcon />
          </div>
        </div>

        <CardContent className="space-y-2 p-3">
          <h3 className="line-clamp-2 text-sm font-medium leading-snug">
            {video.title}
          </h3>

          <div className="text-muted-foreground flex items-center gap-3 text-xs">
            {video.channel_name && (
              <span className="truncate">{video.channel_name}</span>
            )}
            {video.view_count != null && (
              <span className="flex shrink-0 items-center gap-1">
                <Eye className="h-3 w-3" />
                {formatViews(video.view_count)}
              </span>
            )}
            {video.published_at && (
              <span className="flex shrink-0 items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatDate(video.published_at)}
              </span>
            )}
          </div>

          <div className="flex items-center justify-between">
            {video.content_type && video.content_type !== "unknown" ? (
              <Badge variant="secondary" className="text-[10px]">
                {video.content_type}
              </Badge>
            ) : video.source_query ? (
              <Badge variant="secondary" className="max-w-[70%] truncate text-[10px]">
                {video.source_query}
              </Badge>
            ) : (
              <span />
            )}
            <ExternalLink className="text-muted-foreground h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
          </div>
        </CardContent>
      </a>

    </Card>
  )
}
