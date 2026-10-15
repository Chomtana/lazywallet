import { useEffect, useReducer, useRef } from 'react'
import { mnemonicToAccount } from 'viem/accounts'
import { executeSteps, progressText, statusPatch, tokenToSave } from '@/chain/executeTx'
import { txDepsFor } from '@/chain/client'
import { shortAddress, txHash, uid } from '@/lib/format'
import { savedTokens, saveToken } from '@/lib/tokens'
import { say } from '@/mock/agent'
import type { Address, AgentReply, ChoiceOption, Contact, Message } from '@/types'
import { speak } from '@/voice/speech'
import { chatReducer, initialChat } from './chatReducer'
import type { ClientMsg, ServerMsg } from './protocol'

const AGENT_WS_URL: string = import.meta.env.VITE_AGENT_WS_URL ?? 'ws://localhost:8787/ws'
const OFFLINE_TEXT = 'Agent offline — run `pnpm dev:agent`, then try again.'
const BUSY_TEXT = 'Still working on your last request — approve or reject any open card first.'
const THINK_MS = 500
const MOCK_CONFIRM_MS = 1500
const MAX_RETRY_MS = 10_000

type Options = { address?: Address; mnemonic?: string; contacts: Contact[]; speakEnabled: boolean }

export function useAgentChat(options: Options) {
  const [state, dispatch] = useReducer(chatReducer, initialChat)
  const wsRef = useRef<WebSocket | null>(null)
  const spokenRef = useRef('')
  const optsRef = useRef(options)
  const stateRef = useRef(state)

  useEffect(() => {
    optsRef.current = options
    stateRef.current = state
  })

  useEffect(() => {
    let disposed = false
    let wasOnline = false
    let retryMs = 1000
    let timer: number | undefined

    function connect() {
      const ws = new WebSocket(AGENT_WS_URL)
      wsRef.current = ws
      ws.onopen = () => {
        if (disposed) return
        retryMs = 1000
        wasOnline = true
        dispatch({ type: 'online', online: true })
      }
      ws.onmessage = (e) => {
        if (disposed) return
        const msg = JSON.parse(String(e.data)) as ServerMsg
        if (msg.type === 'text_delta') spokenRef.current += msg.text
        if (msg.type === 'text_done' || msg.type === 'error') {
          speak(msg.type === 'error' ? msg.message : spokenRef.current, optsRef.current.speakEnabled)
          spokenRef.current = ''
        }
        dispatch({ type: 'server', msg })
      }
      ws.onclose = () => {
        // A socket from an earlier mount (React StrictMode) may close after the live one exists.
        if (wsRef.current === ws) wsRef.current = null
        if (disposed) return
        if (wasOnline) {
          wasOnline = false
          dispatch({ type: 'online', online: false })
          dispatch({ type: 'local', messages: [say(OFFLINE_TEXT)] })
        }
        timer = window.setTimeout(connect, retryMs)
        retryMs = Math.min(retryMs * 2, MAX_RETRY_MS)
      }
    }

    connect()
    return () => {
      disposed = true
      window.clearTimeout(timer)
      wsRef.current?.close()
    }
  }, [])

  function sendJson(msg: ClientMsg): boolean {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return false
    ws.send(JSON.stringify(msg))
    return true
  }

  function deliver(reply: AgentReply) {
    window.setTimeout(() => {
      dispatch({ type: 'local', messages: reply.messages })
      const text = reply.messages.flatMap((m) => (m.role === 'assistant' && m.kind === 'text' ? [m.text] : [])).join(' ')
      speak(text, optsRef.current.speakEnabled)
    }, THINK_MS)
  }

  function send(text: string, spoken = false) {
    const t = text.trim()
    const { address, contacts } = optsRef.current
    if (!t || !address) return
    dispatch({ type: 'local', messages: [{ id: uid(), role: 'user', kind: 'text', text: t, spoken }] })
    if (stateRef.current.busy) return deliver({ messages: [say(BUSY_TEXT)] })
    const sent = sendJson({
      type: 'user',
      text: t,
      spoken,
      address,
      contacts: contacts.map((c) => ({ name: c.name, address: c.address })),
      tokens: savedTokens(address),
    })
    if (!sent) return deliver({ messages: [say(OFFLINE_TEXT)] })
    dispatch({ type: 'busy', busy: true })
  }

  function findWaitingConfirm(id: string) {
    const m = stateRef.current.messages.find((x) => x.id === id)
    return m && m.kind === 'confirm' && m.state === 'waiting' ? m : null
  }

  async function approve(id: string) {
    const m = findWaitingConfirm(id)
    if (!m) return
    const { mnemonic } = optsRef.current
    // The agent quoted this card for one wallet; never sign it from another.
    if (m.tx.from && (!mnemonic || mnemonicToAccount(mnemonic).address.toLowerCase() !== m.tx.from.toLowerCase())) {
      deliver({ messages: [say(`This card is for wallet ${shortAddress(m.tx.from)} — switch back to it to approve.`)] })
      return
    }
    dispatch({ type: 'update', id, patch: { state: 'approved' } })
    const statusId = uid()
    const steps = m.tx.steps
    const pending: Message = {
      id: statusId,
      role: 'assistant',
      kind: 'status',
      state: 'pending',
      text: steps ? progressText(0, steps) : 'Submitting to Sandbox…',
    }
    dispatch({ type: 'local', messages: [pending] })
    if (!steps) {
      // Phase-1 WalletConnect mock card: no real transaction.
      window.setTimeout(
        () => dispatch({ type: 'update', id: statusId, patch: { state: 'success', text: 'Done! Transaction confirmed.', hash: txHash() } }),
        MOCK_CONFIRM_MS,
      )
      return
    }
    // Tell the agent the user approved, so its approval timeout doesn't fire mid-execution.
    sendJson({ type: 'tx_started', id })
    const outcome = mnemonic
      ? await executeSteps(steps, txDepsFor(mnemonic), (i) => dispatch({ type: 'update', id: statusId, patch: { text: progressText(i, steps) } }))
      : { hashes: [], error: 'No wallet is unlocked.', failedStep: 0 }
    dispatch({ type: 'update', id: statusId, patch: statusPatch(outcome, steps) })
    const bought = tokenToSave(outcome, m.tx)
    if (bought && m.tx.from) saveToken(m.tx.from, bought)
    sendJson({
      type: 'tx_result',
      id,
      outcome: 'approved',
      hash: outcome.hash,
      hashes: outcome.hashes,
      status: outcome.status,
      error: outcome.error,
      failed_step: outcome.failedStep,
    })
  }

  function reject(id: string) {
    const m = findWaitingConfirm(id)
    if (!m) return
    dispatch({ type: 'update', id, patch: { state: 'rejected' } })
    if (m.tx.steps) sendJson({ type: 'tx_result', id, outcome: 'rejected' })
    else deliver({ messages: [say('Cancelled — nothing was sent.')] })
  }

  function choose(id: string, option: ChoiceOption) {
    const m = stateRef.current.messages.find((x) => x.id === id)
    if (!m || m.kind !== 'choice' || m.closed) return
    // Only act if the reply can really be sent; otherwise leave the card open to retry.
    const ws = wsRef.current
    if (stateRef.current.busy || !optsRef.current.address || !ws || ws.readyState !== WebSocket.OPEN) return
    dispatch({ type: 'update', id, patch: { chosen: option.label } })
    send(option.reply)
  }

  return { messages: state.messages, busy: state.busy, online: state.online, send, approve, reject, choose, deliver }
}
