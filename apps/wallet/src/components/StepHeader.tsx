type Props = { step: number; total: number; title: string; subtitle?: string }

export function StepHeader({ step, total, title, subtitle }: Props) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase tracking-wider text-primary">
        Step {step} of {total}
      </p>
      <h1 className="text-2xl font-semibold">{title}</h1>
      {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
    </div>
  )
}
