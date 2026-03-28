import { forwardRef, useImperativeHandle, useRef, useState } from "react"
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

export const VideoPlayer = forwardRef<VideoPlayerHandle, VideoPlayerProps>(
  function VideoPlayer({ url, onTimeUpdate, onDuration }, ref) {
    const playerRef = useRef<ReactPlayer>(null)
    const [playing, setPlaying] = useState(false)

    useImperativeHandle(ref, () => ({
      seekTo: (seconds: number) => playerRef.current?.seekTo(seconds, "seconds"),
      play: () => setPlaying(true),
      pause: () => setPlaying(false),
    }))

    return (
      <div className="relative aspect-video overflow-hidden rounded-xl border bg-black shadow-lg">
        <ReactPlayer
          ref={playerRef}
          url={url}
          width="100%"
          height="100%"
          playing={playing}
          controls
          onDuration={onDuration}
          onProgress={({ playedSeconds }) => onTimeUpdate(playedSeconds)}
          progressInterval={250}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
        />
      </div>
    )
  },
)
