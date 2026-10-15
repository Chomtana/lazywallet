import { describe, expect, it, vi } from 'vitest'
import type { TxRequest, TxStep } from '@/types'
import { executeSteps, executeTx, progressText, statusPatch, type TxDeps } from './executeTx'

const req: TxRequest = { to: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', value: '100', data: '0x' }
const HASH = '0xabc' as const
const ONE: TxStep[] = [{ label: 'Send', request: req }]
const THREE: TxStep[] = [
  { label: 'Allow USDC', request: req },
  { label: 'Allow Uniswap router', request: req },
  { label: 'Swap USDC → ETH', request: req },
]

describe('executeTx', () => {
  it('returns hash and receipt status', async () => {
    const deps: TxDeps = { send: async () => HASH, wait: async () => 'success' }
    expect(await executeTx(req, deps)).toEqual({ hash: HASH, status: 'success' })
  })

  it('reports send errors using the short message when present', async () => {
    const deps: TxDeps = {
      send: async () => {
        throw Object.assign(new Error('long details'), { shortMessage: 'insufficient funds' })
      },
      wait: async () => 'success',
    }
    expect(await executeTx(req, deps)).toEqual({ error: 'insufficient funds' })
  })

  it('reports receipt errors with the hash', async () => {
    const deps: TxDeps = {
      send: async () => HASH,
      wait: async () => {
        throw new Error('timeout')
      },
    }
    expect(await executeTx(req, deps)).toEqual({ hash: HASH, error: 'timeout' })
  })
})

describe('executeSteps', () => {
  it('runs every step in order and reports progress', async () => {
    let n = 0
    const deps: TxDeps = { send: async () => `0x${++n}` as `0x${string}`, wait: async () => 'success' }
    const onStep = vi.fn()
    expect(await executeSteps(THREE, deps, onStep)).toEqual({ hashes: ['0x1', '0x2', '0x3'], hash: '0x3', status: 'success' })
    expect(onStep.mock.calls.map((c) => c[0])).toEqual([0, 1, 2])
  })

  it('stops at the first reverted step', async () => {
    let n = 0
    const deps: TxDeps = { send: async () => `0x${++n}` as `0x${string}`, wait: async (h) => (h === '0x2' ? 'reverted' : 'success') }
    expect(await executeSteps(THREE, deps)).toEqual({ hashes: ['0x1', '0x2'], hash: '0x2', status: 'reverted', failedStep: 1 })
  })

  it('stops when a step cannot be sent', async () => {
    let n = 0
    const deps: TxDeps = {
      send: async () => {
        if (++n === 3) throw new Error('rejected by node')
        return `0x${n}` as `0x${string}`
      },
      wait: async () => 'success',
    }
    expect(await executeSteps(THREE, deps)).toEqual({ hashes: ['0x1', '0x2'], hash: undefined, error: 'rejected by node', failedStep: 2 })
  })
})

describe('statusPatch and progressText', () => {
  it('keeps single-step wording', () => {
    expect(statusPatch({ hashes: [HASH], hash: HASH, status: 'success' }, ONE)).toEqual({ state: 'success', text: 'Confirmed on Sandbox.', hash: HASH })
    expect(statusPatch({ hashes: [HASH], hash: HASH, status: 'reverted', failedStep: 0 }, ONE)).toEqual({
      state: 'failed',
      text: 'Transaction reverted.',
      hash: HASH,
    })
    expect(statusPatch({ hashes: [], error: 'nope', failedStep: 0 }, ONE)).toEqual({ state: 'failed', text: 'Failed: nope', hash: undefined })
  })

  it('names the failing step for multi-step cards', () => {
    expect(statusPatch({ hashes: ['0x1', '0x2'], hash: '0x2', status: 'reverted', failedStep: 2 }, THREE).text).toBe(
      'Swap USDC → ETH: Transaction reverted.',
    )
  })

  it('shows progress only for multi-step cards', () => {
    expect(progressText(1, THREE)).toBe('Step 2 of 3: Allow Uniswap router…')
    expect(progressText(0, ONE)).toBe('Submitting to Sandbox…')
  })
})
