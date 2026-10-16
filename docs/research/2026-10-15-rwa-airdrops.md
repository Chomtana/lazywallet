# Research: RWA airdrops / points programs for an `airdrop` trending category

Date: 2026-10-15 · Status: research spike (no product code) · Context: `docs/superpowers/specs/2026-10-15-lazywallet-avax-trending-design.md`

Legend: **[P]** = primary source (official docs / on-chain), **[S]** = secondary (aggregator/news), **UNVERIFIED** = could not confirm today. Every "on-chain" line was checked with `cast` against `ethereum-rpc.publicnode.com` / `avalanche-c-chain-rpc.publicnode.com` on 2026-10-15. Liquidity numbers are GeckoTerminal / DexScreener, 2026-10-15.

> Points are tracked **off-chain** by each protocol against **real mainnet** activity. Anything we do on the Sandbox fork earns nothing — it is a demo of the flow only. The agent must say so.

## TL;DR

- **Live RWA programs a retail user can farm with a permissionless on-chain action on Ethereum/Avalanche: Re Points S2 (reUSD, ETH + AVAX), Theo thUSD points (ETH), Tori Cores S1 (ETH).** All three gate *minting* behind KYC, but buying the token on a DEX and **holding/staking** earns points.
- Avalanche RWA: only **Re** is live (reUSD on Avalanche, but tiny supply/liquidity). **Avant** (Avalanche-native avUSD) ended S1 on 2026-05-15; AVANT TGE "to be announced" — good "claim coming soon" story, nothing to farm.
- **No usable free live source of RWA points programs exists.** DefiLlama has no airdrop API (its airdrops page is behind Cloudflare and the frontend repo is private); its `/protocols` "tokenless" filter is a weak proxy (issuers like Anemoy/OpenTrade will never airdrop). Alphadrops has an undocumented public JSON but only 7 RWA entries, mostly off-chain perps; its official API is paid.
- **Recommendation:** a small **curated, checked-in list** (what to do, contracts, KYC, season dates, source) enriched **live** with DefiLlama TVL/tokenless status and GeckoTerminal liquidity. Demo: "What RWA airdrops can I farm?" → Re / Theo / Tori → "stake thUSD for Theo points" = Uniswap v4 swap (already supported) + ERC-4626 `deposit`.

## 1. RWA points / airdrop programs (Ethereum, Avalanche)

### 1a. Live — recommendable

| Program | Chain(s) | What qualifies | Permissionless on-chain? | KYC | Token / season | Source (date) |
|---|---|---|---|---|---|---|
| **Re Points S2** (reinsurance yield; reUSD senior, reUSDe mezz.) | Ethereum, **Avalanche** (+ many others) | "Simply holding" reUSD/reUSDe; higher multiples for DeFi use (Curve, Pendle, Tangent, Pharaoh/Blackhole LPs). Referrals: referee 1.06x, referrer +6% | **Yes for holding** — tokens bought on a DEX. Simulated `transfer` from a pool to a random address succeeds on both chains **[P, on-chain]**. Mint is KYC-gated | Mint/redeem only (non-US) | $RE token is live. S1 2025-08-03 → 2026-05-31 (7% of supply). **S2 from 2026-06-01, ~6 months** (≥3.5% of supply) → ends ~Nov/Dec 2026 | [docs.re.xyz/re-points/about-re-points](https://docs.re.xyz/re-points/about-re-points.md) **[P]** (fetched 2026-10-15) |
| **Theo thUSD Points** | Ethereum (thUSD only) | Hold thUSD or stake to sthUSD ("Liquid"); Core/Core+/Boost lock vaults (higher multiplier); referrals +10% | **Yes for buy + stake**: thUSD on Uniswap v4; `sthUSD.deposit(uint256,address)` is a plain ERC-4626 with only `whenNotPaused` **[P, verified source]**. Mint (`ThUSDMinter`) is whitelisted RFQ | Mint only | **No THEO token** (CoinGecko 2026-10-15). Program announced 2026-06-25, no end date. thBILL points S1 stopped 2026-06-19 | [theo.xyz/articles/thusd-points-program](https://theo.xyz/articles/thusd-points-program) **[P]** (2026-06-25); docs.theo.xyz blocks bots (Cloudflare 403) |
| **Tori Finance Cores S1** (trUSD / strUSD synthetic dollar) | Ethereum | Hold trUSD, stake to strUSD, use in Morpho/Pendle/Curve, Ecosystem Vault; referrals 10% | Yes for holding/staking (ERC-20) — addresses **UNVERIFIED** | Mint only | **No token** ("Cores are not a promise of any token"). S1 began 2026-06-23 | [docs.tori.finance/resources/cores](https://docs.tori.finance/resources/cores) **[P]** (2026-10-15) |

### 1b. Live but weaker fit

| Program | Why weaker | Source (date) |
|---|---|---|
| Noon (USN/sUSN, T-bills + credit) | Already has NOON token; points convert monthly. Holding is permissionless, mint KYC | [docs.noon.capital rewards](https://docs.noon.capital/4.-usdnoon/rewards) **[P]** (2026-10-15) |
| Ondo Perps (Ondo Points) | Off-chain perps account; only the USDC deposit is on-chain. Restricted jurisdictions | [docs.ondoperps.xyz](https://docs.ondoperps.xyz) **[P]**; alphadrops (added 2026-07-07) **[S]** |
| xStocks xPoints S1 | Mainly Solana; Ethereum eligibility **UNVERIFIED** | Kraken FAQ (2026-03-26), CoinDesk (2026-03-10) **[S]** |
| Upshift Points | Vault platform (some RWA vaults), on ETH + AVAX; current season **UNVERIFIED** | docs.upshift.finance **[P]**; alphadrops (2026-08-01) **[S]** |
| Falcon Miles S2, Pareto, Spark SPK points | Season status in 2026 **UNVERIFIED** / not really RWA farming | docs.falcon.finance (lastmod 2025-12-10), paragraph.com/@pareto (2025), docs.spark.finance |
| Meridian (Ethereal), QFEX, Arcus, RWAPerp, Huma | Not on ETH/AVAX (Robinhood Chain, Arbitrum, X Layer, Solana) and/or off-chain perps | alphadrops JSON 2026-10-15 **[S]** |

### 1c. Ended — do not recommend

| Program | Status | Source |
|---|---|---|
| **Avant S1** (avUSD/savUSD, Avalanche-native) | Ended 2026-05-15; allocation preview live, **AVANT TGE/claim "to be announced"**; no S2 in docs. DefiLlama still shows no token (`parent#avant-protocol` gecko_id null) | [docs.avantprotocol.com …/avant-season-1-airdrop](https://docs.avantprotocol.com/rewards-program/avant-season-1-airdrop) **[P]** (2026-10-15) |
| Sierra Peaks (Avalanche) | Ended end of Sept 2026; SGT TGE Oct 2026 | docs.sierra.money **[P]** |
| Cap Homestead | Ended 2026-07-23; CAP token done | docs.cap.app **[P]** |
| Plume Points S2 | Accrual ended 2026-03-31 | coingabbar **[S]** |
| Maple Syrup Drips, Usual Pills, OpenEden Bills, Spark Savings AVAX | Ended/archived (2025 – Jun 2026) | respective docs **[P]** |
| Theo thBILL points S1 | Stopped 2026-06-19 | theo.xyz post (2026-06-25) **[P]** |

No points program found (low-confidence negatives for some): Midas, Securitize, Superstate, Spiko, Centrifuge, Grove (one unverified MEXC repost claims "Grove Points"), Sky, Hashnote, Untangled, Dinari.

### 1d. Non-RWA programs on Avalanche (for context)

| Program | Category | Qualifying action | Permissionless C-Chain? | Status | Source (date) |
|---|---|---|---|---|---|
| Suzaku Points S2 | Restaking | Deposit SUZ/AUSD/BTC.b/sAVAX… into restaking vaults; 2.75% SUZ reserved for future seasons | Yes | Started 2025-07-31, end TBD — **live in Oct 2026 UNVERIFIED** | docs.suzaku.network (fetched 2026-10-15) |
| Aave V4 WAVAX incentives (Merkl) | Lending | Supply USDt/USDC on Aave V4 Hub, borrow WAVAX | Yes | **Live**, weekly campaigns (2026-10-08 → 10-16). Direct WAVAX yield, not points | api.merkl.xyz/v4/opportunities?chainId=43114&status=LIVE (2026-10-15) |
| Extended points | Perps (off-chain) | Trade; Avalanche only a deposit route | No | Live, weekly | docs.extended.exchange (2026-10-06) |
| The Moats / Arena V2 staking | Staking/SocialFi | Stake/lock tokens | Yes | Arena V2 date not announced — **UNVERIFIED** | egamers.io (2026-09-06) |
| Retro9000 C-Chain | Builder grants | AVAX burned by a project's contracts | Builder-facing | Round 4 from 2026-06-01; probably over — **UNVERIFIED** | avalanche.com blog (2026-05-27) |
| Ended | GoGoPool/Hypha (shut down 2026-08-15), Suzaku S1, Blackhole and Arena airdrops (2024–25) | | | | hypha.sh, docs |

## 2. Data sources

| Source | Endpoint | Key / limits | RWA filter | Chain filter | Verdict |
|---|---|---|---|---|---|
| DefiLlama airdrops page | `defillama.com/airdrops` | Cloudflare 403 to curl/WebFetch; frontend repo `DefiLlama/defillama-app` now 404 (private). No `/airdrops` route on `api.llama.fi` (404), not in free or pro OpenAPI (`DefiLlama/api-docs`) | — | — | **No API.** |
| DefiLlama `/protocols` | `GET https://api.llama.fi/protocols` (~9 MB, 8,727 protocols) | No key; `cache-control: max-age=1798`; no published free rate limit | `category == "RWA"` (+ `tags`, e.g. "Treasury Bills") | `chains`, `chainTvls.Ethereum/Avalanche` | **Useful for enrichment.** "Tokenless" = `symbol == "-"` and no `gecko_id`, and the parent (from `GET /lite/protocols2` → `parentProtocols`) has no token either. 107 tokenless RWA protocols overall; 24 on ETH/AVAX, but the top ones are issuers (Anemoy $334M, OpenTrade $247M) with no points. Also gives `referralUrl`, `change_7d` |
| Alphadrops | `GET https://alphadrops.net/api/airdrops` (undocumented, used by its site; robots.txt allows it) | No key today. Query params ignored (169 rows, filter client-side). Official `/api/v1/airdrops` is a **paid** Bearer-key API | `categories` contains `"RWA"` (7 rows, 5 active) | `blockchains` | Good for **discovery** only; links carry the site's referral codes; RWA coverage thin and off-chain-perps heavy. Not for runtime |
| CryptoRank drophunting | `api.cryptorank.io/v3/drophunting/...` | 401 without key; drophunting tasks on the Business plan ($9,490/yr); free tier 10 req/min | yes | yes | Too expensive |
| airdrops.io | `wp-json/wp/v2/airdrop` | 401 (auth required) | — | — | No |
| Merkl | `GET https://api.merkl.xyz/v4/opportunities?chainId=43114&status=LIVE` | No key | no | yes | Live **incentive** campaigns (not points), useful for Avalanche |

Sample — DefiLlama `/protocols` row (2026-10-15, trimmed):

```json
{"id":"8604","name":"Theo Network thUSD","slug":"theo-network-thusd","symbol":"-","gecko_id":null,
 "category":"RWA","chains":["Ethereum"],"tvl":132160137.6,"change_7d":-0.068,"url":"https://app.theo.xyz/",
 "parentProtocol":"parent#theo","tags":["Tokenized Trading Strategies"],
 "referralUrl":"https://app.theo.xyz/invite?invite=defillama"}
{"id":"6223","name":"Avant avUSD","symbol":"-","gecko_id":null,"category":"Onchain Capital Allocator",
 "chains":["Avalanche"],"tvl":120191095.5,"change_7d":-3.97,"parentProtocol":"parent#avant-protocol"}
```

Sample — Alphadrops `/api/airdrops` row (2026-10-15, trimmed; other fields: `description`, `tasks[]`, `website`, `fundingAmount`, `claimLink`, `estimatedValue`):

```json
{"name":"Ondo Perps","slug":"ondoperps","status":"active","categories":["Perps","RWA"],
 "blockchains":["Ethereum"],"hasPoints":true,"isClaimable":false,"addedDate":"2026-07-07T06:33:37Z"}
```

## 3. Feasibility on the Sandbox forks

Yes: the qualifying actions for the recommended programs are plain contract calls (ERC-20 swap/hold, ERC-4626 `deposit`) that work on an Anvil fork. **Points are not earned on a fork** — demo-only.

| Candidate | Network | Action on fork | Contracts (verified on-chain 2026-10-15) | How to get the input token on the fork |
|---|---|---|---|---|
| **Theo: stake thUSD → sthUSD** | Ethereum | `thUSD.approve(sthUSD, x)` then `sthUSD.deposit(x, user)` (ERC-4626; `maxDeposit` = uint256 max, `paused()` = false) | thUSD `0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3` (6 dec, supply 132.3M); sthUSD `0xA808Bc9775cb41c52C7842f8b50427fE7A770326` ("Staked thUSD", `asset()` = thUSD). Redeem is async (`initiateRedeem` → `redeem`) | Uniswap **v4** thUSD/USDC 0.01% pool id `0xb30bf32e…594b5a0d` (~$3.6M liquidity) — fits the existing v4 swap path; pool key (tickSpacing/hooks) **UNVERIFIED**, needs a fork test. Or faucet storage write |
| **Re: hold reUSD** | Ethereum (+ Avalanche) | Hold only — buying it is the action | reUSD ETH `0x5086bf358635B81D8C47C66d1C8b9E567Db70c72` ("Re Protocol Deposit Token", proxy, supply 279.1M); reUSD AVAX `0x180aF87b47Bf272B2df59dccf2D76a6eaFa625Bf` (supply 422.5k); reUSDe ETH `0xdDC0f880ff6e4e22E4B74632fBb43Ce4DF6cCC5a`. Addresses from [docs.re.xyz/products/smart-contracts](https://docs.re.xyz/products/smart-contracts.md) | ETH: Fluid reUSD/USDT (~$25M liq), Curve reUSD/sUSDe (~$2.3M), Curve reUSD/USDC (~$0.45M) — not Uniswap v4, so needs the Kyber aggregator path or the faucet. AVAX: only ~$6k (Blackhole v3) → faucet |
| (Avant: stake avUSD → savUSD) | Avalanche | `savUSD.deposit(x, user)` (ERC-4626; 1-day cooldown) | avUSD `0x24dE8771bC5DdB3362Db529Fc3358F2df3A0E346`, savUSD `0x06d47F3fb376649c3A9Dafe069B3D6E35572219E` | Works technically, but **the season ended** — use only as "Avant airdrop claim coming" narrative |

## 4. Recommendation

**Source of truth = curated + live enrichment.**
- **Curated** (checked-in JSON, e.g. `agent/lazyagent/data/airdrops.json`, refreshed by hand/with a script when we re-research): program name, network(s), qualifying action, contracts, KYC level, token status, season dates, source URL, `verified_at`. Initial set: Re S2, Theo thUSD, Tori Cores (RWA, live); Avant (RWA, ended, claim pending); Suzaku S2 and Aave V4 incentives (Avalanche, non-RWA). There is no reliable live feed for "what qualifies" — this must be curated.
- **Live** (per request, cached like `trending`): DefiLlama `/protocols` for TVL + 7d change and a **"token launched?" check** (if `gecko_id` appears on the protocol or parent → flag `token_launched` so a stale "no token yet" entry corrects itself); GeckoTerminal for the farm token's deepest pool → `buyable` (same ≥ $10k rule as `trending`).
- Alphadrops JSON: use offline only, to discover new candidates when re-curating. Not at runtime (undocumented, paid official API, referral links).

**Result entry shape** (`list_trending_tokens(category="airdrop")` or a separate `list_airdrops`):

```json
{
  "name": "Theo thUSD Points",
  "protocol": "theo-network-thusd",          // DefiLlama slug
  "category": "rwa",                          // rwa | other
  "networks": ["ethereum"],
  "status": "live",                           // live | ended | claim_pending
  "season": "thUSD Points", "season_ends": null,
  "token": "none",                            // none | live:$RE | pending:AVANT
  "reward": "points, no token announced",
  "action": "Stake thUSD into sthUSD",
  "action_kind": "deposit",                   // hold | deposit | trade | offchain
  "farm_token": {"symbol": "thUSD", "address": "0xa3fE…85b3", "network": "ethereum"},
  "deposit_contract": "0xA808…0326",          // null for hold
  "permissionless": true,
  "kyc": "mint_only",                         // none | mint_only | required
  "tvl_usd": 132160137, "tvl_change_7d": -0.07,   // live, DefiLlama
  "liquidity_usd": 3555335, "buyable": true,      // live, GeckoTerminal
  "source_url": "https://theo.xyz/articles/thusd-points-program",
  "verified_at": "2026-10-15"
}
```

**Filter / rank:** drop `ended` unless asked ("any airdrops to claim?" → `claim_pending`); `network` filter like `rwa`; rank `live` → `permissionless && kyc != "required"` → `buyable` → `token == "none"` (an unlaunched token is the classic airdrop) → TVL. Cap at 5.

**Agent wording rules:** always say points are tracked by the protocol on real mainnet and the Sandbox action is a demo; never promise a token; mention KYC for minting; say when the season ends if known.

**Demo narrative (voice):**
1. "What RWA airdrops can I farm?" → "Three live ones: **Re** Season 2 — just hold reUSD, reinsurance yield, on Ethereum and Avalanche, paid in RE, ends around December. **Theo** — stake thUSD, a T-bill-backed dollar; no token yet. **Tori** — hold trUSD; no token yet. Avant on Avalanche finished its season; its AVANT claim isn't open yet."
2. "Do the Theo one with 100 dollars." → confirm card with two steps: swap 100 USDC → thUSD on Uniswap v4, then `sthUSD.deposit` (uses the existing `tx.steps` model). Approve → done.
3. Agent: "You're staking 100 thUSD. On mainnet that would earn Theo points; this Sandbox is a demo."
(Avalanche angle: Re's reUSD exists on Avalanche, and the Avant "claim coming" line. A fork deposit on Avalanche needs the faucet because reUSD/avUSD DEX liquidity there is < $10k.)

## 5. Open questions

1. One tool or two? `list_trending_tokens(category="airdrop")` returns a different shape than tokens. A separate `list_airdrops` is cleaner.
2. Do we want an executable "farm it" action (new `propose_deposit` for ERC-4626, built server-side like transfers/swaps), or is listing enough for the demo?
3. Re (the strongest RWA + Avalanche fit) trades on Fluid/Curve, not Uniswap v4. Does the Kyber branch route reUSD, or do we use the faucet?
4. Include non-RWA Avalanche programs (Suzaku, Aave V4 incentives) under `category: other`, or keep `airdrop` RWA-only?
5. Who refreshes the curated list, and how often? Seasons end (Re S2 around Nov/Dec 2026).

UNVERIFIED items to resolve before relying on them: Theo v4 pool key and Core/Boost vault addresses; whether DEX-bought thUSD earns the same points as minted; Tori contract addresses; Suzaku S2 still accruing; xStocks on Ethereum; AVANT TGE date.
