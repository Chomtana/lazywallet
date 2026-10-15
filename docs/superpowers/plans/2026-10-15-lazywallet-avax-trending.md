# LazyWallet — Trending Tokens (Avalanche Memecoins + RWAs) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A read-only agent tool `list_trending_tokens(category, network)` answers "what's trending on Avalanche?" with up to 10 live Avalanche memecoins and "what RWAs can I buy?" with up to 10 real-world-asset tokens on Ethereum and Avalanche (pinned XAUt0 first). Each token has its contract address, network and a `buyable` flag, so the agent can summarise and offer to buy by contract address.

**Architecture:** One new runtime module, `agent/lazyagent/trending.py`. It has pure functions (`parse_pools`, `is_memecoin`, `rank_memes`, `rwa_addresses`, `rwa_candidates`, `parse_tokens`, `rank_rwas`, `check_args`, `to_json`), an injectable `GeckoTerminalSource` (stdlib `urllib` in `asyncio.to_thread`, like `faucet.py`) and a 60 s `TrendingTokens` cache keyed by (category, network). RWA membership (CoinGecko's RWA category mapped to Ethereum/Avalanche addresses) comes from a checked-in snapshot, `agent/lazyagent/data/rwa_coingecko.json`. The offline script `agent/lazyagent/rwa_snapshot.py` refreshes it, pacing CoinGecko's free API. At request time only GeckoTerminal is called. `tools.py` gets one method and one registration and reads the shared cache through a class attribute, so `__init__`, `session.py` and `server.py` are not touched. `prompt.py` gets one line. No UI.

**Tech Stack:** Python 3.12+ (uv, claude-agent-sdk, pytest-asyncio with `asyncio_mode = "auto"`), GeckoTerminal public API v2 (no key), CoinGecko public API v3 (no key, offline snapshot only).

**Spec:** `docs/superpowers/specs/2026-10-15-lazywallet-avax-trending-design.md` (rev. 3)

## Global Constraints

- Branch `feat-trending-avax` in its own worktree, from `main`. The sibling branch (KyberSwap + custom tokens) heavily edits `agent/lazyagent/tools.py` and `prompt.py` and merges first. Limit edits there to:
  - one import line
  - one name in `TOOL_NAMES`
  - one class attribute and one method
  - one `tool(...)` registration
  - one prompt line

  Do not touch `WalletTools.__init__`, `session.py` or `server.py`.
- Networks:
  - Memecoins: Avalanche only.
  - RWAs: Ethereum (CoinGecko platform `ethereum`, GeckoTerminal `eth`) and Avalanche (`avalanche` / `avax`).
  - All data is live **mainnet** and read-only; nothing is signed.
- GeckoTerminal: base `https://api.geckoterminal.com/api/v2/networks`, no key, ~30 req/min, and it 429s after a short burst. Requests (all verified 2026-10-15):
  - `/avax/trending_pools?include=base_token,dex`
  - `/avax/dexes/arena-dex/pools?sort=h24_volume_usd_desc&include=base_token,dex`
  - `/{eth|avax}/tokens/multi/{≤30 comma-separated addresses}?include=top_pools` (more than 30 → HTTP 400 "maximum 30 addresses allowed")
- CoinGecko (snapshot script only):
  - `/api/v3/coins/markets?vs_currency=usd&category=real-world-assets-rwa&per_page=250&page=N` (all pages)
  - `/api/v3/coins/list?include_platform=true`
- HTTP: stdlib `urllib`, no new dependency. Runtime calls go through `asyncio.to_thread` with a 15 s timeout. The snapshot script is synchronous with a 120 s timeout (`coins/list` is ~4 MB).
- Cache: 60 s per (category, network). Errors are never cached.
- Meme filter (spec §2, verbatim):
  - Exclude `AVAX_TOKENS` and WAVAX.
  - Exclude wrapped/bridged/staked tokens: symbol contains AVAX/BTC/ETH, or ends `.e`/`.b`; name contains staked/staking/wrapped/bridged.
  - Exclude stablecoins: symbol contains USD, or is DAI, AUSD, EURC, EUROC, XAUT, XAUT0, FRAX, GHO, MIM or JPYC.
  - Exclude the curated `NOT_MEMES` addresses: JOE, PHAR, BLACK, QI, FOLKS, ARENA, MUON, BEAM, ZRO, GUN, NXPC.
  - Liquidity of the token's deepest pool must be ≥ **$10,000**; anything below is dropped.
- RWA rules:
  - Include only coins in CoinGecko's `real-world-assets-rwa` category that have an Ethereum or Avalanche address.
  - Exclude the curated `NOT_RWA` (network, address) list. It covers LINK on both chains, plus the protocol tokens found during planning.
  - `PINNED = [("avalanche", "0x2775d5105276781b4b85ba6ea6a6653beed1dd32")]` (XAUt0). It always comes first when the network filter includes it, with real market data and the real `buyable` value.
  - `buyable` = deepest pool liquidity ≥ $10,000. Unbuyable RWAs are kept with `buyable: false`.
- Ranking:
  - Memes: trending order first, then 24h volume.
  - RWAs: `PINNED`, then 24h DEX volume, then CoinGecko market cap.
  - Top **10** in both cases.
- `Trending` fields, in order: `symbol, name, address, network, price_usd, volume_24h, change_24h, liquidity_usd, dex, buyable`.
- Tool error text, verbatim:
  - Fetch failure: `Couldn't load trending tokens right now.`
  - Bad category: `category must be 'meme' or 'rwa'.`
  - Bad network: `network must be 'ethereum' or 'avalanche'.`
  - Memes on Ethereum: `Memecoins are Avalanche only.`
- An empty list is a normal result (`tokens: []`). The tool never crashes.
- Buying is out of scope. The prompt tells the model to call `propose_swap` with the token's network and `token_out` = its contract address. Until the Kyber branch lands, that returns the normal unsupported-token error.
- Unit tests never hit the network. They use fixtures (1–2 tokens per case), a local `HTTPServer` and fakes.
- Done = `pnpm test:py`, `pnpm build && pnpm lint` pass.
- Spec deviations decided while planning (recorded in the spec in Task 7):
  - **Snapshot instead of a live 24 h CoinGecko cache.** The RWA category is ~2,470 coins over 10 pages, and CoinGecko's free tier answered 429 (Retry-After 15–60 s) even at one request every 15 s. Building the set on a user's request would take minutes.
  - GeckoTerminal is looked up for at most 30 candidates per network. These are `PINNED`, then the 15 busiest by CoinGecko volume, then the largest by market cap, so zero-volume permissioned funds such as BUIDL still appear.
  - `NOT_RWA` covers more than LINK (ONDO, QNT, INJ, PLUME, …).
  - The RWA `dex` is GeckoTerminal's dex id, because `tokens/multi` can't include dex names; meme `dex` is the display name.
  - RWA `change_24h` and `price_usd` are `null` when unknown.
  - The cache method is named `fetch`, because a method named `list` would shadow the builtin inside the class.
  - `CoinGeckoRwaSource` lives in the offline script `rwa_snapshot.py`, not `trending.py`.

## Review Focus

- **GeckoTerminal 429s after a few quick asks (seen while planning).** The user should hear "Couldn't load trending tokens right now.", the failure must not be cached, and the next ask retries. Tests: Task 4 (`test_source_raises_on_rate_limit`, `test_errors_are_not_cached`) and Task 6 (`test_fetch_failure_is_a_friendly_error`).
- **An RWA with no DEX pool (BUIDL), or whose deepest pool lists it as the quote token (GOOGLon / USDC).** It must still appear with `buyable: false` or a `null` 24h change. It must never show the wrong token's price move. Tests: Task 3 (`test_parse_tokens_avalanche_pool_and_no_pool`, `test_parse_tokens_change_only_when_token_is_the_pool_base`).
- **Ethereum has ~1,170 RWA addresses but the batch endpoint takes 30.** Candidates must include the pinned token, the busiest RWAs and the big permissioned funds, never more than 30. Test: Task 3 (`test_candidates_mix_busiest_and_largest_and_fill_one_batch`, `test_candidates_pin_first_and_skip_not_rwa`).
- **The model passes `network: "ethereum"` for memes, a capitalised network, or a made-up category.** The tool returns a clear error without fetching, and accepts "Avalanche". Tests: Task 2 (`test_check_args`) and Task 6 (`test_bad_arguments_are_errors_without_fetching`, `test_rwa_with_network`).
- **Malformed or partial API data** (base token missing from `included`, `null` numbers, HTML entities such as `S&amp;P` in names). That entry is skipped or reads 0/None, and the rest still render. Tests: Task 2 (`test_parse_pools_skips_pools_without_base_token_and_zeroes_missing_numbers`) and Task 3 (`test_parse_tokens_tolerates_an_empty_body_and_unescapes_names`).

---

## File structure

| File | Responsibility |
|---|---|
| `docs/research/2026-10-15-avalanche-trending-tokens.md` (new) | Sources, filters, rankings, dated sample output for memes and RWAs |
| `agent/lazyagent/trending.py` (new) | Pure: types, meme parse/filter/rank, RWA address/candidates/parse/rank, `check_args`, `to_json`, `load_rwa_snapshot`. I/O: `GeckoTerminalSource`, `TrendingTokens` (60 s cache), `TRENDING` |
| `agent/lazyagent/rwa_snapshot.py` (new) | Offline: `CoinGeckoRwaSource` (paged, Retry-After), `snapshot_json`, `main()` |
| `agent/lazyagent/data/rwa_coingecko.json` (new, generated) | RWA (network, address, CoinGecko id, market cap, volume) snapshot |
| `agent/tests/fixtures/*.json` (new) | Real responses captured 2026-10-15, trimmed to 1–2 tokens |
| `agent/tests/http_stub.py` (new) | Local HTTP stand-in for GeckoTerminal / CoinGecko |
| `agent/tests/test_trending.py`, `test_trending_rwa.py`, `test_trending_source.py`, `test_rwa_snapshot.py`, `test_trending_tools.py` (new) | Tests |
| `agent/tests/fakes.py` | `FakeTrendingSource` (appended) |
| `agent/lazyagent/tools.py`, `prompt.py`, `agent/tests/test_tools.py` | Tool registration, one prompt line, `TOOL_NAMES` |
| `CLAUDE.md`, spec | One convention line; planning deviations |

---

### Task 1: Research note — sources, filters, rankings (memes + RWAs)

**Files:**
- Create: `docs/research/2026-10-15-avalanche-trending-tokens.md`

**Interfaces:**
- Consumes: nothing.
- Produces: the decisions that Tasks 2–6 implement. If your spot-checks contradict them (for example, GeckoTerminal now needs a key, or `tokens/multi` no longer returns `top_pools`), **stop and report** instead of continuing.

- [ ] **Step 1: Re-run the spot-checks.** Space them out: both APIs rate-limit bursts. A 429 just means wait 30–60 s.

```bash
curl -s 'https://api.geckoterminal.com/api/v2/networks/avax/trending_pools?include=base_token,dex' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(p['attributes']['name'], '|', p['relationships']['dex']['data']['id'], '|', p['attributes']['reserve_in_usd'], '|', p['attributes']['volume_usd']['h24']) for p in d['data']]"
curl -s 'https://api.geckoterminal.com/api/v2/networks/avax/dexes/arena-dex/pools?sort=h24_volume_usd_desc&include=base_token,dex' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(p['attributes']['name'], '|', p['attributes']['reserve_in_usd']) for p in d['data'][:10]]"
curl -s 'https://api.geckoterminal.com/api/v2/networks/avax/tokens/multi/0x2775d5105276781b4b85ba6ea6a6653beed1dd32,0x53fc82f14f009009b440a706e31c9021e1196a2f?include=top_pools' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(t['attributes']['symbol'], t['attributes']['price_usd'], t['attributes']['volume_usd'], len(t['relationships']['top_pools']['data'])) for t in d['data']]; print([i['type'] for i in d.get('included',[])])"
curl -s 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&category=real-world-assets-rwa&per_page=250&page=1' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d), d[0]['id'])"
curl -s 'https://api.dexscreener.com/latest/dex/tokens/0x420fca0121dc28039145009570975747295f2329' \
  | python3 -c "import json,sys; p=json.load(sys.stdin)['pairs'][0]; print(p['dexId'], p['priceUsd'], p['volume']['h24'], p['liquidity']['usd'])"
curl -s -m 10 -o /dev/null -w '%{http_code}\n' 'https://api.lfj.gg/v1/pools/avalanche?orderBy=volume&pageSize=3'
```

Expected (as of 2026-10-15):
- The trending list is mostly majors and protocol tokens (BTC.b, PHAR, JOE, sAVAX, USDC.e…); COQ is the only obvious meme.
- Arena DEX pools are small memecoins (AVXTO, GATOR, WOLFI…).
- `tokens/multi`: XAUt0 has a price, a volume and 1 top pool; BUIDL has `null` price and no pools; `included` holds `pool` objects.
- CoinGecko returns 250 coins (page 1 of ~10).
- DexScreener returns COQ on `traderjoe`.
- The LFJ request times out (it needs a key).

- [ ] **Step 2: Write the note** at `docs/research/2026-10-15-avalanche-trending-tokens.md` with this content. Keep the date. If your Step 1 run differs, update the sample tables.

```markdown
# Trending tokens — Avalanche memecoins and RWAs (Ethereum + Avalanche)

Date: 2026-10-15. Feeds `agent/lazyagent/trending.py` (`list_trending_tokens`) and `agent/lazyagent/rwa_snapshot.py`.

## Market data sources

| | GeckoTerminal | DexScreener | LFJ / Arena |
|---|---|---|---|
| Key | None | None | LFJ API timed out without a key; no public Arena API found |
| Rate limit | ~30 req/min (429 after a short burst) | 300/min pairs & tokens, 60/min profiles & boosts | — |
| Coverage | All DEXs on `avax` (incl. `arena-dex`, LFJ v1/v2.1/v2.2, Pharaoh, Blackhole, Pangolin, Uniswap) and `eth` | All DEXs (Arena as `arenatrade`) | Own venue only |
| Trending ranking | `/networks/avax/trending_pools`; `/dexes/{dex}/pools?sort=h24_volume_usd_desc` | None (only paid boosts, 0 Avalanche entries) | — |
| Token batch | `/networks/{net}/tokens/multi/{≤30 addresses}?include=top_pools` → price, 24h volume, deepest pool (reserve, 24h change, dex id) | `/tokens/v1/{chain}/{addresses}` | — |
| Fields | symbol, name, address, price, 24h volume, 24h change, liquidity, DEX | same | — |

**Decision: GeckoTerminal** for all market data: it is the only keyless source with a trending ranking and a batch token lookup, and covers Arena. DexScreener is the fallback for per-token lookups.

## Memecoins (Avalanche)

- Candidates: `trending_pools` page 1 (20 pools; mostly majors and protocol tokens — today only COQ is a meme) **plus** Arena DEX's top pools by 24h volume (where Avalanche memecoins graduate). Each pool's base token only.
- Filter: no reliable meme flag exists — GeckoTerminal token categories are per-request and wrong (JOE → `defi`, `joe-biden`; COQ has no "meme"), CoinGecko has no Avalanche-meme category. Rules: exclude `AVAX_TOKENS` + WAVAX; symbol contains USD or is DAI/AUSD/EURC/EUROC/XAUT/XAUT0/FRAX/GHO/MIM/JPYC; symbol contains AVAX/BTC/ETH or ends `.e`/`.b`; name contains staked/staking/wrapped/bridged; curated `NOT_MEMES` (JOE, PHAR, BLACK, QI, FOLKS, ARENA, MUON, BEAM, ZRO, GUN, NXPC); deepest pool ≥ $10,000.
- Ranking: one entry per token (deepest pool); trending order first, then 24h volume; top 10.

| # | Symbol | 24h | Volume 24h | Liquidity | DEX |
|---|---|---|---|---|---|
| 1 | COQ | -5.1% | $16,938 | $621,870 | LFJ |
| 2 | AVXTO | +9.6% | $597 | $15,523 | Arena DEX |
| 3 | GATOR | +4.9% | $524 | $11,542 | Arena DEX |
| 4 | WOLFI | -3.6% | $351 | $25,999 | Arena DEX |
| 5 | SUPER | -4.5% | $138 | $18,089 | Arena DEX |

## RWAs (Ethereum + Avalanche)

- Membership: CoinGecko free API. `coins/markets?vs_currency=usd&category=real-world-assets-rwa&per_page=250&page=N` → **2,466 coins over 10 pages**; `coins/list?include_platform=true` (~4 MB) → `platforms.ethereum` / `platforms.avalanche`. Result: **1,167 Ethereum + 290 Avalanche** addresses (Avalanche is mostly Dinari dShares, plus XAUt0, BUIDL, ACRED, JTRSY, JAAA, VBILL, Backed bTokens).
- Rate limits: the free tier returned 429 with Retry-After 15–60 s even at one request per 15 s, so the set is a **checked-in snapshot** (`agent/lazyagent/data/rwa_coingecko.json`) refreshed by `python -m lazyagent.rwa_snapshot` (paced, honours Retry-After), not fetched on a user's request.
- Sub-categories: `tokenized-gold` adds `gram-gold`, `tokenized-commodities` adds `gram-gold`/`gram-silver`, `tokenized-exchange-traded-funds-etfs` adds ~34 more Dinari ETFs on Avalanche, `rwa-protocol` adds `maker`/`lode-token` (protocol tokens). `tokenized-stock`, `tokenized-treasuries`, `tokenized-money-market-fund-mmfs`, `tokenized-credit`, `real-estate`, `ondo-tokenized-assets`, `xstocks-ecosystem`, `bstocks-ecosystem` add nothing on Avalanche. Not added: the main category already has the liquid ones, and every extra category costs more rate-limited calls.
- `NOT_RWA` (curated, per network): LINK (both), MKR (both), DEXTF (Avalanche); on Ethereum ONDO, QNT, INJ, PLUME, RSR, DUSK, EPIC, TRAC, CFG, SYRUP, LUMIA, RED, CHR, DIA, KERNEL, CTC, USUAL, CPOOL, EDEN (protocol / oracle / L1 tokens filed under RWA) and USAT (plain stablecoin).
- `PINNED`: XAUt0 on Avalanche `0x2775d5105276781b4b85ba6ea6a6653beed1dd32` (sponsor showcase), always first.
- Market data: GeckoTerminal `tokens/multi` (max 30 addresses — 31 returns HTTP 400). Per network we look up `PINNED`, the 15 busiest by CoinGecko volume, then the largest by market cap (so zero-volume permissioned funds still appear). Permissioned funds (BUIDL, ACRED, JTRSY, JAAA, VBILL, SECZ, Dinari dShares) have no DEX pool → `price_usd` null, `buyable: false`. When a token is the quote side of its deepest pool (e.g. `USDC / GOOGLon`) the 24h change is null.
- `buyable`: deepest pool ≥ $10,000. Ranking: `PINNED`, then 24h DEX volume, then CoinGecko market cap; top 10.

| # | Network | Symbol | 24h volume | Liquidity | DEX | Buyable |
|---|---|---|---|---|---|---|
| 1 | Avalanche | XAUt0 | $146,540 | $64,182 | blackhole-v3 | yes |
| 2 | Ethereum | XAUt | $18.4M | $4.55M | uniswap_v3 | yes |
| 3 | Ethereum | PAXG | $11.4M | $5.79M | uniswap_v3 | yes |
| 4 | Ethereum | GOOGLon | $15,445 | $53,934 | uniswap_v3 | yes |
| 5 | Ethereum | USDY | $7,840 | $16,937 | uniswap-v4-ethereum | yes |
| 6 | Ethereum | spcxx | $2,487 | $9,732 | uniswap-v4-ethereum | no |

Avalanche only (same run): XAUt0 (buyable), KULA (buyable, $15k), then BUIDL, JAAA, JTRSY, ACRED, VBILL, SECZ, bCSPX, bIB01 (no DEX pool, not buyable).
```

- [ ] **Step 3: Commit**

```bash
git add docs/research/2026-10-15-avalanche-trending-tokens.md
git commit -m "docs(research): trending Avalanche memecoins and RWAs on Ethereum + Avalanche"
```

---

### Task 2: Memecoins — parse, filter, rank; shared types, `check_args`, `to_json`

**Files:**
- Create: `agent/lazyagent/trending.py`
- Create: `agent/tests/fixtures/geckoterminal_trending.json`, `agent/tests/fixtures/geckoterminal_arena.json`
- Test: `agent/tests/test_trending.py`

**Interfaces:**
- Consumes: `lazyagent.tokens.AVAX_TOKENS` (a list of `Token` with `.address: str | None`, checksummed).
- Produces, in `lazyagent.trending`:
  - Constants: `GT_API`, `GT_NETWORKS = {"ethereum": "eth", "avalanche": "avax"}`, `TIMEOUT_S = 15`, `TTL_S = 60`, `MIN_LIQUIDITY_USD = 10_000`, `TOP_N = 10`, `GT_BATCH = 30`, `UNAVAILABLE`, `NOT_MEMES`, `EXCLUDED`.
  - `TokenInfo(symbol, name, address)` and `Pool(token, price_usd, volume_24h, change_24h, liquidity_usd, dex, trending: int | None = None)`.
  - `Trending(symbol, name, address, network, price_usd: float | None, volume_24h, change_24h: float | None, liquidity_usd, dex, buyable: bool)`.
  - `_num(value) -> float` and `_rel_id(obj, name) -> str | None` (module-private helpers, also used by Task 3).
  - `parse_pools(body: dict, trending: bool = False) -> list[Pool]`.
  - `is_memecoin(token: TokenInfo) -> bool`.
  - `rank_memes(pools: list[Pool]) -> list[Trending]`. Memes always have `network="avalanche"` and `buyable=True`.
  - `check_args(category: str, network: str | None) -> str | None`.
  - `to_json(items: list[Trending]) -> str`, returning `{"source", "note", "tokens": [asdict...]}`.

- [ ] **Step 1: Add the fixtures.** These are real GeckoTerminal responses captured 2026-10-15 and trimmed.

`agent/tests/fixtures/geckoterminal_trending.json` (a major, BTC.b, then a meme, COQ, in trending order):

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

`agent/tests/fixtures/geckoterminal_arena.json` (a meme with ≥ $10k liquidity, GATOR, and a meme with $2,050, NOCHILL):

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

- [ ] **Step 2: Write the failing tests** in `agent/tests/test_trending.py`

```python
import json
from dataclasses import replace
from pathlib import Path

from lazyagent.trending import Pool, TokenInfo, Trending, check_args, is_memecoin, parse_pools, rank_memes, to_json

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


def test_check_args():
    assert check_args("meme", None) is None and check_args("meme", "avalanche") is None
    assert check_args("rwa", None) is None and check_args("rwa", "ethereum") is None
    assert check_args("nft", None) == "category must be 'meme' or 'rwa'."
    assert check_args("rwa", "solana") == "network must be 'ethereum' or 'avalanche'."
    assert check_args("meme", "ethereum") == "Memecoins are Avalanche only."


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
    }
    assert "buyable" in body["note"] and "contract address" in body["note"]
    assert json.loads(to_json([]))["tokens"] == []
```

- [ ] **Step 3: Run to verify they fail**

Run: `uv run --directory agent pytest tests/test_trending.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lazyagent.trending'`.

- [ ] **Step 4: Implement.** Create `agent/lazyagent/trending.py`:

```python
"""Trending tokens from live mainnet data (read-only): Avalanche memecoins and RWAs on Ethereum + Avalanche.
Research: docs/research/2026-10-15-avalanche-trending-tokens.md."""

import json
from dataclasses import asdict, dataclass

from .tokens import AVAX_TOKENS

GT_API = "https://api.geckoterminal.com/api/v2/networks"
GT_NETWORKS = {"ethereum": "eth", "avalanche": "avax"}
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


def check_args(category: str, network: str | None) -> str | None:
    """Error text for bad tool arguments, else None."""
    if category not in ("meme", "rwa"):
        return "category must be 'meme' or 'rwa'."
    if network is not None and network not in GT_NETWORKS:
        return "network must be 'ethereum' or 'avalanche'."
    if category == "meme" and network not in (None, "avalanche"):
        return "Memecoins are Avalanche only."
    return None


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
Expected: PASS (15 tests).

- [ ] **Step 6: Commit**

```bash
git add agent/lazyagent/trending.py agent/tests/test_trending.py agent/tests/fixtures
git commit -m "feat(agent): parse, filter and rank Avalanche trending memecoins"
```

---

### Task 3: RWAs — CoinGecko addresses, candidates, GeckoTerminal token batch, ranking, pinned

**Files:**
- Modify: `agent/lazyagent/trending.py` (imports; append the RWA section)
- Create: `agent/tests/fixtures/coingecko_markets.json`, `coingecko_coins_list.json`, `geckoterminal_tokens_avax.json`, `geckoterminal_tokens_eth.json`
- Test: `agent/tests/test_trending_rwa.py`

**Interfaces:**
- Consumes: `Trending`, `GT_NETWORKS`, `GT_BATCH`, `TOP_N`, `MIN_LIQUIDITY_USD`, `_num`, `_rel_id` from Task 2.
- Produces, in `lazyagent.trending`:
  - `PINNED: list[tuple[str, str]]` (network, lower-case address), `NOT_RWA: set[tuple[str, str]]`, `RWA_SNAPSHOT: Path` (`lazyagent/data/rwa_coingecko.json`).
  - `RwaCoin(network, address, coingecko_id, market_cap: float, volume_24h: float)` (frozen).
  - `rwa_addresses(markets: list[dict], coin_list: list[dict]) -> list[RwaCoin]`.
  - `rwa_candidates(coins: list[RwaCoin], network: str) -> list[str]`, returning at most 30 lower-case addresses with `PINNED` first.
  - `parse_tokens(body: dict, network: str) -> list[Trending]` (GeckoTerminal `tokens/multi?include=top_pools`).
  - `rank_rwas(items: list[Trending], coins: list[RwaCoin]) -> list[Trending]`.
  - `load_rwa_snapshot(path: Path = RWA_SNAPSHOT) -> list[RwaCoin]`, reading `{"generated", "source", "coins": [RwaCoin fields...]}`.

- [ ] **Step 1: Add the fixtures.** These are real responses captured 2026-10-15 and trimmed.

`agent/tests/fixtures/coingecko_markets.json` (LINK, which is in `NOT_RWA`, and XAUt0, which is pinned):

```json
[
  {"id": "chainlink", "symbol": "link", "name": "Chainlink", "market_cap": 9261003402, "total_volume": 380766175},
  {"id": "tether-gold-tokens", "symbol": "xaut0", "name": "Tether Gold Tokens", "market_cap": 113340161, "total_volume": 5076061}
]
```

`agent/tests/fixtures/coingecko_coins_list.json` (platforms trimmed; pax-gold is not in the markets fixture):

```json
[
  {"id": "chainlink", "symbol": "link", "name": "Chainlink", "platforms": {"ethereum": "0x514910771af9ca656af840dff83e8264ecf986ca", "solana": "LinkhB3afbBKb2EQQu7s7umdZceV3wcvAUJhQAfQ23L", "avalanche": "0x5947bb275c521040051d82396192181b413227a3"}},
  {"id": "tether-gold-tokens", "symbol": "xaut0", "name": "Tether Gold Tokens", "platforms": {"avalanche": "0x2775d5105276781b4b85ba6ea6a6653beed1dd32", "solana": "AymATz4TCL9sWNEEV9Kvyz45CHVhDZ6kUgjTJPzLpU9P"}},
  {"id": "pax-gold", "symbol": "paxg", "name": "PAX Gold", "platforms": {"ethereum": "0x45804880de22913dafe09f4980848ece6ecbaf78"}}
]
```

`agent/tests/fixtures/geckoterminal_tokens_avax.json` (XAUt0 with its pool; BUIDL, a permissioned fund with no pool):

```json
{
  "data": [
    {"id": "avax_0x2775d5105276781b4b85ba6ea6a6653beed1dd32", "type": "token", "attributes": {"address": "0x2775d5105276781b4b85ba6ea6a6653beed1dd32", "name": "XAUt0", "symbol": "XAUt0", "price_usd": "4152.3385911372", "volume_usd": {"h24": "146051.686719744"}}, "relationships": {"top_pools": {"data": [{"id": "avax_0x259dc723d93da1d82d10ed75f3751cd3d3b6d7fa", "type": "pool"}]}}},
    {"id": "avax_0x53fc82f14f009009b440a706e31c9021e1196a2f", "type": "token", "attributes": {"address": "0x53fc82f14f009009b440a706e31c9021e1196a2f", "name": "BlackRock USD Institutional Digital Liquidity Fund", "symbol": "buidl", "price_usd": null, "volume_usd": {"h24": null}}, "relationships": {"top_pools": {"data": []}}}
  ],
  "included": [
    {"id": "avax_0x259dc723d93da1d82d10ed75f3751cd3d3b6d7fa", "type": "pool", "attributes": {"name": "XAUt0 / USDt 0.05%", "reserve_in_usd": "64106.9781", "price_change_percentage": {"h24": "-0.129"}}, "relationships": {"base_token": {"data": {"id": "avax_0x2775d5105276781b4b85ba6ea6a6653beed1dd32", "type": "token"}}, "quote_token": {"data": {"id": "avax_0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7", "type": "token"}}, "dex": {"data": {"id": "blackhole-v3", "type": "dex"}}}}
  ]
}
```

`agent/tests/fixtures/geckoterminal_tokens_eth.json` (XAUt as the base of its pool; GOOGLon as the *quote* of its pool):

```json
{
  "data": [
    {"id": "eth_0x68749665ff8d2d112fa859aa293f07a622782f38", "type": "token", "attributes": {"address": "0x68749665ff8d2d112fa859aa293f07a622782f38", "name": "Tether Gold", "symbol": "XAUt", "price_usd": "4158.0924087181", "volume_usd": {"h24": "18378541.0360716"}}, "relationships": {"top_pools": {"data": [{"id": "eth_0x6546055f46e866a4b9a4a13e81273e3152bae5da", "type": "pool"}]}}},
    {"id": "eth_0xba47214edd2bb43099611b208f75e4b42fdcfedc", "type": "token", "attributes": {"address": "0xba47214edd2bb43099611b208f75e4b42fdcfedc", "name": "Alphabet Class A (Ondo Tokenized)", "symbol": "GOOGLon", "price_usd": "340.8676113819", "volume_usd": {"h24": "15444.8733816736"}}, "relationships": {"top_pools": {"data": [{"id": "eth_0x39fcb1935f6ccb0a106d05eb928205c59646af57", "type": "pool"}]}}}
  ],
  "included": [
    {"id": "eth_0x6546055f46e866a4b9a4a13e81273e3152bae5da", "type": "pool", "attributes": {"name": "XAUt / USDT 0.05%", "reserve_in_usd": "4573467.4966", "price_change_percentage": {"h24": "0.17"}}, "relationships": {"base_token": {"data": {"id": "eth_0x68749665ff8d2d112fa859aa293f07a622782f38", "type": "token"}}, "quote_token": {"data": {"id": "eth_0xdac17f958d2ee523a2206206994597c13d831ec7", "type": "token"}}, "dex": {"data": {"id": "uniswap_v3", "type": "dex"}}}},
    {"id": "eth_0x39fcb1935f6ccb0a106d05eb928205c59646af57", "type": "pool", "attributes": {"name": "USDC / GOOGLon 1%", "reserve_in_usd": "53933.5668", "price_change_percentage": {"h24": "-5.01"}}, "relationships": {"base_token": {"data": {"id": "eth_0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "type": "token"}}, "quote_token": {"data": {"id": "eth_0xba47214edd2bb43099611b208f75e4b42fdcfedc", "type": "token"}}, "dex": {"data": {"id": "uniswap_v3", "type": "dex"}}}}
  ]
}
```

- [ ] **Step 2: Write the failing tests** in `agent/tests/test_trending_rwa.py`. The last test, `test_shipped_snapshot_...`, stays failing until Task 5 generates the snapshot.

```python
import json
from pathlib import Path

from lazyagent.trending import (
    GT_BATCH,
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
XAUT0 = "0x2775d5105276781b4b85ba6ea6a6653beed1dd32"  # Avalanche, pinned
BUIDL = "0x53fc82f14f009009b440a706e31c9021e1196a2f"  # Avalanche, permissioned, no pool
XAUT = "0x68749665ff8d2d112fa859aa293f07a622782f38"  # Ethereum
GOOGLON = "0xba47214edd2bb43099611b208f75e4b42fdcfedc"  # Ethereum, quote side of its top pool
LINK_ETH = "0x514910771af9ca656af840dff83e8264ecf986ca"  # NOT_RWA
LINK_AVAX = "0x5947bb275c521040051d82396192181b413227a3"  # NOT_RWA


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def coin(network: str, n: int, mcap: float = 0, volume: float = 0) -> RwaCoin:
    return RwaCoin(network, f"0x{n:040x}", f"coin-{n}", mcap, volume)


def item(network: str, address: str, volume: float = 0, liquidity: float = 0) -> Trending:
    return Trending("T", "Token", address, network, None, volume, None, liquidity, "", liquidity >= 10_000)


def test_pinned_is_xaut0_on_avalanche():
    assert PINNED == [("avalanche", XAUT0)]


def test_rwa_addresses_maps_both_networks_and_skips_others():
    coins = rwa_addresses(load("coingecko_markets.json"), load("coingecko_coins_list.json"))
    assert [(c.network, c.address, c.coingecko_id) for c in coins] == [
        ("ethereum", LINK_ETH, "chainlink"),
        ("avalanche", LINK_AVAX, "chainlink"),
        ("avalanche", XAUT0, "tether-gold-tokens"),
    ]  # pax-gold isn't in the RWA markets; Solana addresses are ignored
    assert coins[2].market_cap == 113340161 and coins[2].volume_24h == 5076061


def test_rwa_addresses_ignores_coins_missing_from_the_list():
    assert rwa_addresses([{"id": "ghost", "market_cap": 1, "total_volume": 1}], []) == []


def test_candidates_pin_first_and_skip_not_rwa():
    coins = [RwaCoin("avalanche", LINK_AVAX, "chainlink", 9e9, 4e8), coin("avalanche", 1, volume=5), RwaCoin("avalanche", XAUT0, "tether-gold-tokens", 1e8, 5e6)]
    assert rwa_candidates(coins, "avalanche") == [XAUT0, f"0x{1:040x}"]
    assert rwa_candidates(coins, "ethereum") == []


def test_candidates_mix_busiest_and_largest_and_fill_one_batch():
    busy = [coin("ethereum", i, mcap=1, volume=1_000 + i) for i in range(1, 41)]
    big = [coin("ethereum", 100 + i, mcap=1e9 + i, volume=0) for i in range(1, 41)]
    out = rwa_candidates(busy + big, "ethereum")
    assert len(out) == GT_BATCH
    assert out[:15] == [f"0x{i:040x}" for i in range(40, 25, -1)]  # 15 busiest
    assert out[15] == f"0x{140:040x}"  # then the largest, e.g. zero-volume permissioned funds


def test_parse_tokens_avalanche_pool_and_no_pool():
    xaut0, buidl = parse_tokens(load("geckoterminal_tokens_avax.json"), "avalanche")
    assert xaut0 == Trending("XAUt0", "XAUt0", XAUT0, "avalanche", 4152.3385911372, 146051.686719744, -0.129, 64106.9781, "blackhole-v3", True)
    assert buidl == Trending("buidl", "BlackRock USD Institutional Digital Liquidity Fund", BUIDL, "avalanche", None, 0.0, None, 0.0, "", False)


def test_parse_tokens_change_only_when_token_is_the_pool_base():
    xaut, googlon = parse_tokens(load("geckoterminal_tokens_eth.json"), "ethereum")
    assert (xaut.change_24h, xaut.liquidity_usd, xaut.dex, xaut.buyable) == (0.17, 4573467.4966, "uniswap_v3", True)
    assert (googlon.address, googlon.change_24h, googlon.price_usd, googlon.buyable) == (GOOGLON, None, 340.8676113819, True)


def test_parse_tokens_tolerates_an_empty_body_and_unescapes_names():
    assert parse_tokens({}, "ethereum") == []
    [t] = parse_tokens({"data": [{"id": "x", "attributes": {"address": "0xAB", "symbol": "bCSPX", "name": "Backed CSPX Core S&amp;P 500"}}]}, "avalanche")
    assert (t.name, t.address) == ("Backed CSPX Core S&P 500", "0xab")


def test_rank_rwas_pinned_first_then_volume_then_market_cap():
    coins = [coin("ethereum", 1, mcap=10), coin("ethereum", 2, mcap=99)]
    items = [
        item("ethereum", f"0x{1:040x}"),
        item("ethereum", XAUT, volume=1e7, liquidity=4e6),
        item("avalanche", XAUT0, volume=1e5, liquidity=6e4),
        item("ethereum", f"0x{2:040x}"),
    ]
    ranked = rank_rwas(items, coins)
    assert [t.address for t in ranked] == [XAUT0, XAUT, f"0x{2:040x}", f"0x{1:040x}"]


def test_rank_rwas_keeps_unbuyable_drops_not_rwa_and_duplicates_and_caps_at_ten():
    items = [item("ethereum", LINK_ETH, volume=1e9, liquidity=1e7), item("avalanche", BUIDL), item("avalanche", BUIDL)]
    items += [item("ethereum", f"0x{i:040x}", volume=i) for i in range(1, 15)]
    ranked = rank_rwas(items, [])
    assert len(ranked) == 10
    assert LINK_ETH not in [t.address for t in ranked]
    assert [t.address for t in ranked].count(BUIDL) == 0  # zero volume, ranked after the 14 others → cut by the cap
    assert rank_rwas([item("avalanche", BUIDL)], [])[0].buyable is False


def test_rank_rwas_with_live_fixtures_on_both_networks():
    items = parse_tokens(load("geckoterminal_tokens_eth.json"), "ethereum") + parse_tokens(load("geckoterminal_tokens_avax.json"), "avalanche")
    assert [t.symbol for t in rank_rwas(items, [])] == ["XAUt0", "XAUt", "GOOGLon", "buidl"]


def test_load_rwa_snapshot(tmp_path):
    path = tmp_path / "rwa.json"
    path.write_text(json.dumps({"generated": "2026-10-15", "coins": [{"network": "avalanche", "address": XAUT0, "coingecko_id": "tether-gold-tokens", "market_cap": 1.0, "volume_24h": 2.0}]}))
    assert load_rwa_snapshot(path) == [RwaCoin("avalanche", XAUT0, "tether-gold-tokens", 1.0, 2.0)]


def test_shipped_snapshot_covers_both_networks_and_the_pinned_token():
    coins = load_rwa_snapshot()
    assert {c.network for c in coins} == {"ethereum", "avalanche"}
    assert ("avalanche", XAUT0) in {(c.network, c.address) for c in coins}
    assert all(c.address == c.address.lower() and c.address.startswith("0x") for c in coins)
```

- [ ] **Step 3: Run to verify they fail**

Run: `uv run --directory agent pytest tests/test_trending_rwa.py -q`
Expected: FAIL — `ImportError: cannot import name 'PINNED' from 'lazyagent.trending'`.

- [ ] **Step 4: Implement.** In `agent/lazyagent/trending.py`, replace the imports

```python
import json
from dataclasses import asdict, dataclass
```

with

```python
import html
import json
from dataclasses import asdict, dataclass
from pathlib import Path
```

and append to the end of the file (two blank lines before it):

```python
# --- RWAs (Ethereum + Avalanche) ---

# Hackathon sponsor showcase: always first in rwa results, in this order (network, lower-case address).
PINNED = [
    ("avalanche", "0x2775d5105276781b4b85ba6ea6a6653beed1dd32"),  # XAUt0 (Tether Gold, Avalanche)
]
# In CoinGecko's RWA category but not tokenized real-world assets (protocol / oracle / L1 tokens).
NOT_RWA = {
    ("avalanche", "0x5947bb275c521040051d82396192181b413227a3"),  # LINK.e
    ("avalanche", "0x88128fd4b259552a9a1d457f435a6527aab72d42"),  # MKR
    ("avalanche", "0x03e8d118a1864c7dc53bf91e007ab7d91f5a06fa"),  # DEXTF (Memento)
    ("ethereum", "0x514910771af9ca656af840dff83e8264ecf986ca"),  # LINK
    ("ethereum", "0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2"),  # MKR
    ("ethereum", "0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3"),  # ONDO
    ("ethereum", "0x4a220e6096b25eadb88358cb44068a3248254675"),  # QNT
    ("ethereum", "0xe28b3b32b6c345a34ff64674606124dd5aceca30"),  # INJ
    ("ethereum", "0x4c1746a800d224393fe2470c70a35717ed4ea5f1"),  # PLUME
    ("ethereum", "0x320623b8e4ff03373931769a31fc52a4e78b5d70"),  # RSR
    ("ethereum", "0x940a2db1b7008b6c776d4faaca729d6d4a4aa551"),  # DUSK
    ("ethereum", "0x94314a14df63779c99c0764a30e0cd22fa78fc0e"),  # EPIC
    ("ethereum", "0xaa7a9ca87d3694b5755f213b5d04094b8d0f0a6f"),  # TRAC
    ("ethereum", "0xcccccccccc33d538dbc2ee4feab0a7a1ff4e8a94"),  # CFG
    ("ethereum", "0x643c4e15d7d62ad0abec4a9bd4b001aa3ef52d66"),  # SYRUP
    ("ethereum", "0xd9343a049d5dbd89cd19dc6bca8c48fb3a0a42a7"),  # LUMIA
    ("ethereum", "0xc43c6bfeda065fe2c4c11765bf838789bd0bb5de"),  # RED
    ("ethereum", "0x8a2279d4a90b6fe1c4b30fa660cc9f926797baa2"),  # CHR
    ("ethereum", "0x84ca8bc7997272c7cfb4d0cd3d55cd942b3c9419"),  # DIA
    ("ethereum", "0x3f80b1c54ae920be41a77f8b902259d48cf24ccf"),  # KERNEL
    ("ethereum", "0xa3ee21c306a700e682abcdfe9baa6a08f3820419"),  # CTC
    ("ethereum", "0xc4441c2be5d8fa8126822b9929ca0b81ea0de38e"),  # USUAL
    ("ethereum", "0x66761fa41377003622aee3c7675fc7b5c1c2fac5"),  # CPOOL
    ("ethereum", "0x24a3d725c37a8d1a66eb87f0e5d07fe67c120035"),  # EDEN (OpenEden)
    ("ethereum", "0x07041776f5007aca2a54844f50503a18a72a8b68"),  # USAT (Tether US stablecoin)
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


def rwa_addresses(markets: list[dict], coin_list: list[dict]) -> list[RwaCoin]:
    """CoinGecko RWA-category markets + coins/list?include_platform=true → one RwaCoin per
    (coin, network) for the networks we support. Coins without an EVM address there are skipped."""
    platforms = {c.get("id"): c.get("platforms") or {} for c in coin_list}
    coins = []
    for m in markets:
        for network in GT_NETWORKS:
            address = str(platforms.get(m.get("id"), {}).get(network) or "").lower()
            if address.startswith("0x") and len(address) == 42:
                coins.append(RwaCoin(network, address, m["id"], _num(m.get("market_cap")), _num(m.get("total_volume"))))
    return coins


def rwa_candidates(coins: list[RwaCoin], network: str) -> list[str]:
    """Addresses to look up on GeckoTerminal for one network (one batch): PINNED first, then half
    the busiest RWAs by CoinGecko volume, then the largest by market cap (so zero-volume
    permissioned funds like BUIDL still show), NOT_RWA excluded."""
    out = [a for n, a in PINNED if n == network]
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
    """PINNED first (in order), then 24h DEX volume, then CoinGecko market cap; NOT_RWA dropped; top 10."""
    pin = {key: i for i, key in enumerate(PINNED)}
    mcap = {(c.network, c.address): c.market_cap for c in coins}
    seen, kept = set(), []
    for t in items:
        key = (t.network, t.address.lower())
        if key in seen or (key in NOT_RWA and key not in pin):
            continue
        seen.add(key)
        kept.append(t)
    kept.sort(
        key=lambda t: (
            pin.get((t.network, t.address.lower()), len(pin)),
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

Run: `uv run --directory agent pytest tests/test_trending_rwa.py tests/test_trending.py -q --deselect tests/test_trending_rwa.py::test_shipped_snapshot_covers_both_networks_and_the_pinned_token`
Expected: PASS (27 tests, 1 deselected).

- [ ] **Step 6: Commit**

```bash
git add agent/lazyagent/trending.py agent/tests/test_trending_rwa.py agent/tests/fixtures
git commit -m "feat(agent): RWA addresses, candidates and ranking with pinned XAUt0"
```

---

### Task 4: GeckoTerminal source and the 60 s cache

**Files:**
- Modify: `agent/lazyagent/trending.py` (imports; append the I/O section)
- Create: `agent/tests/http_stub.py`
- Modify: `agent/tests/fakes.py` (append `FakeTrendingSource`)
- Test: `agent/tests/test_trending_source.py`

**Interfaces:**
- Consumes: everything from Tasks 2–3.
- Produces, in `lazyagent.trending`:
  - `TrendingSource` (Protocol): `async meme_pools() -> list[Pool]` and `async tokens(network: str, addresses: list[str]) -> dict`.
  - `GeckoTerminalSource(base: str = GT_API)`. `tokens` sends no request for an empty list. Errors raise: `urllib.error.HTTPError` (429 etc.), `OSError` (unreachable) or `ValueError` (non-JSON).
  - `TrendingTokens(source, rwa_coins: Callable[[], list[RwaCoin]] = load_rwa_snapshot, ttl=TTL_S, clock=time.monotonic)` with `.source` and `async fetch(category: str = "meme", network: str | None = None) -> list[Trending]`. It caches per (category, network) and propagates exceptions without caching them.
  - `TRENDING`: the process-wide `TrendingTokens(GeckoTerminalSource())`.
- Produces, in tests:
  - `http_stub.serve(routes) -> (server, seen_paths)`. Routes map a path prefix (longest wins) to `(status, body_bytes, headers)` or to a list of those served in turn (the last one repeats).
  - `fakes.FakeTrendingSource(pools=None, tokens=None)` with `.pools`, `.token_bodies`, `.calls` (a list of tuples) and `.fail`.

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

- [ ] **Step 2: Write the failing tests** in `agent/tests/test_trending_source.py`

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
XAUT = "0x68749665ff8d2d112fa859aa293f07a622782f38"


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
        body = await GeckoTerminalSource(f"http://127.0.0.1:{server.server_port}").tokens("ethereum", [XAUT, "0xba47214edd2bb43099611b208f75e4b42fdcfedc"])
    finally:
        server.shutdown()
    assert len(body["data"]) == 2
    assert seen == [f"/eth/tokens/multi/{XAUT},0xba47214edd2bb43099611b208f75e4b42fdcfedc?include=top_pools"]


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


SNAPSHOT = [RwaCoin("avalanche", XAUT0, "tether-gold-tokens", 1e8, 5e6), RwaCoin("ethereum", XAUT, "tether-gold", 2e9, 3e8)]


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
        ("tokens", "ethereum", (XAUT,)),
        ("tokens", "avalanche", (XAUT0,)),
    ]


async def test_rwa_lists_both_networks_with_pinned_first():
    trending = TrendingTokens(FakeTrendingSource(tokens=tokens_fixtures()), lambda: SNAPSHOT, clock=Clock())
    both = await trending.fetch("rwa")
    assert [(t.symbol, t.network) for t in both] == [("XAUt0", "avalanche"), ("XAUt", "ethereum"), ("GOOGLon", "ethereum"), ("buidl", "avalanche")]
    eth = await trending.fetch("rwa", "ethereum")
    assert [t.symbol for t in eth] == ["XAUt", "GOOGLon"]


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
from dataclasses import asdict, dataclass
from pathlib import Path
```

with

```python
import asyncio
import html
import json
import time
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
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

    async def fetch(self, category: str = "meme", network: str | None = None) -> list[Trending]:
        key = (category, network)
        now = self.clock()
        hit = self._cache.get(key)
        if hit is not None and now - hit[0] < self.ttl:
            return hit[1]
        items = rank_memes(await self.source.meme_pools()) if category == "meme" else await self._rwas(network)
        self._cache[key] = (now, items)
        return items

    async def _rwas(self, network: str | None) -> list[Trending]:
        coins = self.rwa_coins()
        items: list[Trending] = []
        for net in [network] if network else list(GT_NETWORKS):
            items += parse_tokens(await self.source.tokens(net, rwa_candidates(coins, net)), net)
        return rank_rwas(items, coins)


TRENDING = TrendingTokens(GeckoTerminalSource())
```

- [ ] **Step 5: Run to verify they pass**

Run: `uv run --directory agent pytest tests/test_trending_source.py tests/test_trending.py -q`
Expected: PASS (26 tests).

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
- Test: `agent/tests/test_rwa_snapshot.py` (plus the shipped-snapshot test from Task 3)

**Interfaces:**
- Consumes: `RWA_SNAPSHOT`, `RwaCoin`, `rwa_addresses`, `load_rwa_snapshot` (Task 3); `http_stub.serve` (Task 4).
- Produces, in `lazyagent.rwa_snapshot`:
  - `CoinGeckoRwaSource(base=CG_API, sleep=time.sleep, pause=15.0, retries=6, per_page=250)` with `markets() -> list[dict]`, `coin_list() -> list[dict]` and `coins() -> list[RwaCoin]`. On a 429 it sleeps for `Retry-After` (60 if missing); after `retries` attempts it raises `HTTPError`.
  - `snapshot_json(coins, generated: str) -> str`, sorted by network, then volume and market cap descending, one coin per line.
  - `main(path=RWA_SNAPSHOT)`.
  - Run with `uv run --directory agent python -m lazyagent.rwa_snapshot`.

- [ ] **Step 1: Write the failing tests** in `agent/tests/test_rwa_snapshot.py`

```python
import json
import urllib.error
from pathlib import Path

import pytest
from http_stub import serve

from lazyagent.rwa_snapshot import CoinGeckoRwaSource, snapshot_json
from lazyagent.trending import RwaCoin, load_rwa_snapshot

FIXTURES = Path(__file__).parent / "fixtures"
MARKETS = json.loads((FIXTURES / "coingecko_markets.json").read_text())


def body(obj) -> bytes:
    return json.dumps(obj).encode()


def test_fetches_every_page_then_the_coin_list():
    server, seen = serve(
        {
            "/coins/markets": [(200, body(MARKETS[:1]), {}), (200, body(MARKETS[1:]), {}), (200, b"[]", {})],
            "/coins/list": (200, (FIXTURES / "coingecko_coins_list.json").read_bytes(), {}),
        }
    )
    sleeps = []
    try:
        coins = CoinGeckoRwaSource(f"http://127.0.0.1:{server.server_port}", sleep=sleeps.append, per_page=1).coins()
    finally:
        server.shutdown()
    assert [p.split("&page=")[-1] for p in seen[:3]] == ["1", "2", "3"]
    assert seen[0] == "/coins/markets?vs_currency=usd&category=real-world-assets-rwa&per_page=1&page=1"
    assert seen[3] == "/coins/list?include_platform=true"
    assert [(c.network, c.coingecko_id) for c in coins] == [("ethereum", "chainlink"), ("avalanche", "chainlink"), ("avalanche", "tether-gold-tokens")]
    assert sleeps == [15.0, 15.0, 15.0]  # between pages, and before the coin list


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

- [ ] **Step 3: Implement.** Create `agent/lazyagent/rwa_snapshot.py`:

```python
"""Refresh the RWA address snapshot (lazyagent/data/rwa_coingecko.json) from CoinGecko's free API.

CoinGecko's RWA category is ~2,500 coins (10 pages) and the free tier 429s even at one request
every 15 s, so this runs offline (paced, honouring Retry-After) instead of on a user's request.
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
CATEGORY = "real-world-assets-rwa"
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

    def markets(self) -> list[dict]:
        out: list[dict] = []
        page = 1
        while True:
            batch = self._fetch(f"{self.base}/coins/markets?vs_currency=usd&category={CATEGORY}&per_page={self.per_page}&page={page}")
            out += batch
            if len(batch) < self.per_page:
                return out
            page += 1
            self.sleep(self.pause)

    def coin_list(self) -> list[dict]:
        return self._fetch(f"{self.base}/coins/list?include_platform=true")

    def coins(self) -> list[RwaCoin]:
        markets = self.markets()
        self.sleep(self.pause)
        return rwa_addresses(markets, self.coin_list())


def snapshot_json(coins: list[RwaCoin], generated: str) -> str:
    rows = sorted(coins, key=lambda c: (c.network, -c.volume_24h, -c.market_cap, c.address))
    lines = ",\n".join("    " + json.dumps(asdict(c)) for c in rows)
    head = json.dumps({"generated": generated, "source": f"CoinGecko coins/markets category={CATEGORY} (all pages) + coins/list platforms"})[:-1]
    return f'{head}, "coins": [\n{lines}\n]}}\n'


def main(path: Path = RWA_SNAPSHOT) -> None:
    coins = CoinGeckoRwaSource().coins()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot_json(coins, datetime.date.today().isoformat()))
    counts = {n: sum(c.network == n for c in coins) for n in sorted({c.network for c in coins})}
    print(f"Wrote {len(coins)} RWA addresses to {path}: {counts}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run --directory agent pytest tests/test_rwa_snapshot.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Generate the snapshot.** This is live and paced, and takes about 3–6 minutes because of 429 back-offs. Leave it running.

Run: `uv run --directory agent python -m lazyagent.rwa_snapshot`
Expected: `Wrote ~1450 RWA addresses to …/agent/lazyagent/data/rwa_coingecko.json: {'avalanche': ~290, 'ethereum': ~1170}` (2026-10-15: 1,457 = 290 + 1,167; the file is ~270 KB).
Check: `grep -c 0x2775d5105276781b4b85ba6ea6a6653beed1dd32 agent/lazyagent/data/rwa_coingecko.json` → `1`.

- [ ] **Step 6: Run the shipped-snapshot test and a live smoke check.** The smoke check hits GeckoTerminal twice and is not part of the suite.

Run: `uv run --directory agent pytest tests/test_trending_rwa.py -q`
Expected: PASS (13 tests).

Run: `uv run --directory agent python -c "import asyncio; from lazyagent.trending import TRENDING; [print(t.network, t.symbol, t.volume_24h, t.liquidity_usd, t.dex, t.buyable) for t in asyncio.run(TRENDING.fetch('rwa'))]"`
Expected: `avalanche XAUt0 … True` first, then Ethereum gold and tokenized stocks (XAUt, PAXG, …). If a clear non-RWA protocol token or a plain stablecoin shows up, add its (network, address) to `NOT_RWA` and to the research note.

- [ ] **Step 7: Commit**

```bash
git add agent/lazyagent/rwa_snapshot.py agent/lazyagent/data/rwa_coingecko.json agent/tests/test_rwa_snapshot.py
git commit -m "feat(agent): CoinGecko RWA address snapshot (Ethereum + Avalanche)"
```

---

### Task 6: `list_trending_tokens` tool and prompt line

**Files:**
- Modify: `agent/lazyagent/tools.py` (import, `TOOL_NAMES`, class attribute + method after `request_test_funds`, registration before `unsupported_action`)
- Modify: `agent/lazyagent/prompt.py` (one line, directly above the "Bridging between networks" line)
- Modify: `agent/tests/test_tools.py` (`test_mcp_server_and_names`)
- Test: `agent/tests/test_trending_tools.py`

**Interfaces:**
- Consumes: `TRENDING`, `UNAVAILABLE`, `TrendingTokens`, `check_args`, `to_json`, `Pool`, `TokenInfo`, `RwaCoin`, `GeckoTerminalSource` (Tasks 2–4); `FakeTrendingSource`; `ok` and `err` in `tools.py`.
- Produces:
  - `WalletTools.trending: TrendingTokens`, a class attribute defaulting to `TRENDING`; tests assign an instance attribute.
  - `async WalletTools.list_trending_tokens(args: dict) -> dict`. Args: optional `category` (default `meme`) and optional `network`; both are case-insensitive.
  - MCP tool `list_trending_tokens`, with `"mcp__wallet__list_trending_tokens"` last in `TOOL_NAMES`.

- [ ] **Step 1: Write the failing tests** in `agent/tests/test_trending_tools.py`

```python
import json

from fakes import FakeChain, FakeTrendingSource, Outbox

from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.trending import GeckoTerminalSource, Pool, RwaCoin, TokenInfo, TrendingTokens

COQ = "0x420fca0121dc28039145009570975747295f2329"
XAUT0 = "0x2775d5105276781b4b85ba6ea6a6653beed1dd32"
XAUT0_BODY = {
    "data": [{"id": "avax_x", "attributes": {"address": XAUT0, "symbol": "XAUt0", "name": "XAUt0", "price_usd": "4152.3", "volume_usd": {"h24": "146051.7"}}}],
}


def make(source: FakeTrendingSource) -> WalletTools:
    tools = WalletTools(FakeChain(), Outbox(), WalletContext(), Proposals())
    tools.trending = TrendingTokens(source, lambda: [RwaCoin("avalanche", XAUT0, "tether-gold-tokens", 1e8, 5e6)])
    return tools


def text(result):
    return result["content"][0]["text"]


async def test_memes_by_default():
    tools = make(FakeTrendingSource([Pool(TokenInfo("COQ", "COQINU", COQ), 1.2e-7, 16_937.5, -5.1, 623_823.6, "LFJ", 0)]))
    result = await tools.list_trending_tokens({})
    assert not result.get("is_error")
    [coq] = json.loads(text(result))["tokens"]
    assert (coq["symbol"], coq["address"], coq["network"], coq["change_24h"], coq["buyable"]) == ("COQ", COQ, "avalanche", -5.1, True)


async def test_rwa_with_network():
    source = FakeTrendingSource(tokens={"avalanche": XAUT0_BODY})
    result = await make(source).list_trending_tokens({"category": "rwa", "network": "Avalanche"})
    [xaut0] = json.loads(text(result))["tokens"]
    assert (xaut0["symbol"], xaut0["network"], xaut0["buyable"]) == ("XAUt0", "avalanche", False)  # no pool in this body
    assert source.calls == [("tokens", "avalanche", (XAUT0,))]


async def test_works_without_an_active_wallet():
    tools = make(FakeTrendingSource([]))
    assert tools.ctx.address is None
    assert json.loads(text(await tools.list_trending_tokens({})))["tokens"] == []


async def test_bad_arguments_are_errors_without_fetching():
    source = FakeTrendingSource()
    tools = make(source)
    bad = await tools.list_trending_tokens({"category": "nft"})
    assert bad["is_error"] is True and text(bad) == "category must be 'meme' or 'rwa'."
    eth_memes = await tools.list_trending_tokens({"category": "meme", "network": "ethereum"})
    assert text(eth_memes) == "Memecoins are Avalanche only."
    assert source.calls == []


async def test_fetch_failure_is_a_friendly_error():
    source = FakeTrendingSource()
    source.fail = True
    result = await make(source).list_trending_tokens({"category": "rwa"})
    assert result["is_error"] is True and text(result) == "Couldn't load trending tokens right now."


def test_default_source_is_geckoterminal():
    assert isinstance(WalletTools.trending.source, GeckoTerminalSource)
```

In `agent/tests/test_tools.py`, `test_mcp_server_and_names`, add the new name as the last entry:

```python
        "mcp__wallet__request_test_funds",
        "mcp__wallet__list_trending_tokens",
    ]
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --directory agent pytest tests/test_trending_tools.py tests/test_tools.py::test_mcp_server_and_names -q`
Expected: FAIL. `WalletTools` has no `list_trending_tokens` / `trending`, and the `TOOL_NAMES` assertion fails.

- [ ] **Step 3: Implement in `agent/lazyagent/tools.py`.** Make these five small edits and nothing else.

After `from .tokens import find_token` add:

```python
from .trending import TRENDING, UNAVAILABLE, TrendingTokens, check_args, to_json
```

In `TOOL_NAMES`, append the name to the tuple:

```python
    for n in ("get_balances", "resolve_recipient", "propose_transfer", "propose_swap", "unsupported_action", "request_test_funds", "list_trending_tokens")
```

Between the `request_test_funds` and `unsupported_action` methods, insert:

```python
    trending: TrendingTokens = TRENDING  # shared 60 s cache; tests assign their own

    async def list_trending_tokens(self, args: dict) -> dict:
        category = str(args.get("category") or "meme").strip().lower()
        network = str(args["network"]).strip().lower() if args.get("network") else None
        problem = check_args(category, network)
        if problem:
            return err(problem)
        try:
            return ok(to_json(await self.trending.fetch(category, network)))
        except Exception:
            return err(UNAVAILABLE)
```

In `build_mcp_server`, insert this before the `tool("unsupported_action", ...)` entry:

```python
            tool(
                "list_trending_tokens",
                "Live mainnet token lists (read-only). category 'meme' (default): top trending Avalanche memecoins. category 'rwa': top real-world-asset tokens on Ethereum and Avalanche, sponsor pick first. Each token: symbol, name, contract address, network, USD price, 24h volume, 24h change, liquidity, main DEX, buyable.",
                {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": ["meme", "rwa"], "description": "Default 'meme'"},
                        "network": {"type": "string", "enum": ["ethereum", "avalanche"], "description": "rwa only, and only if the user named a network"},
                    },
                },
            )(t.list_trending_tokens),
```

- [ ] **Step 4: Add the prompt line.** In `agent/lazyagent/prompt.py`, insert this directly above `- Bridging between networks, schedules, ...`:

```text
- "What's trending", "hot memecoins on Avalanche" → list_trending_tokens (category meme). "RWAs", "real-world assets", "tokenized gold / stocks / treasuries" → list_trending_tokens with category rwa (network only if the user named one). It's live mainnet data. Summarise the top three or so by symbol with their 24h change in one or two sentences; for RWAs mention the first (pinned) one and say plainly which aren't buyable here. Offer to buy only buyable tokens: call propose_swap with that token's network and token_out set to its contract address, not its symbol. A very new token may not exist on the Sandbox fork yet. If the list is empty or the tool errors, say so plainly.
```

- [ ] **Step 5: Run the agent suite**

Run: `uv run --directory agent pytest -q`
Expected: PASS. Fork tests skip or pass as before, and no test touches GeckoTerminal or CoinGecko.

- [ ] **Step 6: Commit**

```bash
git add agent/lazyagent/tools.py agent/lazyagent/prompt.py agent/tests/test_tools.py agent/tests/test_trending_tools.py
git commit -m "feat(agent): list_trending_tokens tool (memes, RWAs) and prompt routing"
```

---

### Task 7: Docs, spec deviations, full verification, manual check

**Files:**
- Modify: `CLAUDE.md`, `docs/superpowers/specs/2026-10-15-lazywallet-avax-trending-design.md`

- [ ] **Step 1: `CLAUDE.md`.** Under "Wallet app conventions", after the Uniswap v4 bullet, add one line:

```markdown
- Trending tokens (`list_trending_tokens`: Avalanche memecoins; RWAs on Ethereum + Avalanche, `PINNED` first) come from GeckoTerminal via `agent/lazyagent/trending.py` (read-only, 60 s cache). RWA membership is a CoinGecko snapshot in `agent/lazyagent/data/rwa_coingecko.json` — refresh with `uv run --directory agent python -m lazyagent.rwa_snapshot`. Curated `NOT_MEMES` / `NOT_RWA` lists are explained in `docs/research/2026-10-15-avalanche-trending-tokens.md`.
```

- [ ] **Step 2: Record the planning decisions the spec doesn't cover yet.** Set `Status:` to `Implemented on feat-trending-avax` and append:

```markdown
## 7. Decisions made while planning

- RWA membership is a checked-in snapshot (`agent/lazyagent/data/rwa_coingecko.json`, refreshed by `python -m lazyagent.rwa_snapshot`) instead of a live 24 h cache: the RWA category is ~2,470 coins over 10 pages and the free tier returned 429 (Retry-After 15–60 s) even at one request per 15 s, so building it on a user's request would take minutes. Only GeckoTerminal is called at request time.
- GeckoTerminal `tokens/multi` takes at most 30 addresses, so per network we look up `PINNED`, the 15 busiest RWAs by CoinGecko volume, then the largest by market cap (keeps zero-volume permissioned funds like BUIDL).
- `NOT_RWA` also lists protocol tokens CoinGecko files under RWA (ONDO, QNT, INJ, PLUME, RSR, DUSK, EPIC, TRAC, CFG, SYRUP, LUMIA, RED, CHR, DIA, KERNEL, CTC, USUAL, CPOOL, EDEN, MKR, DEXTF) and the USAT stablecoin.
- RWA `dex` is GeckoTerminal's dex id (`tokens/multi` can't include dex names); `price_usd` / `change_24h` are `null` when unknown; 24h change is used only when the token is its deepest pool's base token.
- `CoinGeckoRwaSource` lives in the offline script `agent/lazyagent/rwa_snapshot.py`; the runtime cache method is `TrendingTokens.fetch(category, network)`.
- The cache is one process-wide `TrendingTokens` read through a `WalletTools` class attribute, so `WalletTools.__init__`, `Session` and `server.py` are unchanged.
```

- [ ] **Step 3: Full verification**

Run: `pnpm test:py && pnpm build && pnpm lint`
Expected: all PASS.

- [ ] **Step 4: Manual check.** Run `pnpm dev:sandbox`, `pnpm dev:agent` and `pnpm dev`, then open `http://localhost:5174`.

1. Ask "What's trending on Avalanche?". Expect one or two spoken-friendly sentences naming a few memecoins with their 24h change, and an offer to buy. None of BTC.b / WAVAX / sAVAX / USDC / JOE / PHAR should appear.
2. Ask "What RWAs can I buy?". XAUt0 (Avalanche) should be mentioned first, then e.g. XAUt / PAXG on Ethereum, and the agent should say permissioned funds aren't buyable here.
3. Ask "RWAs on Avalanche only". Expect XAUt0 first, with BUIDL / ACRED-style funds flagged as not buyable.
4. Say "Buy 1 AVAX of XAUt0". The agent should call `propose_swap` with network avalanche and the **contract address** as `token_out` (check the agent log). Before the Kyber branch lands, expect the normal unsupported-token error, explained plainly.
5. Ask again within a minute. The answer should be served from the cache (the agent log shows no new GeckoTerminal error).

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-10-15-lazywallet-avax-trending-design.md
git commit -m "docs: trending memecoins and RWAs"
```

---

## Merge note

The Kyber branch merges first; rebase this branch onto it. Conflicts are expected only in these places:
- `agent/lazyagent/tools.py`: the import line, the `TOOL_NAMES` tuple, the method inserted before `unsupported_action`, and the registration before `tool("unsupported_action", ...)`.
- `agent/lazyagent/prompt.py`: one line.
- `agent/tests/test_tools.py`: the `TOOL_NAMES` list.
- `agent/tests/fakes.py`: the appended class.
- `CLAUDE.md`: one line.

Keep both sides in each. After the rebase, re-run `pnpm test:py` and repeat manual step 4. The buy should now produce a KyberSwap confirm card showing the XAUt0 contract address.
