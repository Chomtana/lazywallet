export type Address = `0x${string}`
export type StoredWallet = { id: string; name: string; mnemonic: string; address: Address }
export type Vault = { wallets: StoredWallet[] }
export type EncryptedVault = { v: 1; salt: string; iv: string; data: string }
export type Contact = { id: string; name: string; address: Address }
// usdPrice null = price unknown (a custom token with no route to USDC) — shown as such, left out of totals.
// logo: an image URL, or null/absent → initials.
export type Holding = { symbol: string; amount: number; usdPrice: number | null; network?: string; logo?: string | null }
export type BalanceChange = { network?: string; symbol: string; before: number; after: number; delta: number; usdPrice: number | null; logo?: string | null }
// A row of the agent's token list card (list_trending_tokens). network is a display name ("Ethereum").
export type TrendingToken = {
  symbol: string
  name: string
  network: string
  address: Address
  priceUsd: number | null
  change24h: number | null
  liquidityUsd: number
  dex: string
  buyable: boolean
  note: string | null
  image: string | null
}
export type CustomToken = { chainId: number; address: Address; symbol: string; decimals: number; logo?: string }
// One row of the airdrops card (agent list_airdrops). farm = short name for "Farm <farm> with N USDC"; buy = a farm token to buy.
export type AirdropItem = {
  id: string
  name: string
  category: 'rwa' | 'other'
  networks: string[]
  status: 'live' | 'unverified' | 'claim_pending'
  action: string
  tvlUsd: number | null
  farm: string | null
  buy: { symbol: string; address: Address } | null
}
// One row of the unlocks card (agent list_unlocks). date: ISO UTC. buybackUsd/burnUsd: last 30 days, null = none.
// network: where LazyWallet can buy it ("Ethereum" | "Avalanche"), null = not available; address null = native AVAX.
export type UnlockItem = {
  symbol: string
  name: string
  logo: string | null
  date: string
  unlockUsd: number | null
  unlockAmount: number
  percentOfSupply: number | null
  allocation: string | null
  buybackUsd: number | null
  burnUsd: number | null
  network: string | null
  address: Address | null
  buyable: boolean
}
export type ChoiceOption = { label: string; detail?: string; reply: string }
export type DappInfo = { name: string; url: string; icon: string }
export type TxRequest = { to: Address; value: string; data: `0x${string}`; chainId?: number }
export type TxStep = { label: string; request: TxRequest }
// The friendly top half of a swap/farm confirm card (agent swaps.py swap_summary / airdrops.py farm_summary).
// amount is a display string ("≈ 41.3" when estimated); usd/logo are null when unknown.
export type SummaryToken = { symbol: string; amount: string; usd: number | null; logo: string | null }
export type TxSummary = {
  kind: 'swap' | 'farm'
  network: string
  pay: SummaryToken
  swap?: { symbol: string; amount: string; via: string; logo: string | null } // farm only: the token it swaps into
  receive: SummaryToken & { note: string | null }
  via?: string // swap only
  fee: string
  program?: string // farm only
  warning: string | null
}
export type TxDraft = {
  title: string
  summary?: TxSummary
  rows: { label: string; value: string }[]
  dapp?: DappInfo
  explanation?: string
  steps?: TxStep[]
  from?: Address
  addToken?: CustomToken // a token this swap buys; saved to lw.tokens once every step succeeded
  addTokens?: CustomToken[] // tokens a multi-step card (e.g. a farm deposit) leaves in the wallet; saved like addToken
}
export type TaskKind = 'dca' | 'alert' | 'conditional'
export type Task = {
  id: string
  kind: TaskKind
  description: string
  schedule: string
  status: 'active' | 'paused'
  trigger?: TxDraft
}
export type ConfirmState = 'waiting' | 'approved' | 'rejected' | 'expired'
export type Message =
  | { id: string; role: 'user'; kind: 'text'; text: string; spoken?: boolean; unsent?: boolean }
  | { id: string; role: 'assistant'; kind: 'text'; text: string }
  | { id: string; role: 'assistant'; kind: 'balance'; holdings: Holding[] }
  | { id: string; role: 'assistant'; kind: 'balance_change'; changes: BalanceChange[] }
  | { id: string; role: 'assistant'; kind: 'tokens'; title: string; items: TrendingToken[] }
  | { id: string; role: 'assistant'; kind: 'confirm'; tx: TxDraft; state: ConfirmState }
  | { id: string; role: 'assistant'; kind: 'status'; state: 'pending' | 'success' | 'failed'; text: string; hash?: string }
  | { id: string; role: 'assistant'; kind: 'task'; task: Task }
  | { id: string; role: 'assistant'; kind: 'choice'; question: string; options: ChoiceOption[]; chosen?: string; closed?: boolean }
  | { id: string; role: 'assistant'; kind: 'airdrops'; title: string; items: AirdropItem[] }
  | { id: string; role: 'assistant'; kind: 'unlocks'; title: string; items: UnlockItem[] }
export type AssistantMessage = Exclude<Message, { role: 'user' }>
export type AgentReply = { messages: Message[]; newTask?: Task }
