import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { savedTokens } from '@/lib/tokens'
import { useAgentChat } from './useAgentChat'

vi.mock('@/chain/client', () => ({
  txDepsFor: () => ({ send: async () => '0x1', wait: async () => 'success' }),
}))

class FakeWebSocket {
  static OPEN = 1
  static instances: FakeWebSocket[] = []
  readyState = 0
  sent: string[] = []
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  constructor() {
    FakeWebSocket.instances.push(this)
  }
  send(data: string) {
    this.sent.push(data)
  }
  close() {
    this.readyState = 3
    queueMicrotask(() => this.onclose?.())
  }
  open() {
    this.readyState = 1
    this.onopen?.()
  }
}

const OPTIONS = {
  address: '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266' as const,
  mnemonic: 'test test test test test test test test test test test junk',
  contacts: [],
  speakEnabled: false,
}

beforeEach(() => {
  FakeWebSocket.instances = []
  vi.stubGlobal('WebSocket', FakeWebSocket)
})
afterEach(() => vi.unstubAllGlobals())

describe('useAgentChat', () => {
  it('sends over the live socket after a StrictMode remount closes the first one', async () => {
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    expect(FakeWebSocket.instances).toHaveLength(2)
    const live = FakeWebSocket.instances.at(-1)!
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    act(() => result.current.send("What's my balance?"))
    expect(live.sent).toHaveLength(1)
    expect(JSON.parse(live.sent[0])).toMatchObject({ type: 'user', text: "What's my balance?" })
    expect(result.current.busy).toBe(true)
  })

  it('streams server text into the chat', async () => {
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    expect(FakeWebSocket.instances).toHaveLength(2)
    const live = FakeWebSocket.instances.at(-1)!
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    act(() => {
      live.onmessage?.({ data: JSON.stringify({ type: 'text_delta', text: 'Hi' }) })
      live.onmessage?.({ data: JSON.stringify({ type: 'text_done' }) })
      live.onmessage?.({ data: JSON.stringify({ type: 'turn_end' }) })
    })
    expect(result.current.messages.at(-1)).toMatchObject({ kind: 'text', text: 'Hi' })
    expect(result.current.online).toBe(true)
  })

  it('refuses to approve a card quoted for a different wallet', async () => {
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    const live = FakeWebSocket.instances.at(-1)!
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    const otherWallet = '0x70997970C51812dc3A010C7d01b50e0d17dc79C8'
    act(() =>
      live.onmessage?.({
        data: JSON.stringify({
          type: 'confirm',
          id: 'pabc',
          tx: { title: 'Send 1 ETH', from: otherWallet, rows: [], steps: [{ label: 'Send', request: { to: otherWallet, value: '1', data: '0x' } }] },
        }),
      }),
    )
    await act(() => result.current.approve('pabc'))
    expect(result.current.messages.find((m) => m.id === 'pabc')).toMatchObject({ state: 'waiting' })
    expect(live.sent).toHaveLength(0)
  })

  it('tells the agent the user started approving before running the steps', async () => {
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    const live = FakeWebSocket.instances.at(-1)!
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    const me = OPTIONS.address
    act(() =>
      live.onmessage?.({
        data: JSON.stringify({
          type: 'confirm',
          id: 'pmine',
          tx: { title: 'Send 1 ETH', from: me, rows: [], steps: [{ label: 'Send', request: { to: me, value: '1', data: '0x' } }] },
        }),
      }),
    )
    await act(() => result.current.approve('pmine'))
    expect(live.sent.map((s) => JSON.parse(s).type)).toEqual(['tx_started', 'tx_result'])
    expect(JSON.parse(live.sent[1])).toMatchObject({ id: 'pmine', status: 'success', hashes: ['0x1'] })
  })

  it('choose() marks the option and sends its reply as a user message', async () => {
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    const live = FakeWebSocket.instances.at(-1)!
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    const option = { label: 'Avalanche', detail: '20 USDC', reply: 'Use Avalanche for that.' }
    act(() =>
      live.onmessage?.({ data: JSON.stringify({ type: 'choice', id: 'c1', question: 'Which network for USDC?', options: [option] }) }),
    )
    act(() => result.current.choose('c1', option))
    expect(JSON.parse(live.sent.at(-1)!)).toMatchObject({ type: 'user', text: 'Use Avalanche for that.' })
    expect(result.current.messages[0]).toMatchObject({ kind: 'choice', chosen: 'Avalanche', closed: true })
    act(() => result.current.choose('c1', option))
    expect(live.sent).toHaveLength(1) // a closed card can't send twice
  })

  const CHOICE = { label: 'Avalanche', detail: '20 USDC', reply: 'Use Avalanche for that.' }
  const choiceFrame = JSON.stringify({ type: 'choice', id: 'c1', question: 'Which network?', options: [CHOICE] })

  it('choose() while busy leaves the card open and sends nothing', async () => {
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    const live = FakeWebSocket.instances.at(-1)!
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    act(() => result.current.send('swap usdc'))
    act(() => live.onmessage?.({ data: choiceFrame }))
    const before = result.current.messages.length
    act(() => result.current.choose('c1', CHOICE))
    expect(live.sent).toHaveLength(1)
    expect(result.current.messages).toHaveLength(before)
    expect(result.current.messages.at(-1)).not.toHaveProperty('chosen')
    expect(result.current.messages.at(-1)).not.toHaveProperty('closed', true)
  })

  it('choose() while offline leaves the card open and sends nothing', async () => {
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    const live = FakeWebSocket.instances.at(-1)!
    act(() => live.onmessage?.({ data: choiceFrame }))
    act(() => result.current.choose('c1', CHOICE))
    expect(live.sent).toHaveLength(0)
    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0]).not.toHaveProperty('chosen')
    expect(result.current.messages[0]).not.toHaveProperty('closed', true)
  })

  it('buy() sends the text as a user message, but not while busy or offline', async () => {
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    const live = FakeWebSocket.instances.at(-1)!
    act(() => result.current.buy('Buy 0.1 AVAX of COQ (0x420FcA0121DC28039145009570975747295f2329)'))
    expect(live.sent).toHaveLength(0) // offline
    expect(result.current.messages).toHaveLength(0)
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    act(() => result.current.buy('Buy 0.1 AVAX of COQ (0x420FcA0121DC28039145009570975747295f2329)'))
    expect(JSON.parse(live.sent.at(-1)!)).toMatchObject({ type: 'user', text: 'Buy 0.1 AVAX of COQ (0x420FcA0121DC28039145009570975747295f2329)' })
    act(() => result.current.buy('Buy 1 AVAX of COQ (0x420FcA0121DC28039145009570975747295f2329)'))
    expect(live.sent).toHaveLength(1) // busy with the first one
    expect(result.current.messages).toHaveLength(1)
  })

  it('saves a bought token after the swap succeeds and sends saved tokens with each message', async () => {
    localStorage.clear()
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    const live = FakeWebSocket.instances.at(-1)!
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    const me = OPTIONS.address
    const COQ = { chainId: 43114, address: '0x420FcA0121DC28039145009570975747295f2329', symbol: 'COQ', decimals: 18 }
    const step = { label: 'Swap AVAX → COQ', request: { to: me, value: '1', data: '0x', chainId: 43114 } }
    act(() =>
      live.onmessage?.({
        data: JSON.stringify({ type: 'confirm', id: 'pbuy', tx: { title: 'Swap 1 AVAX → COQ', from: me, rows: [], steps: [step], addToken: COQ } }),
      }),
    )
    expect(savedTokens(me)).toEqual([])
    await act(() => result.current.approve('pbuy'))
    expect(savedTokens(me)).toEqual([COQ])
    act(() => result.current.send('sell all my COQ'))
    expect(JSON.parse(live.sent.at(-1)!)).toMatchObject({ type: 'user', text: 'sell all my COQ', tokens: [COQ] })
  })

  it('queues a prompt sent while busy and sends queued prompts one at a time after each turn_end', async () => {
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    const live = FakeWebSocket.instances.at(-1)!
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    const turnEnd = () => act(() => live.onmessage?.({ data: JSON.stringify({ type: 'turn_end' }) }))
    const sentTexts = () => live.sent.map((x) => JSON.parse(x).text)
    act(() => result.current.send('one'))
    act(() => result.current.send('two', true))
    act(() => result.current.send('three'))
    expect(sentTexts()).toEqual(['one'])
    expect(result.current.messages.map((m) => (m.kind === 'text' ? m.text : ''))).toEqual(['one']) // no busy reply
    expect(result.current.queue.map((m) => m.text)).toEqual(['two', 'three'])
    turnEnd()
    expect(sentTexts()).toEqual(['one', 'two'])
    expect(JSON.parse(live.sent[1])).toMatchObject({ type: 'user', spoken: true })
    expect(result.current.messages.at(-1)).toMatchObject({ role: 'user', text: 'two' })
    expect(result.current.queue.map((m) => m.text)).toEqual(['three'])
    expect(result.current.busy).toBe(true)
    turnEnd()
    expect(sentTexts()).toEqual(['one', 'two', 'three'])
    expect(result.current.queue).toEqual([])
  })

  it('shows progress labels from the agent while busy', async () => {
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    const live = FakeWebSocket.instances.at(-1)!
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    act(() => result.current.send('balance?'))
    act(() => live.onmessage?.({ data: JSON.stringify({ type: 'progress', label: 'Checking your balances' }) }))
    expect(result.current.progress).toBe('Checking your balances')
  })

  it('marks queued prompts "Not sent" on disconnect and never sends them later', async () => {
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    const live = FakeWebSocket.instances.at(-1)!
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    act(() => result.current.send('one'))
    act(() => result.current.send('two'))
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      await act(async () => {
        live.close()
        await Promise.resolve()
      })
      expect(result.current.queue).toEqual([])
      expect(result.current.messages.find((m) => m.role === 'user' && m.text === 'two')).toMatchObject({ unsent: true })
      await act(async () => {
        vi.advanceTimersByTime(1000)
      })
      const next = FakeWebSocket.instances.at(-1)!
      expect(next).not.toBe(live)
      await act(async () => {
        next.open()
        await Promise.resolve()
      })
      expect(next.sent).toHaveLength(0)
    } finally {
      vi.useRealTimers()
    }
  })
})
