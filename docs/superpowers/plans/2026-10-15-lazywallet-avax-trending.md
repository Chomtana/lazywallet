# LazyWallet — Trending Tokens (Avalanche Memecoins + RWA Project Tokens) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A read-only agent tool `list_trending_tokens(category, network)` answers two questions from live mainnet data:
- "What's trending on Avalanche?" → up to 10 Avalanche memecoins.
- "What RWA tokens are hot?" → up to 10 RWA **project tokens** on Ethereum and Avalanche (ONDO, PLUME, SYRUP, CFG, …), with XAUt0 (tokenized gold) pinned first as the Avalanche showcase.

Each token carries its contract address, network, a `buyable` flag and an optional `note`, so the agent can summarise and offer to buy by contract address.

**Architecture:** One new runtime module, `agent/lazyagent/trending.py`:
- Pure functions: `parse_pools`, `is_memecoin`, `rank_memes`, `rwa_addresses`, `rwa_candidates`, `parse_tokens`, `rank_rwas`, `parse_args`, `to_json`.
- An injectable `GeckoTerminalSource` (stdlib `urllib` in `asyncio.to_thread`, like `faucet.py`).
- A 60 s `TrendingTokens` cache keyed by (category, network), with one fetcher per category.
- The tool layer: `TRENDING_TOOL` (name, description, schema) and `trending_reply`.

Categories are a registry (`CATEGORY_NETWORKS`). Adding one later, such as the planned `airdrop`, means adding a registry entry, a fetcher and a description line in `trending.py`, plus a prompt line. `tools.py` stays as it is.

RWA project tokens come from a checked-in snapshot, `agent/lazyagent/data/rwa_coingecko.json`. A project token is a coin in CoinGecko's `real-world-assets-rwa` category that is not in `tokenized-products`. The offline script `agent/lazyagent/rwa_snapshot.py` builds the snapshot, pacing CoinGecko's free API. At request time only GeckoTerminal is called.

`tools.py` gets one import, one name, one class attribute and method, and a one-line registration `tool(*TRENDING_TOOL)`. `prompt.py` gets one line. No UI.

**Tech Stack:** Python 3.12+ (uv, claude-agent-sdk, pytest-asyncio with `asyncio_mode = "auto"`), GeckoTerminal public API v2 (no key), CoinGecko public API v3 (no key, offline snapshot only).

**Spec:** `docs/superpowers/specs/2026-10-15-lazywallet-avax-trending-design.md` (rev. 4)

## Global Constraints

- **Branch and merge footprint.** Work in a worktree on branch `feat-trending-avax` from `main`. The sibling branch (KyberSwap + custom tokens) heavily edits `agent/lazyagent/tools.py` and `prompt.py`, and it merges first. Limit edits in those two files to:
  - one import line
  - one name in `TOOL_NAMES`
  - one class attribute and one method
  - one `tool(*TRENDING_TOOL)(...)` line
  - one prompt line

  Do not touch `WalletTools.__init__`, `session.py` or `server.py`.
- **Networks.**
  - Memecoins: Avalanche only.
  - RWAs: Ethereum (CoinGecko platform `ethereum`, GeckoTerminal `eth`) and Avalanche (`avalanche` / `avax`).
  - Everything is live **mainnet** and read-only; nothing is signed.
- **GeckoTerminal.** Base URL `https://api.geckoterminal.com/api/v2/networks`. No key, about 30 req/min, and it answers 429 after a short burst. These requests were verified on 2026-10-15:
  - `/avax/trending_pools?include=base_token,dex`
  - `/avax/dexes/arena-dex/pools?sort=h24_volume_usd_desc&include=base_token,dex`
  - `/{eth|avax}/tokens/multi/{≤30 comma-separated addresses}?include=top_pools`. More than 30 addresses returns HTTP 400 "maximum 30 addresses allowed".
- **CoinGecko** (snapshot script only):
  - `/api/v3/coins/markets?vs_currency=usd&category={real-world-assets-rwa|tokenized-products}&per_page=250&page=N`, every page.
  - `/api/v3/coins/list?include_platform=true`.
- **HTTP.** Stdlib `urllib` only, no new dependency. Runtime calls run in `asyncio.to_thread` with a 15 s timeout. The snapshot script is synchronous with a 120 s timeout, because `coins/list` is about 4 MB.
- **Cache.** 60 s per (category, network). Errors are never cached.
- **Meme filter** (spec §2, verbatim). Exclude:
  - `AVAX_TOKENS` and WAVAX.
  - Wrapped, bridged and staked tokens: symbol contains AVAX/BTC/ETH; name contains staked/staking/wrapped/bridged.
  - Stablecoins: symbol contains USD, or is DAI, AUSD, EURC, EUROC, XAUT, XAUT0, FRAX, GHO, MIM or JPYC.
  - The curated `NOT_MEMES` addresses: JOE, PHAR, BLACK, QI, FOLKS, ARENA, MUON, BEAM, ZRO, GUN, NXPC.
  - Tokens whose deepest pool has less than **$10,000** of liquidity.
- **RWA project tokens.** A coin qualifies if it is in `real-world-assets-rwa` and **not** in `tokenized-products`, CoinGecko's "Tokenized Assets" umbrella. Verified 2026-10-15: `tokenized-products` (2,230 ids) contains every tokenized-stock, ETF, gold, silver, commodity, treasury, T-bill, money-market, credit, private-credit, pre-IPO and uranium sub-category, and the union of all those sub-categories adds no id.
  - Also exclude USD stablecoins (symbol contains "usd").
  - Also exclude the curated `NOT_RWA` (network, address) set. It holds infra/oracle/L1 tokens (LINK on both chains, QNT, INJ, TRAC, RED, DIA, CHR), USAT, and three asset tokens CoinGecko left untagged (MPRA; ACRED and VBILL on both chains).
- **Pinned entry.** `PINNED = [("avalanche", "0x2775d5105276781b4b85ba6ea6a6653beed1dd32", "tokenized gold — Avalanche showcase")]` (XAUt0). It always comes first when the network filter includes Avalanche, with real market data, the real `buyable` value and that `note`.
- **Buyable.** `buyable` means the deepest pool holds at least $10,000. RWAs below that are kept with `buyable: false`.
- **Ranking.** Top **10** for both categories.
  - Memes: trending order first, then 24h volume.
  - RWAs: `PINNED`, then 24h DEX volume, then CoinGecko market cap.
- **`Trending` fields, in order:** `symbol, name, address, network, price_usd, volume_24h, change_24h, liquidity_usd, dex, buyable, note`. `note` defaults to `None`.
- **Category registry.** `CATEGORY_NETWORKS = {"meme": ("avalanche",), "rwa": ("ethereum", "avalanche")}`. The tool schema enums, the argument errors and `TrendingTokens` dispatch all derive from it.
- **Tool error texts, verbatim:**
  - Fetch failure: `Couldn't load trending tokens right now.`
  - Unknown category: `category must be one of: meme, rwa.`
  - Unsupported network: `meme tokens are only listed on Avalanche.` / `rwa tokens are only listed on Ethereum and Avalanche.`
- **Empty results.** An empty list is a normal result (`tokens: []`). The tool never crashes.
- **Buying is out of scope.** The prompt tells the model to call `propose_swap` with the token's network and `token_out` set to its contract address. Until the Kyber branch lands, that returns the normal unsupported-token error.
- **Tests.** Unit tests never hit the network: they use fixtures (1–2 tokens per case), a local `HTTPServer` and fakes.
- **Done** means `pnpm test:py` and `pnpm build && pnpm lint` pass.
- **Spec deviations decided while planning** (recorded in the spec in Task 7):
  - The asset exclusion uses one category, `tokenized-products`, instead of listing each sub-category, because it already contains them all.
  - `NOT_RWA` also lists MPRA, ACRED and VBILL, asset tokens that CoinGecko filed only under RWA. MPRA would otherwise rank #2 on Ethereum at about $58M/day.
  - USD stablecoins are dropped by a symbol rule (catches wstUSDT, cUSDO); only USAT needs a `NOT_RWA` entry.
  - Tool arguments are parsed in `trending.py` (`parse_args`, `trending_reply`, `TRENDING_TOOL`), so the `tools.py` change is a few lines and a new category never touches it.

## Review Focus

- **GeckoTerminal returns 429 after a few quick asks** (seen while planning). The user should hear "Couldn't load trending tokens right now.", the failure must not be cached, and the next ask must retry. Tests: Task 4 (`test_source_raises_on_rate_limit`, `test_errors_are_not_cached`) and Task 6 (`test_fetch_failure_is_a_friendly_error`).
- **Asset tokens leaking into "RWA tokens."** Tokenized stocks, gold and funds must not appear, except XAUt0, which is pinned and labelled by its `note`. Tests: Task 3 (`test_rwa_addresses_keeps_project_tokens_and_drops_asset_tokens`, `test_rank_rwas_pinned_first_with_note_...`), Task 5 (`test_pages_both_categories_and_drops_asset_tokens`, `test_shipped_snapshot_has_project_tokens_not_asset_tokens`).
- **A project token whose deepest pool lists it as the quote token** (RSR in a Curve pool), **or a token with no pool at all** (NXRA). It must show a `null` 24h change or `buyable: false`, and never another token's price move. Tests: Task 3 (`test_parse_tokens_change_only_when_token_is_the_pool_base`, `test_parse_tokens_pool_and_no_pool`).
- **The model sends `network: "ethereum"` for memes, a capitalised network, or a made-up category.** The tool should return a clear error without fetching anything, and should accept "Ethereum" or "Avalanche". Tests: Task 2 (`test_parse_args_*`) and Task 6 (`test_bad_arguments_are_errors_without_fetching`, `test_rwa_with_network`).
- **Malformed or partial API data**: a base token missing from `included`, `null` numbers, HTML entities in names. The bad entry is skipped or reads 0/None, and the rest still render. Tests: Task 2 (`test_parse_pools_skips_pools_without_base_token_and_zeroes_missing_numbers`) and Task 3 (`test_parse_tokens_tolerates_an_empty_body_and_unescapes_names`).

---

## File structure

| File | Responsibility |
|---|---|
| `docs/research/2026-10-15-avalanche-trending-tokens.md` (new) | Sources, filters, rankings, dated sample output for memes and RWA project tokens |
| `agent/lazyagent/trending.py` (new) | Pure: types, category registry, meme parse/filter/rank, RWA addresses/candidates/parse/rank, `parse_args`, `to_json`, `load_rwa_snapshot`. I/O: `GeckoTerminalSource`, `TrendingTokens`, `TRENDING`. Tool layer: `TRENDING_TOOL`, `trending_reply` |
| `agent/lazyagent/rwa_snapshot.py` (new) | Offline: `CoinGeckoRwaSource` (paged, Retry-After), `snapshot_json`, `main()` |
| `agent/lazyagent/data/rwa_coingecko.json` (new, generated) | RWA project tokens: network, address, CoinGecko id, market cap, volume (~130 rows, ~21 KB) |
| `agent/tests/fixtures/*.json` (new) | Real responses captured 2026-10-15, trimmed to 1–2 tokens |
| `agent/tests/http_stub.py` (new) | Local HTTP stand-in for GeckoTerminal / CoinGecko |
| `agent/tests/test_trending.py`, `test_trending_rwa.py`, `test_trending_source.py`, `test_rwa_snapshot.py`, `test_trending_tools.py` (new) | Tests |
| `agent/tests/fakes.py` | `FakeTrendingSource` (appended) |
| `agent/lazyagent/tools.py`, `prompt.py`, `agent/tests/test_tools.py` | Tool wiring, one prompt line, `TOOL_NAMES` |
| `CLAUDE.md`, spec | One convention line; planning deviations |

---

### Task 1: Research note — sources, filters, rankings (memes + RWA project tokens)

**Files:**
- Create: `docs/research/2026-10-15-avalanche-trending-tokens.md`

**Interfaces:**
- Consumes: nothing.
- Produces: the decisions that Tasks 2–6 implement. If your spot-checks contradict them, **stop and report** instead of continuing. Examples: GeckoTerminal now needs a key, `tokens/multi` no longer returns `top_pools`, or `tokenized-products` no longer contains the tokenized sub-categories.

- [ ] **Step 1: Re-run the spot-checks.** Space the requests out, because both APIs rate-limit bursts. If you get a 429, wait 30–60 s and retry.

```bash
curl -s 'https://api.geckoterminal.com/api/v2/networks/avax/trending_pools?include=base_token,dex' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(p['attributes']['name'], '|', p['relationships']['dex']['data']['id'], '|', p['attributes']['reserve_in_usd']) for p in d['data']]"
curl -s 'https://api.geckoterminal.com/api/v2/networks/avax/dexes/arena-dex/pools?sort=h24_volume_usd_desc&include=base_token,dex' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(p['attributes']['name'], '|', p['attributes']['reserve_in_usd']) for p in d['data'][:10]]"
curl -s 'https://api.geckoterminal.com/api/v2/networks/eth/tokens/multi/0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3,0x320623b8e4ff03373931769a31fc52a4e78b5d70?include=top_pools' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(t['attributes']['symbol'], t['attributes']['price_usd'], t['attributes']['volume_usd'], len(t['relationships']['top_pools']['data'])) for t in d['data']]; print([i['type'] for i in d.get('included',[])])"
curl -s 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&category=tokenized-products&per_page=250&page=1' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d), [c['id'] for c in d[:3]])"
curl -s 'https://api.coingecko.com/api/v3/coins/ondo-finance?localization=false&tickers=false&market_data=false&community_data=false&developer_data=false' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['categories'])"
curl -s 'https://api.dexscreener.com/latest/dex/tokens/0x420fca0121dc28039145009570975747295f2329' \
  | python3 -c "import json,sys; p=json.load(sys.stdin)['pairs'][0]; print(p['dexId'], p['priceUsd'], p['liquidity']['usd'])"
```

Expected results as of 2026-10-15:
- **Trending pools:** mostly majors and protocol tokens (BTC.b, PHAR, JOE, sAVAX…). COQ is the only clear memecoin.
- **Arena DEX:** small memecoins (AVXTO, GATOR, WOLFI…).
- **`tokens/multi` (Ethereum):** ONDO and RSR each come back with a price, a volume and one top pool, and `included` holds `pool` objects.
- **`tokenized-products`:** a full page of 250 ids.
- **ONDO's categories:** include "Real World Assets (RWA)" and "RWA Protocol", but not "Tokenized Assets".
- **DexScreener:** returns COQ on `traderjoe`.

- [ ] **Step 2: Write the note** at `docs/research/2026-10-15-avalanche-trending-tokens.md` with the content below. Keep the date. If your Step 1 run differs, update the sample tables.

```markdown
# Trending tokens — Avalanche memecoins and RWA project tokens (Ethereum + Avalanche)

Date: 2026-10-15. Feeds `agent/lazyagent/trending.py` (`list_trending_tokens`) and `agent/lazyagent/rwa_snapshot.py`.

## Market data sources

| | GeckoTerminal | DexScreener | LFJ / Arena |
|---|---|---|---|
| Key | None | None | LFJ API timed out without a key; no public Arena API found |
| Rate limit | ~30 req/min (429 after a short burst) | 300/min pairs & tokens, 60/min profiles & boosts | — |
| Coverage | All DEXs on `avax` (incl. `arena-dex`, LFJ v1/v2.1/v2.2, Pharaoh, Blackhole, Pangolin, Uniswap) and `eth` | All DEXs (Arena as `arenatrade`) | Own venue only |
| Trending ranking | `/networks/avax/trending_pools`; `/dexes/{dex}/pools?sort=h24_volume_usd_desc` | None (only paid boosts, 0 Avalanche entries) | — |
| Token batch | `/networks/{net}/tokens/multi/{≤30 addresses}?include=top_pools` → price, 24h volume, deepest pool (reserve, 24h change, dex id); 31 addresses → HTTP 400 | `/tokens/v1/{chain}/{addresses}` | — |

**Decision: GeckoTerminal** for all market data — the only keyless source with a trending ranking and a batch token lookup, and it covers Arena. DexScreener is the fallback for per-token lookups.

## Memecoins (Avalanche)

- Candidates: `trending_pools` page 1 (20 pools; mostly majors and protocol tokens — today only COQ is a meme) **plus** Arena DEX's top pools by 24h volume (where Avalanche memecoins graduate). Each pool's base token only.
- Filter: no reliable meme flag exists (GeckoTerminal tags JOE as `defi`, `joe-biden`; COQ has no "meme"). Rules: exclude `AVAX_TOKENS` + WAVAX; symbol contains USD or is DAI/AUSD/EURC/EUROC/XAUT/XAUT0/FRAX/GHO/MIM/JPYC; symbol contains AVAX/BTC/ETH or ends `.e`/`.b`; name contains staked/staking/wrapped/bridged; curated `NOT_MEMES` (JOE, PHAR, BLACK, QI, FOLKS, ARENA, MUON, BEAM, ZRO, GUN, NXPC); deepest pool ≥ $10,000.
- Ranking: one entry per token (deepest pool); trending order first, then 24h volume; top 10.

| # | Symbol | 24h | Volume 24h | Liquidity | DEX |
|---|---|---|---|---|---|
| 1 | COQ | -5.1% | $16,938 | $621,870 | LFJ |
| 2 | AVXTO | +9.6% | $597 | $15,523 | Arena DEX |
| 3 | GATOR | +4.9% | $524 | $11,542 | Arena DEX |
| 4 | WOLFI | -3.6% | $351 | $25,999 | Arena DEX |
| 5 | SUPER | -4.5% | $138 | $18,089 | Arena DEX |

## RWA project tokens (Ethereum + Avalanche)

"RWA" here means what traders mean: RWA **project** tokens (ONDO, PLUME, SYRUP, CFG, …), not tokenized stocks, ETFs, gold or funds.

- Membership (CoinGecko free API): `coins/markets?category=real-world-assets-rwa` → **2,466 coins / 10 pages**. Asset tokens: `category=tokenized-products` ("Tokenized Assets") → **2,230 ids / 9 pages**; it contains every tokenized sub-category (`tokenized-stock` 1,620, `tokenized-exchange-traded-funds-etfs` 378, `tokenized-exchange-traded-product-etps` 380, `tokenized-commodities` 43, `tokenized-commodity-exchange-traded-products-etps` 27, `tokenized-gold` 26, `tokenized-credit` 22, `tokenized-treasuries` 15, `tokenized-pre-ipo-stocks` 14, `tokenized-money-market-fund-mmfs` 9, `tokenized-silver` 8, `tokenized-non-us-government-securities` 5, `tokenized-private-credit` 2, `tokenized-closed-end-funds-cefs` 1, `tokenized-uranium` 1; `tokenized-t-bills`, `tokenized-treasury-bonds-t-bonds`, `tokenized-bank-deposit` empty) — their union adds no id beyond it. RWA minus tokenized-products = 237 coins; with an Ethereum/Avalanche address = **117 Ethereum + 10 Avalanche**. `coins/list?include_platform=true` (~4 MB) gives the addresses.
- Rate limits: the free tier returned 429 (Retry-After 15–60 s) even at one request per 15 s, so the set is a **checked-in snapshot** (`agent/lazyagent/data/rwa_coingecko.json`, ~21 KB) refreshed by `python -m lazyagent.rwa_snapshot` (~20 paced requests), not fetched on a user's request.
- `NOT_RWA` (curated, per network): infra / oracle / general-L1 tokens CoinGecko files as RWA — LINK (both chains), QNT, INJ, TRAC, RED, DIA, CHR; USAT (USD stablecoin without "usd" in its symbol; others like wstUSDT, cUSDO are dropped by the symbol rule); and asset tokens CoinGecko left out of `tokenized-products` — MPRA (Maya Preferred, ~$58M/day, would rank #2), ACRED and VBILL (funds, both chains). Kept as project tokens: ONDO, PLUME, SYRUP, CFG, RE, RSR, USUAL, DUSK, EPIC, LUMIA, KERNEL, CTC, EDEN, CPOOL, MKR, …
- `PINNED`: XAUt0 on Avalanche `0x2775d5105276781b4b85ba6ea6a6653beed1dd32`, note "tokenized gold — Avalanche showcase" — an asset token, pinned deliberately as the hackathon sponsor showcase; always first.
- Market data: GeckoTerminal `tokens/multi`. Per network we look up `PINNED`, the 15 busiest by CoinGecko volume, then the largest by market cap (≤ 30). Tokens with no DEX pool → `price_usd` null, `buyable: false`; when a token isn't the base of its deepest pool (e.g. RSR in a Curve `ETH+ / eUSD / RSR` pool) the 24h change is null.
- `buyable`: deepest pool ≥ $10,000. Ranking: `PINNED`, then 24h DEX volume, then CoinGecko market cap; top 10.
- Avalanche has essentially no liquid RWA project tokens: KULA ($15k pool) is the only buyable one; LODE, DEXTF, NXRA, OPUL, URQA, MKR.e have no or tiny pools.

| # | Network | Symbol | 24h | 24h volume | Liquidity | DEX | Buyable |
|---|---|---|---|---|---|---|---|
| 1 | Avalanche | XAUt0 (pinned, tokenized gold) | +0.4% | $145,123 | $64,253 | blackhole-v3 | yes |
| 2 | Ethereum | ONDO | -6.8% | $1.18M | $1.75M | uniswap_v3 | yes |
| 3 | Ethereum | DUSK | +11.7% | $634,537 | $328,069 | uniswap-v4-ethereum | yes |
| 4 | Ethereum | CFG | -7.9% | $584,553 | $592,274 | uniswap-v4-ethereum | yes |
| 5 | Ethereum | RSR | — | $543,616 | $1.43M | curve | yes |
| 6 | Ethereum | SYRUP | -12.1% | $438,673 | $1.77M | uniswap-v4-ethereum | yes |
| 7 | Ethereum | USUAL | -5.3% | $154,416 | $656,924 | uniswap-v4-ethereum | yes |
| 8 | Ethereum | EPIC | -19.5% | $121,421 | $45,652 | uniswap-v4-ethereum | yes |
| 9 | Ethereum | IXS | -0.8% | $86,207 | $520,929 | uniswap-v4-ethereum | yes |
| 10 | Ethereum | PLUME | -10.3% | $82,237 | $47,015 | uniswap-v4-ethereum | yes |

Avalanche only (same run): XAUt0 (pinned, buyable), KULA (buyable), then LODE, DEXTF, NXRA, OPUL, URQA, MKR.e (not buyable).
```

- [ ] **Step 3: Commit**

```bash
git add docs/research/2026-10-15-avalanche-trending-tokens.md
git commit -m "docs(research): trending Avalanche memecoins and RWA project tokens"
```

---

### Task 2: Memecoins, shared types, category registry, `parse_args`, `to_json`

**Files:**
- Create: `agent/lazyagent/trending.py`
- Create: `agent/tests/fixtures/geckoterminal_trending.json`, `agent/tests/fixtures/geckoterminal_arena.json`
- Test: `agent/tests/test_trending.py`

**Interfaces:**
- Consumes: `lazyagent.tokens.AVAX_TOKENS`, a list of `Token` whose `.address` is `str | None` and checksummed.
- Produces, in `lazyagent.trending`:
  - Constants: `GT_API`, `GT_NETWORKS = {"ethereum": "eth", "avalanche": "avax"}`, `CATEGORY_NETWORKS`, `TIMEOUT_S = 15`, `TTL_S = 60`, `MIN_LIQUIDITY_USD = 10_000`, `TOP_N = 10`, `GT_BATCH = 30`, `UNAVAILABLE`, `NOT_MEMES`, `EXCLUDED`.
  - `TokenInfo(symbol, name, address)` and `Pool(token, price_usd, volume_24h, change_24h, liquidity_usd, dex, trending: int | None = None)`.
  - `Trending(symbol, name, address, network, price_usd: float | None, volume_24h, change_24h: float | None, liquidity_usd, dex, buyable: bool, note: str | None = None)`.
  - `TrendingError(Exception)`: its message is text for the model.
  - Module-private helpers `_num(value) -> float` and `_rel_id(obj, name) -> str | None`, which Task 3 also uses.
  - `parse_pools(body: dict, trending: bool = False) -> list[Pool]`.
  - `is_memecoin(token: TokenInfo) -> bool`.
  - `rank_memes(pools: list[Pool]) -> list[Trending]`. Every result has `network="avalanche"` and `buyable=True`.
  - `parse_args(args: dict) -> tuple[str, str | None]`. Category defaults to `"meme"` and both arguments are case-insensitive. Raises `TrendingError` on bad input.
  - `to_json(items: list[Trending]) -> str`. Returns `{"source", "note", "tokens": [asdict...]}`.

- [ ] **Step 1: Add the fixtures.** These are real GeckoTerminal responses captured on 2026-10-15, trimmed down.

`agent/tests/fixtures/geckoterminal_trending.json` holds a major (BTC.b), then a memecoin (COQ), in trending order:

```json
{
  "data": [
    {"id": "avax_0x5ca009013f6b898d134b6798b336a4592f3b4af2", "type": "pool", "attributes": {"address": "0x5ca009013f6b898d134b6798b336a4592f3b4af2", "name": "BTC.b / WAVAX 0.05%", "base_token_price_usd": "81343.7253854092", "price_change_percentage": {"h24": "-2.474"}, "volume_usd": {"h24": "5147349.74684319"}, "reserve_in_usd": "3157451.7132"}, "relationships": {"base_token": {"data": {"id": "avax_0x152b9d0fdc40c096757f570a51e494bd4b943e50", "type": "token"}}, "dex": {"data": {"id": "pharaoh-exchange-v3", "type": "dex"}}}},
    {"id": "avax_0x41ab86eecbd110a82ca602d032a461f453066f1e", "type": "pool", "attributes": {"address": "0x41ab86eecbd110a82ca602d032a461f453066f1e", "name": "COQ / WAVAX", "base_token_price_usd": "0.000000121646674452088", "price_change_percentage": {"h24": "-5.1"}, "volume_usd": {"h24": "16937.5461895205"}, "reserve_in_usd": "623823.6468"}, "relationships": {"base_token": {"data": {"id": "avax_0x420fca0121dc28039145009570975747295f2329", "type": "token"}}, "dex": {"data": {"id": "traderjoe", "type": "dex"}}}}
  ],
  "included": [
    {"id": "pharaoh-exchange-v3", "type": "dex", "attributes": {"name": "Pharaoh Exchange V3"}},
    {"id": "avax_0x152b9d0fdc40c096757f570a51e494bd4b943e50", "type": "token", "attributes": {"address": "0x152b9d0fdc40c096757f570a51e494bd4b943e50", "name": "Bitcoin", "symbol": "BTC.b"}},
    {"id": "traderjoe", "type": "dex", "attributes": {"name": "LFJ"}},
    {"id": "avax_0x420fca0121dc28039145009570975747295f2329", "type": "token", "attributes": {"address": "0x420fca0121dc28039145009570975747295f2329", "name": "COQINU", "symbol": "COQ"}}
  ]
}
```

`agent/tests/fixtures/geckoterminal_arena.json` holds one memecoin with at least $10k liquidity (GATOR) and one with only $2,050 (NOCHILL):

```json
{
  "data": [
    {"id": "avax_0x3c5560226ee5861a58707bbf9247c16cf90e0a8c", "type": "pool", "attributes": {"address": "0x3c5560226ee5861a58707bbf9247c16cf90e0a8c", "name": "GATOR / WAVAX", "base_token_price_usd": "0.00000282056862822005", "price_change_percentage": {"h24": "4.946"}, "volume_usd": {"h24": "523.7351283647"}, "reserve_in_usd": "11541.8039"}, "relationships": {"base_token": {"data": {"id": "avax_0x1a31a8fd8bacb64b32dbcdcf5b2215f58baf70c1", "type": "token"}}, "dex": {"data": {"id": "arena-dex", "type": "dex"}}}},
    {"id": "avax_0x92f020fb0ae592bdca43ea4f4386aa3237f6e5d1", "type": "pool", "attributes": {"address": "0x92f020fb0ae592bdca43ea4f4386aa3237f6e5d1", "name": "NOCHILL / WAVAX", "base_token_price_usd": "0.000322432119406396", "price_change_percentage": {"h24": "0"}, "volume_usd": {"h24": "3.0235432146"}, "reserve_in_usd": "2049.9008"}, "relationships": {"base_token": {"data": {"id": "avax_0xacfb898cff266e53278cc0124fc2c7c94c8cb9a5", "type": "token"}}, "dex": {"data": {"id": "arena-dex", "type": "dex"}}}}
  ],
  "included": [
    {"id": "arena-dex", "type": "dex", "attributes": {"name": "Arena DEX"}},
    {"id": "avax_0x1a31a8fd8bacb64b32dbcdcf5b2215f58baf70c1", "type": "token", "attributes": {"address": "0x1a31a8fd8bacb64b32dbcdcf5b2215f58baf70c1", "name": "Gator Dont Play", "symbol": "GATOR"}},
    {"id": "avax_0xacfb898cff266e53278cc0124fc2c7c94c8cb9a5", "type": "token", "attributes": {"address": "0xacfb898cff266e53278cc0124fc2c7c94c8cb9a5", "name": "AVAX HAS NO CHILL", "symbol": "NOCHILL"}}
  ]
}
```

- [ ] **Step 2: Write the failing tests** — `agent/tests/test_trending.py`

```python
import json
from dataclasses import replace
from pathlib import Path

import pytest

from lazyagent.trending import Pool, TokenInfo, Trending, TrendingError, is_memecoin, parse_args, parse_pools, rank_memes, to_json

FIXTURES = Path(__file__).parent / "fixtures"
COQ = "0x420fca0121dc28039145009570975747295f2329"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def pools() -> list[Pool]:
    return parse_pools(load("geckoterminal_trending.json"), trending=True) + parse_pools(load("geckoterminal_arena.json"))


def meme(symbol: str, n: int, liquidity: float = 50_000, volume: float = 1_000, trending: int | None = None) -> Pool:
    return Pool(TokenInfo(symbol, f"{symbol} coin", f"0x{n:040x}"), 0.01, volume, 1.0, liquidity, "LFJ", trending)


def test_parse_pools_reads_token_numbers_and_dex_name():
    btc, coq = parse_pools(load("geckoterminal_trending.json"), trending=True)
    assert coq.token == TokenInfo("COQ", "COQINU", COQ)
    assert (coq.price_usd, coq.volume_24h, coq.change_24h, coq.liquidity_usd) == (0.000000121646674452088, 16937.5461895205, -5.1, 623823.6468)
    assert (coq.dex, coq.trending, btc.trending) == ("LFJ", 1, 0)


def test_parse_pools_without_trending_has_no_position():
    gator, nochill = parse_pools(load("geckoterminal_arena.json"))
    assert (gator.trending, nochill.trending, gator.dex) == (None, None, "Arena DEX")


def test_parse_pools_skips_pools_without_base_token_and_zeroes_missing_numbers():
    body = {
        "data": [
            {"attributes": {"name": "GHOST / WAVAX"}, "relationships": {"base_token": {"data": {"id": "avax_0xdead"}}}},
            {
                "attributes": {"base_token_price_usd": None, "volume_usd": {}, "reserve_in_usd": None},
                "relationships": {"base_token": {"data": {"id": "avax_0x01"}}, "dex": {"data": {"id": "mystery-dex"}}},
            },
        ],
        "included": [{"id": "avax_0x01", "type": "token", "attributes": {"address": "0x01", "symbol": "NEW"}}],
    }
    [p] = parse_pools(body)
    assert p.token == TokenInfo("NEW", "NEW", "0x01")
    assert (p.price_usd, p.volume_24h, p.change_24h, p.liquidity_usd, p.dex) == (0.0, 0.0, 0.0, 0.0, "mystery-dex")


def test_parse_pools_tolerates_an_empty_body():
    assert parse_pools({}) == []


def test_memecoin_filter_on_fixtures():
    assert {p.token.symbol: is_memecoin(p.token) for p in pools()} == {"BTC.b": False, "COQ": True, "GATOR": True, "NOCHILL": True}


def test_memecoin_filter_excludes_curated_protocol_tokens():
    assert not is_memecoin(TokenInfo("JOE", "JoeToken", "0x6e84a6216ea6dacc71ee8e6b0a5b7322eebc0fdd"))


def test_memecoin_filter_matches_registry_addresses_in_any_case():
    assert not is_memecoin(TokenInfo("XYZ", "XYZ", "0x152b9d0FdC40C096757F570A51E494bd4b943E50"))  # BTC.b checksummed
    assert not is_memecoin(TokenInfo("XYZ", "XYZ", "0xB31F66AA3C1E785363F0875A1B74E27B85FD66C7"))  # WAVAX upper-case


def test_memecoin_filter_symbol_and_name_rules():
    def ok(symbol, name="Some Coin"):
        return is_memecoin(TokenInfo(symbol, name, "0x" + "1" * 40))

    assert not ok("avUSD") and not ok("AUSD") and not ok("EURC") and not ok("XAUt0")
    assert not ok("WAVAX") and not ok("sAVAX") and not ok("WBTC") and not ok("WETH.e") and not ok("LINK.e")
    assert not ok("p33", "Pharaoh Liquid Staking Token") and not ok("FOO", "Wrapped Foo") and not ok("BAR", "Bridged Bar")
    assert ok("KET") and ok("NOCHILL", "AVAX HAS NO CHILL")


def test_rank_memes_on_fixtures_drops_majors_and_thin_pools():
    ranked = rank_memes(pools())
    assert [t.symbol for t in ranked] == ["COQ", "GATOR"]  # BTC.b: major; NOCHILL: $2,050 liquidity
    assert ranked[0] == Trending("COQ", "COQINU", COQ, "avalanche", 0.000000121646674452088, 16937.5461895205, -5.1, 623823.6468, "LFJ", True)
    assert ranked[1].dex == "Arena DEX"


def test_rank_memes_keeps_one_entry_per_token_from_its_deepest_pool_and_best_trending_position():
    shallow = meme("DOG", 1, liquidity=20_000, volume=9_000, trending=3)
    deep = replace(shallow, liquidity_usd=900_000, volume_24h=100, dex="Pharaoh Exchange V3", trending=None)
    ranked = rank_memes([meme("CAT", 2, trending=5), deep, shallow])
    assert [t.symbol for t in ranked] == ["DOG", "CAT"]
    assert ranked[0].liquidity_usd == 900_000 and ranked[0].dex == "Pharaoh Exchange V3"


def test_rank_memes_liquidity_threshold_applies_to_the_deepest_pool():
    assert rank_memes([meme("THIN", 1, liquidity=9_999.99)]) == []
    assert [t.symbol for t in rank_memes([meme("EDGE", 1, liquidity=10_000)])] == ["EDGE"]


def test_rank_memes_puts_trending_first_then_volume():
    ranked = rank_memes([meme("A", 1, volume=10), meme("B", 2, volume=500), meme("C", 3, volume=1, trending=4), meme("D", 4, volume=1, trending=0)])
    assert [t.symbol for t in ranked] == ["D", "C", "B", "A"]


def test_rank_memes_caps_at_ten():
    ranked = rank_memes([meme(f"M{i}", i, volume=i) for i in range(1, 16)])
    assert len(ranked) == 10 and ranked[0].symbol == "M15"


def test_parse_args_defaults_and_normalises():
    assert parse_args({}) == ("meme", None)
    assert parse_args({"category": " RWA ", "network": "Ethereum"}) == ("rwa", "ethereum")
    assert parse_args({"category": "meme", "network": "avalanche"}) == ("meme", "avalanche")


def test_parse_args_rejects_unknown_category_and_unsupported_network():
    with pytest.raises(TrendingError, match="^category must be one of: meme, rwa.$"):
        parse_args({"category": "nft"})
    with pytest.raises(TrendingError, match="^meme tokens are only listed on Avalanche.$"):
        parse_args({"category": "meme", "network": "ethereum"})
    with pytest.raises(TrendingError, match="^rwa tokens are only listed on Ethereum and Avalanche.$"):
        parse_args({"category": "rwa", "network": "solana"})


def test_to_json_lists_tokens_for_the_model():
    body = json.loads(to_json(rank_memes(pools())))
    assert body["tokens"][0] == {
        "symbol": "COQ",
        "name": "COQINU",
        "address": COQ,
        "network": "avalanche",
        "price_usd": 0.000000121646674452088,
        "volume_24h": 16937.5461895205,
        "change_24h": -5.1,
        "liquidity_usd": 623823.6468,
        "dex": "LFJ",
        "buyable": True,
        "note": None,
    }
    assert "buyable" in body["note"] and "contract address" in body["note"]
    assert json.loads(to_json([]))["tokens"] == []
```

- [ ] **Step 3: Run to verify they fail**

Run: `uv run --directory agent pytest tests/test_trending.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lazyagent.trending'`.

- [ ] **Step 4: Implement** — create `agent/lazyagent/trending.py`

```python
"""Trending tokens from live mainnet data (read-only): Avalanche memecoins and RWA project tokens on
Ethereum + Avalanche. Research: docs/research/2026-10-15-avalanche-trending-tokens.md.
Adding a category: an entry in CATEGORY_NETWORKS, a fetcher in TrendingTokens, a line in TRENDING_TOOL's description."""

import json
from dataclasses import asdict, dataclass

from .tokens import AVAX_TOKENS

GT_API = "https://api.geckoterminal.com/api/v2/networks"
GT_NETWORKS = {"ethereum": "eth", "avalanche": "avax"}
# category → networks it covers (first is the default when there's only one)
CATEGORY_NETWORKS = {"meme": ("avalanche",), "rwa": ("ethereum", "avalanche")}
TIMEOUT_S = 15
TTL_S = 60
MIN_LIQUIDITY_USD = 10_000
TOP_N = 10
GT_BATCH = 30  # GeckoTerminal tokens/multi accepts at most 30 addresses
UNAVAILABLE = "Couldn't load trending tokens right now."

# --- memecoins (Avalanche) ---

WAVAX = "0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7"
# Protocol / governance tokens that keep showing up in Avalanche trending but aren't memes.
# GeckoTerminal has no reliable meme flag (its categories tag JOE as "joe-biden"), so this is curated.
NOT_MEMES = {
    "0x6e84a6216ea6dacc71ee8e6b0a5b7322eebc0fdd",  # JOE (LFJ)
    "0x13a466998ce03db73abc2d4df3bbd845ed1f28e7",  # PHAR (Pharaoh)
    "0xcd94a87696fac69edae3a70fe5725307ae1c43f6",  # BLACK (Blackhole)
    "0x8729438eb15e2c8b576fcc6aecda6a148776c0f5",  # QI (Benqi)
    "0xff7f8f301f7a706e3cfd3d2275f5dc0b9ee8009b",  # FOLKS (Folks Finance)
    "0xb8d7710f7d8349a506b75dd184f05777c82dad0c",  # ARENA (Arena platform token)
    "0x6b1ecf0c181afff3d7096b26c3d2bc31f55ceab9",  # MUON (Muon Network)
    "0x62d0a8458ed7719fdaf978fe5929c6d342b0bfce",  # BEAM (Beam gaming)
    "0x6985884c4392d348587b19cb9eaaf157f13271cd",  # ZRO (LayerZero)
    "0x26debd39d5ed069770406fca10a0e4f8d2c743eb",  # GUN (Gunz)
    "0x5e0e90e268bc247cc850c789a0db0d5c7621fb59",  # NXPC (Nexpace, bridged)
}
EXCLUDED = {t.address.lower() for t in AVAX_TOKENS if t.address} | {WAVAX} | NOT_MEMES
STABLES = {"DAI", "AUSD", "EURC", "EUROC", "XAUT", "XAUT0", "FRAX", "GHO", "MIM", "JPYC"}
MAJORS = ("AVAX", "BTC", "ETH")  # any symbol containing one: wrapped, bridged or staked majors
NOT_MEME_WORDS = ("staked", "staking", "wrapped", "bridged")


@dataclass(frozen=True)
class TokenInfo:
    symbol: str
    name: str
    address: str


@dataclass(frozen=True)
class Pool:
    token: TokenInfo  # the pool's base token
    price_usd: float
    volume_24h: float
    change_24h: float
    liquidity_usd: float
    dex: str
    trending: int | None = None  # position in GeckoTerminal's trending list; None = not in it


@dataclass(frozen=True)
class Trending:
    symbol: str
    name: str
    address: str
    network: str  # "ethereum" | "avalanche"
    price_usd: float | None  # None = no DEX market
    volume_24h: float
    change_24h: float | None
    liquidity_usd: float  # deepest pool
    dex: str
    buyable: bool  # deepest pool ≥ $10k
    note: str | None = None  # only for pinned entries


class TrendingError(Exception):
    """A message for the model (bad arguments or data unavailable)."""


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _rel_id(obj: dict, name: str) -> str | None:
    return (((obj.get("relationships") or {}).get(name) or {}).get("data") or {}).get("id")


# --- memecoins: pure ---


def parse_pools(body: dict, trending: bool = False) -> list[Pool]:
    """GeckoTerminal pools JSON (requested with include=base_token,dex) → pools. Pools whose
    base token isn't in `included` are skipped; missing numbers read as 0."""
    included = {(i.get("type"), i.get("id")): i.get("attributes") or {} for i in body.get("included") or []}
    pools = []
    for n, p in enumerate(body.get("data") or []):
        attrs = p.get("attributes") or {}
        token = included.get(("token", _rel_id(p, "base_token")))
        if not token or not token.get("address") or not token.get("symbol"):
            continue
        dex_id = _rel_id(p, "dex") or "unknown"
        pools.append(
            Pool(
                token=TokenInfo(token["symbol"], token.get("name") or token["symbol"], token["address"]),
                price_usd=_num(attrs.get("base_token_price_usd")),
                volume_24h=_num((attrs.get("volume_usd") or {}).get("h24")),
                change_24h=_num((attrs.get("price_change_percentage") or {}).get("h24")),
                liquidity_usd=_num(attrs.get("reserve_in_usd")),
                dex=(included.get(("dex", dex_id)) or {}).get("name") or dex_id,
                trending=n if trending else None,
            )
        )
    return pools


def is_memecoin(token: TokenInfo) -> bool:
    if token.address.lower() in EXCLUDED:
        return False
    symbol = token.symbol.upper()
    if "USD" in symbol or symbol in STABLES or symbol.endswith((".E", ".B")):
        return False
    if any(m in symbol for m in MAJORS):
        return False
    return not any(w in token.name.lower() for w in NOT_MEME_WORDS)


def rank_memes(pools: list[Pool]) -> list[Trending]:
    """One entry per memecoin (its highest-liquidity pool), liquidity ≥ $10k,
    trending order first then 24h volume, top 10."""
    best: dict[str, Pool] = {}
    order: dict[str, int] = {}
    for p in pools:
        if not is_memecoin(p.token):
            continue
        key = p.token.address.lower()
        if p.trending is not None:
            order[key] = min(order.get(key, p.trending), p.trending)
        if key not in best or p.liquidity_usd > best[key].liquidity_usd:
            best[key] = p
    kept = [(k, p) for k, p in best.items() if p.liquidity_usd >= MIN_LIQUIDITY_USD]
    kept.sort(key=lambda kp: (order.get(kp[0], float("inf")), -kp[1].volume_24h))
    return [
        Trending(p.token.symbol, p.token.name, p.token.address, "avalanche", p.price_usd, p.volume_24h, p.change_24h, p.liquidity_usd, p.dex, True)
        for _, p in kept[:TOP_N]
    ]


# --- shared ---


def parse_args(args: dict) -> tuple[str, str | None]:
    """Tool arguments → (category, network). Raises TrendingError with text for the model."""
    category = str(args.get("category") or "meme").strip().lower()
    network = str(args["network"]).strip().lower() if args.get("network") else None
    if category not in CATEGORY_NETWORKS:
        raise TrendingError(f"category must be one of: {', '.join(CATEGORY_NETWORKS)}.")
    allowed = CATEGORY_NETWORKS[category]
    if network is not None and network not in allowed:
        raise TrendingError(f"{category} tokens are only listed on {' and '.join(n.capitalize() for n in allowed)}.")
    return category, network


def to_json(items: list[Trending]) -> str:
    return json.dumps(
        {
            "source": "GeckoTerminal, live mainnet",
            "note": "Offer to buy only buyable tokens. Buy with propose_swap: network = the token's network, token_out = its contract address.",
            "tokens": [asdict(t) for t in items],
        }
    )
```

- [ ] **Step 5: Run to verify they pass**

Run: `uv run --directory agent pytest tests/test_trending.py -q`
Expected: PASS (16 tests).

- [ ] **Step 6: Commit**

```bash
git add agent/lazyagent/trending.py agent/tests/test_trending.py agent/tests/fixtures
git commit -m "feat(agent): parse, filter and rank Avalanche trending memecoins"
```

---

### Task 3: RWA project tokens — CoinGecko addresses, candidates, GeckoTerminal token batch, ranking, pinned XAUt0

**Files:**
- Modify: `agent/lazyagent/trending.py` (imports; append the RWA section)
- Create: `agent/tests/fixtures/coingecko_markets.json`, `coingecko_coins_list.json`, `geckoterminal_tokens_avax.json`, `geckoterminal_tokens_eth.json`
- Test: `agent/tests/test_trending_rwa.py`

**Interfaces:**
- Consumes: `Trending`, `GT_NETWORKS`, `GT_BATCH`, `TOP_N`, `MIN_LIQUIDITY_USD`, `_num` and `_rel_id` from Task 2.
- Produces, in `lazyagent.trending`:
  - `PINNED: list[tuple[str, str, str]]` (network, lower-case address, note), `NOT_RWA: set[tuple[str, str]]`, and `RWA_SNAPSHOT: Path` pointing at `lazyagent/data/rwa_coingecko.json`.
  - `RwaCoin(network, address, coingecko_id, market_cap: float, volume_24h: float)`, frozen.
  - `rwa_addresses(markets: list[dict], coin_list: list[dict], asset_ids: set[str]) -> list[RwaCoin]`.
  - `rwa_candidates(coins: list[RwaCoin], network: str) -> list[str]`. Returns at most 30 lower-case addresses, with `PINNED` first.
  - `parse_tokens(body: dict, network: str) -> list[Trending]`. Parses GeckoTerminal `tokens/multi?include=top_pools`.
  - `rank_rwas(items: list[Trending], coins: list[RwaCoin]) -> list[Trending]`. Pinned entries get their `note`.
  - `load_rwa_snapshot(path: Path = RWA_SNAPSHOT) -> list[RwaCoin]`. Reads `{"generated", "source", "coins": [RwaCoin fields...]}`.

- [ ] **Step 1: Add the fixtures.** These are real responses captured on 2026-10-15, trimmed down.

`agent/tests/fixtures/coingecko_markets.json` holds ONDO (a project token) and XAUt0 (an asset token, in `tokenized-products`):

```json
[
  {"id": "ondo-finance", "symbol": "ondo", "name": "Ondo", "market_cap": 2108143509, "total_volume": 228379176},
  {"id": "tether-gold-tokens", "symbol": "xaut0", "name": "Tether Gold Tokens", "market_cap": 113358580, "total_volume": 4999402}
]
```

`agent/tests/fixtures/coingecko_coins_list.json` has the platforms trimmed:

```json
[
  {"id": "ondo-finance", "symbol": "ondo", "name": "Ondo", "platforms": {"ethereum": "0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3"}},
  {"id": "tether-gold-tokens", "symbol": "xaut0", "name": "Tether Gold Tokens", "platforms": {"avalanche": "0x2775d5105276781b4b85ba6ea6a6653beed1dd32", "solana": "AymATz4TCL9sWNEEV9Kvyz45CHVhDZ6kUgjTJPzLpU9P"}}
]
```

`agent/tests/fixtures/geckoterminal_tokens_avax.json` holds XAUt0 with its pool, and NXRA, a project token with no pool:

```json
{
  "data": [
    {"id": "avax_0x2775d5105276781b4b85ba6ea6a6653beed1dd32", "type": "token", "attributes": {"address": "0x2775d5105276781b4b85ba6ea6a6653beed1dd32", "name": "XAUt0", "symbol": "XAUt0", "price_usd": "4151.7951702526", "volume_usd": {"h24": "145093.15533864"}}, "relationships": {"top_pools": {"data": [{"id": "avax_0x259dc723d93da1d82d10ed75f3751cd3d3b6d7fa", "type": "pool"}]}}},
    {"id": "avax_0x644192291cc835a93d6330b24ea5f5fedd0eef9e", "type": "token", "attributes": {"address": "0x644192291cc835a93d6330b24ea5f5fedd0eef9e", "name": "AllianceBlock Nexera Token", "symbol": "NXRA", "price_usd": null, "volume_usd": {"h24": null}}, "relationships": {"top_pools": {"data": []}}}
  ],
  "included": [
    {"id": "avax_0x259dc723d93da1d82d10ed75f3751cd3d3b6d7fa", "type": "pool", "attributes": {"name": "XAUt0 / USDt 0.05%", "reserve_in_usd": "64072.6693", "price_change_percentage": {"h24": "0.241"}}, "relationships": {"base_token": {"data": {"id": "avax_0x2775d5105276781b4b85ba6ea6a6653beed1dd32", "type": "token"}}, "quote_token": {"data": {"id": "avax_0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7", "type": "token"}}, "dex": {"data": {"id": "blackhole-v3", "type": "dex"}}}}
  ]
}
```

`agent/tests/fixtures/geckoterminal_tokens_eth.json` holds ONDO, which is the base token of its pool, and RSR, which is **not** the base token of its deepest pool (a Curve pool):

```json
{
  "data": [
    {"id": "eth_0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3", "type": "token", "attributes": {"address": "0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3", "name": "Ondo", "symbol": "ONDO", "price_usd": "0.4317345948", "volume_usd": {"h24": "1183578.34877635"}}, "relationships": {"top_pools": {"data": [{"id": "eth_0x7b1e5d984a43ee732de195628d20d05cfabc3cc7", "type": "pool"}]}}},
    {"id": "eth_0x320623b8e4ff03373931769a31fc52a4e78b5d70", "type": "token", "attributes": {"address": "0x320623b8e4ff03373931769a31fc52a4e78b5d70", "name": "Reserve Rights", "symbol": "RSR", "price_usd": "0.001970645956", "volume_usd": {"h24": "525898.151530515"}}, "relationships": {"top_pools": {"data": [{"id": "eth_0xdb6925ea42897ca786a045b252d95aa7370f44b4", "type": "pool"}]}}}
  ],
  "included": [
    {"id": "eth_0x7b1e5d984a43ee732de195628d20d05cfabc3cc7", "type": "pool", "attributes": {"name": "ONDO / WETH 0.3%", "reserve_in_usd": "1765680.8565", "price_change_percentage": {"h24": "-7.529"}}, "relationships": {"base_token": {"data": {"id": "eth_0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3", "type": "token"}}, "quote_token": {"data": {"id": "eth_0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "type": "token"}}, "dex": {"data": {"id": "uniswap_v3", "type": "dex"}}}},
    {"id": "eth_0xdb6925ea42897ca786a045b252d95aa7370f44b4", "type": "pool", "attributes": {"name": "ETH+ / eUSD / RSR", "reserve_in_usd": "1435171.8096", "price_change_percentage": {"h24": "-5.615"}}, "relationships": {"base_token": {"data": {"id": "eth_0xe72b141df173b999ae7c1adcbf60cc9833ce56a8", "type": "token"}}, "quote_token": {"data": {"id": "eth_0xa0d69e286b938e21cbf7e51d71f6a4c8918f482f", "type": "token"}}, "dex": {"data": {"id": "curve", "type": "dex"}}}}
  ]
}
```

- [ ] **Step 2: Write the failing tests** in `agent/tests/test_trending_rwa.py`. The last test, `test_shipped_snapshot_...`, will keep failing until Task 5 generates the snapshot.

```python
import json
from pathlib import Path

from lazyagent.trending import (
    GT_BATCH,
    NOT_RWA,
    PINNED,
    RwaCoin,
    Trending,
    load_rwa_snapshot,
    parse_tokens,
    rank_rwas,
    rwa_addresses,
    rwa_candidates,
)

FIXTURES = Path(__file__).parent / "fixtures"
XAUT0 = "0x2775d5105276781b4b85ba6ea6a6653beed1dd32"  # Avalanche, pinned asset token
NXRA = "0x644192291cc835a93d6330b24ea5f5fedd0eef9e"  # Avalanche project token, no pool
ONDO = "0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3"  # Ethereum project token, base of its pool
RSR = "0x320623b8e4ff03373931769a31fc52a4e78b5d70"  # Ethereum project token, not the base of its pool
LINK = "0x514910771af9ca656af840dff83e8264ecf986ca"  # Ethereum, NOT_RWA
NOTE = "tokenized gold — Avalanche showcase"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def coin(network: str, n: int, mcap: float = 0, volume: float = 0) -> RwaCoin:
    return RwaCoin(network, f"0x{n:040x}", f"coin-{n}", mcap, volume)


def item(network: str, address: str, volume: float = 0, liquidity: float = 0) -> Trending:
    return Trending("T", "Token", address, network, None, volume, None, liquidity, "", liquidity >= 10_000)


def test_pinned_is_xaut0_on_avalanche_with_a_note():
    assert PINNED == [("avalanche", XAUT0, NOTE)]


def test_not_rwa_keeps_project_tokens():
    assert ("ethereum", LINK) in NOT_RWA
    assert not {("ethereum", ONDO), ("ethereum", RSR)} & NOT_RWA


def test_rwa_addresses_keeps_project_tokens_and_drops_asset_tokens():
    coins = rwa_addresses(load("coingecko_markets.json"), load("coingecko_coins_list.json"), {"tether-gold-tokens"})
    assert coins == [RwaCoin("ethereum", ONDO, "ondo-finance", 2108143509, 228379176)]


def test_rwa_addresses_maps_every_supported_network_and_skips_others():
    coins = rwa_addresses(load("coingecko_markets.json"), load("coingecko_coins_list.json"), set())
    assert [(c.network, c.coingecko_id) for c in coins] == [("ethereum", "ondo-finance"), ("avalanche", "tether-gold-tokens")]  # Solana ignored


def test_rwa_addresses_drops_usd_stablecoins_and_coins_missing_from_the_list():
    markets = [{"id": "wrapped-staked-usdt", "symbol": "wstusdt"}, {"id": "ghost", "symbol": "ghost"}]
    coin_list = [{"id": "wrapped-staked-usdt", "platforms": {"ethereum": "0x" + "1" * 40}}]
    assert rwa_addresses(markets, coin_list, set()) == []


def test_candidates_pin_first_and_skip_not_rwa():
    coins = [RwaCoin("ethereum", LINK, "chainlink", 9e9, 4e8), RwaCoin("ethereum", ONDO, "ondo-finance", 2e9, 2e8)]
    assert rwa_candidates(coins, "ethereum") == [ONDO]
    assert rwa_candidates(coins, "avalanche") == [XAUT0]


def test_candidates_mix_busiest_and_largest_and_fill_one_batch():
    busy = [coin("ethereum", i, mcap=1, volume=1_000 + i) for i in range(1, 41)]
    big = [coin("ethereum", 100 + i, mcap=1e9 + i, volume=0) for i in range(1, 41)]
    out = rwa_candidates(busy + big, "ethereum")
    assert len(out) == GT_BATCH
    assert out[:15] == [f"0x{i:040x}" for i in range(40, 25, -1)]  # 15 busiest
    assert out[15] == f"0x{140:040x}"  # then the largest by market cap


def test_parse_tokens_pool_and_no_pool():
    xaut0, nxra = parse_tokens(load("geckoterminal_tokens_avax.json"), "avalanche")
    assert xaut0 == Trending("XAUt0", "XAUt0", XAUT0, "avalanche", 4151.7951702526, 145093.15533864, 0.241, 64072.6693, "blackhole-v3", True)
    assert nxra == Trending("NXRA", "AllianceBlock Nexera Token", NXRA, "avalanche", None, 0.0, None, 0.0, "", False)


def test_parse_tokens_change_only_when_token_is_the_pool_base():
    ondo, rsr = parse_tokens(load("geckoterminal_tokens_eth.json"), "ethereum")
    assert (ondo.change_24h, ondo.liquidity_usd, ondo.dex, ondo.buyable) == (-7.529, 1765680.8565, "uniswap_v3", True)
    assert (rsr.address, rsr.change_24h, rsr.price_usd, rsr.dex, rsr.buyable) == (RSR, None, 0.001970645956, "curve", True)


def test_parse_tokens_tolerates_an_empty_body_and_unescapes_names():
    assert parse_tokens({}, "ethereum") == []
    [t] = parse_tokens({"data": [{"id": "x", "attributes": {"address": "0xAB", "symbol": "PRO", "name": "Propy &amp; Co"}}]}, "ethereum")
    assert (t.name, t.address) == ("Propy & Co", "0xab")


def test_rank_rwas_pinned_first_with_note_then_volume_then_market_cap():
    coins = [coin("ethereum", 1, mcap=10), coin("ethereum", 2, mcap=99)]
    items = [
        item("ethereum", f"0x{1:040x}"),
        item("ethereum", ONDO, volume=1e6, liquidity=2e6),
        item("avalanche", XAUT0, volume=1e5, liquidity=6e4),
        item("ethereum", f"0x{2:040x}"),
    ]
    ranked = rank_rwas(items, coins)
    assert [t.address for t in ranked] == [XAUT0, ONDO, f"0x{2:040x}", f"0x{1:040x}"]
    assert ranked[0].note == NOTE and ranked[1].note is None


def test_rank_rwas_keeps_unbuyable_drops_not_rwa_and_duplicates_and_caps_at_ten():
    items = [item("ethereum", LINK, volume=1e9, liquidity=1e7), item("avalanche", NXRA, volume=0.5), item("avalanche", NXRA, volume=0.5)]
    items += [item("ethereum", f"0x{i:040x}", volume=i) for i in range(1, 10)]
    ranked = rank_rwas(items, [])
    assert len(ranked) == 10
    assert LINK not in [t.address for t in ranked]
    assert [t.address for t in ranked].count(NXRA) == 1 and ranked[-1].buyable is False


def test_rank_rwas_with_live_fixtures_on_both_networks():
    items = parse_tokens(load("geckoterminal_tokens_eth.json"), "ethereum") + parse_tokens(load("geckoterminal_tokens_avax.json"), "avalanche")
    assert [t.symbol for t in rank_rwas(items, [])] == ["XAUt0", "ONDO", "RSR", "NXRA"]


def test_load_rwa_snapshot(tmp_path):
    path = tmp_path / "rwa.json"
    path.write_text(json.dumps({"generated": "2026-10-15", "coins": [{"network": "ethereum", "address": ONDO, "coingecko_id": "ondo-finance", "market_cap": 1.0, "volume_24h": 2.0}]}))
    assert load_rwa_snapshot(path) == [RwaCoin("ethereum", ONDO, "ondo-finance", 1.0, 2.0)]


def test_shipped_snapshot_has_project_tokens_not_asset_tokens():
    coins = {(c.network, c.address) for c in load_rwa_snapshot()}
    assert ("ethereum", ONDO) in coins  # project token
    assert ("avalanche", XAUT0) not in coins  # tokenized gold — only shown because it's PINNED
    assert all(a == a.lower() and a.startswith("0x") for _, a in coins)
```

- [ ] **Step 3: Run to verify they fail**

Run: `uv run --directory agent pytest tests/test_trending_rwa.py -q`
Expected: FAIL — `ImportError: cannot import name 'NOT_RWA' from 'lazyagent.trending'`.

- [ ] **Step 4: Implement.** In `agent/lazyagent/trending.py`, replace the imports

```python
import json
from dataclasses import asdict, dataclass
```

with

```python
import html
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
```

and append to the end of the file (two blank lines before it):

```python
# --- RWA project tokens (Ethereum + Avalanche) ---

# Hackathon sponsor showcase: always first in rwa results, in this order (network, lower-case address, note).
# XAUt0 is an asset token, not a project token — pinned deliberately and labelled.
PINNED = [
    ("avalanche", "0x2775d5105276781b4b85ba6ea6a6653beed1dd32", "tokenized gold — Avalanche showcase"),  # XAUt0
]
# In CoinGecko's RWA category, not in any tokenized-asset sub-category, but not RWA projects:
# infra / oracle / general-L1 tokens, a USD stablecoin without "USD" in its symbol, and funds CoinGecko left untagged.
NOT_RWA = {
    ("ethereum", "0x514910771af9ca656af840dff83e8264ecf986ca"),  # LINK
    ("avalanche", "0x5947bb275c521040051d82396192181b413227a3"),  # LINK.e
    ("ethereum", "0x4a220e6096b25eadb88358cb44068a3248254675"),  # QNT
    ("ethereum", "0xe28b3b32b6c345a34ff64674606124dd5aceca30"),  # INJ
    ("ethereum", "0xaa7a9ca87d3694b5755f213b5d04094b8d0f0a6f"),  # TRAC
    ("ethereum", "0xc43c6bfeda065fe2c4c11765bf838789bd0bb5de"),  # RED (RedStone)
    ("ethereum", "0x84ca8bc7997272c7cfb4d0cd3d55cd942b3c9419"),  # DIA
    ("ethereum", "0x8a2279d4a90b6fe1c4b30fa660cc9f926797baa2"),  # CHR (Chromia)
    ("ethereum", "0x07041776f5007aca2a54844f50503a18a72a8b68"),  # USAT (Tether US stablecoin)
    ("ethereum", "0xec1227bfb3e76d7a2a9bca24d9e98f68de8bf808"),  # MPRA (Maya Preferred — tokenized preferred stock)
    ("ethereum", "0x17418038ecf73ba4026c4f428547bf099706f27b"),  # ACRED (Apollo credit fund)
    ("avalanche", "0x7c64925002bfa705834b118a923e9911bee32875"),  # ACRED
    ("ethereum", "0x2255718832bc9fd3be1caf75084f4803da14ff01"),  # VBILL (VanEck treasury fund)
    ("avalanche", "0x7f4546ef315efc65336187fe3765ea779ac90183"),  # VBILL
}
RWA_SNAPSHOT = Path(__file__).parent / "data" / "rwa_coingecko.json"


@dataclass(frozen=True)
class RwaCoin:
    network: str
    address: str  # lower-case
    coingecko_id: str
    market_cap: float
    volume_24h: float  # CoinGecko, all venues — only used to pick which candidates to look up


def _opt(value) -> float | None:
    return None if value is None else _num(value)


# --- RWAs: pure ---


def rwa_addresses(markets: list[dict], coin_list: list[dict], asset_ids: set[str]) -> list[RwaCoin]:
    """CoinGecko RWA-category markets + coins/list?include_platform=true → one RwaCoin per
    (project token, network). Skips coins in a tokenized-asset sub-category (`asset_ids`), USD
    stablecoins (symbol contains "usd") and coins without an EVM address on a supported network."""
    platforms = {c.get("id"): c.get("platforms") or {} for c in coin_list}
    coins = []
    for m in markets:
        if m.get("id") in asset_ids or "usd" in str(m.get("symbol", "")).lower():
            continue
        for network in GT_NETWORKS:
            address = str(platforms.get(m.get("id"), {}).get(network) or "").lower()
            if address.startswith("0x") and len(address) == 42:
                coins.append(RwaCoin(network, address, m["id"], _num(m.get("market_cap")), _num(m.get("total_volume"))))
    return coins


def rwa_candidates(coins: list[RwaCoin], network: str) -> list[str]:
    """Addresses to look up on GeckoTerminal for one network (one batch): PINNED first, then half
    the busiest by CoinGecko volume, then the largest by market cap; NOT_RWA excluded."""
    out = [a for n, a, _ in PINNED if n == network]
    pool = [c for c in coins if c.network == network and (network, c.address) not in NOT_RWA]
    by_volume = sorted(pool, key=lambda c: (-c.volume_24h, -c.market_cap))
    by_mcap = sorted(pool, key=lambda c: (-c.market_cap, -c.volume_24h))
    for c in by_volume[: (GT_BATCH - len(out)) // 2] + by_mcap:
        if len(out) >= GT_BATCH:
            break
        if c.address not in out:
            out.append(c.address)
    return out


def parse_tokens(body: dict, network: str) -> list[Trending]:
    """GeckoTerminal tokens/multi JSON (include=top_pools) → entries. A token with no pool has
    price/change None, 0 volume and liquidity, buyable False. 24h change comes from the deepest
    pool only when the token is that pool's base token."""
    pools = {i.get("id"): i for i in body.get("included") or [] if i.get("type") == "pool"}
    out = []
    for t in body.get("data") or []:
        a = t.get("attributes") or {}
        if not a.get("address"):
            continue
        ids = [p.get("id") for p in ((t.get("relationships") or {}).get("top_pools") or {}).get("data") or []]
        top = [pools[i] for i in ids if i in pools]
        pool = max(top, key=lambda p: _num((p.get("attributes") or {}).get("reserve_in_usd")), default=None)
        liquidity, change, dex = 0.0, None, ""
        if pool:
            pa = pool.get("attributes") or {}
            liquidity = _num(pa.get("reserve_in_usd"))
            dex = _rel_id(pool, "dex") or ""
            if _rel_id(pool, "base_token") == t.get("id"):
                change = _opt((pa.get("price_change_percentage") or {}).get("h24"))
        symbol = a.get("symbol") or "?"
        out.append(
            Trending(
                symbol, html.unescape(a.get("name") or symbol), a["address"].lower(), network,
                _opt(a.get("price_usd")), _num((a.get("volume_usd") or {}).get("h24")), change,
                liquidity, dex, liquidity >= MIN_LIQUIDITY_USD,
            )
        )
    return out


def rank_rwas(items: list[Trending], coins: list[RwaCoin]) -> list[Trending]:
    """PINNED first (in order, with their note), then 24h DEX volume, then CoinGecko market cap;
    NOT_RWA and duplicates dropped; top 10."""
    pin = {(n, a): (i, note) for i, (n, a, note) in enumerate(PINNED)}
    mcap = {(c.network, c.address): c.market_cap for c in coins}
    seen, kept = set(), []
    for t in items:
        key = (t.network, t.address.lower())
        if key in seen or (key in NOT_RWA and key not in pin):
            continue
        seen.add(key)
        kept.append(replace(t, note=pin[key][1]) if key in pin else t)
    kept.sort(
        key=lambda t: (
            pin.get((t.network, t.address.lower()), (len(pin), None))[0],
            -t.volume_24h,
            -mcap.get((t.network, t.address.lower()), 0.0),
        )
    )
    return kept[:TOP_N]


def load_rwa_snapshot(path: Path = RWA_SNAPSHOT) -> list[RwaCoin]:
    body = json.loads(path.read_text())
    return [RwaCoin(**c) for c in body["coins"]]
```

- [ ] **Step 5: Run to verify they pass** (all except the shipped-snapshot test)

Run: `uv run --directory agent pytest tests/test_trending_rwa.py tests/test_trending.py -q --deselect tests/test_trending_rwa.py::test_shipped_snapshot_has_project_tokens_not_asset_tokens`
Expected: PASS (30 tests, 1 deselected).

- [ ] **Step 6: Commit**

```bash
git add agent/lazyagent/trending.py agent/tests/test_trending_rwa.py agent/tests/fixtures
git commit -m "feat(agent): RWA project tokens, candidates and ranking with pinned XAUt0"
```

---

### Task 4: GeckoTerminal source and the 60 s cache with per-category fetchers

**Files:**
- Modify: `agent/lazyagent/trending.py` (imports; append the I/O section)
- Create: `agent/tests/http_stub.py`
- Modify: `agent/tests/fakes.py` (append `FakeTrendingSource`)
- Test: `agent/tests/test_trending_source.py`

**Interfaces:**
- Consumes: everything from Tasks 2–3.
- Produces, in `lazyagent.trending`:
  - `TrendingSource` (a Protocol) with `async meme_pools() -> list[Pool]` and `async tokens(network: str, addresses: list[str]) -> dict`.
  - `GeckoTerminalSource(base: str = GT_API)`. `tokens` sends no request for an empty address list. Failures raise `urllib.error.HTTPError` (429 and other HTTP errors), `OSError` (unreachable) or `ValueError` (non-JSON body).
  - `TrendingTokens(source, rwa_coins: Callable[[], list[RwaCoin]] = load_rwa_snapshot, ttl=TTL_S, clock=time.monotonic)`, with a `.source` attribute and `async fetch(category: str = "meme", network: str | None = None) -> list[Trending]`. It dispatches through `self._fetchers` (one entry per `CATEGORY_NETWORKS` key), caches per (category, network), and lets exceptions propagate without caching them.
  - `TRENDING`: the process-wide `TrendingTokens(GeckoTerminalSource())`.
- Produces, in tests:
  - `http_stub.serve(routes) -> (server, seen_paths)`. Each route maps a path prefix (the longest match wins) to `(status, body_bytes, headers)`, or to a list of those tuples served in turn, with the last one repeating.
  - `fakes.FakeTrendingSource(pools=None, tokens=None)`, with `.pools`, `.token_bodies`, `.calls` (a list of tuples) and `.fail`.

- [ ] **Step 1: Add the test helpers**

Create `agent/tests/http_stub.py`:

```python
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def serve(routes):
    """Local HTTP stand-in: path prefix → (status, body bytes, headers) or a list of those served in turn.
    Returns (server, seen request paths)."""
    seen: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            match = next((k for k in sorted(routes, key=len, reverse=True) if self.path.startswith(k)), None)
            reply = routes.get(match, (404, b"{}", {}))
            if isinstance(reply, list):
                reply = reply.pop(0) if len(reply) > 1 else reply[0]
            status, body, headers = reply
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, seen
```

Append to `agent/tests/fakes.py`:

```python


class FakeTrendingSource:
    """Stands in for GeckoTerminal so tests never hit the network."""

    def __init__(self, pools=None, tokens=None):
        self.pools = pools if pools is not None else []
        self.token_bodies = tokens or {}  # network -> tokens/multi JSON
        self.calls: list[tuple] = []
        self.fail = False

    async def meme_pools(self):
        self.calls.append(("meme_pools",))
        if self.fail:
            raise ConnectionError("HTTP Error 429: Too Many Requests")
        return self.pools

    async def tokens(self, network, addresses):
        self.calls.append(("tokens", network, tuple(addresses)))
        if self.fail:
            raise ConnectionError("HTTP Error 429: Too Many Requests")
        return self.token_bodies.get(network, {})
```

- [ ] **Step 2: Write the failing tests** — `agent/tests/test_trending_source.py`

```python
import json
import urllib.error
from pathlib import Path

import pytest
from fakes import FakeTrendingSource
from http_stub import serve

from lazyagent.trending import PINNED, GeckoTerminalSource, Pool, RwaCoin, TokenInfo, TrendingTokens

FIXTURES = Path(__file__).parent / "fixtures"
COQ_POOL = Pool(TokenInfo("COQ", "COQINU", "0x420fca0121dc28039145009570975747295f2329"), 1.2e-7, 16_937.5, -5.1, 623_823.6, "LFJ", 0)
XAUT0 = PINNED[0][1]
ONDO = "0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3"
RSR = "0x320623b8e4ff03373931769a31fc52a4e78b5d70"


def ok(name: str):
    return (200, (FIXTURES / name).read_bytes(), {})


async def test_meme_pools_fetch_trending_and_arena():
    server, seen = serve({"/avax/trending_pools": ok("geckoterminal_trending.json"), "/avax/dexes/arena-dex/pools": ok("geckoterminal_arena.json")})
    try:
        pools = await GeckoTerminalSource(f"http://127.0.0.1:{server.server_port}").meme_pools()
    finally:
        server.shutdown()
    assert [(p.token.symbol, p.trending) for p in pools] == [("BTC.b", 0), ("COQ", 1), ("GATOR", None), ("NOCHILL", None)]
    assert seen == ["/avax/trending_pools?include=base_token,dex", "/avax/dexes/arena-dex/pools?sort=h24_volume_usd_desc&include=base_token,dex"]


async def test_tokens_batch_url_per_network():
    server, seen = serve({"/eth/tokens/multi/": ok("geckoterminal_tokens_eth.json")})
    try:
        body = await GeckoTerminalSource(f"http://127.0.0.1:{server.server_port}").tokens("ethereum", [ONDO, RSR])
    finally:
        server.shutdown()
    assert len(body["data"]) == 2
    assert seen == [f"/eth/tokens/multi/{ONDO},{RSR}?include=top_pools"]


async def test_tokens_with_no_addresses_makes_no_request():
    assert await GeckoTerminalSource("http://127.0.0.1:1").tokens("avalanche", []) == {}


async def test_source_raises_on_rate_limit():
    server, _ = serve({"/avax/trending_pools": (429, b'{"status":"429","error":"Rate limited"}', {})})
    try:
        with pytest.raises(urllib.error.HTTPError):
            await GeckoTerminalSource(f"http://127.0.0.1:{server.server_port}").meme_pools()
    finally:
        server.shutdown()


async def test_source_raises_on_non_json_body():
    server, _ = serve({"/": (200, b"<html>oops</html>", {})})
    try:
        with pytest.raises(ValueError):
            await GeckoTerminalSource(f"http://127.0.0.1:{server.server_port}").tokens("avalanche", [XAUT0])
    finally:
        server.shutdown()


async def test_source_raises_when_unreachable():
    with pytest.raises(OSError):
        await GeckoTerminalSource("http://127.0.0.1:1").meme_pools()


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def tokens_fixtures() -> dict:
    return {
        "ethereum": json.loads((FIXTURES / "geckoterminal_tokens_eth.json").read_text()),
        "avalanche": json.loads((FIXTURES / "geckoterminal_tokens_avax.json").read_text()),
    }


SNAPSHOT = [RwaCoin("ethereum", ONDO, "ondo-finance", 2e9, 2e8), RwaCoin("ethereum", RSR, "reserve-rights-token", 1e8, 3e7)]


async def test_cache_serves_within_60_seconds_and_refetches_after():
    source, clock = FakeTrendingSource([COQ_POOL]), Clock()
    trending = TrendingTokens(source, lambda: SNAPSHOT, clock=clock)
    first = await trending.fetch()
    clock.t += 59.9
    assert await trending.fetch() == first and len(source.calls) == 1
    clock.t += 0.2
    await trending.fetch()
    assert len(source.calls) == 2


async def test_cache_is_per_category_and_network():
    source = FakeTrendingSource([COQ_POOL], tokens_fixtures())
    trending = TrendingTokens(source, lambda: SNAPSHOT, clock=Clock())
    await trending.fetch("meme")
    await trending.fetch("rwa", "avalanche")
    await trending.fetch("rwa", "avalanche")
    await trending.fetch("rwa")
    assert source.calls == [
        ("meme_pools",),
        ("tokens", "avalanche", (XAUT0,)),
        ("tokens", "ethereum", (ONDO, RSR)),
        ("tokens", "avalanche", (XAUT0,)),
    ]


async def test_rwa_lists_both_networks_with_pinned_first():
    trending = TrendingTokens(FakeTrendingSource(tokens=tokens_fixtures()), lambda: SNAPSHOT, clock=Clock())
    both = await trending.fetch("rwa")
    assert [(t.symbol, t.network) for t in both] == [("XAUt0", "avalanche"), ("ONDO", "ethereum"), ("RSR", "ethereum"), ("NXRA", "avalanche")]
    assert both[0].note == PINNED[0][2]
    eth = await trending.fetch("rwa", "ethereum")
    assert [t.symbol for t in eth] == ["ONDO", "RSR"]


async def test_errors_are_not_cached():
    source, clock = FakeTrendingSource([COQ_POOL]), Clock()
    trending = TrendingTokens(source, lambda: SNAPSHOT, clock=clock)
    source.fail = True
    with pytest.raises(ConnectionError):
        await trending.fetch()
    source.fail = False
    assert [t.symbol for t in await trending.fetch()] == ["COQ"]
    assert len(source.calls) == 2


async def test_an_empty_list_is_cached_too():
    source = FakeTrendingSource([])
    trending = TrendingTokens(source, lambda: SNAPSHOT, clock=Clock())
    assert await trending.fetch() == [] and await trending.fetch() == []
    assert len(source.calls) == 1
```

- [ ] **Step 3: Run to verify they fail**

Run: `uv run --directory agent pytest tests/test_trending_source.py -q`
Expected: FAIL — `ImportError: cannot import name 'GeckoTerminalSource' from 'lazyagent.trending'`.

- [ ] **Step 4: Implement.** In `agent/lazyagent/trending.py`, replace the imports

```python
import html
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
```

with

```python
import asyncio
import html
import json
import time
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Protocol
```

and append to the end of the file (two blank lines before it):

```python
# --- I/O ---


def _get(url: str):
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as res:
        return json.loads(res.read())


class TrendingSource(Protocol):
    async def meme_pools(self) -> list[Pool]: ...
    async def tokens(self, network: str, addresses: list[str]) -> dict: ...


class GeckoTerminalSource:
    def __init__(self, base: str = GT_API):
        self.base = base

    async def meme_pools(self) -> list[Pool]:
        """Trending pools across all Avalanche DEXs, plus Arena DEX's busiest pools (where memecoins graduate to)."""
        trending = await asyncio.to_thread(_get, f"{self.base}/avax/trending_pools?include=base_token,dex")
        arena = await asyncio.to_thread(_get, f"{self.base}/avax/dexes/arena-dex/pools?sort=h24_volume_usd_desc&include=base_token,dex")
        return parse_pools(trending, trending=True) + parse_pools(arena)

    async def tokens(self, network: str, addresses: list[str]) -> dict:
        if not addresses:
            return {}
        url = f"{self.base}/{GT_NETWORKS[network]}/tokens/multi/{','.join(addresses[:GT_BATCH])}?include=top_pools"
        return await asyncio.to_thread(_get, url)


class TrendingTokens:
    """Ranked lists per (category, network), cached for 60 s. Errors propagate and are never cached."""

    def __init__(
        self,
        source: TrendingSource,
        rwa_coins: Callable[[], list[RwaCoin]] = load_rwa_snapshot,
        ttl: float = TTL_S,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.source = source
        self.rwa_coins = rwa_coins
        self.ttl = ttl
        self.clock = clock
        self._cache: dict[tuple[str, str | None], tuple[float, list[Trending]]] = {}
        # one fetcher per CATEGORY_NETWORKS key
        self._fetchers: dict[str, Callable[[str | None], Awaitable[list[Trending]]]] = {"meme": self._memes, "rwa": self._rwas}

    async def fetch(self, category: str = "meme", network: str | None = None) -> list[Trending]:
        key = (category, network)
        now = self.clock()
        hit = self._cache.get(key)
        if hit is not None and now - hit[0] < self.ttl:
            return hit[1]
        items = await self._fetchers[category](network)
        self._cache[key] = (now, items)
        return items

    async def _memes(self, network: str | None) -> list[Trending]:
        return rank_memes(await self.source.meme_pools())

    async def _rwas(self, network: str | None) -> list[Trending]:
        coins = self.rwa_coins()
        items: list[Trending] = []
        for net in [network] if network else CATEGORY_NETWORKS["rwa"]:
            items += parse_tokens(await self.source.tokens(net, rwa_candidates(coins, net)), net)
        return rank_rwas(items, coins)


TRENDING = TrendingTokens(GeckoTerminalSource())
```

- [ ] **Step 5: Run to verify they pass**

Run: `uv run --directory agent pytest tests/test_trending_source.py tests/test_trending.py -q`
Expected: PASS (27 tests).

- [ ] **Step 6: Commit**

```bash
git add agent/lazyagent/trending.py agent/tests/test_trending_source.py agent/tests/http_stub.py agent/tests/fakes.py
git commit -m "feat(agent): GeckoTerminal trending source with a 60 s cache"
```

---

### Task 5: RWA snapshot script and the generated snapshot

**Files:**
- Create: `agent/lazyagent/rwa_snapshot.py`
- Create (generated): `agent/lazyagent/data/rwa_coingecko.json`
- Test: `agent/tests/test_rwa_snapshot.py`, plus the shipped-snapshot test from Task 3

**Interfaces:**
- Consumes: `RWA_SNAPSHOT`, `RwaCoin`, `rwa_addresses` and `load_rwa_snapshot` from Task 3; `http_stub.serve` from Task 4.
- Produces, in `lazyagent.rwa_snapshot`:
  - `RWA_CATEGORY = "real-world-assets-rwa"` and `ASSET_CATEGORIES = ("tokenized-products",)`.
  - `CoinGeckoRwaSource(base=CG_API, sleep=time.sleep, pause=15.0, retries=6, per_page=250)` with:
    - `markets(category) -> list[dict]`: fetches every page, sleeping `pause` after each page.
    - `coin_list() -> list[dict]`.
    - `coins() -> list[RwaCoin]`.

    On a 429 it sleeps for `Retry-After` seconds (60 if the header is missing). After `retries` attempts it re-raises the `HTTPError`.
  - `snapshot_json(coins, generated: str) -> str`: sorted by network, then volume and market cap descending, one coin per line.
  - `main(path=RWA_SNAPSHOT)`, run with `uv run --directory agent python -m lazyagent.rwa_snapshot`.

- [ ] **Step 1: Write the failing tests** — `agent/tests/test_rwa_snapshot.py`

```python
import json
import urllib.error
from pathlib import Path

import pytest
from http_stub import serve

from lazyagent.rwa_snapshot import CoinGeckoRwaSource, snapshot_json
from lazyagent.trending import RwaCoin, load_rwa_snapshot

FIXTURES = Path(__file__).parent / "fixtures"
MARKETS = json.loads((FIXTURES / "coingecko_markets.json").read_text())  # ondo-finance, tether-gold-tokens
RWA = "/coins/markets?vs_currency=usd&category=real-world-assets-rwa"
ASSETS = "/coins/markets?vs_currency=usd&category=tokenized-products"


def body(obj) -> bytes:
    return json.dumps(obj).encode()


def test_pages_both_categories_and_drops_asset_tokens():
    server, seen = serve(
        {
            RWA: [(200, body(MARKETS[:1]), {}), (200, body(MARKETS[1:]), {}), (200, b"[]", {})],
            ASSETS: [(200, body([{"id": "tether-gold-tokens"}]), {}), (200, b"[]", {})],
            "/coins/list": (200, (FIXTURES / "coingecko_coins_list.json").read_bytes(), {}),
        }
    )
    sleeps = []
    try:
        coins = CoinGeckoRwaSource(f"http://127.0.0.1:{server.server_port}", sleep=sleeps.append, per_page=1).coins()
    finally:
        server.shutdown()
    assert seen == [
        f"{RWA}&per_page=1&page=1",
        f"{RWA}&per_page=1&page=2",
        f"{RWA}&per_page=1&page=3",
        f"{ASSETS}&per_page=1&page=1",
        f"{ASSETS}&per_page=1&page=2",
        "/coins/list?include_platform=true",
    ]
    assert [(c.network, c.coingecko_id) for c in coins] == [("ethereum", "ondo-finance")]
    assert sleeps == [15.0] * 5  # after every markets page


def test_waits_out_429_using_retry_after():
    server, _ = serve({"/coins/list": [(429, b"{}", {"Retry-After": "7"}), (200, b"[]", {})]})
    sleeps = []
    try:
        assert CoinGeckoRwaSource(f"http://127.0.0.1:{server.server_port}", sleep=sleeps.append).coin_list() == []
    finally:
        server.shutdown()
    assert sleeps == [7.0]


def test_gives_up_after_the_retries():
    server, _ = serve({"/coins/list": (429, b"{}", {"Retry-After": "1"})})
    try:
        with pytest.raises(urllib.error.HTTPError):
            CoinGeckoRwaSource(f"http://127.0.0.1:{server.server_port}", sleep=lambda s: None, retries=2).coin_list()
    finally:
        server.shutdown()


def test_snapshot_json_round_trips_and_sorts(tmp_path):
    coins = [RwaCoin("ethereum", "0x01", "a", 1.0, 1.0), RwaCoin("avalanche", "0x02", "b", 5.0, 0.0), RwaCoin("avalanche", "0x03", "c", 1.0, 9.0)]
    path = tmp_path / "rwa.json"
    path.write_text(snapshot_json(coins, "2026-10-15"))
    assert json.loads(path.read_text())["generated"] == "2026-10-15"
    assert [c.coingecko_id for c in load_rwa_snapshot(path)] == ["c", "b", "a"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --directory agent pytest tests/test_rwa_snapshot.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lazyagent.rwa_snapshot'`.

- [ ] **Step 3: Implement** — create `agent/lazyagent/rwa_snapshot.py`

```python
"""Refresh the RWA project-token snapshot (lazyagent/data/rwa_coingecko.json) from CoinGecko's free API.

RWA project token = in CoinGecko's `real-world-assets-rwa` category and NOT in `tokenized-products`
("Tokenized Assets" — the umbrella that contains every tokenized stock/ETF/gold/silver/commodity/
treasury/T-bill/money-market/credit sub-category; verified 2026-10-15). Both categories are ~10 pages
and the free tier 429s even at one request every 15 s, so this runs offline (paced, honouring
Retry-After) instead of on a user's request.
Run: uv run --directory agent python -m lazyagent.rwa_snapshot
"""

import datetime
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from .trending import RWA_SNAPSHOT, RwaCoin, rwa_addresses

CG_API = "https://api.coingecko.com/api/v3"
RWA_CATEGORY = "real-world-assets-rwa"
ASSET_CATEGORIES = ("tokenized-products",)
PER_PAGE = 250


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as res:
        return json.loads(res.read())


class CoinGeckoRwaSource:
    def __init__(
        self,
        base: str = CG_API,
        sleep: Callable[[float], None] = time.sleep,
        pause: float = 15.0,
        retries: int = 6,
        per_page: int = PER_PAGE,
    ):
        self.base = base
        self.sleep = sleep
        self.pause = pause
        self.retries = retries
        self.per_page = per_page

    def _fetch(self, url: str):
        for attempt in range(self.retries):
            try:
                return _get_json(url)
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == self.retries - 1:
                    raise
                self.sleep(float(e.headers.get("retry-after") or 60))
        raise RuntimeError("unreachable")

    def markets(self, category: str) -> list[dict]:
        """Every page of coins/markets for one category; pauses between requests."""
        out: list[dict] = []
        page = 1
        while True:
            batch = self._fetch(f"{self.base}/coins/markets?vs_currency=usd&category={category}&per_page={self.per_page}&page={page}")
            out += batch
            self.sleep(self.pause)
            if len(batch) < self.per_page:
                return out
            page += 1

    def coin_list(self) -> list[dict]:
        return self._fetch(f"{self.base}/coins/list?include_platform=true")

    def coins(self) -> list[RwaCoin]:
        markets = self.markets(RWA_CATEGORY)
        asset_ids = {c["id"] for cat in ASSET_CATEGORIES for c in self.markets(cat)}
        return rwa_addresses(markets, self.coin_list(), asset_ids)


def snapshot_json(coins: list[RwaCoin], generated: str) -> str:
    rows = sorted(coins, key=lambda c: (c.network, -c.volume_24h, -c.market_cap, c.address))
    lines = ",\n".join("    " + json.dumps(asdict(c)) for c in rows)
    head = json.dumps(
        {
            "generated": generated,
            "source": f"CoinGecko coins/markets category={RWA_CATEGORY} minus {', '.join(ASSET_CATEGORIES)} (all pages) + coins/list platforms",
        }
    )[:-1]
    return f'{head}, "coins": [\n{lines}\n]}}\n'


def main(path: Path = RWA_SNAPSHOT) -> None:
    coins = CoinGeckoRwaSource().coins()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot_json(coins, datetime.date.today().isoformat()))
    counts = {n: sum(c.network == n for c in coins) for n in sorted({c.network for c in coins})}
    print(f"Wrote {len(coins)} RWA project-token addresses to {path}: {counts}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run --directory agent pytest tests/test_rwa_snapshot.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Generate the snapshot.** This calls CoinGecko live and is paced: about 20 requests, roughly 6–10 minutes including 429 back-offs. Leave it running.

Run: `uv run --directory agent python -m lazyagent.rwa_snapshot`
Expected: `Wrote ~130 RWA project-token addresses to …/agent/lazyagent/data/rwa_coingecko.json: {'avalanche': ~10, 'ethereum': ~117}`. On 2026-10-15 the file had 127 rows and was about 21 KB.
Check: `grep -c '"ondo-finance"' agent/lazyagent/data/rwa_coingecko.json` → `1`; `grep -c tether-gold agent/lazyagent/data/rwa_coingecko.json` → `0`.

- [ ] **Step 6: Run the shipped-snapshot test, then a live smoke check.** The smoke check calls GeckoTerminal twice and is not part of the suite.

Run: `uv run --directory agent pytest tests/test_trending_rwa.py -q`
Expected: PASS (15 tests).

Run: `uv run --directory agent python -c "import asyncio; from lazyagent.trending import TRENDING; [print(t.network, t.symbol, t.volume_24h, t.liquidity_usd, t.dex, t.buyable, t.note) for t in asyncio.run(TRENDING.fetch('rwa'))]"`
Expected: `avalanche XAUt0 … True tokenized gold — Avalanche showcase` first, then Ethereum project tokens. On 2026-10-15 these were ONDO, DUSK, CFG, RSR, SYRUP, USUAL, EPIC, IXS and PLUME. If a clear asset token, infra token or stablecoin shows up, add its (network, address) to `NOT_RWA` and record it in the research note.

- [ ] **Step 7: Commit**

```bash
git add agent/lazyagent/rwa_snapshot.py agent/lazyagent/data/rwa_coingecko.json agent/tests/test_rwa_snapshot.py
git commit -m "feat(agent): CoinGecko RWA project-token snapshot (Ethereum + Avalanche)"
```

---

### Task 6: `list_trending_tokens` tool and prompt line

**Files:**
- Modify: `agent/lazyagent/trending.py` (append the tool layer)
- Modify: `agent/lazyagent/tools.py`: the import, `TOOL_NAMES`, a class attribute and method after `request_test_funds`, and a registration line before `unsupported_action`
- Modify: `agent/lazyagent/prompt.py`: one line, directly above the "Bridging between networks" line
- Modify: `agent/tests/test_tools.py` (`test_mcp_server_and_names`)
- Test: `agent/tests/test_trending_tools.py`

**Interfaces:**
- Consumes: `CATEGORY_NETWORKS`, `GT_NETWORKS`, `UNAVAILABLE`, `TrendingError`, `parse_args`, `to_json`, `TrendingTokens` and `TRENDING` (Tasks 2–4); `FakeTrendingSource`; `ok` and `err` from `tools.py`.
- Produces:
  - `trending.TRENDING_TOOL: tuple[str, str, dict]`, holding the name, description and input schema. Its enums come from `CATEGORY_NETWORKS` and `GT_NETWORKS`.
  - `async trending.trending_reply(trending: TrendingTokens, args: dict) -> str`. Returns JSON text, and raises `TrendingError` for bad arguments or when the fetch fails (with `UNAVAILABLE`).
  - `WalletTools.trending: TrendingTokens`, a class attribute that defaults to `TRENDING`. Tests assign an instance attribute instead.
  - `async WalletTools.list_trending_tokens(args) -> dict`.
  - The MCP tool `list_trending_tokens`, with `"mcp__wallet__list_trending_tokens"` added last in `TOOL_NAMES`.
- **To add a category later** (e.g. `airdrop`), change only `trending.py`: add a `CATEGORY_NETWORKS` entry, a fetcher in `TrendingTokens._fetchers`, and a sentence in the `TRENDING_TOOL` description. Then add a line to `prompt.py`.

- [ ] **Step 1: Write the failing tests** — `agent/tests/test_trending_tools.py`

```python
import json

from fakes import FakeChain, FakeTrendingSource, Outbox

from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.trending import CATEGORY_NETWORKS, TRENDING_TOOL, GeckoTerminalSource, Pool, RwaCoin, TokenInfo, TrendingTokens

COQ = "0x420fca0121dc28039145009570975747295f2329"
ONDO = "0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3"
ONDO_BODY = {"data": [{"id": "eth_x", "attributes": {"address": ONDO, "symbol": "ONDO", "name": "Ondo", "price_usd": "0.43", "volume_usd": {"h24": "1183578.3"}}}]}


def make(source: FakeTrendingSource) -> WalletTools:
    tools = WalletTools(FakeChain(), Outbox(), WalletContext(), Proposals())
    tools.trending = TrendingTokens(source, lambda: [RwaCoin("ethereum", ONDO, "ondo-finance", 2e9, 2e8)])
    return tools


def text(result):
    return result["content"][0]["text"]


async def test_memes_by_default():
    tools = make(FakeTrendingSource([Pool(TokenInfo("COQ", "COQINU", COQ), 1.2e-7, 16_937.5, -5.1, 623_823.6, "LFJ", 0)]))
    result = await tools.list_trending_tokens({})
    assert not result.get("is_error")
    [coq] = json.loads(text(result))["tokens"]
    assert (coq["symbol"], coq["address"], coq["network"], coq["change_24h"], coq["buyable"], coq["note"]) == ("COQ", COQ, "avalanche", -5.1, True, None)


async def test_rwa_with_network():
    source = FakeTrendingSource(tokens={"ethereum": ONDO_BODY})
    result = await make(source).list_trending_tokens({"category": "rwa", "network": "Ethereum"})
    [ondo] = json.loads(text(result))["tokens"]
    assert (ondo["symbol"], ondo["network"], ondo["buyable"]) == ("ONDO", "ethereum", False)  # no pool in this body
    assert source.calls == [("tokens", "ethereum", (ONDO,))]


async def test_works_without_an_active_wallet():
    tools = make(FakeTrendingSource([]))
    assert tools.ctx.address is None
    assert json.loads(text(await tools.list_trending_tokens({})))["tokens"] == []


async def test_bad_arguments_are_errors_without_fetching():
    source = FakeTrendingSource()
    tools = make(source)
    bad = await tools.list_trending_tokens({"category": "nft"})
    assert bad["is_error"] is True and text(bad) == "category must be one of: meme, rwa."
    eth_memes = await tools.list_trending_tokens({"category": "meme", "network": "ethereum"})
    assert text(eth_memes) == "meme tokens are only listed on Avalanche."
    assert source.calls == []


async def test_fetch_failure_is_a_friendly_error():
    source = FakeTrendingSource()
    source.fail = True
    result = await make(source).list_trending_tokens({"category": "rwa"})
    assert result["is_error"] is True and text(result) == "Couldn't load trending tokens right now."


def test_tool_schema_follows_the_category_registry():
    name, _, schema = TRENDING_TOOL
    assert name == "list_trending_tokens"
    assert schema["properties"]["category"]["enum"] == list(CATEGORY_NETWORKS) == ["meme", "rwa"]
    assert schema["properties"]["network"]["enum"] == ["ethereum", "avalanche"]


def test_default_source_is_geckoterminal():
    assert isinstance(WalletTools.trending.source, GeckoTerminalSource)
```

In `agent/tests/test_tools.py`, inside `test_mcp_server_and_names`, add the new name as the last entry:

```python
        "mcp__wallet__request_test_funds",
        "mcp__wallet__list_trending_tokens",
    ]
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --directory agent pytest tests/test_trending_tools.py tests/test_tools.py::test_mcp_server_and_names -q`
Expected: FAIL — `ImportError: cannot import name 'TRENDING_TOOL' from 'lazyagent.trending'`, and the `TOOL_NAMES` assertion fails.

- [ ] **Step 3: Append the tool layer** to the end of `agent/lazyagent/trending.py`, with two blank lines before it:

```python
# --- agent tool ---

TRENDING_TOOL = (
    "list_trending_tokens",
    "Live mainnet token lists (read-only). category 'meme' (default): top trending Avalanche memecoins. "
    "category 'rwa': top RWA project tokens (ONDO, PLUME, SYRUP, …) on Ethereum and Avalanche, with XAUt0 "
    "(tokenized gold) pinned first as the Avalanche showcase. Each token: symbol, name, contract address, "
    "network, USD price, 24h volume, 24h change, liquidity, main DEX, buyable, note.",
    {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": list(CATEGORY_NETWORKS), "description": "Default 'meme'"},
            "network": {"type": "string", "enum": list(GT_NETWORKS), "description": "Only if the user named a network"},
        },
    },
)


async def trending_reply(trending: TrendingTokens, args: dict) -> str:
    """The tool's answer as JSON text. Raises TrendingError with text for the model."""
    category, network = parse_args(args)
    try:
        items = await trending.fetch(category, network)
    except Exception as e:
        raise TrendingError(UNAVAILABLE) from e
    return to_json(items)
```

- [ ] **Step 4: Wire it into `agent/lazyagent/tools.py`.** Make these four small edits and nothing else.

After `from .tokens import find_token`, add:

```python
from .trending import TRENDING, TRENDING_TOOL, TrendingError, TrendingTokens, trending_reply
```

In `TOOL_NAMES`, append the name to the tuple:

```python
    for n in ("get_balances", "resolve_recipient", "propose_transfer", "propose_swap", "unsupported_action", "request_test_funds", "list_trending_tokens")
```

Between the `request_test_funds` and `unsupported_action` methods, insert:

```python
    trending: TrendingTokens = TRENDING  # shared 60 s cache; tests assign their own

    async def list_trending_tokens(self, args: dict) -> dict:
        try:
            return ok(await trending_reply(self.trending, args))
        except TrendingError as e:
            return err(str(e))
```

In `build_mcp_server`, insert this line before the `tool("unsupported_action", ...)` entry:

```python
            tool(*TRENDING_TOOL)(t.list_trending_tokens),
```

- [ ] **Step 5: Add the prompt line.** In `agent/lazyagent/prompt.py`, insert this directly above `- Bridging between networks, schedules, ...`:

```text
- "What's trending", "hot memecoins on Avalanche" → list_trending_tokens (category meme). "RWA tokens", "RWA plays", "real-world-asset projects" → list_trending_tokens with category rwa (network only if the user named one). It's live mainnet data. Summarise the top three or so by symbol with their 24h change in one or two sentences; for RWAs say XAUt0 is tokenized gold pinned as the Avalanche showcase (its note), and say plainly which aren't buyable here. Offer to buy only buyable tokens: call propose_swap with that token's network and token_out set to its contract address, not its symbol. A very new token may not exist on the Sandbox fork yet. If the list is empty or the tool errors, say so plainly.
```

- [ ] **Step 6: Run the agent suite**

Run: `uv run --directory agent pytest -q`
Expected: PASS. Fork tests skip or pass as before, and no test touches GeckoTerminal or CoinGecko.

- [ ] **Step 7: Commit**

```bash
git add agent/lazyagent/trending.py agent/lazyagent/tools.py agent/lazyagent/prompt.py agent/tests/test_tools.py agent/tests/test_trending_tools.py
git commit -m "feat(agent): list_trending_tokens tool (memes, RWA project tokens) and prompt routing"
```

---

### Task 7: Docs, spec deviations, full verification, manual check

**Files:**
- Modify: `CLAUDE.md`, `docs/superpowers/specs/2026-10-15-lazywallet-avax-trending-design.md`

- [ ] **Step 1: Update `CLAUDE.md`.** Under "Wallet app conventions", add this line after the Uniswap v4 bullet:

```markdown
- Trending tokens (`list_trending_tokens`: Avalanche memecoins; RWA project tokens on Ethereum + Avalanche with XAUt0 pinned) come from GeckoTerminal via `agent/lazyagent/trending.py` (read-only, 60 s cache). Categories are a registry (`CATEGORY_NETWORKS`) — a new one is a change to `trending.py` plus a prompt line. RWA project tokens are a CoinGecko snapshot in `agent/lazyagent/data/rwa_coingecko.json` — refresh with `uv run --directory agent python -m lazyagent.rwa_snapshot`. Curated `NOT_MEMES` / `NOT_RWA` lists are explained in `docs/research/2026-10-15-avalanche-trending-tokens.md`.
```

- [ ] **Step 2: Record the planning decisions the spec doesn't cover yet.** Set `Status:` to `Implemented on feat-trending-avax`, then append:

```markdown
## 7. Decisions made while planning

- Asset tokens are excluded via one CoinGecko category, `tokenized-products` ("Tokenized Assets"): verified 2026-10-15 it contains every tokenized-stock/ETF/gold/silver/commodity/treasury/T-bill/money-market/credit/pre-IPO sub-category (their union adds no id).
- `NOT_RWA` also lists MPRA, ACRED and VBILL — asset tokens CoinGecko filed only under RWA (MPRA would otherwise rank #2 on Ethereum). USD stablecoins are dropped by symbol ("usd"), so only USAT needs an entry.
- GeckoTerminal `tokens/multi` takes at most 30 addresses, so per network we look up `PINNED`, the 15 busiest by CoinGecko volume, then the largest by market cap.
- RWA `dex` is GeckoTerminal's dex id (`tokens/multi` can't include dex names); `price_usd` / `change_24h` are `null` when unknown; 24h change is used only when the token is its deepest pool's base token.
- Tool arguments, schema and reply live in `trending.py` (`parse_args`, `TRENDING_TOOL`, `trending_reply`); `tools.py` only registers them. The cache is one process-wide `TrendingTokens` read through a `WalletTools` class attribute, so `WalletTools.__init__`, `Session` and `server.py` are unchanged.
```

- [ ] **Step 3: Full verification**

Run: `pnpm test:py && pnpm build && pnpm lint`
Expected: all PASS.

- [ ] **Step 4: Manual check.** Start `pnpm dev:sandbox`, `pnpm dev:agent` and `pnpm dev`, then open `http://localhost:5174`.

1. Ask "What's trending on Avalanche?" Expect one or two spoken-friendly sentences that name a few memecoins with their 24h change and offer to buy. None of BTC.b, WAVAX, sAVAX, USDC, JOE or PHAR should appear.
2. Ask "What RWA tokens are hot?" Expect XAUt0 first, described as tokenized gold and the Avalanche showcase, then Ethereum project tokens such as ONDO, CFG and SYRUP. No tokenized stocks should appear.
3. Ask "RWA tokens on Avalanche". Expect XAUt0 first, and the rest flagged as not buyable here.
4. Say "Buy 100 USDC of ONDO". The agent should call `propose_swap` with network ethereum and the **contract address** as `token_out`; check the agent log. Until the Kyber branch lands, expect the normal unsupported-token error, explained plainly.
5. Ask the same question again within a minute. It should be served from the cache, with no new GeckoTerminal error in the agent log.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-10-15-lazywallet-avax-trending-design.md
git commit -m "docs: trending memecoins and RWA project tokens"
```

---

## Merge note

The Kyber branch merges first, then this branch rebases onto it. Conflicts are expected only in these places:
- `agent/lazyagent/tools.py`: the import line, the `TOOL_NAMES` tuple, the method inserted before `unsupported_action`, and the `tool(*TRENDING_TOOL)` line.
- `agent/lazyagent/prompt.py`: one line.
- `agent/tests/test_tools.py`: the `TOOL_NAMES` list.
- `agent/tests/fakes.py`: the appended class.
- `CLAUDE.md`: one line.

All of them are additive, so keep both sides. After the rebase, re-run `pnpm test:py` and repeat manual step 4. The buy should now produce a KyberSwap confirm card that shows the ONDO contract address.
