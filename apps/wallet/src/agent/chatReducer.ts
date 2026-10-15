import type { Message } from '@/types'
import type { ServerMsg } from './protocol'

export type ChatState = {
  messages: Message[]
  streamingId: string | null
  busy: boolean
  online: boolean
  seq: number
  progress: string | null // what the agent is doing right now (not a chat message)
  queue: UserText[] // prompts typed or spoken while busy, sent in order after turn_end
}

export type UserText = Extract<Message, { role: 'user' }>

export type ChatEvent =
  | { type: 'local'; messages: Message[] }
  | { type: 'server'; msg: ServerMsg }
  | { type: 'busy'; busy: boolean }
  | { type: 'online'; online: boolean }
  | { type: 'update'; id: string; patch: Partial<Message> }
  | { type: 'enqueue'; message: UserText }
  | { type: 'dequeue' } // the oldest queued prompt was sent

export const initialChat: ChatState = { messages: [], streamingId: null, busy: false, online: false, seq: 0, progress: null, queue: [] }

// Agent cards (they carry a tx request) can no longer be answered once the agent's turn or session is gone.
function expireAgentCards(messages: Message[]): Message[] {
  return messages.map((m) => (m.kind === 'confirm' && m.state === 'waiting' && m.tx.steps ? { ...m, state: 'expired' } : m))
}

function closeChoices(messages: Message[]): Message[] {
  return messages.map((m) => (m.kind === 'choice' && !m.closed ? { ...m, closed: true } : m))
}

export const WAITING_FOR_APPROVAL = 'Waiting for your approval'

// The progress bubble's label, or null when it should be hidden.
export function progressLabel(s: ChatState): string | null {
  if (!s.busy) return null
  if (s.messages.some((m) => m.kind === 'confirm' && m.state === 'waiting' && m.tx.steps)) return WAITING_FOR_APPROVAL
  return s.progress
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
        progress: null,
        messages: [...s.messages, { id: nextId, role: 'assistant', kind: 'text', text: msg.text }],
      }
    case 'text_done':
      return { ...s, streamingId: null }
    case 'progress':
      return { ...s, progress: msg.label }
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
        progress: null,
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
        progress: null,
        messages: [...s.messages, { id: nextId, role: 'assistant', kind: 'text', text: msg.message }],
      }
    case 'turn_end':
      return { ...s, busy: false, streamingId: null, progress: null, messages: expireAgentCards(s.messages) }
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
        : {
            ...s,
            online: false,
            busy: false,
            streamingId: null,
            progress: null,
            queue: [],
            messages: [...closeChoices(expireAgentCards(s.messages)), ...s.queue.map((m) => ({ ...m, unsent: true }))],
          }
    case 'update':
      return { ...s, messages: s.messages.map((m) => (m.id === e.id ? ({ ...m, ...e.patch } as Message) : m)) }
    case 'enqueue':
      return { ...s, queue: [...s.queue, e.message] }
    case 'dequeue': {
      const [next, ...rest] = s.queue
      return next ? { ...s, busy: true, queue: rest, messages: [...closeChoices(s.messages), next] } : s
    }
  }
}
