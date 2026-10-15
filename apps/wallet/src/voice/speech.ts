import { useEffect, useRef, useState } from 'react'

type RecognitionResultList = ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>
interface Recognition {
  lang: string
  interimResults: boolean
  continuous: boolean
  start(): void
  stop(): void
  onresult: ((e: { resultIndex: number; results: RecognitionResultList }) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
}
type RecognitionCtor = new () => Recognition

export function getRecognitionCtor(w: object = window): RecognitionCtor | null {
  const g = w as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return g.SpeechRecognition ?? g.webkitSpeechRecognition ?? null
}

function canSpeak(): boolean {
  return typeof globalThis.speechSynthesis !== 'undefined' && typeof globalThis.SpeechSynthesisUtterance !== 'undefined'
}

export function speak(text: string, enabled: boolean): void {
  if (!enabled || !text || !canSpeak()) return
  globalThis.speechSynthesis.cancel()
  globalThis.speechSynthesis.speak(new SpeechSynthesisUtterance(text))
}

export function useSpeechRecognition(onFinal: (text: string) => void) {
  const Ctor = getRecognitionCtor()
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState('')
  const recRef = useRef<Recognition | null>(null)
  const onFinalRef = useRef(onFinal)

  useEffect(() => {
    onFinalRef.current = onFinal
  })
  useEffect(() => () => recRef.current?.stop(), [])

  function start() {
    if (!Ctor || recRef.current) return
    if (canSpeak()) globalThis.speechSynthesis.cancel()
    const rec = new Ctor()
    rec.lang = 'en-US'
    rec.interimResults = true
    rec.continuous = false
    let finalText = ''
    rec.onresult = (e) => {
      let live = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const result = e.results[i]
        if (result.isFinal) finalText += result[0].transcript
        else live += result[0].transcript
      }
      setInterim(finalText + live)
    }
    rec.onerror = (e) =>
      setError(e.error === 'not-allowed' ? 'Microphone permission was denied.' : `Voice error: ${e.error}`)
    rec.onend = () => {
      recRef.current = null
      setListening(false)
      setInterim('')
      if (finalText.trim()) onFinalRef.current(finalText.trim())
    }
    recRef.current = rec
    setError('')
    setListening(true)
    rec.start()
  }

  function stop() {
    recRef.current?.stop()
  }

  return { supported: Ctor !== null, listening, interim, error, start, stop }
}
