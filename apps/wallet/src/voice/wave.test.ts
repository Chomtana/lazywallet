import { describe, expect, it } from 'vitest'
import { barHeights } from './wave'

describe('barHeights', () => {
  it('returns a flat floor line for silence', () => {
    expect(barHeights(new Uint8Array(32), 6)).toEqual([0.08, 0.08, 0.08, 0.08, 0.08, 0.08])
  })

  it('averages bands, normalizes to 1 and mirrors around the center', () => {
    // 4 bins → 2 bands: [255, 255] → 1, [0, 102] → 0.2
    expect(barHeights([255, 255, 0, 102], 4)).toEqual([0.2, 1, 1, 0.2])
  })

  it('handles an odd count with a single center bar', () => {
    const h = barHeights([255, 255, 0, 102, 0, 0], 5)
    expect(h).toEqual([0.08, 0.2, 1, 0.2, 0.08])
  })

  it('always returns `count` bars, even with fewer bins than bars', () => {
    expect(barHeights([128], 7)).toHaveLength(7)
  })
})
