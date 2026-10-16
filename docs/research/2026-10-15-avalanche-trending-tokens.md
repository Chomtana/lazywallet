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
| 1 | COQ | -5.1% | $16,938 | $626,968 | LFJ |
| 2 | AVXTO | +9.6% | $597 | $15,686 | Arena DEX |
| 3 | GATOR | +4.9% | $524 | $11,650 | Arena DEX |
| 4 | WOLFI | -3.6% | $351 | $26,194 | Arena DEX |
| 5 | SUPER | -4.5% | $138 | $18,253 | Arena DEX |

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
