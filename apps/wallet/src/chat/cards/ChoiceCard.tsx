import { Button } from '@/components/ui/button'
import type { ChoiceOption } from '@/types'

type Props = { question: string; options: ChoiceOption[]; chosen?: string; closed?: boolean; onChoose: (option: ChoiceOption) => void }

export function ChoiceCard({ question, options, chosen, closed, onChoose }: Props) {
  return (
    <div className="rounded-2xl border bg-card p-4">
      <p className="font-semibold">{question}</p>
      <div className="mt-3 grid gap-2">
        {options.map((o) => (
          <Button
            key={o.label}
            variant={chosen === o.label ? 'default' : 'secondary'}
            disabled={closed}
            onClick={() => onChoose(o)}
            className="h-auto justify-between py-2.5"
          >
            <span>{o.label}</span>
            {o.detail && <span className="font-mono text-xs opacity-70">{o.detail}</span>}
          </Button>
        ))}
      </div>
    </div>
  )
}
