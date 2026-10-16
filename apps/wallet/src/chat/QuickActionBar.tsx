import { QUICK_ACTIONS } from './quickActions'

type Props = { onPick: (text: string) => void; disabled?: boolean }

// A single row of compact pills that scrolls sideways on narrow screens.
export function QuickActionBar({ onPick, disabled }: Props) {
  return (
    <div className="-mx-4 flex gap-2 overflow-x-auto px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {QUICK_ACTIONS.map((a) => (
        <button
          key={a.label}
          type="button"
          disabled={disabled}
          onClick={() => onPick(a.text)}
          className="shrink-0 whitespace-nowrap rounded-full border px-3 py-1.5 text-xs text-muted-foreground transition hover:border-primary hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
        >
          {a.label}
        </button>
      ))}
    </div>
  )
}
