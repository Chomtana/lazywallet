# LazyWallet — Trending Avalanche Tokens (Memecoins + RWAs) Spec

Date: 2026-10-15
Status: Approved design (rev. 4: RWA = RWA *project* tokens, pinned XAUt0) — not yet implemented
Builds on: `2026-10-15-lazywallet-avalanche-dexalot-design.md` (Phase 4, merged to `main`)
Branch: `feat-trending-avax` (worktree, from `main`)
Sibling: `2026-10-15-lazywallet-kyber-custom-tokens-design.md` (built in parallel; buying a listed token goes through it **by contract address**)

## 1. Goal

"What's trending on Avalanche?" → the agent answers with the top memecoins right now. "What RWA tokens are hot?" → the top RWA **project tokens** (what degens mean by RWA: ONDO, PLUME, SYRUP, CFG, …), with the sponsor-showcase XAUt0 on Avalanche pinned first. Both from live mainnet data, so the user can pick one to buy.

**Success criteria**
- A short research note picks the data sources, the memecoin filter and the RWA source, with reasons.
- New read-only agent tool `list_trending_tokens(category)` with `category` = `meme` (default) or `rwa`, and optional `network` (`ethereum` | `avalanche`, `rwa` only; default both), returning up to 10 tokens: symbol, name, contract address, network, price USD, 24h volume, 24h change, liquidity, main DEX, `buyable`.
- `meme`: no majors, stablecoins, wrapped, liquid-staking or known DEX/governance tokens.
- `rwa`: RWA **project tokens** — tokens in CoinGecko's `real-world-assets-rwa` category that are NOT in any tokenized-asset sub-category (tokenized stocks, ETFs, gold, silver, commodities, treasuries, T-bills, money-market funds, credit, …), minus a small `NOT_RWA` list of infra/oracle/L1 tokens and stablecoins. In practice this is mostly Ethereum (ONDO, PLUME, SYRUP, CFG, RE, RSR, USUAL, …); Avalanche has no liquid RWA project tokens. `PINNED` (XAUt0 on Avalanche, tokenized gold, labelled as such) always comes first. Tokens without liquidity appear with `buyable: false`.
- The agent summarises in one or two spoken-friendly sentences, offers to buy only `buyable` tokens, and any buy is proposed by contract address.
- `pnpm test:py`, `pnpm build && pnpm lint` pass. Unit tests never hit the network.

## 2. Decisions

| Topic | Decision |
|---|---|
| Network | Memecoins: Avalanche only. RWAs: Ethereum (CoinGecko platform `ethereum`, GeckoTerminal `eth`) and Avalanche (`avalanche` / `avax`) |
| Market data | GeckoTerminal public API (no key, ~30 req/min; 429s after a short burst — verified). `GET /api/v2/networks/avax/trending_pools`, `GET /api/v2/networks/avax/dexes/{dex}/pools?sort=h24_volume_usd_desc`, `?include=base_token,dex` for symbol/name/address/DEX display name; token batch lookup for RWAs via `GET /api/v2/networks/avax/tokens/multi/{addresses}` (verify in research). LFJ = `traderjoe`, `traderjoe-v2-1-avalanche`, `traderjoe-v2-2-avalanche`; Arena = `arena-dex` |
| Meme candidates | `trending_pools` **plus** `arena-dex` top pools by 24h volume (trending alone yields ~1 memecoin) |
| Meme filter | Exclude `AVAX_TOKENS`, wrapped/bridged/staked (symbol contains AVAX/BTC/ETH; name contains staked/staking/wrapped/bridged), stablecoins (symbol contains USD, or DAI, AUSD, EURC, EUROC, XAUT, XAUT0, FRAX, GHO, MIM, JPYC), and a curated `NOT_MEMES` address list (JOE, PHAR, BLACK, QI, FOLKS, ARENA, MUON, BEAM, ZRO, GUN, NXPC). No data source tags memes reliably (GeckoTerminal tags JOE as `joe-biden`), so the curated list is accepted |
| RWA source | CoinGecko free API (no key) is too rate-limited to query per request (RWA category ≈ 2,466 coins / 10 pages; 429s even at 1 req/15 s — verified). So an offline script `python -m lazyagent.rwa_snapshot` pages through `coins/markets?category=real-world-assets-rwa` and each tokenized-asset sub-category, plus `coins/list?include_platform=true`, waits out 429s, and writes the checked-in snapshot `agent/lazyagent/data/rwa_coingecko.json` (project-token addresses per network + CoinGecko volume/market cap). The tool reads the snapshot; live market data still comes from GeckoTerminal |
| RWA filter | Project token = in the RWA category and not in any tokenized-asset sub-category. `NOT_RWA` (curated, per network): infra/oracle/general-L1 tokens CoinGecko files as RWA — LINK, QNT, INJ, TRAC, RED, DIA, CHR — and USD stablecoins (e.g. USAT). Verified 2026-10-15 on Ethereum: ONDO $188M/24h, PLUME $31M, CFG $16M, SYRUP $15M, RE $11M |
| Pinned RWAs | `PINNED` constant, in order, always first in `rwa` results (when the network filter includes it), with real market data and real `buyable`, and a `note`: XAUt0 on Avalanche `0x2775d5105276781b4b85ba6ea6a6653beed1dd32`, note "tokenized gold — Avalanche showcase" (it is an asset token, pinned deliberately as the hackathon sponsor showcase) |
| `buyable` | Deepest pool liquidity ≥ $10,000. Memes below that are dropped; RWAs below it are kept with `buyable: false` |
| Ranking | Meme: trending order first, then the rest by 24h volume. RWA: `PINNED` first, then 24h DEX volume, then CoinGecko market cap |
| Caching | 60 s for computed lists (per category + network). RWA addresses come from the checked-in snapshot (refresh by rerunning the script). Errors are never cached |
| UI | None new; chat text only |
| Buying | Not in this branch. The prompt tells the model to buy via `propose_swap` with the contract address; until the Kyber branch lands, that returns the normal unsupported-token error |
| Out of scope | Ethereum memecoins, charts, alerts, a Trending screen, Arena bonding-curve (pre-graduation) tokens, KYC/permissioned RWA purchase flows |

## 3. Research step (first task)

Write `docs/research/2026-10-15-avalanche-trending-tokens.md` (keep it short):

- Memes: compare GeckoTerminal, DexScreener (public; no trending endpoint; includes Arena as `arenatrade`), and any public LFJ / Arena endpoints (LFJ timed out without a key; no public Arena API found) on: key needed, rate limit, DEX coverage, freshness, fields.
- RWAs: confirm the CoinGecko category + sub-category endpoints, record how many project tokens per network survive the filter and which are liquid, confirm the GeckoTerminal batch-token endpoint (max 30 addresses) returns price/volume/liquidity for them.
- Record the filters, rankings and a date-stamped sample output for both categories. If the checks contradict this spec, stop and report.

## 4. Agent tool

New `agent/lazyagent/trending.py`:

- Sources behind protocols (HTTP via stdlib `urllib` in `asyncio.to_thread`, like `faucet.py`; no new dependency; injectable so tests use fixtures): `GeckoTerminalSource` (pools, token batch) and snapshot loader for `agent/lazyagent/data/rwa_coingecko.json`; `CoinGeckoRwaSource` lives in the offline `rwa_snapshot.py`.
- Pure, unit-tested functions: `parse_pools`, `is_memecoin`, `rank_memes`, `rwa_addresses(markets, coin_list)`, `rank_rwas`, `to_json`.
- `Trending`: `symbol, name, address, network, price_usd, volume_24h, change_24h, liquidity_usd, dex, buyable, note` (`note` only for pinned entries).
- Errors (HTTP failure, 429, non-JSON) → a plain error string ("Couldn't load trending tokens right now."); never a crash. Empty list is a normal result.

`tools.py`: register `list_trending_tokens` with optional args `category` (`meme` | `rwa`, default `meme`) and `network` (`ethereum` | `avalanche`, `rwa` only, default both); anything else → error text, returning JSON text for the model.

`prompt.py`: "trending / hot memecoins on Avalanche" → `category: meme`; "RWA tokens / RWA plays / real-world-asset projects" → `category: rwa` (pass `network` only if the user named one). Summarise the top few by symbol with 24h change; for RWAs mention XAUt0 is tokenized gold pinned as the Avalanche showcase, and say which aren't buyable here. Offer to buy only `buyable` tokens; when buying, pass the **contract address** to `propose_swap`. Data is live mainnet; a very new token may not exist on the Sandbox fork yet.

## 5. Testing

- pytest with fixture JSON captured from GeckoTerminal and CoinGecko, kept small (1–2 tokens per case): meme parse/filter/rank, `NOT_MEMES`, low liquidity dropped; RWA project-token extraction on both chains (asset sub-category ids excluded), `NOT_RWA`, `PINNED` first, network filter, `buyable` true/false, ranking; top-10 cap; both caches (60 s / 24 h) with a fake clock; HTTP error/429/non-JSON → friendly message; bad `category` → error.
- Manual: "what's trending on Avalanche?" and "what RWA tokens are hot?" in the wallet app.

## 6. Merge plan

The Kyber branch merges first; this branch then rebases. Expected conflicts: tool registration in `tools.py`, `prompt.py`, `test_tools.py` (`TOOL_NAMES`) and the end of `fakes.py` — all additive, keep both sides.
