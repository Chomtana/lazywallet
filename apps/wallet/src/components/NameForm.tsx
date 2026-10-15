import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function NameForm({ initial, onSubmit }: { initial: string; onSubmit: (name: string) => void }) {
  const [name, setName] = useState(initial)
  const trimmed = name.trim()
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (trimmed) onSubmit(trimmed)
      }}
      className="space-y-4"
    >
      <div className="space-y-2">
        <Label htmlFor="wallet-name">Wallet name</Label>
        <Input
          id="wallet-name"
          autoFocus
          maxLength={32}
          placeholder="e.g. Main"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      <Button type="submit" size="lg" className="w-full" disabled={!trimmed}>
        Continue
      </Button>
    </form>
  )
}
