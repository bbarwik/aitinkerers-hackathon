import { useCallback, useState } from "react"
import type { StudyReport } from "@/types/analysis"

type StudyState = {
  status: "idle" | "loading" | "done" | "error"
  report: StudyReport | null
  error: string | null
}

export function useStudy() {
  const [state, setState] = useState<StudyState>({ status: "idle", report: null, error: null })

  const analyze = useCallback(async (gameKey: string) => {
    setState({ status: "loading", report: null, error: null })
    try {
      const resp = await fetch(`/api/studies/${encodeURIComponent(gameKey)}/analyze`, { method: "POST" })
      if (!resp.ok) {
        const text = await resp.text()
        throw new Error(`HTTP ${resp.status}: ${text}`)
      }
      const report: StudyReport = await resp.json()
      setState({ status: "done", report, error: null })
      return report
    } catch (err) {
      setState({ status: "error", report: null, error: (err as Error).message })
      return null
    }
  }, [])

  const fetch_ = useCallback(async (gameKey: string) => {
    setState({ status: "loading", report: null, error: null })
    try {
      const resp = await fetch(`/api/studies/${encodeURIComponent(gameKey)}`)
      if (!resp.ok) {
        if (resp.status === 404) {
          setState({ status: "idle", report: null, error: null })
          return null
        }
        throw new Error(`HTTP ${resp.status}`)
      }
      const report: StudyReport = await resp.json()
      setState({ status: "done", report, error: null })
      return report
    } catch (err) {
      setState({ status: "error", report: null, error: (err as Error).message })
      return null
    }
  }, [])

  return { ...state, analyze, fetchStudy: fetch_ }
}
