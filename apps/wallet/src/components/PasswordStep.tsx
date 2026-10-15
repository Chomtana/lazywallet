import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { validatePassword } from '@/lib/password'

export function PasswordStep({ onSubmit, busy }: { onSubmit: (password: string) => void; busy?: boolean }) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)

  function submit(e: FormEvent) {
    e.preventDefault()
    const err = validatePassword(password, confirm)
    setError(err)
    if (!err) onSubmit(password)
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input id="password" type="password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password-confirm">Confirm password</Label>
        <Input id="password-confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      </div>
      <p className="text-xs text-muted-foreground">
        Encrypts your wallets on this device. We can't recover it for you.
      </p>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" size="lg" className="w-full" disabled={busy}>
        Continue
      </Button>
    </form>
  )
}
