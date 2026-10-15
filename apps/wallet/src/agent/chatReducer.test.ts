import { describe, expect, it } from 'vitest'
import type { Message } from '@/types'
import { chatReducer, initialChat, progressLabel, type ChatEvent, type ChatState } from './chatReducer'

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

  it('adds a token list card', () => {
    const item = {
      symbol: 'COQ',
      name: 'COQINU',
      network: 'Avalanche',
      address: '0x420fca0121dc28039145009570975747295f2329' as const,
      priceUsd: 1.2e-7,
      change24h: -5.1,
      liquidityUsd: 623_823.6,
      dex: 'LFJ',
      buyable: true,
      note: null,
      image: null,
    }
    const s = run([server({ type: 'text_delta', text: 'Hi' }), server({ type: 'tokens', title: 'Trending memecoins', items: [item] })])
    expect(s.messages[1]).toMatchObject({ role: 'assistant', kind: 'tokens', title: 'Trending memecoins', items: [item] })
    expect(new Set(s.messages.map((m) => m.id)).size).toBe(2)
    expect(s.streamingId).toBeNull()
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

  const choiceMsg = server({
    type: 'choice',
    id: 'c1',
    question: 'Which network for USDC?',
    options: [
      { label: 'Ethereum', detail: '500 USDC', reply: 'Use Ethereum for that.' },
      { label: 'Avalanche', detail: '20 USDC', reply: 'Use Avalanche for that.' },
    ],
  })

  it('adds a choice card that stays open after the turn ends', () => {
    const s = run([choiceMsg, server({ type: 'turn_end' })])
    expect(s.messages[0]).toMatchObject({ id: 'c1', kind: 'choice', question: 'Which network for USDC?' })
    expect(s.messages[0]).not.toHaveProperty('closed', true)
  })

  it('closes open choice cards when the user answers in any way', () => {
    const user: Message = { id: 'u1', role: 'user', kind: 'text', text: 'avalanche' }
    const s = run([choiceMsg, { type: 'local', messages: [user] }])
    expect(s.messages[0]).toMatchObject({ kind: 'choice', closed: true })
  })

  it('closes open choice cards when the connection drops (a new session has no context)', () => {
    const s = run([choiceMsg, server({ type: 'turn_end' }), { type: 'online', online: false }])
    expect(s.messages[0]).toMatchObject({ kind: 'choice', closed: true })
  })

  it('adds a balance change card', () => {
    const change = { network: 'Ethereum', symbol: 'USDC', before: 500, after: 400, delta: -100, usdPrice: 1 }
    const s = run([server({ type: 'balance_change', changes: [change] })])
    expect(s.messages[0]).toMatchObject({ role: 'assistant', kind: 'balance_change', changes: [change] })
  })
})

describe('progress', () => {
  const busy: ChatEvent = { type: 'busy', busy: true }
  const thinking = server({ type: 'progress', label: 'Thinking…' })

  it('shows the latest progress label while busy', () => {
    const s = run([busy, thinking, server({ type: 'progress', label: 'Checking your balances' })])
    expect(progressLabel(s)).toBe('Checking your balances')
    expect(s.messages).toHaveLength(0) // not a chat message
  })

  it('hides once reply text streams, and comes back on the next tool call', () => {
    const s = run([busy, thinking, server({ type: 'text_delta', text: 'Hi' })])
    expect(progressLabel(s)).toBeNull()
    const t = run([server({ type: 'text_done' }), server({ type: 'progress', label: 'Finding the best route' })], s)
    expect(progressLabel(t)).toBe('Finding the best route')
  })

  it.each([
    ['turn_end', [server({ type: 'turn_end' })]],
    ['error', [server({ type: 'error', message: 'boom' })]],
    ['offline', [{ type: 'online', online: false }]],
  ] as [string, ChatEvent[]][])('clears on %s', (_, events) => {
    expect(progressLabel(run([busy, thinking, ...events]))).toBeNull()
  })

  it('says it is waiting for approval while an agent confirm card is open', () => {
    const s = run([busy, thinking, server({ type: 'progress', label: 'Preparing your transfer' }), confirmMsg])
    expect(progressLabel(s)).toBe('Waiting for your approval')
    expect(progressLabel(run([{ type: 'update', id: 'p1', patch: { state: 'approved' } }], s))).toBeNull()
  })
})

describe('queue', () => {
  const queued = (id: string, text: string): Extract<Message, { role: 'user' }> => ({ id, role: 'user', kind: 'text', text })

  it('holds queued prompts outside the chat, in order', () => {
    const s = run([{ type: 'busy', busy: true }, { type: 'enqueue', message: queued('q1', 'one') }, { type: 'enqueue', message: queued('q2', 'two') }])
    expect(s.queue.map((m) => m.text)).toEqual(['one', 'two'])
    expect(s.messages).toHaveLength(0)
  })

  it('dequeue moves the oldest into the chat as a normal message and marks busy', () => {
    const s = run([
      server({ type: 'choice', id: 'c1', question: 'Which network?', options: [] }),
      { type: 'enqueue', message: queued('q1', 'one') },
      { type: 'enqueue', message: queued('q2', 'two') },
      server({ type: 'turn_end' }),
      { type: 'dequeue' },
    ])
    expect(s.busy).toBe(true)
    expect(s.queue.map((m) => m.text)).toEqual(['two'])
    expect(s.messages.at(-1)).toEqual(queued('q1', 'one'))
    expect(s.messages[0]).toMatchObject({ kind: 'choice', closed: true })
  })

  it('marks queued prompts "Not sent" when the connection drops', () => {
    const s = run([{ type: 'busy', busy: true }, { type: 'enqueue', message: queued('q1', 'one') }, { type: 'online', online: false }])
    expect(s.queue).toEqual([])
    expect(s.messages).toEqual([{ ...queued('q1', 'one'), unsent: true }])
  })
})
