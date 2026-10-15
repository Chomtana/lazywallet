import { useState } from 'react'
import { Loader2, Wallet } from 'lucide-react'
import { toast } from 'sonner'
import { requestFunds } from '@/chain/faucet'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Address } from '@/types'

// Sent through the chat so the agent adds funds and shows the new balance card.
export const FUND_PROMPT = 'Add funds to my wallet'

type Props = {
  address: Address
  onFunded: () => Promise<void> | void
  agentOnline: boolean
  busy: boolean
  onAsk: (text: string) => void
  className?: string
}

// One tap tops the wallet up. With the agent online it goes through the chat (new balance card);
// otherwise it calls the faucet directly and re-reads the balance.
export function GetFundsButton({ address, onFunded, agentOnline, busy, onAsk, className }: Props) {
  const [funding, setFunding] = useState(false)

  async function fund() {
    if (agentOnline) return onAsk(FUND_PROMPT)
    setFunding(true)
    try {
      toast.success(`Added ${await requestFunds(address)}`)
      await onFunded()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Couldn't add funds")
    } finally {
      setFunding(false)
    }
  }

  const working = funding || (agentOnline && busy)
  return (
    <Button size="lg" className={cn('h-11 rounded-full px-5 text-base', className)} onClick={fund} disabled={working}>
      {working ? <Loader2 className="animate-spin" /> : <Wallet />}
      {working ? 'Adding funds…' : 'Get funds'}
    </Button>
  )
}
