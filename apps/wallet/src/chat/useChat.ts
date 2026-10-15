import { useState } from 'react'
import { txHash, uid } from '@/lib/format'
import { respond, say } from '@/mock/agent'
import { HOLDINGS } from '@/mock/fixtures'
import type { AgentReply, Contact, Message, Task } from '@/types'
import { speak } from '@/voice/speech'

type Options = { contacts: Contact[]; speakEnabled: boolean; onTask: (task: Task) => void }

const THINK_MS = 500
const CONFIRM_MS = 1500

export function useChat({ contacts, speakEnabled, onTask }: Options) {
  const [messages, setMessages] = useState<Message[]>([])

  const push = (...ms: Message[]) => setMessages((prev) => [...prev, ...ms])
  const update = (id: string, patch: Partial<Message>) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? ({ ...m, ...patch } as Message) : m)))

  function deliver(reply: AgentReply) {
    window.setTimeout(() => {
      push(...reply.messages)
      if (reply.newTask) onTask(reply.newTask)
      const spokenText = reply.messages
        .flatMap((m) => (m.role === 'assistant' && m.kind === 'text' ? [m.text] : []))
        .join(' ')
      speak(spokenText, speakEnabled)
    }, THINK_MS)
  }

  function send(text: string, spoken = false) {
    if (!text.trim()) return
    push({ id: uid(), role: 'user', kind: 'text', text, spoken })
    deliver(respond(text, { contacts, holdings: HOLDINGS }))
  }

  function approve(id: string) {
    update(id, { state: 'approved' })
    const statusId = uid()
    push({ id: statusId, role: 'assistant', kind: 'status', state: 'pending', text: 'Submitting to Sandbox…' })
    window.setTimeout(
      () => update(statusId, { state: 'success', text: 'Done! Transaction confirmed.', hash: txHash() }),
      CONFIRM_MS,
    )
  }

  function reject(id: string) {
    update(id, { state: 'rejected' })
    push(say('Cancelled — nothing was sent.'))
  }

  return { messages, send, deliver, approve, reject }
}
