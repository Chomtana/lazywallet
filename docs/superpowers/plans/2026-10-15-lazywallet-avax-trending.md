# LazyWallet — Trending Avalanche Memecoins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "What's trending on Avalanche?" → a read-only agent tool `list_trending_tokens` returns up to 10 live Avalanche memecoins (symbol, name, contract address, price, 24h volume, 24h change, liquidity, DEX) and the agent summarises them and offers to buy by contract address.

**Architecture:** New `agent/lazyagent/trending.py` holds pure functions (`parse_pools`, `is_memecoin`, `rank`, `to_json`) plus an injectable `GeckoTerminalSource` (stdlib `urllib` in `asyncio.to_thread`, like `faucet.py`) and a 60 s `TrendingTokens` cache. `tools.py` gets one method + one registration and reads the shared cache through a class attribute (no constructor / `Session` / `server.py` changes). `prompt.py` gets one line. No UI.

**Tech Stack:** Python 3.12+ (uv, claude-agent-sdk, pytest-asyncio with `asyncio_mode = "auto"`), GeckoTerminal public API v2 (no key).

**Spec:** `docs/superpowers/specs/2026-10-15-lazywallet-avax-trending-design.md`

## Global Constraints

- Branch `feat-trending-avax` in its own worktree, from `main`. The sibling branch (KyberSwap + custom tokens) heavily edits `agent/lazyagent/tools.py` and `prompt.py` and merges first. Keep edits there to: one import line, one name in `TOOL_NAMES`, one class attribute + one method, one `tool(...)` registration, one prompt line. Do not touch `WalletTools.__init__`, `session.py`, `server.py`.
- Network: Avalanche only. Data is live **mainnet**, read-only; nothing is signed.
- Source: GeckoTerminal public API, no key, ~30 req/min. Base `https://api.geckoterminal.com/api/v2/networks/avax`. Requests: `/trending_pools?include=base_token,dex` and `/dexes/arena-dex/pools?sort=h24_volume_usd_desc&include=base_token,dex` (both verified 2026-10-15).
- HTTP: stdlib `urllib` in `asyncio.to_thread`, no new dependency; timeout 15 s.
- Cache: 60 s in-process cache of the computed list. Errors are never cached.
- Filter: exclude `AVAX_TOKENS` registry addresses and WAVAX, wrapped / bridged (`*.e`, `*.b`, symbols containing AVAX/BTC/ETH, names containing "wrapped"/"bridged"), stablecoins (symbol contains `USD`, or DAI, AUSD, EURC, EUROC, XAUT, XAUT0, FRAX, GHO, MIM, JPYC), liquid staking (symbol contains AVAX; name contains "staked"/"staking"), and a curated `NOT_MEMES` address list. Liquidity ≥ **$10,000** (of the token's deepest pool).
- Ranking: GeckoTerminal trending order first, then 24h volume (descending); one entry per token (its highest-liquidity pool); top **10**.
- Error text from the tool, exactly: `Couldn't load trending tokens right now.` Never a crash.
- Buying is out of scope here: the prompt tells the model to call `propose_swap` with `network "avalanche"` and `token_out` = the contract address. Until the Kyber branch lands, that returns the normal unsupported-token error.
- Unit tests never hit the network (fixtures + local `HTTPServer` + fakes).
- Done = `pnpm test:py`, `pnpm build && pnpm lint` pass.
- Spec deviations decided while planning (recorded in the spec in Task 5): Arena DEX's top-volume pools are added to the candidate set; a curated `NOT_MEMES` address list; only each pool's **base** token is considered; `dex` is GeckoTerminal's display name ("LFJ", "Arena DEX"); the cache is shared process-wide via a `WalletTools` class attribute.

## Review Focus

- GeckoTerminal answers 429 after a few quick asks (we hit it while planning) → the user hears "Couldn't load trending tokens right now.", the failure is not cached, and the next ask retries → tests in Task 3 (`test_source_raises_on_rate_limit`, `test_errors_are_not_cached`) and Task 4 (`test_list_trending_tokens_reports_a_friendly_error`).
- A pool whose base token is missing from `included`, or with `null` price / reserve / volume (brand-new pools) → that pool is skipped or reads 0, the rest still render → test in Task 2 (`test_parse_pools_skips_pools_without_base_token_and_zeroes_missing_numbers`, `test_parse_pools_tolerates_an_empty_body`).
- The same memecoin trending on two DEXs → one entry, from its deepest pool, keeping its best trending position; the $10k check uses that deepest pool → tests in Task 2 (`test_rank_keeps_one_entry_per_token_...`, `test_rank_liquidity_threshold_applies_to_the_deepest_pool`).
- Registry addresses are checksummed, the API returns lower-case → BTC.b / WAVAX are still excluded whatever the case → test in Task 2 (`test_memecoin_filter_matches_registry_addresses_in_any_case`).
- Asked before any wallet is unlocked, or when nothing passes the filter → the tool still answers (`tokens: []`), not "No wallet is active" → test in Task 4 (`test_list_trending_tokens_works_without_an_active_wallet`) and Task 3 (`test_an_empty_list_is_cached_too`).

---

## File structure

| File | Responsibility |
|---|---|
| `docs/research/2026-10-15-avalanche-trending-memecoins.md` (new) | Source comparison, filter, ranking, dated sample output |
| `agent/lazyagent/trending.py` (new) | Pure: `TokenInfo`, `Pool`, `Trending`, `parse_pools`, `is_memecoin`, `rank`, `to_json`. I/O: `TrendingSource`, `GeckoTerminalSource`, `TrendingTokens` (60 s cache), `TRENDING` (shared instance) |
| `agent/tests/fixtures/geckoterminal_trending.json` (new) | Real `trending_pools` response, trimmed (captured 2026-10-15) |
| `agent/tests/fixtures/geckoterminal_arena.json` (new) | Real `dexes/arena-dex/pools` response, trimmed (captured 2026-10-15) |
| `agent/tests/test_trending.py` (new) | Pure-function tests |
| `agent/tests/test_trending_source.py` (new) | HTTP source against a local server + cache tests |
| `agent/tests/test_trending_tools.py` (new) | Tool result / error tests |
| `agent/tests/fakes.py` | `FakeTrendingSource` (appended) |
| `agent/lazyagent/tools.py` | Register `list_trending_tokens` |
| `agent/lazyagent/prompt.py` | One routing line |
| `agent/tests/test_tools.py` | `TOOL_NAMES` expectation |
| `CLAUDE.md`, spec | One convention line; planning deviations |

---

### Task 1: Research note — source, memecoin filter, ranking

**Files:**
- Create: `docs/research/2026-10-15-avalanche-trending-memecoins.md`

**Interfaces:**
- Consumes: nothing.
- Produces: the decisions Tasks 2–4 implement (GeckoTerminal; trending + Arena DEX candidates; filter rules and `NOT_MEMES`; ranking). If your spot-checks contradict them (e.g. GeckoTerminal now needs a key), **stop and report** instead of continuing.

- [ ] **Step 1: Re-run the spot-checks** (space them out — GeckoTerminal rate-limits bursts; a 429 just means wait ~30 s)

```bash
curl -s 'https://api.geckoterminal.com/api/v2/networks/avax/trending_pools?include=base_token,dex' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); inc={i['id']:i['attributes'] for i in d['included']}; [print(p['attributes']['name'], '|', p['relationships']['dex']['data']['id'], '|', p['attributes']['reserve_in_usd'], '|', p['attributes']['volume_usd']['h24'], '|', p['attributes']['price_change_percentage']['h24']) for p in d['data']]"
curl -s 'https://api.geckoterminal.com/api/v2/networks/avax/dexes/arena-dex/pools?sort=h24_volume_usd_desc&include=base_token,dex' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(p['attributes']['name'], '|', p['attributes']['reserve_in_usd'], '|', p['attributes']['volume_usd']['h24']) for p in d['data'][:10]]"
curl -s 'https://api.geckoterminal.com/api/v2/networks/avax/tokens/0x6e84a6216ea6dacc71ee8e6b0a5b7322eebc0fdd/info' \
  | python3 -c "import json,sys; a=json.load(sys.stdin)['data']['attributes']; print(a['symbol'], a['gt_category_ids'])"
curl -s 'https://api.dexscreener.com/latest/dex/tokens/0x420fca0121dc28039145009570975747295f2329' \
  | python3 -c "import json,sys; p=json.load(sys.stdin)['pairs'][0]; print(p['dexId'], p['priceUsd'], p['volume']['h24'], p['priceChange']['h24'], p['liquidity']['usd'])"
curl -s 'https://api.dexscreener.com/token-boosts/top/v1' | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d), sum(x['chainId']=='avalanche' for x in d))"
curl -s -m 10 -o /dev/null -w '%{http_code}\n' 'https://api.lfj.gg/v1/pools/avalanche?orderBy=volume&pageSize=3'
```

Expected (as of 2026-10-15): trending list mostly majors / protocol tokens (BTC.b, PHAR, JOE, sAVAX, USDC.e, BLACK, QI…) with COQ the only obvious meme; Arena DEX pools are all small memecoins (AVXTO, GATOR, WOLFI…); JOE's categories are `['defi', 'joe-biden']`; DexScreener returns COQ on `traderjoe` with all fields; boosts have 0 Avalanche entries; LFJ API times out / needs a key.

- [ ] **Step 2: Write the note** — `docs/research/2026-10-15-avalanche-trending-memecoins.md`, with this content (update the sample table with your Step 1 run if it differs, keep the date):

```markdown
# Avalanche trending memecoins — data source and filter

Date: 2026-10-15. Feeds `agent/lazyagent/trending.py` (`list_trending_tokens`).

## Sources compared

| | GeckoTerminal | DexScreener | LFJ / Arena |
|---|---|---|---|
| Key | None | None | LFJ API needs a key (request timed out unauthenticated); no public Arena API found |
| Rate limit | ~30 req/min (429 seen after a burst) | 300/min pairs & tokens, 60/min profiles & boosts | — |
| Avalanche coverage | All DEXs incl. `arena-dex`, LFJ v1/v2.1/v2.2, Pharaoh, Blackhole, Pangolin, Uniswap v3/v4 | All DEXs incl. `arenatrade` | Own venue only |
| "Trending" ranking | Yes — `/networks/avax/trending_pools`; plus `/dexes/{dex}/pools?sort=h24_volume_usd_desc` | No trending endpoint; only paid boosts (0 Avalanche entries today) and search / by-token lookups | — |
| Fields | address, symbol, name (via `include=base_token`), price USD, 24h volume, 24h change, `reserve_in_usd`, DEX display name (via `include=dex`) | Same, per pair | — |
| Freshness | Live (minutes) | Live | — |

**Decision: GeckoTerminal.** It is the only keyless source with a trending ranking and covers every Avalanche venue including Arena DEX. DexScreener would be the fallback for per-token lookups (`/tokens/v1/avalanche/{addresses}`), not for discovery.

## Candidates

`trending_pools` (page 1, 20 pools) is dominated by majors and protocol tokens, so on its own it rarely yields memecoins. Add Arena DEX's top pools by 24h volume (`/dexes/arena-dex/pools?sort=h24_volume_usd_desc`) — Arena is where Avalanche memecoins graduate to. Two requests per refresh; with the 60 s cache that is ≤ 2 req/min. Only each pool's base token is considered (GeckoTerminal puts the non-WAVAX / non-stable side first; price and 24h change are given for the base token).

## Memecoin filter

GeckoTerminal has no reliable meme flag: token `categories` need one request per token and are wrong or missing (JOE → `defi`, `joe-biden`; COQ → `animal`, `chicken`, `inu`, no "meme"); the categories endpoint needs a paid key. So the filter is rule-based:

- Exclude the Avalanche registry (`AVAX_TOKENS`) and WAVAX by address (case-insensitive).
- Stablecoins: symbol contains `USD` (USDC, USDt, USDC.e, avUSD, bUSDC, AUSD…) or is DAI, AUSD, EURC, EUROC, XAUT, XAUT0, FRAX, GHO, MIM, JPYC.
- Wrapped / bridged / liquid staking: symbol ends `.e` / `.b`; symbol contains AVAX, BTC or ETH (WAVAX, sAVAX, ggAVAX, WBTC, BTC.b, WETH.e); name contains "staked", "staking", "wrapped", "bridged" (p33 = "Pharaoh Liquid Staking Token").
- Protocol / governance tokens: a short curated address list (`NOT_MEMES`: JOE, PHAR, BLACK, QI, FOLKS, ARENA, MUON, BEAM, ZRO, GUN, NXPC). The spec says not to guess without a reliable signal; the data has none, and without this list today's "top memecoins" would be PHAR, JOE, BLACK, MUON, QI, FOLKS. Extend it when a non-meme shows up.
- Liquidity ≥ $10,000 in the token's deepest pool.

## Ranking

One entry per token (its highest-liquidity pool). Tokens in the trending list come first in trending order; the rest follow by 24h volume. Top 10.

## Sample output (2026-10-15, with the rules above)

| # | Symbol | 24h | Volume 24h | Liquidity | DEX |
|---|---|---|---|---|---|
| 1 | COQ | -5.1% | $16,938 | $621,870 | LFJ |
| 2 | AVXTO | +9.6% | $597 | $15,523 | Arena DEX |
| 3 | GATOR | +4.9% | $524 | $11,542 | Arena DEX |
| 4 | WOLFI | -3.6% | $351 | $25,999 | Arena DEX |
| 5 | SUPER | -4.5% | $138 | $18,089 | Arena DEX |
| 6 | GLADIUS | +2.5% | $24 | $37,565 | Arena DEX |
| 7 | EMINI | 0.0% | $11 | $12,699 | Arena DEX |
| 8 | MEOW | -5.1% | $4 | $22,671 | Arena DEX |

Excluded from the same data: BTC.b, WETH.e, sAVAX, p33, USDC.e, bUSDC, bAUSD, EUROC, XAUt0 (rules); PHAR, JOE, BLACK, QI, FOLKS, MUON, ARENA (`NOT_MEMES`); NOCHILL, NXPC (< $10k liquidity).
```

- [ ] **Step 3: Commit**

```bash
git add docs/research/2026-10-15-avalanche-trending-memecoins.md
git commit -m "docs(research): Avalanche trending memecoins source and filter"
```

---

### Task 2: Pure logic — parse, filter, rank, JSON (with real fixtures)

**Files:**
- Create: `agent/lazyagent/trending.py`
- Create: `agent/tests/fixtures/geckoterminal_trending.json`, `agent/tests/fixtures/geckoterminal_arena.json`
- Test: `agent/tests/test_trending.py`

**Interfaces:**
- Consumes: `lazyagent.tokens.AVAX_TOKENS` (list of `Token` with `.address: str | None`, checksummed).
- Produces (in `lazyagent.trending`):
  - `TokenInfo(symbol: str, name: str, address: str)` (frozen dataclass)
  - `Pool(token: TokenInfo, price_usd: float, volume_24h: float, change_24h: float, liquidity_usd: float, dex: str, trending: int | None = None)` (frozen)
  - `Trending(symbol, name, address: str, price_usd, volume_24h, change_24h, liquidity_usd: float, dex: str)` (frozen)
  - `parse_pools(body: dict, trending: bool = False) -> list[Pool]`
  - `is_memecoin(token: TokenInfo) -> bool`
  - `rank(pools: list[Pool]) -> list[Trending]`
  - `to_json(items: list[Trending]) -> str` — `{"source", "note", "tokens": [asdict(Trending)...]}`
  - Constants `API`, `TIMEOUT_S = 15`, `TTL_S = 60`, `MIN_LIQUIDITY_USD = 10_000`, `TOP_N = 10`, `UNAVAILABLE = "Couldn't load trending tokens right now."`

- [ ] **Step 1: Add the fixtures** (real GeckoTerminal responses captured 2026-10-15, trimmed to the fields we read; requested with `include=base_token,dex`)

`agent/tests/fixtures/geckoterminal_trending.json` — trending order: p33 (liquid staking), BTC.b (major), JOE (protocol), sAVAX (staked), USDC.e ×2 (stable), COQ (meme):

```json
{
  "data": [
    {"id": "avax_0xabfc76e5126941ab22858906b9d65e4b09fb3d1a", "type": "pool", "attributes": {"address": "0xabfc76e5126941ab22858906b9d65e4b09fb3d1a", "name": "p33 / PHAR 1%", "base_token_price_usd": "0.132111473860289", "price_change_percentage": {"h24": "-2.793"}, "volume_usd": {"h24": "106008.156592465"}, "reserve_in_usd": "444818.5236"}, "relationships": {"base_token": {"data": {"id": "avax_0x26e9dbe75aed331e41272bece932ff1b48926ca9", "type": "token"}}, "dex": {"data": {"id": "pharaoh-exchange-v3", "type": "dex"}}}},
    {"id": "avax_0x5ca009013f6b898d134b6798b336a4592f3b4af2", "type": "pool", "attributes": {"address": "0x5ca009013f6b898d134b6798b336a4592f3b4af2", "name": "BTC.b / WAVAX 0.05%", "base_token_price_usd": "81343.7253854092", "price_change_percentage": {"h24": "-2.474"}, "volume_usd": {"h24": "5147349.74684319"}, "reserve_in_usd": "3157451.7132"}, "relationships": {"base_token": {"data": {"id": "avax_0x152b9d0fdc40c096757f570a51e494bd4b943e50", "type": "token"}}, "dex": {"data": {"id": "pharaoh-exchange-v3", "type": "dex"}}}},
    {"id": "avax_0x454e67025631c065d3cfad6d71e6892f74487a15", "type": "pool", "attributes": {"address": "0x454e67025631c065d3cfad6d71e6892f74487a15", "name": "JOE / WAVAX", "base_token_price_usd": "0.0327066838304185", "price_change_percentage": {"h24": "-11.986"}, "volume_usd": {"h24": "20788.7779236591"}, "reserve_in_usd": "284132.5235"}, "relationships": {"base_token": {"data": {"id": "avax_0x6e84a6216ea6dacc71ee8e6b0a5b7322eebc0fdd", "type": "token"}}, "dex": {"data": {"id": "traderjoe", "type": "dex"}}}},
    {"id": "avax_0x65b9016c376604fe0af38c1e336ffcec0f8ecbbd", "type": "pool", "attributes": {"address": "0x65b9016c376604fe0af38c1e336ffcec0f8ecbbd", "name": "sAVAX / WAVAX 0.01%", "base_token_price_usd": "12.3009073143183", "price_change_percentage": {"h24": "-5.977"}, "volume_usd": {"h24": "123550.728584656"}, "reserve_in_usd": "71676.464"}, "relationships": {"base_token": {"data": {"id": "avax_0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be", "type": "token"}}, "dex": {"data": {"id": "pharaoh-exchange-v3", "type": "dex"}}}},
    {"id": "avax_0xa389f9430876455c36478deea9769b7ca4e3ddb1", "type": "pool", "attributes": {"address": "0xa389f9430876455c36478deea9769b7ca4e3ddb1", "name": "USDC.e / WAVAX", "base_token_price_usd": "0.998254862297838", "price_change_percentage": {"h24": "-0.281"}, "volume_usd": {"h24": "36437.7695970232"}, "reserve_in_usd": "433899.7943"}, "relationships": {"base_token": {"data": {"id": "avax_0xa7d7079b0fead91f3e65f86e8915cb59c1a4c664", "type": "token"}}, "dex": {"data": {"id": "traderjoe", "type": "dex"}}}},
    {"id": "avax_0x67926d973cd8ee876ad210faaf7dffa99e414acf", "type": "pool", "attributes": {"address": "0x67926d973cd8ee876ad210faaf7dffa99e414acf", "name": "USDC.e / JOE", "base_token_price_usd": "0.99825486229784", "price_change_percentage": {"h24": "-0.281"}, "volume_usd": {"h24": "24794.6682504022"}, "reserve_in_usd": "287122.5124"}, "relationships": {"base_token": {"data": {"id": "avax_0xa7d7079b0fead91f3e65f86e8915cb59c1a4c664", "type": "token"}}, "dex": {"data": {"id": "traderjoe", "type": "dex"}}}},
    {"id": "avax_0x41ab86eecbd110a82ca602d032a461f453066f1e", "type": "pool", "attributes": {"address": "0x41ab86eecbd110a82ca602d032a461f453066f1e", "name": "COQ / WAVAX", "base_token_price_usd": "0.000000121646674452088", "price_change_percentage": {"h24": "-5.1"}, "volume_usd": {"h24": "16937.5461895205"}, "reserve_in_usd": "623823.6468"}, "relationships": {"base_token": {"data": {"id": "avax_0x420fca0121dc28039145009570975747295f2329", "type": "token"}}, "dex": {"data": {"id": "traderjoe", "type": "dex"}}}}
  ],
  "included": [
    {"id": "avax_0x26e9dbe75aed331e41272bece932ff1b48926ca9", "type": "token", "attributes": {"address": "0x26e9dbe75aed331e41272bece932ff1b48926ca9", "name": "Pharaoh Liquid Staking Token", "symbol": "p33"}},
    {"id": "pharaoh-exchange-v3", "type": "dex", "attributes": {"name": "Pharaoh Exchange V3"}},
    {"id": "avax_0x152b9d0fdc40c096757f570a51e494bd4b943e50", "type": "token", "attributes": {"address": "0x152b9d0fdc40c096757f570a51e494bd4b943e50", "name": "Bitcoin", "symbol": "BTC.b"}},
    {"id": "avax_0x6e84a6216ea6dacc71ee8e6b0a5b7322eebc0fdd", "type": "token", "attributes": {"address": "0x6e84a6216ea6dacc71ee8e6b0a5b7322eebc0fdd", "name": "JoeToken", "symbol": "JOE"}},
    {"id": "traderjoe", "type": "dex", "attributes": {"name": "LFJ"}},
    {"id": "avax_0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be", "type": "token", "attributes": {"address": "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be", "name": "Staked AVAX", "symbol": "sAVAX"}},
    {"id": "avax_0xa7d7079b0fead91f3e65f86e8915cb59c1a4c664", "type": "token", "attributes": {"address": "0xa7d7079b0fead91f3e65f86e8915cb59c1a4c664", "name": "USD Coin", "symbol": "USDC.e"}},
    {"id": "avax_0x420fca0121dc28039145009570975747295f2329", "type": "token", "attributes": {"address": "0x420fca0121dc28039145009570975747295f2329", "name": "COQINU", "symbol": "COQ"}}
  ]
}
```

`agent/tests/fixtures/geckoterminal_arena.json` — Arena DEX by 24h volume: AVXTO, GATOR (memes ≥ $10k), NOCHILL (meme, $2,050 liquidity):

```json
{
  "data": [
    {"id": "avax_0x2bdebde7e1088e42aafef104b5f7457aca5ab86f", "type": "pool", "attributes": {"address": "0x2bdebde7e1088e42aafef104b5f7457aca5ab86f", "name": "AVXTO / WAVAX", "base_token_price_usd": "0.00000518650114051699", "price_change_percentage": {"h24": "9.621"}, "volume_usd": {"h24": "597.4983591645"}, "reserve_in_usd": "15523.1697"}, "relationships": {"base_token": {"data": {"id": "avax_0xf56cecc07d97ac50630022cf84c19e612ae8c93d", "type": "token"}}, "dex": {"data": {"id": "arena-dex", "type": "dex"}}}},
    {"id": "avax_0x3c5560226ee5861a58707bbf9247c16cf90e0a8c", "type": "pool", "attributes": {"address": "0x3c5560226ee5861a58707bbf9247c16cf90e0a8c", "name": "GATOR / WAVAX", "base_token_price_usd": "0.00000282056862822005", "price_change_percentage": {"h24": "4.946"}, "volume_usd": {"h24": "523.7351283647"}, "reserve_in_usd": "11541.8039"}, "relationships": {"base_token": {"data": {"id": "avax_0x1a31a8fd8bacb64b32dbcdcf5b2215f58baf70c1", "type": "token"}}, "dex": {"data": {"id": "arena-dex", "type": "dex"}}}},
    {"id": "avax_0x92f020fb0ae592bdca43ea4f4386aa3237f6e5d1", "type": "pool", "attributes": {"address": "0x92f020fb0ae592bdca43ea4f4386aa3237f6e5d1", "name": "NOCHILL / WAVAX", "base_token_price_usd": "0.000322432119406396", "price_change_percentage": {"h24": "0"}, "volume_usd": {"h24": "3.0235432146"}, "reserve_in_usd": "2049.9008"}, "relationships": {"base_token": {"data": {"id": "avax_0xacfb898cff266e53278cc0124fc2c7c94c8cb9a5", "type": "token"}}, "dex": {"data": {"id": "arena-dex", "type": "dex"}}}}
  ],
  "included": [
    {"id": "arena-dex", "type": "dex", "attributes": {"name": "Arena DEX"}},
    {"id": "avax_0xf56cecc07d97ac50630022cf84c19e612ae8c93d", "type": "token", "attributes": {"address": "0xf56cecc07d97ac50630022cf84c19e612ae8c93d", "name": "AVAX Toolbox Token", "symbol": "AVXTO"}},
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

from lazyagent.trending import Pool, TokenInfo, is_memecoin, parse_pools, rank, to_json

FIXTURES = Path(__file__).parent / "fixtures"
COQ = "0x420fca0121dc28039145009570975747295f2329"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def pools() -> list[Pool]:
    return parse_pools(load("geckoterminal_trending.json"), trending=True) + parse_pools(load("geckoterminal_arena.json"))


def meme(symbol: str, n: int, liquidity: float = 50_000, volume: float = 1_000, trending: int | None = None) -> Pool:
    token = TokenInfo(symbol, f"{symbol} coin", f"0x{n:040x}")
    return Pool(token, 0.01, volume, 1.0, liquidity, "LFJ", trending)


def test_parse_pools_reads_token_numbers_and_dex_name():
    parsed = parse_pools(load("geckoterminal_trending.json"), trending=True)
    assert len(parsed) == 7
    coq = parsed[6]
    assert coq.token == TokenInfo("COQ", "COQINU", COQ)
    assert coq.price_usd == 0.000000121646674452088
    assert coq.volume_24h == 16937.5461895205
    assert coq.change_24h == -5.1
    assert coq.liquidity_usd == 623823.6468
    assert coq.dex == "LFJ"
    assert coq.trending == 6
    assert parsed[0].trending == 0


def test_parse_pools_without_trending_has_no_position():
    assert {p.trending for p in parse_pools(load("geckoterminal_arena.json"))} == {None}
    assert parse_pools(load("geckoterminal_arena.json"))[0].dex == "Arena DEX"


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


def test_memecoin_filter_excludes_majors_stables_wrapped_staked_and_protocol_tokens():
    by_symbol = {p.token.symbol: is_memecoin(p.token) for p in pools()}
    assert by_symbol == {
        "p33": False,  # "Pharaoh Liquid Staking Token"
        "BTC.b": False,  # Avalanche registry
        "JOE": False,  # protocol token
        "sAVAX": False,  # staked AVAX
        "USDC.e": False,  # stablecoin
        "COQ": True,
        "AVXTO": True,
        "GATOR": True,
        "NOCHILL": True,  # a meme — dropped later for low liquidity
    }


def test_memecoin_filter_matches_registry_addresses_in_any_case():
    assert not is_memecoin(TokenInfo("XYZ", "XYZ", "0x152b9d0FdC40C096757F570A51E494bd4b943E50"))  # BTC.b checksummed
    assert not is_memecoin(TokenInfo("XYZ", "XYZ", "0xB31F66AA3C1E785363F0875A1B74E27B85FD66C7"))  # WAVAX upper-case


def test_memecoin_filter_symbol_and_name_rules():
    def ok(symbol, name="Some Coin"):
        return is_memecoin(TokenInfo(symbol, name, "0x" + "1" * 40))

    assert not ok("avUSD") and not ok("AUSD") and not ok("EURC") and not ok("XAUt0")
    assert not ok("WAVAX") and not ok("ggAVAX") and not ok("WBTC") and not ok("WETH.e") and not ok("LINK.e")
    assert not ok("FOO", "Wrapped Foo") and not ok("BAR", "Bridged Bar")
    assert ok("KET") and ok("NOCHILL", "AVAX HAS NO CHILL")


def test_rank_fixture_end_to_end():
    ranked = rank(pools())
    assert [t.symbol for t in ranked] == ["COQ", "AVXTO", "GATOR"]  # NOCHILL: $2,050 liquidity
    assert ranked[0].address == COQ and ranked[0].dex == "LFJ" and ranked[0].change_24h == -5.1
    assert ranked[1].dex == "Arena DEX"


def test_rank_keeps_one_entry_per_token_from_its_deepest_pool_and_best_trending_position():
    shallow = meme("DOG", 1, liquidity=20_000, volume=9_000, trending=3)
    deep = replace(shallow, liquidity_usd=900_000, volume_24h=100, dex="Pharaoh Exchange V3", trending=None)
    other = meme("CAT", 2, trending=5)
    ranked = rank([other, deep, shallow])
    assert [t.symbol for t in ranked] == ["DOG", "CAT"]
    assert ranked[0].liquidity_usd == 900_000 and ranked[0].dex == "Pharaoh Exchange V3"


def test_rank_liquidity_threshold_applies_to_the_deepest_pool():
    assert rank([meme("THIN", 1, liquidity=9_999.99)]) == []
    assert [t.symbol for t in rank([meme("EDGE", 1, liquidity=10_000)])] == ["EDGE"]


def test_rank_puts_trending_first_then_volume():
    ranked = rank([meme("A", 1, volume=10), meme("B", 2, volume=500), meme("C", 3, volume=1, trending=4), meme("D", 4, volume=1, trending=0)])
    assert [t.symbol for t in ranked] == ["D", "C", "B", "A"]


def test_rank_caps_at_ten():
    ranked = rank([meme(f"M{i}", i, volume=i) for i in range(1, 16)])
    assert len(ranked) == 10
    assert ranked[0].symbol == "M15"


def test_to_json_lists_tokens_for_the_model():
    body = json.loads(to_json(rank(pools())))
    assert body["tokens"][0] == {
        "symbol": "COQ",
        "name": "COQINU",
        "address": COQ,
        "price_usd": 0.000000121646674452088,
        "volume_24h": 16937.5461895205,
        "change_24h": -5.1,
        "liquidity_usd": 623823.6468,
        "dex": "LFJ",
    }
    assert "contract address" in body["note"]
    assert json.loads(to_json([]))["tokens"] == []
```

- [ ] **Step 3: Run to verify they fail**

Run: `uv run --directory agent pytest tests/test_trending.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lazyagent.trending'`.

- [ ] **Step 4: Implement** — create `agent/lazyagent/trending.py`

```python
"""Trending Avalanche memecoins from GeckoTerminal (read-only, live mainnet data)."""

import json
from dataclasses import asdict, dataclass

from .tokens import AVAX_TOKENS

API = "https://api.geckoterminal.com/api/v2/networks/avax"
TIMEOUT_S = 15
TTL_S = 60
MIN_LIQUIDITY_USD = 10_000
TOP_N = 10
UNAVAILABLE = "Couldn't load trending tokens right now."

WAVAX = "0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7"
# Protocol / governance tokens that keep showing up in Avalanche trending but aren't memes.
# GeckoTerminal has no reliable meme flag (its categories tag JOE as "joe-biden"), so this is curated.
# See docs/research/2026-10-15-avalanche-trending-memecoins.md.
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
    price_usd: float
    volume_24h: float
    change_24h: float
    liquidity_usd: float
    dex: str


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_pools(body: dict, trending: bool = False) -> list[Pool]:
    """GeckoTerminal pools JSON (requested with include=base_token,dex) → pools. Pools whose
    base token isn't in `included` are skipped; missing numbers read as 0."""
    included = {(i.get("type"), i.get("id")): i.get("attributes") or {} for i in body.get("included") or []}
    pools = []
    for n, p in enumerate(body.get("data") or []):
        attrs, rel = p.get("attributes") or {}, p.get("relationships") or {}
        token = included.get(("token", ((rel.get("base_token") or {}).get("data") or {}).get("id")))
        if not token or not token.get("address") or not token.get("symbol"):
            continue
        dex_id = ((rel.get("dex") or {}).get("data") or {}).get("id") or "unknown"
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


def rank(pools: list[Pool]) -> list[Trending]:
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
        Trending(p.token.symbol, p.token.name, p.token.address, p.price_usd, p.volume_24h, p.change_24h, p.liquidity_usd, p.dex)
        for _, p in kept[:TOP_N]
    ]


def to_json(items: list[Trending]) -> str:
    return json.dumps(
        {
            "source": "GeckoTerminal, live Avalanche mainnet",
            "note": "Buy with propose_swap using the token's contract address as token_out.",
            "tokens": [asdict(t) for t in items],
        }
    )
```

- [ ] **Step 5: Run to verify they pass**

Run: `uv run --directory agent pytest tests/test_trending.py -q`
Expected: PASS (13 tests).

- [ ] **Step 6: Commit**

```bash
git add agent/lazyagent/trending.py agent/tests/test_trending.py agent/tests/fixtures
git commit -m "feat(agent): parse, filter and rank Avalanche trending memecoins"
```

---

### Task 3: GeckoTerminal source and 60 s cache

**Files:**
- Modify: `agent/lazyagent/trending.py` (imports; append source + cache)
- Modify: `agent/tests/fakes.py` (append `FakeTrendingSource`)
- Test: `agent/tests/test_trending_source.py`

**Interfaces:**
- Consumes: `parse_pools`, `rank`, `Pool`, `Trending`, `API`, `TIMEOUT_S`, `TTL_S` from Task 2.
- Produces (in `lazyagent.trending`):
  - `class TrendingSource(Protocol): async def pools(self) -> list[Pool]`
  - `GeckoTerminalSource(base: str = API)` with `async pools() -> list[Pool]` — trending pools (with positions) + Arena DEX pools; raises on HTTP error (`urllib.error.HTTPError`), unreachable (`OSError`), non-JSON (`ValueError`).
  - `TrendingTokens(source: TrendingSource, ttl: float = TTL_S, clock: Callable[[], float] = time.monotonic)` with `.source` and `async list() -> list[Trending]` (cached `ttl` seconds; exceptions propagate, not cached).
  - `TRENDING: TrendingTokens` — process-wide instance over `GeckoTerminalSource()`.
- Produces (in `tests/fakes.py`): `FakeTrendingSource(pools: list[Pool] | None = None)` with `.result`, `.calls`, `.fail` (raises `ConnectionError` when set).

- [ ] **Step 1: Add the fake** — append to `agent/tests/fakes.py`:

```python


class FakeTrendingSource:
    """Stands in for GeckoTerminal so tests never hit the network."""

    def __init__(self, pools=None):
        self.result = pools if pools is not None else []
        self.calls = 0
        self.fail = False

    async def pools(self):
        self.calls += 1
        if self.fail:
            raise ConnectionError("HTTP Error 429: Too Many Requests")
        return self.result
```

- [ ] **Step 2: Write the failing tests** — `agent/tests/test_trending_source.py`

```python
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fakes import FakeTrendingSource

from lazyagent.trending import GeckoTerminalSource, Pool, TokenInfo, TrendingTokens

FIXTURES = Path(__file__).parent / "fixtures"
COQ_POOL = Pool(TokenInfo("COQ", "COQINU", "0x420fca0121dc28039145009570975747295f2329"), 1.2e-7, 16_937.5, -5.1, 623_823.6, "LFJ", 0)


def serve(routes: dict[str, tuple[int, bytes]]):
    """Local stand-in for GeckoTerminal: path prefix → (status, body). Records request paths."""
    seen: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            status, body = next((v for k, v in routes.items() if self.path.startswith(k)), (404, b"{}"))
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, seen


def fixture(name: str) -> tuple[int, bytes]:
    return 200, (FIXTURES / name).read_bytes()


async def test_source_fetches_trending_and_arena_pools():
    server, seen = serve({"/trending_pools": fixture("geckoterminal_trending.json"), "/dexes/arena-dex/pools": fixture("geckoterminal_arena.json")})
    try:
        pools = await GeckoTerminalSource(f"http://127.0.0.1:{server.server_port}").pools()
    finally:
        server.shutdown()
    assert [p.token.symbol for p in pools] == ["p33", "BTC.b", "JOE", "sAVAX", "USDC.e", "USDC.e", "COQ", "AVXTO", "GATOR", "NOCHILL"]
    assert [p.trending for p in pools][-3:] == [None, None, None]
    assert seen == [
        "/trending_pools?include=base_token,dex",
        "/dexes/arena-dex/pools?sort=h24_volume_usd_desc&include=base_token,dex",
    ]


async def test_source_raises_on_rate_limit():
    server, _ = serve({"/trending_pools": (429, b'{"status":"429","error":"Rate limited"}')})
    try:
        with pytest.raises(urllib.error.HTTPError):
            await GeckoTerminalSource(f"http://127.0.0.1:{server.server_port}").pools()
    finally:
        server.shutdown()


async def test_source_raises_on_non_json_body():
    server, _ = serve({"/": (200, b"<html>oops</html>")})
    try:
        with pytest.raises(ValueError):
            await GeckoTerminalSource(f"http://127.0.0.1:{server.server_port}").pools()
    finally:
        server.shutdown()


async def test_source_raises_when_unreachable():
    with pytest.raises(OSError):
        await GeckoTerminalSource("http://127.0.0.1:1").pools()


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


async def test_cache_serves_within_60_seconds_and_refetches_after():
    source, clock = FakeTrendingSource([COQ_POOL]), Clock()
    trending = TrendingTokens(source, clock=clock)
    first = await trending.list()
    clock.t += 59.9
    assert await trending.list() == first and source.calls == 1
    clock.t += 0.2
    await trending.list()
    assert source.calls == 2


async def test_errors_are_not_cached():
    source, clock = FakeTrendingSource([COQ_POOL]), Clock()
    trending = TrendingTokens(source, clock=clock)
    source.fail = True
    with pytest.raises(ConnectionError):
        await trending.list()
    source.fail = False
    assert [t.symbol for t in await trending.list()] == ["COQ"]
    assert source.calls == 2


async def test_an_empty_list_is_cached_too():
    source = FakeTrendingSource([])
    trending = TrendingTokens(source, clock=Clock())
    assert await trending.list() == [] and await trending.list() == []
    assert source.calls == 1
```

- [ ] **Step 3: Run to verify they fail**

Run: `uv run --directory agent pytest tests/test_trending_source.py -q`
Expected: FAIL — `ImportError: cannot import name 'GeckoTerminalSource' from 'lazyagent.trending'`.

- [ ] **Step 4: Implement** — in `agent/lazyagent/trending.py` replace the import block

```python
import json
from dataclasses import asdict, dataclass

from .tokens import AVAX_TOKENS
```

with

```python
import asyncio
import json
import time
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Protocol

from .tokens import AVAX_TOKENS
```

and append to the end of the file:

```python


class TrendingSource(Protocol):
    async def pools(self) -> list[Pool]: ...


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as res:
        return json.loads(res.read())


class GeckoTerminalSource:
    """Trending pools across all Avalanche DEXs, plus Arena DEX's busiest pools (where memecoins graduate to)."""

    def __init__(self, base: str = API):
        self.base = base

    async def pools(self) -> list[Pool]:
        trending = await asyncio.to_thread(_get, f"{self.base}/trending_pools?include=base_token,dex")
        arena = await asyncio.to_thread(_get, f"{self.base}/dexes/arena-dex/pools?sort=h24_volume_usd_desc&include=base_token,dex")
        return parse_pools(trending, trending=True) + parse_pools(arena)


class TrendingTokens:
    """The ranked list, cached for 60 s. Errors propagate and are never cached."""

    def __init__(self, source: TrendingSource, ttl: float = TTL_S, clock: Callable[[], float] = time.monotonic):
        self.source = source
        self.ttl = ttl
        self.clock = clock
        self._items: list[Trending] | None = None
        self._at = 0.0

    async def list(self) -> list[Trending]:
        now = self.clock()
        if self._items is not None and now - self._at < self.ttl:
            return self._items
        items = rank(await self.source.pools())
        self._items, self._at = items, now
        return items


TRENDING = TrendingTokens(GeckoTerminalSource())
```

- [ ] **Step 5: Run to verify they pass**

Run: `uv run --directory agent pytest tests/test_trending_source.py tests/test_trending.py -q`
Expected: PASS (20 tests).

- [ ] **Step 6: Optional live smoke check** (hits the real API once; not part of the suite)

Run: `uv run --directory agent python -c "import asyncio; from lazyagent.trending import TRENDING; [print(t.symbol, t.change_24h, t.dex, t.address) for t in asyncio.run(TRENDING.list())]"`
Expected: a handful of memecoins (2026-10-15: COQ, AVXTO, GATOR, WOLFI, SUPER, GLADIUS, EMINI, MEOW). If a clear non-meme protocol token appears, add its address to `NOT_MEMES` (and the research note) — do not add symbol guesses.

- [ ] **Step 7: Commit**

```bash
git add agent/lazyagent/trending.py agent/tests/test_trending_source.py agent/tests/fakes.py
git commit -m "feat(agent): GeckoTerminal trending source with a 60 s cache"
```

---

### Task 4: `list_trending_tokens` tool and prompt line

**Files:**
- Modify: `agent/lazyagent/tools.py` (import, `TOOL_NAMES`, class attribute + method after `request_test_funds`, registration before `unsupported_action`)
- Modify: `agent/lazyagent/prompt.py` (one line before the "Bridging between networks" line)
- Modify: `agent/tests/test_tools.py` (`test_mcp_server_and_names`)
- Test: `agent/tests/test_trending_tools.py`

**Interfaces:**
- Consumes: `TRENDING`, `UNAVAILABLE`, `TrendingTokens`, `to_json`, `Pool`, `TokenInfo` from Tasks 2–3; `FakeTrendingSource` from `tests/fakes.py`; `ok`/`err` in `tools.py`.
- Produces: `WalletTools.trending: TrendingTokens` (class attribute, default `TRENDING`; tests assign an instance attribute), `async WalletTools.list_trending_tokens(args: dict) -> dict`; MCP tool `list_trending_tokens` (no args); `"mcp__wallet__list_trending_tokens"` last in `TOOL_NAMES`.

- [ ] **Step 1: Write the failing tests** — `agent/tests/test_trending_tools.py`

```python
import json

from fakes import FakeChain, FakeTrendingSource, Outbox

from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.trending import GeckoTerminalSource, Pool, TokenInfo, TrendingTokens

COQ = "0x420fca0121dc28039145009570975747295f2329"


def make(source: FakeTrendingSource) -> WalletTools:
    tools = WalletTools(FakeChain(), Outbox(), WalletContext(), Proposals())
    tools.trending = TrendingTokens(source)
    return tools


def text(result):
    return result["content"][0]["text"]


async def test_list_trending_tokens_returns_json_for_the_model():
    tools = make(FakeTrendingSource([Pool(TokenInfo("COQ", "COQINU", COQ), 1.2e-7, 16_937.5, -5.1, 623_823.6, "LFJ", 0)]))
    result = await tools.list_trending_tokens({})
    assert not result.get("is_error")
    [coq] = json.loads(text(result))["tokens"]
    assert coq["symbol"] == "COQ" and coq["address"] == COQ and coq["change_24h"] == -5.1 and coq["dex"] == "LFJ"


async def test_list_trending_tokens_works_without_an_active_wallet():
    tools = make(FakeTrendingSource([]))
    assert tools.ctx.address is None
    assert json.loads(text(await tools.list_trending_tokens({})))["tokens"] == []


async def test_list_trending_tokens_reports_a_friendly_error():
    source = FakeTrendingSource()
    source.fail = True
    result = await make(source).list_trending_tokens({})
    assert result["is_error"] is True
    assert text(result) == "Couldn't load trending tokens right now."


def test_default_trending_source_is_geckoterminal():
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
Expected: FAIL — `AttributeError: 'WalletTools' object has no attribute 'list_trending_tokens'` / `type object 'WalletTools' has no attribute 'trending'`, and the `TOOL_NAMES` assertion.

- [ ] **Step 3: Implement in `agent/lazyagent/tools.py`** (five small edits; nothing else)

After `from .tokens import find_token` add:

```python
from .trending import TRENDING, UNAVAILABLE, TrendingTokens, to_json
```

In `TOOL_NAMES`, append the name to the tuple:

```python
    for n in ("get_balances", "resolve_recipient", "propose_transfer", "propose_swap", "unsupported_action", "request_test_funds", "list_trending_tokens")
```

Between `request_test_funds` and `unsupported_action` methods insert:

```python
    trending: TrendingTokens = TRENDING  # shared 60 s cache; tests assign their own

    async def list_trending_tokens(self, args: dict) -> dict:
        try:
            return ok(to_json(await self.trending.list()))
        except Exception:
            return err(UNAVAILABLE)
```

In `build_mcp_server`, insert before the `tool("unsupported_action", ...)` entry:

```python
            tool(
                "list_trending_tokens",
                "Top trending Avalanche memecoins right now (live mainnet data from GeckoTerminal): symbol, name, contract address, USD price, 24h volume, 24h change, liquidity and main DEX. Read-only.",
                {"type": "object", "properties": {}},
            )(t.list_trending_tokens),
```

- [ ] **Step 4: Add the prompt line** — in `agent/lazyagent/prompt.py`, insert directly above `- Bridging between networks, schedules, ...`:

```text
- "What's trending", "hot memecoins on Avalanche" and similar → list_trending_tokens (live Avalanche mainnet data). Summarise the top three or so by symbol with their 24h change in one or two sentences and offer to buy one. To buy, call propose_swap with network "avalanche" and token_out set to the token's contract address from the list, not its symbol. A very new token may not exist on the Sandbox fork yet. If the list is empty or the tool errors, say so plainly.
```

- [ ] **Step 5: Run the agent suite**

Run: `uv run --directory agent pytest -q`
Expected: PASS (fork tests skip or pass as before; no test touches GeckoTerminal).

- [ ] **Step 6: Commit**

```bash
git add agent/lazyagent/tools.py agent/lazyagent/prompt.py agent/tests/test_tools.py agent/tests/test_trending_tools.py
git commit -m "feat(agent): list_trending_tokens tool and prompt routing"
```

---

### Task 5: Docs, spec deviations, full verification, manual check

**Files:**
- Modify: `CLAUDE.md`, `docs/superpowers/specs/2026-10-15-lazywallet-avax-trending-design.md`

- [ ] **Step 1: `CLAUDE.md`** — under "Wallet app conventions", after the Uniswap v4 bullet, add one line:

```markdown
- Trending Avalanche memecoins (`list_trending_tokens`) come from GeckoTerminal via `agent/lazyagent/trending.py` (read-only, 60 s cache); the filter's curated `NOT_MEMES` list and rules are explained in `docs/research/2026-10-15-avalanche-trending-memecoins.md`.
```

- [ ] **Step 2: Record planning decisions in the spec** — set `Status:` to `Implemented on feat-trending-avax`, and add a final section:

```markdown
## 7. Decisions made while planning

- Candidates = GeckoTerminal `trending_pools` (page 1) + Arena DEX's top pools by 24h volume; trending alone is almost all majors and protocol tokens.
- The data has no reliable meme flag (token categories are per-request and wrong, e.g. JOE → "joe-biden"), so besides the rules a short curated `NOT_MEMES` address list excludes protocol tokens (JOE, PHAR, BLACK, QI, FOLKS, ARENA, MUON, BEAM, ZRO, GUN, NXPC).
- Only each pool's base token is considered (price and 24h change are given for it). The `dex` field is GeckoTerminal's display name ("LFJ", "Arena DEX").
- The cache is one process-wide `TrendingTokens` read through a `WalletTools` class attribute, so `WalletTools.__init__`, `Session` and `server.py` are unchanged (fewer conflicts with the Kyber branch).
- An empty list is a normal result (`tokens: []`), not an error.
```

- [ ] **Step 3: Full verification**

Run: `pnpm test:py && pnpm build && pnpm lint`
Expected: all PASS.

- [ ] **Step 4: Manual check** (run `pnpm dev:sandbox`, `pnpm dev:agent`, `pnpm dev`; open `http://localhost:5174`)

1. Ask "What's trending on Avalanche?" → one or two spoken-friendly sentences naming a few memecoins with 24h change, and an offer to buy. No BTC.b / WAVAX / sAVAX / USDC / JOE / PHAR.
2. Ask again within a minute → same answer (cache; check the agent log shows no new GeckoTerminal error).
3. Say "Buy 1 AVAX of the first one" → the agent calls `propose_swap` with network avalanche and the **contract address** as token_out (visible in the agent log / tool call). Before the Kyber branch lands, expect the normal unsupported-token error, explained plainly.
4. Disconnect the network (or point `API` at `http://127.0.0.1:1` temporarily) and ask again after 60 s → "Couldn't load trending tokens right now." and no crash; restore.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-10-15-lazywallet-avax-trending-design.md
git commit -m "docs: trending Avalanche memecoins"
```

---

## Merge note

The Kyber branch merges first; rebase this branch onto it. Expected conflicts only in `agent/lazyagent/tools.py` (import line, `TOOL_NAMES` tuple, the method inserted before `unsupported_action`, the registration before `tool("unsupported_action", ...)`), `agent/lazyagent/prompt.py` (one line), `agent/tests/test_tools.py` (`TOOL_NAMES` list), `agent/tests/fakes.py` (appended class) and `CLAUDE.md` (one line). Keep both sides in each. After the rebase, re-run `pnpm test:py` and repeat manual step 3 — the buy should now produce a KyberSwap confirm card showing the COQ contract address.
