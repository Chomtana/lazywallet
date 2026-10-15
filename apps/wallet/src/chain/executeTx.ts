import type { CustomToken, TxDraft, TxRequest, TxStep } from '@/types'
import { networkName } from './networks'

type Hash = `0x${string}`

export type TxDeps = {
  send: (req: TxRequest) => Promise<Hash>
  wait: (hash: Hash, chainId?: number) => Promise<'success' | 'reverted'>
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
    return { hash, status: await deps.wait(hash, req.chainId) }
  } catch (e) {
    return { hash, error: messageOf(e) }
  }
}

export type StepsOutcome = { hashes: string[]; hash?: string; status?: 'success' | 'reverted'; error?: string; failedStep?: number }

export async function executeSteps(steps: TxStep[], deps: TxDeps, onStep?: (index: number) => void): Promise<StepsOutcome> {
  const hashes: string[] = []
  for (let i = 0; i < steps.length; i++) {
    onStep?.(i)
    const r = await executeTx(steps[i].request, deps)
    if (r.hash) hashes.push(r.hash)
    if (r.error || r.status === 'reverted') return { hashes, hash: r.hash, status: r.status, error: r.error, failedStep: i }
  }
  return { hashes, hash: hashes.at(-1), status: 'success' }
}

export function statusPatch(o: StepsOutcome, steps: TxStep[]): { state: 'success' | 'failed'; text: string; hash?: string } {
  const at = o.failedStep !== undefined && steps.length > 1 ? `${steps[o.failedStep].label}: ` : ''
  if (o.error) return { state: 'failed', text: `${at}Failed: ${o.error}`, hash: o.hash }
  if (o.status === 'reverted') return { state: 'failed', text: `${at}Transaction reverted.`, hash: o.hash }
  return { state: 'success', text: `Confirmed on ${networkName(steps.at(-1)?.request.chainId)} (Sandbox).`, hash: o.hash }
}

export function progressText(index: number, steps: TxStep[]): string {
  return steps.length > 1 ? `Step ${index + 1} of ${steps.length}: ${steps[index].label}…` : `Submitting to ${networkName(steps[index].request.chainId)} (Sandbox)…`
}

/** The token a swap card asked to remember — only once every step succeeded. */
export function tokenToSave(o: StepsOutcome, tx: TxDraft): CustomToken | undefined {
  return o.status === 'success' && !o.error ? tx.addToken : undefined
}
