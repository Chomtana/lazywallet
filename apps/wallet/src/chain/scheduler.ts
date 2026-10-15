import { createPublicClient, erc20Abi, http, type Chain } from 'viem'
import type { Address } from '@/types'
import { sandboxChains } from './networks'

// = contracts/src/Deployment.sol (CREATE2, identical on both forks)
export const SCHEDULER_ADDRESS: Address = '0xE99d9DFBeA09687AdCDdB9a45914d778f330b513'
const MAX_LISTED = 200n

export const schedulerAbi = [
  { type: 'function', name: 'nextId', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
  {
    type: 'function',
    name: 'getOrder',
    stateMutability: 'view',
    inputs: [{ name: 'id', type: 'uint256' }],
    outputs: [
      {
        type: 'tuple',
        components: [
          { name: 'owner', type: 'address' },
          { name: 'tokenIn', type: 'address' },
          { name: 'tokenOut', type: 'address' },
          { name: 'amountIn', type: 'uint256' },
          { name: 'minOut', type: 'uint256' },
          { name: 'startTime', type: 'uint64' },
          { name: 'interval', type: 'uint64' },
          { name: 'count', type: 'uint32' },
          { name: 'executed', type: 'uint32' },
          { name: 'nextTime', type: 'uint64' },
          { name: 'cancelled', type: 'bool' },
        ],
      },
    ],
  },
] as const

export type TokenInfo = { address: Address; symbol: string; decimals: number }
export type ScheduledOrder = {
  chainId: number
  network: string
  id: bigint
  tokenIn: TokenInfo
  tokenOut: TokenInfo
  amountIn: bigint
  minOut: bigint
  interval: number
  count: number
  executed: number
  nextTime: number
  cancelled: boolean
}
export type OrderStatus = { state: 'active' | 'done' | 'cancelled'; label: string }

export function durationLabel(seconds: number): string {
  for (const [size, unit] of [
    [86400, 'd'],
    [3600, 'h'],
    [60, 'min'],
  ] as const) {
    if (seconds >= size) return `${Math.round(seconds / size)} ${unit}`
  }
  return `${seconds}s`
}

export function orderStatus(o: Pick<ScheduledOrder, 'cancelled' | 'executed' | 'count' | 'nextTime'>, nowSec: number): OrderStatus {
  if (o.cancelled) return { state: 'cancelled', label: 'Cancelled' }
  if (o.executed >= o.count) return { state: 'done', label: 'Done' }
  const wait = o.nextTime - nowSec
  return { state: 'active', label: wait <= 0 ? 'Due now' : `Next run in ${durationLabel(wait)}` }
}

export function mergeSettled<T>(results: PromiseSettledResult<T[]>[]): T[] {
  return results.flatMap((r) => (r.status === 'fulfilled' ? r.value : []))
}

async function ordersOn(chain: Chain, owner: Address): Promise<ScheduledOrder[]> {
  const client = createPublicClient({ chain, transport: http(chain.rpcUrls.default.http[0]) })
  if (!(await client.getCode({ address: SCHEDULER_ADDRESS }))) return []
  const n = await client.readContract({ address: SCHEDULER_ADDRESS, abi: schedulerAbi, functionName: 'nextId' })
  const ids: bigint[] = []
  for (let i = n > MAX_LISTED ? n - MAX_LISTED : 0n; i < n; i++) ids.push(i)
  const all = await Promise.all(
    ids.map((id) => client.readContract({ address: SCHEDULER_ADDRESS, abi: schedulerAbi, functionName: 'getOrder', args: [id] })),
  )
  const mine = all.map((o, i) => ({ ...o, id: ids[i] })).filter((o) => o.owner.toLowerCase() === owner.toLowerCase())
  const tokens = new Map<string, TokenInfo>()
  for (const address of new Set(mine.flatMap((o) => [o.tokenIn, o.tokenOut]))) {
    const [symbol, decimals] = await Promise.all([
      client.readContract({ address, abi: erc20Abi, functionName: 'symbol' }),
      client.readContract({ address, abi: erc20Abi, functionName: 'decimals' }),
    ])
    tokens.set(address, { address, symbol, decimals })
  }
  return mine.map((o) => ({
    chainId: chain.id,
    network: chain.name,
    id: o.id,
    tokenIn: tokens.get(o.tokenIn)!,
    tokenOut: tokens.get(o.tokenOut)!,
    amountIn: o.amountIn,
    minOut: o.minOut,
    interval: Number(o.interval),
    count: o.count,
    executed: o.executed,
    nextTime: Number(o.nextTime),
    cancelled: o.cancelled,
  }))
}

/** The owner's orders on every Sandbox fork; a fork that's down just contributes none. */
export async function readOrders(owner: Address): Promise<ScheduledOrder[]> {
  return mergeSettled(await Promise.allSettled(sandboxChains.map((c) => ordersOn(c, owner))))
}
