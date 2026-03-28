import { useCallback, useRef, useState } from "react"
import type { DiscoveredVideo } from "@/hooks/use-discover"
import type { InsightMoment, AnalysisReport, TimelineChunk, BatchStreamEvent } from "@/types/analysis"

export type VideoAnalysisEntry = {
  video: DiscoveredVideo
  status: "pending" | "processing" | "done" | "error"
  progress: string[]
  insights: InsightMoment[]
  timeline: TimelineChunk[]
  report: AnalysisReport | null
  error: string | null
}

type BatchState = {
  status: "idle" | "loading" | "done" | "error"
  entries: VideoAnalysisEntry[]
  error: string | null
}

const INITIAL: BatchState = { status: "idle", entries: [], error: null }

export function useBatchAnalysis() {
  const [state, setState] = useState<BatchState>(INITIAL)
  const abortRef = useRef<AbortController | null>(null)
  const counterRef = useRef(0)

  const startBatch = useCallback(async (videos: DiscoveredVideo[]) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    counterRef.current = 0

    const entries: VideoAnalysisEntry[] = videos.map((video) => ({
      video,
      status: "pending",
      progress: [],
      insights: [],
      timeline: [],
      report: null,
      error: null,
    }))

    setState({ status: "loading", entries, error: null })

    // Helper to update a single video entry by video_id
    const updateEntry = (videoId: string, updater: (entry: VideoAnalysisEntry) => VideoAnalysisEntry) => {
      setState((s) => ({
        ...s,
        entries: s.entries.map((e) => (e.video.video_id === videoId ? updater(e) : e)),
      }))
    }

    try {
      const payload = videos.map((v) => ({
        video_id: v.video_id,
        url: v.url,
        title: v.title,
        platform: v.platform,
      }))

      const resp = await fetch("/api/videos/analyze/batch/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ videos: payload }),
        signal: controller.signal,
      })

      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`)

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
            const event: BatchStreamEvent = JSON.parse(line)
            switch (event.type) {
              case "video_start":
                updateEntry(event.video_id, (e) => ({ ...e, status: "processing" }))
                break
              case "progress":
                updateEntry(event.video_id, (e) => ({
                  ...e,
                  progress: [...e.progress, event.message],
                }))
                break
              case "timeline_chunk":
                updateEntry(event.video_id, (e) => ({
                  ...e,
                  timeline: [...e.timeline, event.data],
                }))
                break
              case "insight": {
                const moments: InsightMoment[] = event.data.moments.map((m) => ({
                  ...m,
                  id: `insight-${counterRef.current++}`,
                }))
                updateEntry(event.video_id, (e) => ({
                  ...e,
                  insights: [...e.insights, ...moments],
                }))
                break
              }
              case "video_report":
                updateEntry(event.video_id, (e) => ({
                  ...e,
                  status: "done",
                  report: event.data,
                }))
                break
              case "video_error":
                updateEntry(event.video_id, (e) => ({
                  ...e,
                  status: "error",
                  error: event.message,
                }))
                break
              case "done":
                setState((s) => ({ ...s, status: "done" }))
                break
            }
          } catch {
            // skip malformed
          }
        }
      }

      setState((s) => (s.status === "loading" ? { ...s, status: "done" } : s))
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setState((s) => ({ ...s, status: "error", error: (err as Error).message }))
      }
    }
  }, [])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    setState((s) => (s.status === "loading" ? { ...s, status: "idle" } : s))
  }, [])

  const completedCount = state.entries.filter((e) => e.status === "done").length
  const totalCount = state.entries.length

  return { ...state, completedCount, totalCount, startBatch, cancel }
}
