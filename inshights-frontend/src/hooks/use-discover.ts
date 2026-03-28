import { useCallback, useRef, useState } from "react"

export type DiscoveredVideo = {
  platform: "youtube" | "twitch"
  video_id: string
  url: string
  title: string
  channel_name: string | null
  description: string | null
  duration_seconds: number | null
  view_count: number | null
  published_at: string | null
  thumbnail_url: string | null
  source_query: string | null
}

export type DiscoveryResult = {
  game_name: string
  game_context: string
  queries: string[]
  total_found: number
  popular: DiscoveredVideo[]
  recent: DiscoveredVideo[]
  source_breakdown: Record<string, number>
  partial: boolean
  warnings: string[]
  cached: boolean
  generated_at: string
}

type StreamEvent =
  | { type: "progress"; message: string }
  | { type: "result"; data: DiscoveryResult }
  | { type: "error"; message: string }

type DiscoverState = {
  status: "idle" | "loading" | "done" | "error"
  progress: string[]
  result: DiscoveryResult | null
  error: string | null
}

export function useDiscover() {
  const [state, setState] = useState<DiscoverState>({
    status: "idle",
    progress: [],
    result: null,
    error: null,
  })
  const abortRef = useRef<AbortController | null>(null)

  const discover = useCallback(async (gameName: string, refresh = false, period = "month") => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setState({ status: "loading", progress: [], result: null, error: null })

    try {
      const resp = await fetch("/api/research/discover/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_name: gameName, refresh, period }),
        signal: controller.signal,
      })

      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`)
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() ?? ""

        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const event: StreamEvent = JSON.parse(line)
            if (event.type === "progress") {
              setState((s) => ({
                ...s,
                progress: [...s.progress, event.message],
              }))
            } else if (event.type === "result") {
              setState((s) => ({
                ...s,
                status: "done",
                result: event.data,
              }))
            } else if (event.type === "error") {
              setState((s) => ({
                ...s,
                status: "error",
                error: event.message,
              }))
            }
          } catch {
            // skip malformed lines
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setState((s) => ({
          ...s,
          status: "error",
          error: (err as Error).message,
        }))
      }
    }
  }, [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setState({ status: "idle", progress: [], result: null, error: null })
  }, [])

  return { ...state, discover, reset }
}
