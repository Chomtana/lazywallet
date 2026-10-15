import { Volume2 } from 'lucide-react'
import { speak } from '@/voice/speech'

export function TextBubble({ text }: { text: string }) {
  return (
    <div className="flex min-w-0 items-start gap-2">
      <div className="min-w-0 rounded-2xl rounded-bl-md bg-card px-4 py-2.5 wrap-anywhere">{text}</div>
      <button
        type="button"
        aria-label="Read aloud"
        onClick={() => speak(text, true)}
        className="mt-2 text-muted-foreground opacity-60 transition hover:text-primary hover:opacity-100"
      >
        <Volume2 className="size-4" />
      </button>
    </div>
  )
}
