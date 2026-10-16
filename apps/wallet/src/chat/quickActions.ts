// One-tap prompts above the composer; each sends `text` as a normal user message.
export type QuickAction = { label: string; text: string }

export const QUICK_ACTIONS: QuickAction[] = [
  { label: 'Check balances', text: "What's my balance?" },
  { label: 'Trending airdrops', text: 'What airdrops can I farm?' },
  { label: 'Upcoming unlocks', text: 'What are the upcoming token unlocks?' },
  { label: 'Trending memes', text: 'What memecoins are trending?' },
  { label: 'Swap 10 AVAX to COQ', text: 'Swap 10 AVAX to COQ' },
]
