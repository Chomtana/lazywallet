import type { Address } from '@/types'

const FAUCET_URL: string = import.meta.env.VITE_FAUCET_URL ?? 'http://localhost:8547'

export async function requestFunds(address: Address): Promise<string> {
  let res: Response
  try {
    res = await fetch(`${FAUCET_URL}/fund`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ address }),
    })
  } catch {
    throw new Error('Sandbox faucet is offline — run `pnpm dev:sandbox`.')
  }
  const body = (await res.json().catch(() => ({}))) as { summary?: string; detail?: string }
  if (!res.ok) throw new Error(body.detail ?? `Faucet error (${res.status})`)
  return body.summary ?? 'test funds'
}
