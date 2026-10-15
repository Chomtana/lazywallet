// Premium auto-hunting plans — a demo mock-up: no payment or hunting happens on chain.
// Prices follow the business-model slide.
export type PlanId = 'airdrop' | 'perp_rwa'

export type Plan = {
  id: PlanId
  name: string // shown in the plan sheet
  paneTitle: string // shown in the premium pane while active
  priceUsd: number
  minWalletUsd: number
  blurb: string
}

export const PLANS: Plan[] = [
  {
    id: 'airdrop',
    name: 'Auto Airdrop Hunt',
    paneTitle: 'Auto Hunting Airdrops',
    priceUsd: 200,
    minWalletUsd: 2_000,
    blurb: 'Researches and farms points programs for you in a dedicated VM. Insured.',
  },
  {
    id: 'perp_rwa',
    name: 'Auto Perp/RWA Hunt',
    paneTitle: 'Auto Hunting Perp/RWA Airdrops',
    priceUsd: 1_000,
    minWalletUsd: 10_000,
    blurb: 'Optimal-strategy volume on trending perp DEXs and RWA projects for points. Insured.',
  },
]

export const DEFAULT_PLAN: PlanId = 'airdrop'
export const PERKS = ['Insurance covers hacks and rug pulls', 'Dedicated browser with a real IP address', 'A team that solves captchas for you']

export const planOf = (id: PlanId): Plan => PLANS.find((p) => p.id === id)!

export type Subscription = { plan: PlanId; since: string } // since: ISO date

export type HuntProtocol = {
  name: string
  kind: string // "Perp DEX", "RWA", "Points"
  network: string // '' when not confirmed
  activity: string // what the bot did there
  points: string
  estUsd: number
  status: 'farming' | 'qualified' | 'snapshot soon'
}

export type HuntResults = {
  summary: string // shown and spoken
  stats: { label: string; value: string }[]
  protocols: HuntProtocol[]
  log: { when: string; text: string }[]
}

export const RESULTS: Record<PlanId, HuntResults> = {
  airdrop: {
    summary:
      'Overnight I farmed four points programs. Your best position is Avant: savUSD points are up 18 percent this week. ' +
      'Theo and Re keep earning on idle stablecoins, and Tori qualified you for Season 1. ' +
      'Estimated airdrop value so far is about 640 dollars, with no new risk flags.',
    stats: [
      { label: 'Est. airdrop value', value: '$640' },
      { label: 'Points this week', value: '+18%' },
      { label: 'Programs farmed', value: '4' },
      { label: 'Risk flags', value: '0' },
    ],
    protocols: [
      { name: 'Avant', kind: 'Points', network: 'Avalanche', activity: 'Staked 800 avUSD → savUSD', points: '41,200 pts', estUsd: 260, status: 'farming' },
      { name: 'Theo', kind: 'RWA', network: 'Ethereum', activity: 'Holding 500 sthUSD', points: '18,900 pts', estUsd: 150, status: 'farming' },
      { name: 'Re', kind: 'RWA', network: 'Ethereum', activity: 'Deposited 400 reUSD', points: '9,750 pts', estUsd: 130, status: 'farming' },
      { name: 'Tori', kind: 'Points', network: 'Ethereum', activity: 'Daily check-ins, 21-day streak', points: '3,100 cores', estUsd: 100, status: 'qualified' },
    ],
    log: [
      { when: '06:12', text: 'Claimed daily Tori cores (captcha solved by the team)' },
      { when: '03:40', text: 'Re-staked Avant rewards into savUSD' },
      { when: '01:05', text: 'Scanned 37 new programs — none passed the safety check' },
    ],
  },
  perp_rwa: {
    summary:
      'Overnight I traded delta-neutral volume across three perp exchanges and topped up two RWA vaults. ' +
      'That is 184 thousand dollars of volume for only 92 dollars in fees and funding. ' +
      'Your strongest position is on Variational, which snapshots soon. ' +
      'Estimated airdrop value is about 4,100 dollars, and your hedges are flat, so price moves did not cost you.',
    stats: [
      { label: 'Est. airdrop value', value: '$4,100' },
      { label: 'Volume generated', value: '$184K' },
      { label: 'Fees + funding', value: '$92' },
      { label: 'Net exposure', value: '0%' },
    ],
    protocols: [
      // Picked from memory (mid-2026) while offline — re-check each points program before a live demo.
      { name: 'Variational', kind: 'Perp DEX', network: 'Arbitrum', activity: 'BTC/ETH hedged volume', points: '12,480 pts', estUsd: 1_350, status: 'snapshot soon' },
      { name: 'Extended', kind: 'Perp DEX', network: 'Starknet', activity: 'Delta-neutral volume', points: '2,940 pts', estUsd: 1_100, status: 'farming' },
      { name: 'Paper Trade', kind: 'Perp DEX', network: '', activity: 'Funding-rate arbitrage', points: '6,210 pts', estUsd: 750, status: 'farming' },
      { name: 'Ostium', kind: 'RWA perps', network: 'Arbitrum', activity: 'Gold and FX hedged volume', points: '8,400 pts', estUsd: 520, status: 'farming' },
      { name: 'Theo', kind: 'RWA', network: 'Ethereum', activity: 'Holding 2,000 sthUSD', points: '5,600 pts', estUsd: 380, status: 'qualified' },
    ],
    log: [
      { when: '06:30', text: 'Rebalanced hedges after BTC moved 2.1%' },
      { when: '04:15', text: 'Closed funding arb on Paper Trade (+$14)' },
      { when: '00:50', text: 'Rotated $3,000 of volume to Variational before the snapshot' },
    ],
  },
}
