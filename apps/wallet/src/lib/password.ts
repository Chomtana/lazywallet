export function validatePassword(pw: string, confirm: string): string | null {
  if (pw.length < 8) return 'Use at least 8 characters'
  if (pw !== confirm) return 'Passwords do not match'
  return null
}
