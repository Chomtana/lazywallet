import type { ReactNode } from 'react'
import { Logo } from './Logo'

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="w-full max-w-md space-y-8">
        <Logo className="justify-center" />
        <div className="space-y-6 rounded-2xl border bg-card p-6 sm:p-8">{children}</div>
      </div>
    </div>
  )
}
