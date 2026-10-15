export type Address = `0x${string}`
export type StoredWallet = { id: string; name: string; mnemonic: string; address: Address }
export type Vault = { wallets: StoredWallet[] }
export type EncryptedVault = { v: 1; salt: string; iv: string; data: string }
export type Contact = { id: string; name: string; address: Address }
export type Holding = { symbol: string; amount: number; usdPrice: number }
export type DappInfo = { name: string; url: string; icon: string }
export type TxRequest = { to: Address; value: string; data: `0x${string}` }
export type TxDraft = {
  title: string
  rows: { label: string; value: string }[]
  dapp?: DappInfo
  explanation?: string
  request?: TxRequest
  from?: Address
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
  | { id: string; role: 'user'; kind: 'text'; text: string; spoken?: boolean }
  | { id: string; role: 'assistant'; kind: 'text'; text: string }
  | { id: string; role: 'assistant'; kind: 'balance'; holdings: Holding[] }
  | { id: string; role: 'assistant'; kind: 'confirm'; tx: TxDraft; state: ConfirmState }
  | { id: string; role: 'assistant'; kind: 'status'; state: 'pending' | 'success' | 'failed'; text: string; hash?: string }
  | { id: string; role: 'assistant'; kind: 'task'; task: Task }
export type AssistantMessage = Exclude<Message, { role: 'user' }>
export type AgentReply = { messages: Message[]; newTask?: Task }
