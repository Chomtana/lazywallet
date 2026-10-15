import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import { useStored } from './useStored'

vi.mock('sonner', () => ({ toast: { error: vi.fn() } }))

afterEach(() => vi.restoreAllMocks())

describe('useStored', () => {
  it('tells the user when it cannot save', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    renderHook(() => useStored('k', 1))
    expect(toast.error).toHaveBeenCalled()
  })
})
