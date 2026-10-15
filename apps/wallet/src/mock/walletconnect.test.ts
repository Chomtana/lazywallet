import { describe, expect, it } from 'vitest'
import { UNISWAP } from './fixtures'
import { dappRequest, isWcUri } from './walletconnect'

const topic = 'a'.repeat(64)
const valid = `wc:${topic}@2?relay-protocol=irn&symKey=${'b'.repeat(64)}&expiryTimestamp=1760000000`

describe('isWcUri', () => {
  it('accepts a v2 pairing URI, tolerating surrounding whitespace', () => {
    expect(isWcUri(valid)).toBe(true)
    expect(isWcUri(`  ${valid}\n`)).toBe(true)
  })
  it('rejects v1 URIs, missing params and non-wc text', () => {
    expect(isWcUri(`wc:${topic}@1?bridge=https%3A%2F%2Fbridge&key=abc`)).toBe(false)
    expect(isWcUri(`wc:${topic}@2?relay-protocol=irn`)).toBe(false)
    expect(isWcUri('https://app.uniswap.org')).toBe(false)
    expect(isWcUri('')).toBe(false)
  })
})

describe('dappRequest', () => {
  it('produces an explained confirm card from the dapp', () => {
    const reply = dappRequest(UNISWAP)
    const card = reply.messages.find((m) => m.kind === 'confirm')
    if (!card || card.kind !== 'confirm') throw new Error('expected confirm')
    expect(card.tx.dapp).toEqual(UNISWAP)
    expect(card.tx.explanation).toBeTruthy()
  })
})
