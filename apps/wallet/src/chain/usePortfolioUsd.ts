import { useCallback, useEffect, useRef, useState } from 'react'
import type { Address } from '@/types'
import { readPortfolioUsd } from './portfolio'

// The wallet's total USD balance read wallet-side; null until known or when the forks can't be read.
export function usePortfolioUsd(address: Address | undefined) {
  const [state, setState] = useState<{ address?: Address; usd: number | null }>({ usd: null })
  const latest = useRef(address)

  useEffect(() => {
    latest.current = address
  })

  const refresh = useCallback(async () => {
    if (!address) return
    const usd = await readPortfolioUsd(address)
    // Ignore a read that finished after the user switched wallets.
    if (latest.current === address) setState({ address, usd })
  }, [address])

  return { usd: state.address === address ? state.usd : null, refresh }
}
