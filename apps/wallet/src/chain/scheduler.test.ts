import { describe, expect, test } from 'vitest'
import { durationLabel, mergeSettled, orderStatus } from './scheduler'

const base = { cancelled: false, executed: 1, count: 3, nextTime: 1_000 }

describe('durationLabel', () => {
  test('rounds to the largest unit', () => {
    expect(durationLabel(45)).toBe('45s')
    expect(durationLabel(60)).toBe('1 min')
    expect(durationLabel(7200)).toBe('2 h')
    expect(durationLabel(604800)).toBe('7 d')
  })
})

describe('orderStatus', () => {
  test('active with time until next run', () => {
    expect(orderStatus(base, 970)).toEqual({ state: 'active', label: 'Next run in 30s' })
  })
  test('due now once nextTime passes', () => {
    expect(orderStatus(base, 1_005)).toEqual({ state: 'active', label: 'Due now' })
  })
  test('done after the last run', () => {
    expect(orderStatus({ ...base, executed: 3 }, 0)).toEqual({ state: 'done', label: 'Done' })
  })
  test('cancelled wins', () => {
    expect(orderStatus({ ...base, cancelled: true }, 0)).toEqual({ state: 'cancelled', label: 'Cancelled' })
  })
})

describe('mergeSettled', () => {
  test('mergeSettled keeps fulfilled chains', () => {
    const ok: PromiseSettledResult<number[]> = { status: 'fulfilled', value: [1, 2] }
    const down: PromiseSettledResult<number[]> = { status: 'rejected', reason: new Error('fork down') }
    expect(mergeSettled([down, ok])).toEqual([1, 2])
  })
})
