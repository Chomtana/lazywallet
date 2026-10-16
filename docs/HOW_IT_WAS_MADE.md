# LazyWallet: Let AI agents hunt airdrops and trade while you sleep.

## Hunting airdrops
The agent research and list trending airdrop programs in a single card. On Avalanche that's Avant: swap USDC to avUSD, then stake it into savUSD, all in one click. It also surfaces trending Avalanche memecoins and RWA tokens, buy and schedule auto sell based on price / time condition in one click.

## Auto Airdrop Hunt (premium)
Each subscriber gets a dedicated VM running a Claude computer-use agent in a real browser with its own residential IP, so it can use any dApp, including quest and points sites with no API. A research agent re-ranks programs daily from our airdrop data (live TVL, liquidity, Tokenomist token data) and writes a step-by-step plan per protocol. The agent signs with a session key limited to the user's hunting wallet, an allowlist of contracts and a daily spend cap, so it can farm without the user's main keys. When it hits a captcha, it hands off to our captcha solving team, and an insurance pool covers hack and rug losses.

## What's unlocking soon?, with Tokenomist
Ask "what's unlocking soon?" and the agent pulls Tokenomist API v5 for the next 30 days of unlocks (size, % of supply, who's unlocking) and the last 30 days of buybacks and burns. It tells you which supply is about to hit the market and whether buybacks or burns offset it. Every buyable token links straight to a swap.

## Voice Powered, with ElevenLabs
You can speak to the agent, and it answers in a natural voice through ElevenLabs streaming TTS (eleven_flash_v2_5, low latency).

## Scheduled trade while you sleep, on Avalanche
Our SwapScheduler contract holds recurring and delayed orders on Avalanche C-Chain. An executor fills them through Dexalot's RFQ at its live price (EIP-712 signed orders), or through KyberSwap for long-tail tokens like COQ, and the minimum output is checked on-chain. "Buy now, sell later" is the buy plus an automatic scheduled sale for exactly the amount received.