import { getAddress, isAddress } from 'viem'
import { formatAmount, formatUsd, shortAddress, uid } from '@/lib/format'
import type { AgentReply, Contact, Holding, Message, Task, TxDraft } from '@/types'

export type AgentContext = { contacts: Contact[]; holdings: Holding[] }

const NUM = '(\\d+(?:\\.\\d+)?)'
const SYM = '([a-z]+)'
const DAYS = 'day|week|monday|tuesday|wednesday|thursday|friday|saturday|sunday'
const BELOW = '(?:<|is below|drops below|falls below|goes below|below|under)'

const CONDITIONAL = new RegExp(`^if ${SYM} ${BELOW} \\$?${NUM},? (?:then )?swap ${NUM} ?${SYM} (?:to|for|into) ${SYM}$`)
const ALERT = new RegExp(`(?:alert|notify|tell) me (?:if|when) ${SYM} ${BELOW} \\$?${NUM}`)
const DCA = new RegExp(`buy ${SYM} every (${DAYS}) with ${NUM} ?${SYM}`)
const SEND = new RegExp(`^(?:send|transfer|pay) ${NUM} ?${SYM} to (.+)$`)
const SWAP = new RegExp(`^swap ${NUM} ?${SYM} (?:to|for|into) ${SYM}$`)

const FALLBACK =
  'I can\'t do that yet. Try: "What\'s my balance?", "Send 0.1 ETH to Alice", "Swap 100 USDC to ETH" or "Alert me if ETH drops below 3000".'

export const say = (text: string): Message => ({ id: uid(), role: 'assistant', kind: 'text', text })
export const confirm = (tx: TxDraft): Message => ({ id: uid(), role: 'assistant', kind: 'confirm', tx, state: 'waiting' })

// Voice transcripts arrive capitalised, punctuated and with thousands separators.
function normalize(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/(\d),(?=\d{3}\b)/g, '$1')
    .replace(/[.!?]+$/, '')
    .replace(/\s+/g, ' ')
}

const usdLabel = (n: number) => `$${n.toLocaleString('en-US')}`
const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

function findHolding(ctx: AgentContext, symbol: string) {
  return ctx.holdings.find((h) => h.symbol === symbol.toUpperCase())
}

function checkSpend(ctx: AgentContext, amount: number, symbol: string): Holding | string {
  const sym = symbol.toUpperCase()
  if (amount <= 0) return 'The amount needs to be more than 0.'
  const holding = findHolding(ctx, symbol)
  if (!holding) return `You don't have any ${sym}.`
  if (amount > holding.amount) return `You only have ${formatAmount(holding.amount)} ${sym}, so I can't use ${formatAmount(amount)}.`
  return holding
}

function send(ctx: AgentContext, amount: number, symbol: string, recipient: string): AgentReply {
  const holding = checkSpend(ctx, amount, symbol)
  if (typeof holding === 'string') return { messages: [say(holding)] }
  const contact = ctx.contacts.find((c) => c.name.toLowerCase() === recipient)
  const address = contact?.address ?? (isAddress(recipient) ? getAddress(recipient) : null)
  if (!address) {
    return {
      messages: [say(`I don't know "${recipient}" yet. Add them in the address book (top right), then try again.`)],
    }
  }
  const sym = holding.symbol
  const to = contact ? `${contact.name} (${shortAddress(address)})` : shortAddress(address)
  return {
    messages: [
      say(`Here's the transfer. Check it and approve when you're ready.`),
      confirm({
        title: `Send ${formatAmount(amount)} ${sym}`,
        rows: [
          { label: 'To', value: to },
          { label: 'Amount', value: `${formatAmount(amount)} ${sym} (${formatUsd(amount * holding.usdPrice)})` },
          { label: 'Network fee', value: '~$1.20' },
          { label: 'Network', value: 'Sandbox' },
        ],
      }),
    ],
  }
}

function swapDraft(ctx: AgentContext, amount: number, from: string, to: string): TxDraft | string {
  const a = findHolding(ctx, from)
  const b = findHolding(ctx, to)
  if (!a || !b) return 'I can only swap ETH, USDC and WBTC in Sandbox for now.'
  if (a.symbol === b.symbol) return 'Pick two different tokens to swap.'
  const out = ((amount * a.usdPrice) / b.usdPrice) * 0.997
  return {
    title: `Swap ${formatAmount(amount)} ${a.symbol} → ${b.symbol}`,
    rows: [
      { label: 'You pay', value: `${formatAmount(amount)} ${a.symbol}` },
      { label: 'You receive', value: `≈ ${formatAmount(out)} ${b.symbol}` },
      { label: 'Minimum received', value: `${formatAmount(out * 0.995)} ${b.symbol}` },
      { label: 'Route', value: 'Uniswap v3' },
      { label: 'Price impact', value: '0.05%' },
      { label: 'Network fee', value: '~$4.80' },
    ],
  }
}

function swap(ctx: AgentContext, amount: number, from: string, to: string): AgentReply {
  const draft = swapDraft(ctx, amount, from, to)
  if (typeof draft === 'string') return { messages: [say(draft)] }
  const holding = checkSpend(ctx, amount, from)
  if (typeof holding === 'string') return { messages: [say(holding)] }
  return { messages: [say("Here's the best quote I found:"), confirm(draft)] }
}

function newTask(task: Omit<Task, 'id' | 'status'>): AgentReply {
  const full: Task = { ...task, id: uid(), status: 'active' }
  return {
    messages: [
      say("Done — I'll take care of it while this tab is open."),
      { id: uid(), role: 'assistant', kind: 'task', task: full },
    ],
    newTask: full,
  }
}

export function respond(input: string, ctx: AgentContext): AgentReply {
  const text = normalize(input)
  let m: RegExpMatchArray | null

  if ((m = text.match(CONDITIONAL))) {
    const [, watch, price, amount, from, to] = m
    const trigger = swapDraft(ctx, Number(amount), from, to)
    if (typeof trigger === 'string') return { messages: [say(trigger)] }
    return newTask({
      kind: 'conditional',
      description: `${trigger.title} when ${watch.toUpperCase()} < ${usdLabel(Number(price))}`,
      schedule: 'Checks price every minute',
      trigger,
    })
  }
  if ((m = text.match(ALERT))) {
    const [, sym, price] = m
    return newTask({
      kind: 'alert',
      description: `Price alert: ${sym.toUpperCase()} below ${usdLabel(Number(price))}`,
      schedule: 'Checks price every minute',
    })
  }
  if ((m = text.match(DCA))) {
    const [, buy, period, amount, payWith] = m
    return newTask({
      kind: 'dca',
      description: `Buy ${buy.toUpperCase()} with ${formatAmount(Number(amount))} ${payWith.toUpperCase()}`,
      schedule: `Every ${capitalize(period)}`,
    })
  }
  if (/\bbridge\b/.test(text)) {
    return {
      messages: [say("Bridging and other chains are coming soon. Right now you're in Sandbox, an Ethereum mainnet fork.")],
    }
  }
  if ((m = text.match(SEND))) return send(ctx, Number(m[1]), m[2], m[3])
  if ((m = text.match(SWAP))) return swap(ctx, Number(m[1]), m[2], m[3])
  if (/\b(balance|portfolio|how much)\b/.test(text)) {
    return {
      messages: [say("Here's what you have:"), { id: uid(), role: 'assistant', kind: 'balance', holdings: ctx.holdings }],
    }
  }
  return { messages: [say(FALLBACK)] }
}

export function simulateTrigger(task: Task): AgentReply {
  if (!task.trigger) return { messages: [] }
  return { messages: [say(`Condition met: ${task.description}. Approve to execute.`), confirm(task.trigger)] }
}
