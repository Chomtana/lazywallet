import type { Status } from '@/state/wallet-context'

// Locked users must never reach /create or /import: creating a new vault there would overwrite the locked one.
export function redirectFor(status: Status, path: string): string | null {
  // React Router matches case-insensitively and ignores a trailing slash, so the guard must too.
  switch (path.toLowerCase().replace(/(.)\/+$/, '$1')) {
    case '/':
      return status === 'none' ? '/welcome' : status === 'locked' ? '/unlock' : null
    case '/unlock':
      return status === 'none' ? '/welcome' : status === 'unlocked' ? '/' : null
    case '/welcome':
      return status === 'locked' ? '/unlock' : status === 'unlocked' ? '/' : null
    case '/create':
    case '/import':
      return status === 'locked' ? '/unlock' : null
    default:
      return null
  }
}
