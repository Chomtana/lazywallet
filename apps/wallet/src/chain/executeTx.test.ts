import { describe, expect, it } from 'vitest'
import type { TxRequest } from '@/types'
import { executeTx, statusPatch, type TxDeps } from './executeTx'

const req: TxRequest = { to: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', value: '100', data: '0x' }
const HASH = '0xabc' as const

describe('executeTx', () => {
  it('returns hash and receipt status', async () => {
    const deps: TxDeps = { send: async () => HASH, wait: async () => 'success' }
    expect(await executeTx(req, deps)).toEqual({ hash: HASH, status: 'success' })
  })

  it('reports a revert', async () => {
    const deps: TxDeps = { send: async () => HASH, wait: async () => 'reverted' }
    expect(await executeTx(req, deps)).toEqual({ hash: HASH, status: 'reverted' })
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

describe('statusPatch', () => {
  it('maps outcomes to status card states', () => {
    expect(statusPatch({ hash: HASH, status: 'success' })).toEqual({ state: 'success', text: 'Confirmed on Sandbox.', hash: HASH })
    expect(statusPatch({ hash: HASH, status: 'reverted' })).toEqual({ state: 'failed', text: 'Transaction reverted.', hash: HASH })
    expect(statusPatch({ error: 'nope' })).toEqual({ state: 'failed', text: 'Failed: nope', hash: undefined })
  })
})
