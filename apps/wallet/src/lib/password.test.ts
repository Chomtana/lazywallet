import { describe, expect, it } from 'vitest'
import { validatePassword } from './password'

describe('validatePassword', () => {
  it('requires 8+ characters', () => {
    expect(validatePassword('short', 'short')).toBe('Use at least 8 characters')
  })
  it('requires matching confirmation', () => {
    expect(validatePassword('longenough', 'different')).toBe('Passwords do not match')
  })
  it('accepts a good password', () => {
    expect(validatePassword('longenough', 'longenough')).toBeNull()
  })
})
