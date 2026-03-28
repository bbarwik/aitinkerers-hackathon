import { forwardRef, useCallback, useImperativeHandle, useRef } from "react"
import ReactPlayer from "react-player"

export interface VideoPlayerHandle {
  seekTo: (seconds: number) => void
  play: () => void
  pause: () => void
}

interface VideoPlayerProps {
  url: string
  onTimeUpdate: (seconds: number) => void
  onDuration: (seconds: number) => void
}

type MediaEl = HTMLVideoElement & { currentTime: number; duration: number }

export const VideoPlayer = forwardRef<VideoPlayerHandle, VideoPlayerProps>(
  function VideoPlayer({ url, onTimeUpdate, onDuration }, ref) {
    const elRef = useRef<MediaEl | null>(null)

    useImperativeHandle(ref, () => ({
      seekTo: (seconds: number) => {
        try { if (elRef.current) elRef.current.currentTime = seconds } catch { /* not ready */ }
      },
      play: () => {
        try { elRef.current?.play() } catch { /* not ready */ }
      },
      pause: () => {
        try { elRef.current?.pause() } catch { /* not ready */ }
      },
    }))

    const handleRef = useCallback((node: MediaEl | null) => {
      if (elRef.current) {
        elRef.current.removeEventListener("timeupdate", onTime)
        elRef.current.removeEventListener("durationchange", onMeta)
        elRef.current.removeEventListener("loadedmetadata", onMeta)
      }
      elRef.current = node
      if (!node) return
      node.addEventListener("timeupdate", onTime)
      node.addEventListener("durationchange", onMeta)
      node.addEventListener("loadedmetadata", onMeta)
      if (node.duration && !isNaN(node.duration)) onDuration(node.duration)

      function onTime() { if (node) onTimeUpdate(node.currentTime) }
      function onMeta() { if (node?.duration && !isNaN(node.duration)) onDuration(node.duration) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    return (
      <div className="relative aspect-video overflow-hidden rounded-xl border bg-black shadow-lg">
        {/* @ts-expect-error react-player v3 ref is a custom video element */}
        <ReactPlayer
          ref={handleRef}
          src={url}
          width="100%"
          height="100%"
          controls
        />
      </div>
    )
  },
)
