import { useEffect, useRef, type ReactNode } from 'react'
import { EXAMPLES } from '@/mock/fixtures'
import type { Message } from '@/types'
import { ProgressBubble } from './cards/ProgressBubble'
import { MessageItem, type MessageActions } from './MessageItem'

type Props = {
  messages: Message[]
  progress?: string | null // the agent's current step, while it works
  queue?: Message[] // prompts waiting for the current turn to end
  onPick: (text: string) => void
  action?: ReactNode // e.g. the Get funds button, shown on the empty chat
} & MessageActions

export function ChatView({ messages, progress, queue = [], onPick, action, ...actions }: Props) {
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, progress, queue])

  if (messages.length === 0) {
    return (
      <div className="mx-auto flex h-full max-w-[720px] flex-col items-center justify-center gap-6 px-4 text-center">
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold">What should I do?</h2>
          <p className="text-muted-foreground">Tap the mic and just say it — or type.</p>
        </div>
        {action}
        <div className="flex flex-wrap justify-center gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => onPick(ex)}
              className="rounded-full border px-4 py-2 text-sm text-muted-foreground transition hover:border-primary hover:text-foreground"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-[720px] flex-col gap-3 px-4 py-6">
      {messages.map((m) => (
        <MessageItem key={m.id} message={m} {...actions} />
      ))}
      {progress && <ProgressBubble label={progress} />}
      {queue.map((m) => (
        <MessageItem key={m.id} message={m} queued {...actions} />
      ))}
      <div ref={endRef} />
    </div>
  )
}
