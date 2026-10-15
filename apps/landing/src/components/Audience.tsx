import { Sparkles, Zap, type LucideIcon } from 'lucide-react'

const GROUPS: { icon: LucideIcon; title: string; points: string[] }[] = [
  {
    icon: Sparkles,
    title: 'New to crypto',
    points: [
      'No DeFi dashboards to learn — just ask.',
      '“Send 20 USDC to Alice” uses your address book.',
      'Every transaction is explained in plain words before you approve.',
    ],
  },
  {
    icon: Zap,
    title: 'Degens',
    points: [
      'Price alerts and conditional orders by voice.',
      'Recurring buys: “Buy ETH every Monday with 50 USDC”.',
      'Connect any dApp with WalletConnect and let the AI read the fine print.',
    ],
  },
]

export function Audience() {
  return (
    <section className="mx-auto grid max-w-6xl gap-4 px-4 py-16 md:grid-cols-2">
      {GROUPS.map(({ icon: Icon, title, points }) => (
        <div key={title} className="space-y-4 rounded-3xl border bg-card p-6 md:p-8">
          <span className="flex size-10 items-center justify-center rounded-full bg-primary/15 text-primary">
            <Icon className="size-5" />
          </span>
          <h2 className="text-2xl font-semibold">{title}</h2>
          <ul className="space-y-2 text-muted-foreground">
            {points.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}
