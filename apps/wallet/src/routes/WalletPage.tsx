import { Button } from '@/components/ui/button'
import { useWallet } from '@/state/wallet-context'

export default function WalletPage() {
  const { active, lock } = useWallet()
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4">
      <p className="font-mono">{active?.address}</p>
      <Button onClick={lock}>Lock</Button>
    </div>
  )
}
