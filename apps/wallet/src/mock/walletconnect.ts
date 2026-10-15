import { shortAddress } from '@/lib/format'
import type { AgentReply, DappInfo } from '@/types'
import { confirm, say } from './agent'
import { UNISWAP } from './fixtures'

export type Proposal = { dapp: DappInfo; chain: string; methods: string[] }

const UNIVERSAL_ROUTER = '0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD'

// WalletConnect v2 pairing URI: wc:{64-hex topic}@2?relay-protocol=...&symKey=...
export function isWcUri(input: string): boolean {
  return /^wc:[0-9a-f]{64}@2\?(?=.*\brelay-protocol=)(?=.*\bsymKey=)/i.test(input.trim())
}

export function mockProposal(): Proposal {
  return { dapp: UNISWAP, chain: 'Sandbox (eip155:1)', methods: ['eth_sendTransaction', 'personal_sign'] }
}

export function dappRequest(dapp: DappInfo): AgentReply {
  return {
    messages: [
      say(`${dapp.name} is asking you to approve a transaction. Here's what it does:`),
      confirm({
        title: 'Swap 0.05 ETH → USDC',
        dapp,
        explanation: `This swaps 0.05 ETH for about 159.5 USDC on ${dapp.name}. It only spends the 0.05 ETH shown — no unlimited token approval.`,
        rows: [
          { label: 'Method', value: 'eth_sendTransaction' },
          { label: 'Contract', value: shortAddress(UNIVERSAL_ROUTER) },
          { label: 'Value', value: '0.05 ETH' },
          { label: 'Network fee', value: '~$3.10' },
        ],
      }),
    ],
  }
}
