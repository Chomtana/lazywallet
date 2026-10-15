import { afterEach, describe, expect, it, vi } from 'vitest'
import { readJSON, removeKey, writeJSON } from './storage'

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('storage', () => {
  it('round-trips JSON', () => {
    expect(writeJSON('k', { a: 1 })).toBe(true)
    expect(readJSON('k', null)).toEqual({ a: 1 })
  })

  it('returns fallback for missing key', () => {
    expect(readJSON('missing', 42)).toBe(42)
  })

  it('returns fallback for corrupt JSON', () => {
    localStorage.setItem('k', '{not json')
    expect(readJSON('k', 'fallback')).toBe('fallback')
  })

  it('returns fallback when storage throws on read', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(readJSON('k', 'fallback')).toBe('fallback')
  })

  it('reports false when storage throws on write', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    expect(writeJSON('k', 1)).toBe(false)
  })

  it('removeKey never throws', () => {
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(() => removeKey('k')).not.toThrow()
  })
})
