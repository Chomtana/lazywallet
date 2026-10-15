import { describe, expect, it } from 'vitest'
import { QUICK_ACTIONS } from './quickActions'

describe('QUICK_ACTIONS', () => {
  it('lists the four judge-facing actions in order, each with the message it sends', () => {
    expect(QUICK_ACTIONS).toEqual([
      { label: 'Check balances', text: "What's my balance?" },
      { label: 'Trending airdrops', text: 'What airdrops can I farm?' },
      { label: 'Upcoming unlocks', text: 'What are the upcoming token unlocks?' },
      { label: 'Trending memes', text: 'What memecoins are trending?' },
    ])
  })

  it('never names a chain or a coming-soon note', () => {
    for (const a of QUICK_ACTIONS) {
      expect(`${a.label} ${a.text}`).not.toMatch(/avalanche|ethereum|sandbox|soon/i)
    }
  })
})
