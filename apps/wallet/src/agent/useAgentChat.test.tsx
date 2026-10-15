import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAgentChat } from './useAgentChat'

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
})
