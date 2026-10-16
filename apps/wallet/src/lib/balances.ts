import type { BalanceChange, Holding } from '@/types'

export type ChainGroup<T> = { network: string; subtotal: number; items: T[] }

const usdOf = (h: Holding) => (h.usdPrice === null ? null : h.amount * h.usdPrice)

function group<T extends { network?: string }>(items: T[]): ChainGroup<T>[] {
  const groups = new Map<string, T[]>()
  for (const item of items) {
    const key = item.network ?? ''
    groups.set(key, [...(groups.get(key) ?? []), item])
  }
  return [...groups].map(([network, list]) => ({ network, subtotal: 0, items: list }))
}

// Balance card: richest chain first; within a chain by USD value, unknown prices last.
export function groupHoldings(holdings: Holding[]): ChainGroup<Holding>[] {
  return group(holdings)
    .map((g) => ({
      ...g,
      subtotal: g.items.reduce((sum, h) => sum + (usdOf(h) ?? 0), 0),
      items: [...g.items].sort((a, b) => (usdOf(b) ?? -1) - (usdOf(a) ?? -1)),
    }))
    .sort((a, b) => b.subtotal - a.subtotal)
}

// Balance-change card: grouped by chain, in the order the agent sent them (the change reads in → out).
export function groupChanges(changes: BalanceChange[]): ChainGroup<BalanceChange>[] {
  return group(changes)
}
