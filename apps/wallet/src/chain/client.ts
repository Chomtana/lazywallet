import { createPublicClient, createWalletClient, http } from 'viem'
import { mnemonicToAccount } from 'viem/accounts'
import { sandbox } from '@/lib/wagmi'
import type { TxDeps } from './executeTx'

export function txDepsFor(mnemonic: string): TxDeps {
  const transport = http(sandbox.rpcUrls.default.http[0])
  const wallet = createWalletClient({ account: mnemonicToAccount(mnemonic), chain: sandbox, transport })
  const reader = createPublicClient({ chain: sandbox, transport })
  return {
    send: (req) => wallet.sendTransaction({ to: req.to, value: BigInt(req.value), data: req.data }),
    wait: async (hash) => (await reader.waitForTransactionReceipt({ hash })).status,
  }
}
