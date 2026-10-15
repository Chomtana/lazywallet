import type { ReactNode } from 'react'

export function TopBar({ left, center, right }: { left?: ReactNode; center: ReactNode; right?: ReactNode }) {
  return (
    <header className="border-b">
      <div className="mx-auto flex h-16 w-full max-w-[720px] items-center gap-2 px-4">
        <div className="flex w-20 justify-start gap-2">{left}</div>
        <div className="flex min-w-0 flex-1 justify-center">{center}</div>
        <div className="flex w-20 justify-end gap-2">{right}</div>
      </div>
    </header>
  )
}
