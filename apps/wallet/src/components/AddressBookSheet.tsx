import { useState, type FormEvent } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { BOTTOM_SHEET } from '@/components/sheet-styles'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { validateContact } from '@/lib/contacts'
import { shortAddress, uid } from '@/lib/format'
import type { Address, Contact } from '@/types'

type Props = {
  open: boolean
  onOpenChange: (v: boolean) => void
  contacts: Contact[]
  onChange: (contacts: Contact[]) => void
}

export function AddressBookSheet({ open, onOpenChange, contacts, onChange }: Props) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [error, setError] = useState<string | null>(null)

  function reset() {
    setEditingId(null)
    setName('')
    setAddress('')
    setError(null)
  }

  function save(e: FormEvent) {
    e.preventDefault()
    const err = validateContact(name, address, contacts, editingId)
    setError(err)
    if (err) return
    const entry: Contact = { id: editingId ?? uid(), name: name.trim(), address: address.trim() as Address }
    onChange(editingId ? contacts.map((c) => (c.id === editingId ? entry : c)) : [...contacts, entry])
    reset()
  }

  function edit(c: Contact) {
    setEditingId(c.id)
    setName(c.name)
    setAddress(c.address)
    setError(null)
  }

  return (
    <Sheet
      open={open}
      onOpenChange={(v) => {
        if (!v) reset()
        onOpenChange(v)
      }}
    >
      <SheetContent side="bottom" className={BOTTOM_SHEET}>
        <SheetHeader>
          <SheetTitle>Address book</SheetTitle>
          <SheetDescription>Say a name — “send 0.1 ETH to Alice” — and I'll use the address saved here.</SheetDescription>
        </SheetHeader>
        <div className="flex-1 space-y-6 overflow-y-auto px-4 pb-4">
          <form onSubmit={save} className="space-y-3 rounded-2xl border p-4">
            <div className="space-y-2">
              <Label htmlFor="contact-name">Name</Label>
              <Input id="contact-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contact-address">Address</Label>
              <Input
                id="contact-address"
                className="font-mono"
                placeholder="0x…"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex gap-2">
              {editingId && (
                <Button type="button" variant="secondary" onClick={reset}>
                  Cancel
                </Button>
              )}
              <Button type="submit" className="flex-1">
                {editingId ? 'Save' : 'Add contact'}
              </Button>
            </div>
          </form>
          {contacts.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground">No contacts yet.</p>
          ) : (
            <ul className="divide-y">
              {contacts.map((c) => (
                <li key={c.id} className="flex items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{c.name}</p>
                    <p className="font-mono text-xs text-muted-foreground">{shortAddress(c.address)}</p>
                  </div>
                  <Button size="icon" variant="ghost" aria-label={`Edit ${c.name}`} onClick={() => edit(c)}>
                    <Pencil />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={`Delete ${c.name}`}
                    onClick={() => onChange(contacts.filter((x) => x.id !== c.id))}
                  >
                    <Trash2 />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
