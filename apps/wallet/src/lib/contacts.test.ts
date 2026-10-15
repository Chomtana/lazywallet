import { describe, expect, it } from 'vitest'
import type { Contact } from '@/types'
import { validateContact } from './contacts'

const alice: Contact = { id: 'a', name: 'Alice', address: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8' }
const ok = '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC'

describe('validateContact', () => {
  it('requires a name', () => {
    expect(validateContact('  ', ok, [], null)).toBe('Enter a name')
  })
  it('requires a valid address (bad checksum rejected)', () => {
    expect(validateContact('Bob', '0x123', [], null)).toBe('Enter a valid 0x address')
    expect(validateContact('Bob', '0x3c44CdDdB6a900fa2b585dd299e03d12FA4293BC', [], null)).toBe(
      'Enter a valid 0x address',
    )
  })
  it('rejects duplicate names case-insensitively', () => {
    expect(validateContact('alice', ok, [alice], null)).toBe('You already have a contact named alice')
  })
  it('allows keeping the same name when editing', () => {
    expect(validateContact('Alice', ok, [alice], 'a')).toBeNull()
  })
  it('accepts lowercase addresses', () => {
    expect(validateContact('Bob', ok.toLowerCase(), [alice], null)).toBeNull()
  })
})
