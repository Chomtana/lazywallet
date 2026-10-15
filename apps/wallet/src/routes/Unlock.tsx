import { useState, type FormEvent } from 'react'
import { AuthLayout } from '@/components/AuthLayout'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { WrongPasswordError } from '@/lib/vault'
import { useWallet } from '@/state/wallet-context'

export default function Unlock() {
  const { unlock, resetAll } = useWallet()
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await unlock(password)
    } catch (err) {
      setError(err instanceof WrongPasswordError ? 'Wrong password' : 'Could not unlock this wallet')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout>
      <div className="space-y-1 text-center">
        <h1 className="text-2xl font-semibold">Welcome back</h1>
        <p className="text-sm text-muted-foreground">Enter your password to unlock.</p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoFocus
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" size="lg" className="w-full" disabled={busy || !password}>
          {busy ? 'Unlocking…' : 'Unlock'}
        </Button>
      </form>
      <Button variant="ghost" className="w-full text-muted-foreground" onClick={() => setConfirmReset(true)}>
        Forgot password? Reset all wallets
      </Button>
      <Dialog open={confirmReset} onOpenChange={setConfirmReset}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset LazyWallet?</DialogTitle>
            <DialogDescription>
              This deletes every wallet on this device. You can only get them back with their seed phrases.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setConfirmReset(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={resetAll}>
              Reset everything
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AuthLayout>
  )
}
