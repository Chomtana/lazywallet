import { useState, type FormEvent } from 'react'
import { ArrowUp, Mic, Square, Volume2, VolumeX } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useSpeechRecognition } from '@/voice/speech'

type Props = {
  onSend: (text: string, spoken: boolean) => void
  speakEnabled: boolean
  onToggleSpeak: () => void
}

export function InputBar({ onSend, speakEnabled, onToggleSpeak }: Props) {
  const [text, setText] = useState('')
  const voice = useSpeechRecognition((t) => onSend(t, true))
  const hasText = text.trim().length > 0

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!hasText) return
    onSend(text.trim(), false)
    setText('')
  }

  return (
    <div className="space-y-2">
      {(voice.listening || voice.error) && (
        <p className={cn('px-2 text-sm', voice.error ? 'text-destructive' : 'text-muted-foreground')}>
          {voice.error || voice.interim || 'Listening…'}
        </p>
      )}
      <form onSubmit={submit} className="flex items-center gap-2 rounded-full border bg-card p-1.5 pl-4">
        <input
          aria-label="Message"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Say or type what you want…"
          className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground"
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={onToggleSpeak}
          aria-label={speakEnabled ? 'Mute spoken replies' : 'Speak replies aloud'}
        >
          {speakEnabled ? <Volume2 /> : <VolumeX />}
        </Button>
        {hasText ? (
          <Button type="submit" size="icon" className="size-11 rounded-full" aria-label="Send">
            <ArrowUp />
          </Button>
        ) : (
          <Button
            type="button"
            size="icon"
            className={cn('size-11 rounded-full', voice.listening && 'animate-pulse')}
            onClick={voice.listening ? voice.stop : voice.start}
            disabled={!voice.supported}
            aria-label={voice.listening ? 'Stop listening' : 'Start talking'}
          >
            {voice.listening ? <Square /> : <Mic />}
          </Button>
        )}
      </form>
      {!voice.supported && (
        <p className="px-2 text-xs text-muted-foreground">
          Voice input isn't supported in this browser — try Chrome or Edge. You can still type.
        </p>
      )}
    </div>
  )
}
