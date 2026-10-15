import type { Address, Holding, TxDraft, TxStep } from '@/types'

export type ClientMsg =
  | { type: 'tx_started'; id: string }
  | {
      type: 'user'
      text: string
      spoken: boolean
      address: Address
      contacts: { name: string; address: Address }[]
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
  | { type: 'balances'; holdings: Holding[] }
  | { type: 'confirm'; id: string; tx: TxDraft & { steps: TxStep[]; from: Address } }
  | { type: 'error'; message: string }
  | { type: 'turn_end' }
