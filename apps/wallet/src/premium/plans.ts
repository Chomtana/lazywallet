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
    blurb: 'Everything in Auto Airdrop Hunt, plus optimal-strategy volume on trending perp DEXs and RWA projects. Insured.',
  },
]

export const DEFAULT_PLAN: PlanId = 'airdrop'
export const PERKS = ['Insurance covers hacks and rug pulls', 'Dedicated browser with a real IP address', 'A team that solves captchas for you']

export const planOf = (id: PlanId): Plan => PLANS.find((p) => p.id === id)!

export type Subscription = { plan: PlanId; since: string } // since: ISO date

// One row per project: points (total and gained in the last 24 h); perp/RWA rows also carry trading volume.
export type HuntProject = {
  name: string
  kind: string // "Perp DEX", "RWA", "Points"
  network: string // '' when not confirmed
  points: number
  pointsToday: number
  unit: string // "pts", "cores", "PAPER"
  volumeUsd?: number // last 24 h; perp/RWA plan only (absent for hold-only RWA)
}

export type HuntSection = { title: string; showVolume: boolean; projects: HuntProject[] }

export type HuntResults = {
  summary: string // shown and spoken
  stats: { label: string; value: string }[]
  sections: HuntSection[]
}

const AIRDROPS: HuntSection = {
  title: 'Airdrop programs',
  showVolume: false,
  projects: [
    { name: 'Avant', kind: 'Points', network: 'Avalanche', points: 41_200, pointsToday: 1_480, unit: 'pts' },
    { name: 'Theo', kind: 'RWA', network: 'Ethereum', points: 18_900, pointsToday: 760, unit: 'pts' },
    { name: 'Re', kind: 'RWA', network: 'Ethereum', points: 9_750, pointsToday: 540, unit: 'pts' },
    { name: 'Tori', kind: 'Points', network: 'Ethereum', points: 3_100, pointsToday: 150, unit: 'cores' },
  ],
}

// Trending pre-TGE programs as of 2026-10-16 (Lighter, GRVT, edgeX, Paradex already launched tokens).
const PERP_RWA: HuntSection = {
  title: 'Perp & RWA',
  showVolume: true,
  projects: [
    { name: 'Ostium', kind: 'RWA perps', network: 'Arbitrum', volumeUsd: 52_000, points: 14_200, pointsToday: 2_100, unit: 'pts' },
    { name: 'Extended', kind: 'Perp DEX', network: 'Starknet', volumeUsd: 61_000, points: 2_940, pointsToday: 310, unit: 'pts' },
    { name: 'Papertrade', kind: 'Perp DEX', network: 'HyperEVM', volumeUsd: 24_000, points: 38_500, pointsToday: 4_200, unit: 'PAPER' },
    { name: 'PERPTools', kind: 'Perp DEX', network: '', volumeUsd: 31_000, points: 6_210, pointsToday: 890, unit: 'pts' },
    { name: 'Ondo Perps', kind: 'RWA perps', network: 'Ethereum', volumeUsd: 16_000, points: 8_400, pointsToday: 620, unit: 'pts' },
  ],
}

export const RESULTS: Record<PlanId, HuntResults> = {
  airdrop: {
    summary:
      'Overnight I farmed four points programs and earned about 2,900 points. ' +
      'Avant is your biggest, at 41 thousand points, up 18 percent this week. ' +
      'Theo and Re keep earning on idle stablecoins, and Tori is on a 21-day streak.',
    stats: [
      { label: 'Programs', value: '4' },
      { label: 'Points this week', value: '+18%' },
    ],
    sections: [AIRDROPS],
  },
  // The perp/RWA plan includes everything the airdrop plan hunts.
  perp_rwa: {
    summary:
      'Overnight I traded 184 thousand dollars of hedged volume across five exchanges. ' +
      'Extended took the most, 61 thousand. On Ostium a boost window doubled your points to 14 thousand. ' +
      'PERPTools converts points to tokens later this quarter, so I am leaning in there. ' +
      'Your four airdrop programs added about 2,900 points, led by Avant.',
    stats: [
      { label: 'Volume (24h)', value: '$184K' },
      { label: 'Fees + funding', value: '$92' },
      { label: 'Programs', value: '9' },
    ],
    sections: [PERP_RWA, AIRDROPS],
  },
}
