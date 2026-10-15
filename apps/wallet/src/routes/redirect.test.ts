import { describe, expect, it } from 'vitest'
import { redirectFor } from './redirect'

describe('redirectFor', () => {
  it.each([
    ['none', '/', '/welcome'],
    ['locked', '/', '/unlock'],
    ['unlocked', '/', null],
    ['none', '/unlock', '/welcome'],
    ['locked', '/unlock', null],
    ['unlocked', '/unlock', '/'],
    ['none', '/welcome', null],
    ['locked', '/welcome', '/unlock'],
    ['unlocked', '/welcome', '/'],
    ['none', '/create', null],
    ['locked', '/create', '/unlock'],
    ['unlocked', '/create', null],
    ['locked', '/import', '/unlock'],
    ['unlocked', '/import', null],
  ] as const)('%s at %s → %s', (status, path, expected) => {
    expect(redirectFor(status, path)).toBe(expected)
  })
})
