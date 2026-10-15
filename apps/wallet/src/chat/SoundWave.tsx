import { useEffect, useRef } from 'react'
import { barHeights } from '@/voice/wave'

const BARS = 29
const VOICE_BINS = 24 // fftSize 256 at 48 kHz → ~190 Hz per bin; the first 24 cover the speaking voice

// Live mic level while listening: its own getUserMedia stream (recognition keeps its own) → AnalyserNode →
// bar heights written straight to the DOM each frame. Without mic access the bars stay a flat line.
export function SoundWave() {
  const barsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let disposed = false
    let frame = 0
    let stream: MediaStream | undefined
    let ctx: AudioContext | undefined

    void (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      } catch {
        return
      }
      if (disposed) return stream.getTracks().forEach((t) => t.stop())
      ctx = new AudioContext()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.7
      ctx.createMediaStreamSource(stream).connect(analyser)
      const bins = new Uint8Array(analyser.frequencyBinCount)
      const draw = () => {
        analyser.getByteFrequencyData(bins)
        const heights = barHeights(bins.subarray(0, VOICE_BINS), BARS)
        const bars = barsRef.current?.children
        if (bars) for (let i = 0; i < bars.length; i++) (bars[i] as HTMLElement).style.transform = `scaleY(${heights[i]})`
        frame = requestAnimationFrame(draw)
      }
      draw()
    })()

    return () => {
      disposed = true
      cancelAnimationFrame(frame)
      stream?.getTracks().forEach((t) => t.stop())
      void ctx?.close()
    }
  }, [])

  return (
    <div
      ref={barsRef}
      role="img"
      aria-label="Listening"
      className="flex h-11 min-w-0 flex-1 items-center justify-center gap-[3px] overflow-hidden"
    >
      {Array.from({ length: BARS }, (_, i) => (
        <div
          key={i}
          className="h-full w-[3px] origin-center rounded-full bg-primary transition-transform duration-75"
          style={{ transform: 'scaleY(0.08)' }}
        />
      ))}
    </div>
  )
}
