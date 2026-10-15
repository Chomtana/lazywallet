import { useState } from 'react'
import { Loader2, Wallet } from 'lucide-react'
import { toast } from 'sonner'
import { requestFunds } from '@/chain/faucet'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Address } from '@/types'

type Props = { address: Address; onFunded: () => Promise<void> | void; className?: string }

// One tap tops the wallet up from the faucet, then re-reads the balance.
export function GetFundsButton({ address, onFunded, className }: Props) {
  const [funding, setFunding] = useState(false)

  async function fund() {
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

  return (
    <Button size="lg" className={cn('h-11 rounded-full px-5 text-base', className)} onClick={fund} disabled={funding}>
      {funding ? <Loader2 className="animate-spin" /> : <Wallet />}
      {funding ? 'Adding funds…' : 'Get funds'}
    </Button>
  )
}
