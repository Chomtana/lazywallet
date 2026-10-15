// Analyser frequency bytes (0–255) → `count` bar heights in [floor, 1], mirrored so the lowest
// (loudest, most voice-like) band sits in the middle and the wave looks symmetric.
export function barHeights(bins: ArrayLike<number>, count: number, floor = 0.08): number[] {
  const half = Math.ceil(count / 2)
  const size = Math.max(1, Math.floor(bins.length / half))
  const levels: number[] = []
  for (let i = 0; i < half; i++) {
    let sum = 0
    for (let j = i * size; j < (i + 1) * size && j < bins.length; j++) sum += bins[j]
    levels.push(Math.min(1, Math.max(floor, sum / size / 255)))
  }
  const left = [...levels].reverse()
  return [...left, ...levels.slice(count % 2)]
}
