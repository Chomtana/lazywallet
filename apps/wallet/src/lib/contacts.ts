import { isAddress } from 'viem'
import type { Contact } from '@/types'

export function validateContact(
  name: string,
  address: string,
  contacts: Contact[],
  editingId: string | null,
): string | null {
  const n = name.trim()
  if (!n) return 'Enter a name'
  if (!isAddress(address.trim())) return 'Enter a valid 0x address'
  if (contacts.some((c) => c.id !== editingId && c.name.toLowerCase() === n.toLowerCase())) {
    return `You already have a contact named ${n}`
  }
  return null
}
