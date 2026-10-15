import type { Address, Holding, TxDraft, TxRequest } from '@/types'

export type ClientMsg =
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
    }

export type ServerMsg =
  | { type: 'text_delta'; text: string }
  | { type: 'text_done' }
  | { type: 'balances'; holdings: Holding[] }
  | { type: 'confirm'; id: string; tx: TxDraft & { request: TxRequest; from: Address } }
  | { type: 'error'; message: string }
  | { type: 'turn_end' }
