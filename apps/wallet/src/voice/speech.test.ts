import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getRecognitionCtor, speak, stopSpeaking, ttsUrl } from './speech'

afterEach(() => vi.unstubAllGlobals())

describe('getRecognitionCtor', () => {
  it('returns null when unsupported (e.g. Firefox)', () => {
    expect(getRecognitionCtor({})).toBeNull()
  })
  it('prefers the standard constructor, falls back to webkit', () => {
    class A {}
    class B {}
    expect(getRecognitionCtor({ SpeechRecognition: A, webkitSpeechRecognition: B })).toBe(A)
    expect(getRecognitionCtor({ webkitSpeechRecognition: B })).toBe(B)
  })
})

describe('ttsUrl', () => {
  it('derives the agent HTTP endpoint from its WebSocket URL', () => {
    expect(ttsUrl('ws://localhost:8787/ws')).toBe('http://localhost:8787/tts')
    expect(ttsUrl('wss://agent.example/ws')).toBe('https://agent.example/tts')
  })
})

describe('speak', () => {
  beforeEach(() => vi.stubGlobal('Audio', class { pause() {} }))

  it('asks the agent only when enabled', () => {
    const fetch = vi.fn(() => new Promise<Response>(() => {}))
    vi.stubGlobal('fetch', fetch)
    speak('hello', false)
    speak('   ', true)
    expect(fetch).not.toHaveBeenCalled()
    speak('hello', true)
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8787/tts',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ text: 'hello' }) }),
    )
    stopSpeaking()
  })

  it('aborts the previous reply when a new one starts or speaking stops', () => {
    const signals: AbortSignal[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) => {
        signals.push(init.signal as AbortSignal)
        return new Promise<Response>(() => {})
      }),
    )
    speak('one', true)
    speak('two', true)
    expect(signals[0].aborted).toBe(true)
    expect(signals[1].aborted).toBe(false)
    stopSpeaking()
    expect(signals[1].aborted).toBe(true)
  })

  it('stays silent when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))))
    expect(() => speak('hello', true)).not.toThrow()
    await new Promise((r) => setTimeout(r, 0))
  })
})
