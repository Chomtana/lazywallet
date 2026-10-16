// A short rising three-note chime for "you're subscribed" (Web Audio, no asset). Fails silently.
export function playChime(): void {
  try {
    const ctx = new AudioContext()
    const start = ctx.currentTime
    ;[523.25, 659.25, 783.99].forEach((freq, i) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      const t = start + i * 0.12
      osc.type = 'sine'
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0, t)
      gain.gain.linearRampToValueAtTime(0.2, t + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.6)
      osc.connect(gain).connect(ctx.destination)
      osc.start(t)
      osc.stop(t + 0.6)
    })
    window.setTimeout(() => void ctx.close(), 1200)
  } catch {
    // no audio support: stay silent
  }
}
