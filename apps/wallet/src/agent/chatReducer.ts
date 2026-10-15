import type { Message } from '@/types'
import type { ServerMsg } from './protocol'

export type ChatState = {
  messages: Message[]
  streamingId: string | null
  busy: boolean
  online: boolean
  seq: number
}

export type ChatEvent =
  | { type: 'local'; messages: Message[] }
  | { type: 'server'; msg: ServerMsg }
  | { type: 'busy'; busy: boolean }
  | { type: 'online'; online: boolean }
  | { type: 'update'; id: string; patch: Partial<Message> }

export const initialChat: ChatState = { messages: [], streamingId: null, busy: false, online: false, seq: 0 }

// Agent cards (they carry a tx request) can no longer be answered once the agent's turn or session is gone.
function expireAgentCards(messages: Message[]): Message[] {
  return messages.map((m) => (m.kind === 'confirm' && m.state === 'waiting' && m.tx.steps ? { ...m, state: 'expired' } : m))
}

function closeChoices(messages: Message[]): Message[] {
  return messages.map((m) => (m.kind === 'choice' && !m.closed ? { ...m, closed: true } : m))
}

function onServer(s: ChatState, msg: ServerMsg): ChatState {
  const nextId = `a${s.seq}`
  switch (msg.type) {
    case 'text_delta':
      if (s.streamingId) {
        return {
          ...s,
          messages: s.messages.map((m) => (m.id === s.streamingId && m.kind === 'text' ? { ...m, text: m.text + msg.text } : m)),
        }
      }
      return {
        ...s,
        seq: s.seq + 1,
        streamingId: nextId,
        messages: [...s.messages, { id: nextId, role: 'assistant', kind: 'text', text: msg.text }],
      }
    case 'text_done':
      return { ...s, streamingId: null }
    case 'balances':
      return {
        ...s,
        seq: s.seq + 1,
        streamingId: null,
        messages: [...s.messages, { id: nextId, role: 'assistant', kind: 'balance', holdings: msg.holdings }],
      }
    case 'balance_change':
      return {
        ...s,
        seq: s.seq + 1,
        streamingId: null,
        messages: [...s.messages, { id: nextId, role: 'assistant', kind: 'balance_change', changes: msg.changes }],
      }
    case 'tokens':
      return {
        ...s,
        seq: s.seq + 1,
        streamingId: null,
        messages: [...s.messages, { id: nextId, role: 'assistant', kind: 'tokens', title: msg.title, items: msg.items }],
      }
    case 'confirm':
      return {
        ...s,
        streamingId: null,
        messages: [...s.messages, { id: msg.id, role: 'assistant', kind: 'confirm', tx: msg.tx, state: 'waiting' }],
      }
    case 'choice':
      return {
        ...s,
        streamingId: null,
        messages: [...s.messages, { id: msg.id, role: 'assistant', kind: 'choice', question: msg.question, options: msg.options }],
      }
    case 'error':
      return {
        ...s,
        seq: s.seq + 1,
        streamingId: null,
        messages: [...s.messages, { id: nextId, role: 'assistant', kind: 'text', text: msg.message }],
      }
    case 'turn_end':
      return { ...s, busy: false, streamingId: null, messages: expireAgentCards(s.messages) }
  }
}

export function chatReducer(s: ChatState, e: ChatEvent): ChatState {
  switch (e.type) {
    case 'local': {
      const answered = e.messages.some((m) => m.role === 'user')
      return { ...s, messages: [...(answered ? closeChoices(s.messages) : s.messages), ...e.messages] }
    }
    case 'server':
      return onServer(s, e.msg)
    case 'busy':
      return { ...s, busy: e.busy }
    case 'online':
      return e.online
        ? { ...s, online: true }
        : { ...s, online: false, busy: false, streamingId: null, messages: closeChoices(expireAgentCards(s.messages)) }
    case 'update':
      return { ...s, messages: s.messages.map((m) => (m.id === e.id ? ({ ...m, ...e.patch } as Message) : m)) }
  }
}
