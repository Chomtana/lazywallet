const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export function shortAddress(a: string): string {
  return a.length > 12 ? `${a.slice(0, 6)}…${a.slice(-4)}` : a
}

export function formatUsd(n: number): string {
  return usd.format(n)
}

export function formatAmount(n: number): string {
  return Number(n.toPrecision(6)).toString()
}

export function hostOf(url: string): string {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

export function uid(): string {
  return crypto.randomUUID()
}

export function txHash(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32))
  return '0x' + Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}
