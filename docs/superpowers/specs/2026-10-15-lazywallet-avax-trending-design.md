# LazyWallet — Trending Avalanche Tokens (Memecoins + RWAs) Spec

Date: 2026-10-15
Status: Approved design (rev. 2: adds RWAs) — not yet implemented
Builds on: `2026-10-15-lazywallet-avalanche-dexalot-design.md` (Phase 4, merged to `main`)
Branch: `feat-trending-avax` (worktree, from `main`)
Sibling: `2026-10-15-lazywallet-kyber-custom-tokens-design.md` (built in parallel; buying a listed token goes through it **by contract address**)

## 1. Goal

"What's trending on Avalanche?" → the agent answers with the top memecoins right now. "What RWAs are on Avalanche?" → the top real-world-asset tokens, saying plainly which ones can actually be bought here. Both from live mainnet data, so the user can pick one to buy.

**Success criteria**
- A short research note picks the data sources, the memecoin filter and the RWA source, with reasons.
- New read-only agent tool `list_trending_tokens(category)` with `category` = `meme` (default) or `rwa`, returning up to 10 Avalanche tokens: symbol, name, contract address, price USD, 24h volume, 24h change, liquidity, main DEX, `buyable`.
- `meme`: no majors, stablecoins, wrapped, liquid-staking or known DEX/governance tokens.
- `rwa`: only tokens in CoinGecko's RWA category with an Avalanche address, minus a small not-RWA list (e.g. LINK). Permissioned funds (BUIDL, ACRED, …) appear with `buyable: false`.
- The agent summarises in one or two spoken-friendly sentences, offers to buy only `buyable` tokens, and any buy is proposed by contract address.
- `pnpm test:py`, `pnpm build && pnpm lint` pass. Unit tests never hit the network.

## 2. Decisions

| Topic | Decision |
|---|---|
| Network | Avalanche only |
| Market data | GeckoTerminal public API (no key, ~30 req/min; 429s after a short burst — verified). `GET /api/v2/networks/avax/trending_pools`, `GET /api/v2/networks/avax/dexes/{dex}/pools?sort=h24_volume_usd_desc`, `?include=base_token,dex` for symbol/name/address/DEX display name; token batch lookup for RWAs via `GET /api/v2/networks/avax/tokens/multi/{addresses}` (verify in research). LFJ = `traderjoe`, `traderjoe-v2-1-avalanche`, `traderjoe-v2-2-avalanche`; Arena = `arena-dex` |
| Meme candidates | `trending_pools` **plus** `arena-dex` top pools by 24h volume (trending alone yields ~1 memecoin) |
| Meme filter | Exclude `AVAX_TOKENS`, wrapped/bridged/staked (symbol contains AVAX/BTC/ETH; name contains staked/staking/wrapped/bridged), stablecoins (symbol contains USD, or DAI, AUSD, EURC, EUROC, XAUT, XAUT0, FRAX, GHO, MIM, JPYC), and a curated `NOT_MEMES` address list (JOE, PHAR, BLACK, QI, FOLKS, ARENA, MUON, BEAM, ZRO, GUN, NXPC). No data source tags memes reliably (GeckoTerminal tags JOE as `joe-biden`), so the curated list is accepted |
| RWA source | CoinGecko free API (no key): `GET /api/v3/coins/markets?vs_currency=usd&category=real-world-assets-rwa` (all pages) → coin ids; `GET /api/v3/coins/list?include_platform=true` → `platforms.avalanche` address. Verified 2026-10-15: 15 Avalanche RWAs in the first 250 (XAUt0 ~$5M/day; bCSPX, BUIDL, JAAA, JTRSY, ACRED, VBILL, SECZ, BIB01, HINC, CURR, BC3M, DEJAAA, BCOIN ~$0; LINK miscategorised). Research checks whether sub-categories (`tokenized-gold`, `tokenized-stock`, `tokenized-treasuries`, …) add Avalanche coins |
| RWA filter | Curated `NOT_RWA` address list (LINK on Avalanche `0x5947BB275c521040051D82396192181b413227A3`) |
| `buyable` | Deepest pool liquidity ≥ $10,000. Memes below that are dropped; RWAs below it are kept with `buyable: false` |
| Ranking | Meme: trending order first, then the rest by 24h volume. RWA: 24h DEX volume, then CoinGecko market cap |
| Caching | 60 s for computed lists; 24 h for the RWA address set (CoinGecko free tier allows only a few requests/min; `coins/list` is large). Errors are never cached |
| UI | None new; chat text only |
| Buying | Not in this branch. The prompt tells the model to buy via `propose_swap` with the contract address; until the Kyber branch lands, that returns the normal unsupported-token error |
| Out of scope | Ethereum trending, charts, alerts, a Trending screen, Arena bonding-curve (pre-graduation) tokens, KYC/permissioned RWA purchase flows |

## 3. Research step (first task)

Write `docs/research/2026-10-15-avalanche-trending-tokens.md` (keep it short):

- Memes: compare GeckoTerminal, DexScreener (public; no trending endpoint; includes Arena as `arenatrade`), and any public LFJ / Arena endpoints (LFJ timed out without a key; no public Arena API found) on: key needed, rate limit, DEX coverage, freshness, fields.
- RWAs: confirm the CoinGecko endpoints above, list which RWA categories add Avalanche coins, and confirm the GeckoTerminal batch-token endpoint returns price/volume/liquidity for them. Note which RWAs are permissioned.
- Record the filters, rankings and a date-stamped sample output for both categories. If the checks contradict this spec, stop and report.

## 4. Agent tool

New `agent/lazyagent/trending.py`:

- Sources behind protocols (HTTP via stdlib `urllib` in `asyncio.to_thread`, like `faucet.py`; no new dependency; injectable so tests use fixtures): `GeckoTerminalSource` (pools, token batch) and `CoinGeckoRwaSource` (RWA Avalanche addresses).
- Pure, unit-tested functions: `parse_pools`, `is_memecoin`, `rank_memes`, `rwa_addresses(markets, coin_list)`, `rank_rwas`, `to_json`.
- `Trending`: `symbol, name, address, price_usd, volume_24h, change_24h, liquidity_usd, dex, buyable`.
- Errors (HTTP failure, 429, non-JSON) → a plain error string ("Couldn't load trending tokens right now."); never a crash. Empty list is a normal result.

`tools.py`: register `list_trending_tokens` with one optional arg `category` (`meme` | `rwa`, default `meme`; anything else → error text), returning JSON text for the model.

`prompt.py`: "trending / hot memecoins on Avalanche" → `category: meme`; "RWA / real-world assets / tokenized gold, stocks, treasuries on Avalanche" → `category: rwa`. Summarise the top few by symbol with 24h change; for RWAs say which aren't buyable here (permissioned). Offer to buy only `buyable` tokens; when buying, pass the **contract address** to `propose_swap`. Data is live mainnet; a very new token may not exist on the Sandbox fork yet.

## 5. Testing

- pytest with fixture JSON captured from GeckoTerminal and CoinGecko, kept small (1–2 tokens per case): meme parse/filter/rank, `NOT_MEMES`, low liquidity dropped; RWA address extraction, `NOT_RWA`, `buyable` true/false, ranking; top-10 cap; both caches (60 s / 24 h) with a fake clock; HTTP error/429/non-JSON → friendly message; bad `category` → error.
- Manual: "what's trending on Avalanche?" and "what RWAs are on Avalanche?" in the wallet app.

## 6. Merge plan

The Kyber branch merges first; this branch then rebases. Expected conflicts: tool registration in `tools.py`, `prompt.py`, `test_tools.py` (`TOOL_NAMES`) and the end of `fakes.py` — all additive, keep both sides.
