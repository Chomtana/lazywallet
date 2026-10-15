# LazyWallet — token unlocks

"What's unlocking soon?" → `list_unlocks` → an "Upcoming unlocks" card: the month's biggest token unlocks, each with its
buybacks/burns over the last 30 days and a Buy button when LazyWallet can buy the token. Read-only, live data.

## Data (Tokenomist API v5, header `x-api-key`)

Checked against the live API on 2026-10-16.

| Call | Use |
| --- | --- |
| `GET /v5/unlock/events/upcoming?start=<today>&end=<today+30>&pageSize=200` | One event per token, sorted by date ascending (139 for this month, so one page). Per event: `tokenId`, `tokenSymbol`, `tokenName`, `upcomingEvent.unlockDate`, `upcomingEvent.cliffUnlocks.{totalCliffAmount, totalCliffValue, valueToMarketCap, allocationBreakdown[]}`. The live field names are `totalCliffAmount`/`totalCliffValue`, not `cliffAmount`/`cliffValue` as the docs say. |
| `GET /v5/token/list?tokenId=a,b,…` | One call for the shown tokens: `maxSupply` (→ % of supply) and the `hasBuyback` / `hasBurn` flags. |
| `GET /v5/buyback/{tokenId}?start=<today-30>&end=<today>` | Only for tokens with `hasBuyback`: `data.totalBuybackValue` (USD, null when none) for the range. |
| `GET /v5/burn/{tokenId}?start=…&end=…` | Only for tokens with `hasBurn`: `data.totalBurnValue`. Unflagged tokens answer 403 "This token is not supported" — hence the flags. |

Limits: the plan has 50,000 requests/month (`metadata.credit`), resetting on the 1st; quota or rate limit → `429`.
No key → 401, a wrong key → 403. One refresh costs 2 + (flagged tokens among the 10) Tokenomist requests, and is cached for 10 minutes.

Selection: unlocks from now to 30 days ahead; the 10 largest by USD value; shown soonest first. Allocation = the two
biggest standard allocations by value ("Founder / Team" → "Team", "Private Investors" → "Investors").

## Where it can be bought

Tokenomist gives no contract addresses, but its token ids are CoinGecko coin ids (`layerzero`, `avalanche-2`,
`crypto-com-chain`). So:

1. CoinGecko free `coins/list?include_platform=true` (one ~4 MB call, cached for a day) → the `ethereum` platform
   address, used only when CoinGecko's symbol matches Tokenomist's.
2. GeckoTerminal `tokens/multi` on `eth` (one call, ≤ 30 addresses) → logo and deepest pool; **buyable = a pool ≥ $10k**,
   the trending-tokens rule.
3. AVAX (`avalanche-2`) is Avalanche's native coin: network Avalanche, no address, buyable.

Other chains' tokens show dimmed with no Buy.

## Failure handling

Only the unlock list is required: if it fails (no key, 429, network) the tool says "Couldn't load token unlocks right
now." and nothing is cached. A failed token list, buyback, or burn call leaves those fields null. A failed CoinGecko call
leaves availability unknown (only AVAX is buyable). If GeckoTerminal fails, a token on Ethereum counts as buyable.

## Card

`{"type": "unlocks", "title": "Upcoming unlocks", "items": [{symbol, name, logo, date, unlockUsd, unlockAmount,
percentOfSupply, allocation, buybackUsd, burnUsd, network, address, buyable}]}`. The date is shown in UTC ("in 3 days · Oct 19"),
as Tokenomist dates it. The Buy chips match the token list: on Ethereum they send "Buy 50 USDC of SYM (0x…)", on
Avalanche "Buy 0.5 AVAX of SYM (0x…)", and for native AVAX "Buy 50 USDC of AVAX".

## Security

The key is read from the environment (root `.env`, loaded by `config.load_settings`) inside the agent process. It is
only sent as a request header and is never put in a URL, a log line, an error message, a card, or a test fixture.
