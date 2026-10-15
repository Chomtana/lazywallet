# LazyWallet — Trending Avalanche Memecoins Spec

Date: 2026-10-15
Status: Approved design — not yet implemented
Builds on: `2026-10-15-lazywallet-avalanche-dexalot-design.md` (Phase 4, merged to `main`)
Branch: `feat-trending-avax` (worktree, from `main`)
Sibling: `2026-10-15-lazywallet-kyber-custom-tokens-design.md` (built in parallel; buying a trending token goes through it **by contract address**)

## 1. Goal

"What's trending on Avalanche?" → the agent answers with the top memecoins right now, from live mainnet data, so the user can pick one to buy.

**Success criteria**
- A short research note picks the data source and the memecoin filter, with reasons.
- New read-only agent tool `list_trending_tokens` returns up to 10 Avalanche memecoins: symbol, name, contract address, price USD, 24h volume, 24h change, liquidity, main DEX.
- The agent summarises the list in one or two spoken-friendly sentences and offers to buy; any buy is proposed by contract address.
- No majors, stablecoins, wrapped or liquid-staking tokens in the list.
- `pnpm test:py`, `pnpm build && pnpm lint` pass. Unit tests never hit the network.

## 2. Decisions

| Topic | Decision |
|---|---|
| Network | Avalanche only |
| Default source | GeckoTerminal public API (no key, ~30 req/min). Verified 2026-10-15: `GET /api/v2/networks/avax/trending_pools` and `GET /api/v2/networks/avax/dexes/{dex}/pools?sort=h24_volume_usd_desc` work; LFJ appears as `traderjoe`, `traderjoe-v2-1-avalanche`, `traderjoe-v2-2-avalanche`; Arena as `arena-dex`; also `pharaoh-*`, `blackhole-*` |
| Scope of venues | All Avalanche DEXs (memecoin activity is spread across LFJ, Pharaoh, Blackhole, Arena), not LFJ only |
| Source change | The research step (§3) may switch source only if another is clearly better on the §3 criteria, and must say why |
| Caching | 60 s in-process cache of the computed list |
| UI | None new; chat text only |
| Buying | Not in this branch. The prompt tells the model to buy via `propose_swap` with the contract address; until the Kyber branch lands, that returns the normal unsupported-token error |
| Out of scope | Ethereum trending, charts, alerts, a Trending screen, Arena bonding-curve (pre-graduation) tokens |

## 3. Research step (first task)

Write `docs/research/2026-10-15-avalanche-trending-memecoins.md` (keep it short):

- Compare GeckoTerminal, DexScreener (public endpoints), and any public LFJ / Arena endpoints on: needs a key?, rate limit, Avalanche DEX coverage (incl. Arena DEX), freshness, fields available (address, price, volume, change, liquidity).
- Define the memecoin filter: exclude the Avalanche registry symbols/addresses (`AVAX_TOKENS`), wrapped (WAVAX, *.e, BTC.b), stablecoins (USD*, DAI*, AUSD, …), liquid staking (sAVAX, ggAVAX, …) and DEX/governance tokens that clearly aren't memes only if the data offers a reliable way to tell (otherwise don't guess). Require liquidity ≥ $10,000.
- Pick the ranking: GeckoTerminal trending order, falling back to 24h volume.
- Record the decision and the sample output it was based on (date-stamped).

## 4. Agent tool

New `agent/lazyagent/trending.py`:

- `TrendingSource` protocol + `GeckoTerminalSource` (HTTP via stdlib `urllib` in `asyncio.to_thread`, like `faucet.py`; no new dependency; the source is injectable so tests use fixtures).
- Pure functions, unit-tested: `parse_pools(json) -> list[Pool]`, `is_memecoin(token) -> bool`, `rank(pools) -> list[Trending]` (one entry per token: its highest-liquidity pool; filter; sort; top 10).
- `Trending`: `symbol, name, address, price_usd, volume_24h, change_24h, liquidity_usd, dex`.
- Errors (HTTP failure, 429) → a plain error string from the tool ("Couldn't load trending tokens right now."); never a crash.

`tools.py`: register `list_trending_tokens` (no args), returning the list as JSON text for the model.

`prompt.py`: "What's trending / hot memecoins on Avalanche" → `list_trending_tokens`; summarise the top few by symbol with 24h change in one or two sentences; offer to buy; when buying, pass the token's **contract address** to `propose_swap`. Trending data is live mainnet; a very new token may not exist on the Sandbox fork yet.

## 5. Testing

- pytest with fixture JSON captured from GeckoTerminal: parsing, memecoin filter (stable/wrapped/major excluded, low liquidity excluded), de-dup by token, ranking, top-10 cap, cache hit within 60 s, HTTP error → friendly message.
- Manual: ask "what's trending on Avalanche?" in the wallet app.

## 6. Merge plan

The Kyber branch merges first; this branch then rebases. Expected conflicts are limited to tool registration in `tools.py` and `prompt.py`.
