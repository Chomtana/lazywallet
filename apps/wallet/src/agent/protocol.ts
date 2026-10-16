import type { Address, AirdropItem, BalanceChange, ChoiceOption, CustomToken, Holding, TrendingToken, TxDraft, TxStep, UnlockItem } from '@/types'

export const AGENT_WS_URL: string = import.meta.env.VITE_AGENT_WS_URL ?? 'ws://localhost:8787/ws'

export type ClientMsg =
  | { type: 'tx_started'; id: string }
  | {
      type: 'user'
      text: string
      spoken: boolean
      address: Address
      contacts: { name: string; address: Address }[]
      tokens: CustomToken[]
    }
  | {
      type: 'tx_result'
      id: string
      outcome: 'approved' | 'rejected'
      hash?: string
      status?: 'success' | 'reverted'
      error?: string
      hashes?: string[]
      failed_step?: number
    }

export type ServerMsg =
  | { type: 'text_delta'; text: string }
  | { type: 'text_done' }
  | { type: 'progress'; label: string }
  | { type: 'balances'; holdings: Holding[] }
  | { type: 'balance_change'; changes: BalanceChange[] }
  | { type: 'tokens'; title: string; items: TrendingToken[] }
  | { type: 'confirm'; id: string; tx: TxDraft & { steps: TxStep[]; from: Address } }
  | { type: 'choice'; id: string; question: string; options: ChoiceOption[] }
  | { type: 'airdrops'; title: string; items: AirdropItem[] }
  | { type: 'unlocks'; title: string; items: UnlockItem[] }
  | { type: 'error'; message: string }
  | { type: 'turn_end' }
