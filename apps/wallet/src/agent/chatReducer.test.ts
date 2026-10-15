import { describe, expect, it } from 'vitest'
import type { Message } from '@/types'
import { chatReducer, initialChat, type ChatEvent, type ChatState } from './chatReducer'

const run = (events: ChatEvent[], from: ChatState = initialChat) => events.reduce(chatReducer, from)
const server = (msg: Extract<ChatEvent, { type: 'server' }>['msg']): ChatEvent => ({ type: 'server', msg })
const confirmMsg = server({
  type: 'confirm',
  id: 'p1',
  tx: {
    title: 'Send 0.1 ETH',
    from: '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266',
    rows: [],
    steps: [{ label: 'Send', request: { to: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', value: '1', data: '0x' } }],
  },
})

describe('chatReducer', () => {
  it('streams deltas into one assistant bubble and ends it on text_done', () => {
    const s = run([server({ type: 'text_delta', text: 'Hel' }), server({ type: 'text_delta', text: 'lo' }), server({ type: 'text_done' })])
    expect(s.messages).toHaveLength(1)
    expect(s.messages[0]).toMatchObject({ role: 'assistant', kind: 'text', text: 'Hello' })
    expect(s.streamingId).toBeNull()
  })

  it('starts a new bubble after text_done', () => {
    const s = run([
      server({ type: 'text_delta', text: 'One' }),
      server({ type: 'text_done' }),
      server({ type: 'text_delta', text: 'Two' }),
    ])
    expect(s.messages.map((m) => (m.kind === 'text' ? m.text : ''))).toEqual(['One', 'Two'])
    expect(new Set(s.messages.map((m) => m.id)).size).toBe(2)
  })

  it('adds balance and confirm cards', () => {
    const s = run([server({ type: 'balances', holdings: [{ symbol: 'ETH', amount: 1, usdPrice: 3000 }] }), confirmMsg])
    expect(s.messages[0].kind).toBe('balance')
    expect(s.messages[1]).toMatchObject({ id: 'p1', kind: 'confirm', state: 'waiting' })
  })

  it('turn_end clears busy and expires cards still waiting for the agent', () => {
    const s = run([{ type: 'busy', busy: true }, confirmMsg, server({ type: 'turn_end' })])
    expect(s.busy).toBe(false)
    expect((s.messages[0] as Extract<Message, { kind: 'confirm' }>).state).toBe('expired')
  })

  it('going offline clears busy and expires waiting agent cards, but not mock cards', () => {
    const mock: Message = { id: 'm1', role: 'assistant', kind: 'confirm', state: 'waiting', tx: { title: 'Mock', rows: [] } }
    const s = run([{ type: 'busy', busy: true }, { type: 'local', messages: [mock] }, confirmMsg, { type: 'online', online: false }])
    expect(s.busy).toBe(false)
    expect(s.online).toBe(false)
    expect(s.messages.map((m) => (m.kind === 'confirm' ? m.state : ''))).toEqual(['waiting', 'expired'])
  })

  it('error ends streaming and shows the message', () => {
    const s = run([server({ type: 'text_delta', text: 'x' }), server({ type: 'error', message: 'boom' })])
    expect(s.streamingId).toBeNull()
    expect(s.messages[1]).toMatchObject({ kind: 'text', text: 'boom' })
  })

  it('update patches one message', () => {
    const s = run([confirmMsg, { type: 'update', id: 'p1', patch: { state: 'approved' } }])
    expect(s.messages[0]).toMatchObject({ state: 'approved' })
  })
})
