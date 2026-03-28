import { useEffect, useRef } from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Loader2 } from "lucide-react"

export function ProgressLog({
  messages,
  loading,
}: {
  messages: string[]
  loading: boolean
}) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages.length])

  if (messages.length === 0) return null

  return (
    <ScrollArea className="bg-muted/50 h-48 rounded-lg border p-4 font-mono text-xs">
      <div className="space-y-1">
        {messages.map((msg, i) => (
          <div key={i} className="text-muted-foreground flex items-start gap-2">
            <span className="text-primary mt-0.5 shrink-0">{">"}</span>
            <span>{msg}</span>
          </div>
        ))}
        {loading && (
          <div className="text-muted-foreground flex items-center gap-2">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>Working...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
