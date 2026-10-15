export const KEYS = {
  vault: 'lw.vault',
  active: 'lw.active',
  contacts: 'lw.contacts',
  tasks: 'lw.tasks',
  speak: 'lw.speak',
} as const

export function readJSON<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}

export function writeJSON(key: string, value: unknown): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(value))
    return true
  } catch {
    return false
  }
}

export function removeKey(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    // storage unavailable — nothing to remove
  }
}
