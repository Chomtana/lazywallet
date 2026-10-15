import { afterEach, describe, expect, it, vi } from 'vitest'
import { getRecognitionCtor, speak } from './speech'

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

describe('speak', () => {
  it('does nothing when speech synthesis is missing', () => {
    expect(() => speak('hello', true)).not.toThrow()
  })

  it('speaks only when enabled', () => {
    const synth = { cancel: vi.fn(), speak: vi.fn() }
    vi.stubGlobal('speechSynthesis', synth)
    vi.stubGlobal(
      'SpeechSynthesisUtterance',
      class {
        text: string
        constructor(text: string) {
          this.text = text
        }
      },
    )
    speak('hello', false)
    expect(synth.speak).not.toHaveBeenCalled()
    speak('hello', true)
    expect(synth.cancel).toHaveBeenCalled()
    expect(synth.speak).toHaveBeenCalledWith(expect.objectContaining({ text: 'hello' }))
  })
})
