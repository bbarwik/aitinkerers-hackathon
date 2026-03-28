import { useState } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { ProgressLog } from "@/components/progress-log"
import { ResultsView } from "@/components/results-view"
import { useDiscover } from "@/hooks/use-discover"
import { Gamepad2, Search, RefreshCw, AlertCircle, Calendar, X } from "lucide-react"

const PERIODS = [
  { value: "day", label: "24h" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "all", label: "All time" },
] as const

export function App() {
  const [gameName, setGameName] = useState("")
  const [period, setPeriod] = useState("month")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const { status, progress, result, error, discover, reset } = useDiscover()

  const handlePeriod = (value: string) => {
    setPeriod(value)
    setDateFrom("")
    setDateTo("")
  }

  const handleDateChange = (from: string, to: string) => {
    setDateFrom(from)
    setDateTo(to)
    if (from || to) setPeriod("")
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const name = gameName.trim()
    if (name) discover(name, false, period || "all", dateFrom || undefined, dateTo || undefined)
  }

  const handleRefresh = () => {
    const name = gameName.trim()
    if (name) discover(name, true, period || "all", dateFrom || undefined, dateTo || undefined)
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-6 py-4">
          <div className="flex items-center gap-2">
            <Gamepad2 className="h-6 w-6 text-primary" />
            <h1 className="font-heading text-lg font-bold tracking-tight">
              GameSight
            </h1>
          </div>

          <form
            onSubmit={handleSubmit}
            className="flex flex-1 items-center gap-2"
          >
            <div className="relative max-w-md flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={gameName}
                onChange={(e) => setGameName(e.target.value)}
                placeholder="Enter a game name..."
                className="pl-9"
                disabled={status === "loading"}
              />
            </div>
            <Button type="submit" disabled={status === "loading" || !gameName.trim()}>
              {status === "loading" ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                "Discover"
              )}
            </Button>
            {result && (
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={handleRefresh}
                disabled={status === "loading"}
                title="Refresh (bypass cache)"
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            )}
          </form>

          <div className="flex items-center gap-1 rounded-lg border p-1">
            <Calendar className="ml-1.5 h-3.5 w-3.5 text-muted-foreground" />
            {PERIODS.map((p) => (
              <button
                key={p.value}
                onClick={() => handlePeriod(p.value)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  period === p.value
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {p.label}
              </button>
            ))}

            <Popover>
              <PopoverTrigger asChild>
                <button
                  className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                    !period
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {!period && dateFrom
                    ? `${dateFrom}${dateTo ? ` – ${dateTo}` : ""}`
                    : "Custom"}
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-3" align="end">
                <div className="flex flex-col gap-2">
                  <label className="text-xs font-medium text-muted-foreground">Date range</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="date"
                      value={dateFrom}
                      onChange={(e) => handleDateChange(e.target.value, dateTo)}
                      className="rounded-md border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring"
                    />
                    <span className="text-sm text-muted-foreground">to</span>
                    <input
                      type="date"
                      value={dateTo}
                      onChange={(e) => handleDateChange(dateFrom, e.target.value)}
                      className="rounded-md border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring"
                    />
                  </div>
                  {(dateFrom || dateTo) && (
                    <button
                      onClick={() => handlePeriod("month")}
                      className="flex items-center gap-1 self-end text-xs text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-3 w-3" />
                      Clear
                    </button>
                  )}
                </div>
              </PopoverContent>
            </Popover>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto max-w-7xl px-6 py-8">
        {/* Idle state */}
        {status === "idle" && !result && (
          <div className="flex flex-col items-center justify-center gap-4 py-32 text-center">
            <Gamepad2 className="h-16 w-16 text-muted-foreground/30" />
            <div>
              <h2 className="text-xl font-medium">Discover gameplay videos</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Enter a game name to find the most popular and recent gameplay
                recordings from YouTube and Twitch.
              </p>
            </div>
          </div>
        )}

        {/* Progress log */}
        {progress.length > 0 && (
          <div className="mb-8">
            <ProgressLog messages={progress} loading={status === "loading"} />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-8 flex items-center gap-3 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            <AlertCircle className="h-5 w-5 shrink-0" />
            {error}
          </div>
        )}

        {/* Results */}
        {result && <ResultsView result={result} />}
      </main>
    </div>
  )
}

export default App
