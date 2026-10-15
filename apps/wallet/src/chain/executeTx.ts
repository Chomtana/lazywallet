import type { TxRequest } from '@/types'

type Hash = `0x${string}`

export type TxDeps = {
  send: (req: TxRequest) => Promise<Hash>
  wait: (hash: Hash) => Promise<'success' | 'reverted'>
}

export type TxOutcome = { hash?: string; status?: 'success' | 'reverted'; error?: string }

function messageOf(e: unknown): string {
  if (e && typeof e === 'object' && 'shortMessage' in e && typeof e.shortMessage === 'string') return e.shortMessage
  return e instanceof Error ? e.message : String(e)
}

export async function executeTx(req: TxRequest, deps: TxDeps): Promise<TxOutcome> {
  let hash: Hash
  try {
    hash = await deps.send(req)
  } catch (e) {
    return { error: messageOf(e) }
  }
  try {
    return { hash, status: await deps.wait(hash) }
  } catch (e) {
    return { hash, error: messageOf(e) }
  }
}

export function statusPatch(o: TxOutcome): { state: 'success' | 'failed'; text: string; hash?: string } {
  if (o.error) return { state: 'failed', text: `Failed: ${o.error}`, hash: o.hash }
  if (o.status === 'reverted') return { state: 'failed', text: 'Transaction reverted.', hash: o.hash }
  return { state: 'success', text: 'Confirmed on Sandbox.', hash: o.hash }
}
