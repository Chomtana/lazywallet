import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useWallet } from '@/state/wallet-context'
import { SeedPhrase } from './SeedPhrase'

export function ShowSeedDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { active, verifyPassword } = useWallet()
  const [password, setPassword] = useState('')
  const [verified, setVerified] = useState(false)
  const [error, setError] = useState('')

  function handleOpenChange(v: boolean) {
    if (!v) {
      setPassword('')
      setVerified(false)
      setError('')
    }
    onOpenChange(v)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (await verifyPassword(password)) setVerified(true)
    else setError('Wrong password')
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Seed phrase — {active?.name}</DialogTitle>
          <DialogDescription>Anyone with these words controls this wallet.</DialogDescription>
        </DialogHeader>
        {verified && active ? (
          <SeedPhrase mnemonic={active.mnemonic} />
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <Label htmlFor="seed-password">Enter your password</Label>
            <Input
              id="seed-password"
              type="password"
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={!password}>
              Show
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
