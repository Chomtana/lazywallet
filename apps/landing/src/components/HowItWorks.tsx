import { Check, Eye, Mic, type LucideIcon } from 'lucide-react'

const STEPS: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: Mic, title: 'Speak', text: 'Tap the mic and say what you want.' },
  { icon: Eye, title: 'Review', text: 'LazyWallet shows exactly what will happen.' },
  { icon: Check, title: 'Approve', text: 'One tap. Your keys never leave your device.' },
]

export function HowItWorks() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16">
      <h2 className="mb-8 text-center text-3xl font-semibold">How it works</h2>
      <ol className="grid gap-4 md:grid-cols-3">
        {STEPS.map(({ icon: Icon, title, text }, i) => (
          <li key={title} className="space-y-3 rounded-3xl border bg-card p-6">
            <div className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <Icon className="size-5" />
              </span>
              <span className="font-mono text-sm text-muted-foreground">0{i + 1}</span>
            </div>
            <h3 className="text-xl font-semibold">{title}</h3>
            <p className="text-muted-foreground">{text}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
