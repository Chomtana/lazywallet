// What the agent is doing right now: shown under the chat while it works, before its reply streams.
export function ProgressBubble({ label }: { label: string }) {
  return (
    <div className="flex justify-start">
      <div role="status" aria-live="polite" className="flex items-center gap-2.5 rounded-2xl rounded-bl-md bg-card px-4 py-2.5 text-sm text-muted-foreground">
        <span className="flex items-center gap-1" aria-hidden>
          {[0, 150, 300].map((delay) => (
            <span key={delay} className="size-1.5 animate-bounce rounded-full bg-primary" style={{ animationDelay: `${delay}ms` }} />
          ))}
        </span>
        {label}
      </div>
    </div>
  )
}
