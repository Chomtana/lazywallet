import { useEffect, useRef, useState } from 'react'
import { AGENT_WS_URL } from '@/agent/protocol'

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

// Spoken replies come from the agent's POST /tts (ElevenLabs; the key never reaches the browser).
export function ttsUrl(wsUrl: string): string {
  const u = new URL(wsUrl)
  u.protocol = u.protocol === 'wss:' ? 'https:' : 'http:'
  u.pathname = '/tts'
  return u.toString()
}

const TTS_URL = ttsUrl(AGENT_WS_URL)
type Playing = { abort: AbortController; audio: HTMLAudioElement; url?: string }
let playing: Playing | null = null

// Stop any reply being fetched or played (a newer reply, or the mic starting).
export function stopSpeaking(): void {
  if (!playing) return
  playing.abort.abort()
  playing.audio.pause()
  if (playing.url) URL.revokeObjectURL(playing.url)
  playing = null
}

// Fire-and-forget; a failed request stays silent (no robotic fallback).
export function speak(text: string, enabled: boolean): void {
  if (!enabled || !text.trim()) return
  stopSpeaking()
  const current: Playing = { abort: new AbortController(), audio: new Audio() }
  playing = current
  void (async () => {
    try {
      const res = await fetch(TTS_URL, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ text }),
        signal: current.abort.signal,
      })
      if (!res.ok) return
      const blob = await res.blob()
      if (playing !== current) return
      current.url = URL.createObjectURL(blob)
      current.audio.src = current.url
      current.audio.onended = () => {
        if (playing === current) stopSpeaking()
      }
      await current.audio.play()
    } catch {
      // aborted, offline or autoplay-blocked: stay silent
    }
  })()
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
    stopSpeaking()
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
