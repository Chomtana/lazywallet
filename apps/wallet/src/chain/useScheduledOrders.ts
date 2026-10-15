import { useQuery } from '@tanstack/react-query'
import type { Address } from '@/types'
import { readOrders } from './scheduler'

export function useScheduledOrders(address?: Address) {
  return useQuery({
    queryKey: ['scheduled-orders', address],
    queryFn: () => readOrders(address!),
    enabled: !!address,
    refetchInterval: 10_000,
  })
}
