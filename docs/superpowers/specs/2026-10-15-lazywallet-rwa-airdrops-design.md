# LazyWallet — RWA Airdrops (list + farm) Spec

Date: 2026-10-15
Status: Draft design — not yet implemented
Builds on: `main` after the KyberSwap + custom tokens merge (`68d9f38`)
Research: `docs/research/2026-10-15-rwa-airdrops.md` (`235f59c`)
Branch: `feat-rwa-airdrops` (worktree, from `main`)
Sibling: `2026-10-15-lazywallet-avax-trending-design.md` (`list_trending_tokens` in `trending.py`, built in parallel; no shared code, same registration pattern)

## 1. Goal

"What RWA airdrops can I farm?" → the agent names the live RWA points programs (and, after them, a few non-RWA Avalanche ones), each with what to do and whether LazyWallet can do it. "Farm Theo with $100" → one Approve card that swaps USDC → thUSD and stakes it into Theo's sthUSD vault. "Get me some reUSD" → the existing KyberSwap swap. Every answer and card says points only count on real mainnet; the Sandbox is a demo.

**Success criteria**
- New read-only tool `list_airdrops(category?, network?)` returns the curated programs, ranked RWA first, enriched live with TVL (DefiLlama) and farm-token liquidity (GeckoTerminal). A DefiLlama/GeckoTerminal outage degrades to the curated data, never to an error.
- New tool `propose_deposit(farm, amount)` for curated ERC-4626 farms. For Theo it shows one confirm card with these steps, building only the approvals that are actually needed: [Allow USDC → Allow Uniswap router → Swap USDC → thUSD (Uniswap v4) → Allow thUSD → Stake thUSD → sthUSD]. Approve executes in the browser. The agent reports the sthUSD received and the leftover thUSD.
- All calldata is built by the agent backend from pinned addresses. The model only passes a farm id and an amount.
- The confirm card and the agent's spoken reply both state that points only count on real mainnet and the Sandbox is a demo. They never promise a token.
- "Buy reUSD" style requests go through `propose_swap` with the contract address taken from `list_airdrops`. There is no new swap code.
- `pnpm test:py`, `pnpm --filter wallet test`, `pnpm build && pnpm lint` pass. Unit tests never hit the network. An opt-in fork test runs the whole Theo farm on an Ethereum fork.

## 2. Decisions

| Topic | Decision |
|---|---|
| Tools | Separate `list_airdrops` (not a `list_trending_tokens` category) and `propose_deposit`. Both live in a new module, `agent/lazyagent/airdrops.py`; `tools.py` and `prompt.py` only change to register them |
| Source of truth | Curated, checked-in `agent/lazyagent/data/airdrops.json`, refreshed by hand. Each entry carries `source_url` and `verified_at`. Alphadrops is only for discovery while curating, never at runtime |
| Live enrichment | DefiLlama `GET https://api.llama.fi/protocol/{slug}`: `currentChainTvls` gives TVL, and `gecko_id` / `symbol` flag a token that launched after curation. GeckoTerminal `GET /networks/{eth\|avax}/tokens/{addr}/pools` gives the farm token's deepest pool, which sets `liquidity_usd` and `buyable` (≥ $10,000, same rule as custom tokens and `trending`). HTTP via stdlib `urllib` in `asyncio.to_thread`, reusing `kyber.http_json`. Cache 10 min per entry. Errors are never cached and never fatal |
| Categories | `rwa` first, then `other`. Initial list (§3): **rwa** = Theo thUSD, Re. **other** = Tori, Avant, Suzaku S2, Aave V4 Avalanche incentives |
| Executable farm | Only entries with a `deposit` block. Initially just **Theo** (Ethereum): USDC → thUSD on the pinned Uniswap v4 pool, then `sthUSD.deposit`. Re is hold-only: buy reUSD through `propose_swap` / KyberSwap by contract address |
| Theo swap venue | Uniswap v4 hookless pool USDC/thUSD, fee 100, tickSpacing 1, pool id `0xb30bf32e…594b5a0d`. The route is pinned in the JSON: no route search and no Kyber fallback. If the pinned route doesn't quote, the tool returns an error |
| Deposit amount | Stake the swap's **minimum** output (quote × (1 − slippage), default 1%), so the deposit can never exceed what the swap delivered. The rest (≤ ~1%) stays in the wallet as thUSD, and the card and reply say so |
| Mainnet-only notice | A card row `Points` = "Only count on real Ethereum mainnet. This Sandbox is a demo and earns nothing." No UI change. The prompt requires the same sentence in replies |
| Wallet | `tx.addTokens?: CustomToken[]` next to the existing `addToken`. The deposit card sends thUSD and sthUSD so balances show them afterwards. That is the only wallet change |
| Network | Ethereum and Avalanche Sandbox forks. `propose_deposit` runs on the farm's own network (Theo = Ethereum); the model never picks the network for it |
| Out of scope | Withdrawals/unstaking (sthUSD redemption is an async `initiateRedeem` → `redeem`), points dashboards, referrals, claiming airdrops, any KYC-gated mint, Re/Tori/Avant/Suzaku/Aave executable actions, auto-refresh of the curated list |

Verified on 2026-10-15 (Ethereum fork, block 26197220, own port, with `lazyagent.uniswap` helpers):
- The pool id above equals `pool_id((USDC, thUSD, 100, 1, 0x0))`.
- V4Quoter quoted 100 USDC → 100.037 thUSD.
- The run: USDC approve to Permit2 (55k gas), Permit2 approve (48k), `UniversalRouter.execute` (156k), thUSD approve (51k), then `sthUSD.deposit(100.037 thUSD)` (88k), which minted 98.197 sthUSD (`previewDeposit` matched).

KyberSwap's live API routes 100 USDC → reUSD on Ethereum via Curve (90.29 reUSD ≈ $100.12). On Avalanche the same route loses ~48% (output $52.5 for $100 in), so reUSD on Avalanche is listed but `buyable: false`.

## 3. Curated data — `agent/lazyagent/data/airdrops.json`

A list of entries. All addresses are checksummed and were verified on-chain on 2026-10-15 unless marked otherwise.

```json
{
  "id": "theo-thusd",
  "name": "Theo thUSD Points",
  "category": "rwa",
  "networks": ["ethereum"],
  "status": "live",
  "reward": "Theo points — no token announced",
  "token": "none",
  "season_ends": null,
  "action": "Stake thUSD (a T-bill-backed dollar) into sthUSD",
  "action_kind": "deposit",
  "kyc": "mint_only",
  "farm_tokens": [{"network": "ethereum", "symbol": "thUSD", "address": "0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3", "decimals": 6}],
  "defillama_slug": "theo-network-thusd",
  "deposit": {
    "network": "ethereum",
    "vault": {"symbol": "sthUSD", "address": "0xA808Bc9775cb41c52C7842f8b50427fE7A770326", "decimals": 6},
    "asset": "0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3",
    "pay": "USDC",
    "route": {"fee": 100, "tick_spacing": 1}
  },
  "source_url": "https://theo.xyz/articles/thusd-points-program",
  "verified_at": "2026-10-15"
}
```

Initial entries:

| id | category | networks | status | action (`action_kind`) | farm token(s) | executable | token | source |
|---|---|---|---|---|---|---|---|---|
| `theo-thusd` | rwa | ethereum | live | Stake thUSD → sthUSD (`deposit`) | thUSD `0xa3fE…85b3` | **yes** | none | theo.xyz/articles/thusd-points-program (2026-06-25) |
| `re` | rwa | ethereum, avalanche | live — S2 from 2026-06-01, ~6 months (`season_ends: "~2026-12"`) | Hold reUSD (`hold`) | reUSD ETH `0x5086bf358635B81D8C47C66d1C8b9E567Db70c72`, AVAX `0x180aF87b47Bf272B2df59dccf2D76a6eaFa625Bf` (18 dec) | no (buy via `propose_swap`) | live: RE | docs.re.xyz/re-points/about-re-points |
| `tori` | other (DefiLlama: Basis Trading) | ethereum | live — Cores S1 from 2026-06-23 | Hold trUSD or stake to strUSD (`hold`) | trUSD `0xd0580192E98eA6CEB9c7b6191Ed2E27560911697` (18 dec) | no (buy via `propose_swap`; ~$2.6M Fluid trUSD/USDC) | none | docs.tori.finance/resources/cores, …/contracts |
| `avant` | other | avalanche | `claim_pending` — S1 ended 2026-05-15, AVANT TGE TBA | Nothing to farm; the claim isn't open yet | — | no | pending: AVANT | docs.avantprotocol.com …/avant-season-1-airdrop |
| `suzaku-s2` | other | avalanche | `unverified` — S2 from 2025-07-31, end TBD | Deposit into Suzaku restaking vaults (`deposit`) | — | no | live: SUZ | docs.suzaku.network …/suzaku-points |
| `aave-v4-avax` | other | avalanche | live — weekly Merkl campaigns | Supply USDt/USDC on Aave V4 (WAVAX incentives, not points) (`deposit`) | — | no | n/a | api.merkl.xyz/v4/opportunities?chainId=43114&status=LIVE |

`status` values: `live`, `unverified` (the program's own docs don't confirm it's still running; the agent says "may have ended"), `claim_pending`. Ended programs are removed from the file, not flagged.

## 4. `list_airdrops` — `agent/lazyagent/airdrops.py`

- `load_curated() -> list[Program]` reads and validates the JSON once at import. Invalid entries fail loudly in tests, not at runtime: a unit test loads the real file.
- Sources sit behind protocols so tests use fixtures: `DefiLlamaSource.protocol(slug) -> dict` and `GeckoSource.pools(network, address) -> dict`.
- Pure, unit-tested functions:
  - `enrich(program, llama, pools) -> Airdrop` sets `tvl_usd` (sum of `currentChainTvls` for the program's networks); `token_launched` (true when the curated `token` is `none` but DefiLlama now has a `gecko_id` or a symbol other than `-`); and, per farm token, `liquidity_usd` and `buyable`.
  - `rank(airdrops)`: category `rwa` → `other`; then status `live` → `unverified` → `claim_pending`; then executable → buyable → `token == "none"`; then TVL descending.
  - `filter(category, network)`.
  - `to_json`.
- Result entry (JSON text for the model): `id, name, category, networks, status, reward, token, token_launched, season_ends, action, action_kind, executable, kyc, farm_tokens[{network, symbol, address, liquidity_usd, buyable}], tvl_usd, source_url, verified_at`. At most 8 entries.
- Arguments:
  - `category`: `rwa` | `other` | `all`, default `all`. RWA entries always rank first.
  - `network`: `ethereum` | `avalanche`, default both.
  - Anything else → an error string.
- An enrichment failure leaves `tvl_usd` / `liquidity_usd` as `null` and `buyable` as `null` ("unknown"), and the tool still returns the curated list.

## 5. `propose_deposit` — `airdrops.py` + `WalletTools`

Arguments:
- `farm`: an id from `list_airdrops`.
- `amount`: decimal USDC.

The tool runs these steps in order. Any failure is a `TransferError`, which the model sees as plain text.

1. **Farm lookup.** The farm must exist and have a `deposit` block. Otherwise: "I can list that program but can't farm it from here yet."
2. **Wallet and amount.** No active wallet → error. `parse_amount` the amount. Check the USDC balance on the farm's network (`_balance_on`).
3. **On-chain safety checks.** These guard against a stale JSON or an upgraded proxy:
   - `vault.asset()` must equal `deposit.asset`.
   - `vault.maxDeposit(user)` must be ≥ the deposit amount.
   - On failure: "Theo's vault isn't accepting deposits right now."
4. **Quote.** Build `Route((USDC, thUSD), (Hop(fee, tick_spacing),))` from the JSON. Quote it with `self.quoter.quote` (no route search). Check price impact against `MAX_PRICE_IMPACT` with the existing probe method. Then `minimum = min_out(quote, DEFAULT_SLIPPAGE_BPS)`.
5. **Steps.** All built with existing helpers:
   - `approval_steps` for USDC → Permit2 → UniversalRouter.
   - `Step("Swap USDC → thUSD", UniversalRouter.execute(encode_swap(route, amount, minimum, deadline)))`.
   - `erc20_approval(thUSD, allowance(user, vault), minimum, vault)`.
   - `Step("Stake thUSD → sthUSD", {to: vault, data: deposit(minimum, user)}, gas=GAS["deposit"])` with a new `GAS["deposit"] = 120_000`.
   - `encode_erc4626_deposit(assets, receiver)` sits next to the other encoders in `airdrops.py`.
6. **Fees.** `gas_reserve` + `check_swap_funds`, as `propose_swap` does.
7. **The card** (`type: "confirm"`):
   - Title: `Farm Theo points: 100 USDC → sthUSD`.
   - Rows: From · You pay · Swap `USDC → thUSD · Uniswap v4 0.01%` (`route_label` can't name thUSD, so the row is built from the JSON symbols) · Expected `≈ 100.03 thUSD` · Stake `99.03 thUSD → ≈ 97.2 sthUSD` (`previewDeposit(minimum)`) · Left in wallet `≈ 1.0 thUSD` · Program `Theo thUSD Points — no token announced` · **Points** `Only count on real Ethereum mainnet. This Sandbox is a demo and earns nothing.` · Vault address · thUSD address · Network fee · Network.
   - `steps`: as above, with `chainId`.
   - `addTokens`: thUSD and sthUSD.
8. **After a successful run.** `_show_change` covers USDC, thUSD and sthUSD. The reply reads: "Staked X thUSD into sthUSD, got Y sthUSD; Z thUSD left. Confirmed on Ethereum (Sandbox), tx …". Reverts go through `outcome_text(..., "deposit", ..., revert_hint=" The price probably moved more than the 1% slippage — ask again for a fresh quote.")`.

The model never sees calldata, the pool, the vault address or the amounts in raw units.

## 6. Wallet

- `types.ts`: `addTokens?: CustomToken[]` on the confirm `tx`, with the same comment as `addToken`.
- `chain/executeTx.ts`: after all steps succeed, return `addToken` plus `addTokens` (deduplicated), and save each one through the existing `lw.tokens` path.
- Unit test in `executeTx.test.ts`: both fields are saved, and nothing is saved on failure.

## 7. Prompt (`prompt.py`)

Add these bullets:
- "Airdrops, points, farming, 'what can I farm'" → `list_airdrops`. Pass `category: "rwa"` only if the user said RWA or real-world assets. Pass `network` only if the user named one.
- Summarise the top two or three by name, what to do, and the reward. Say clearly which ones LazyWallet can do (`executable`, or a `buyable` farm token). For `unverified` say "may have ended". For `claim_pending` say "the claim isn't open yet". Never promise a token or an airdrop.
- "Farm X" / "stake into Theo" → `propose_deposit` with the farm id and the USDC amount. For hold-type programs (Re, Tori), offer to buy the farm token with `propose_swap`, passing the **contract address** from `list_airdrops` on that network. Offer it only if `buyable` isn't `false`.
- Whenever you talk about farming: points only count on real mainnet; this Sandbox is a demo.
- Other dApps, staking anywhere else and withdrawals stay with `unsupported_action`.

## 8. Testing

- **pytest (no network):** load and validate the real `airdrops.json`, checking addresses are checksummed, ids unique, and every `deposit` block's `asset` is one of its `farm_tokens`.
- **`enrich`:**
  - TVL summed over the program's networks.
  - `token_launched` flips when a `gecko_id` appears.
  - `buyable` true / false / null at the $10k rule.
  - DefiLlama/GeckoTerminal error → curated data with nulls.
- **`rank` / `filter`:** RWA before other, then the status order, then the network filter. Cap at 8; a bad `category` returns an error.
- **Caching:** 10 min with a fake clock; errors are not cached.
- **`propose_deposit` with fakes** (`fakes.py` chain/quoter/proposals):
  - Step list and order, with and without existing allowances.
  - The deposit amount equals `minimum` and is decoded back from the calldata.
  - The vault-asset mismatch error and the `maxDeposit` too-low error.
  - Unknown farm, non-executable farm, insufficient USDC, price impact too high.
  - The card contains the `Points` row and `addTokens`.
  - The success summary reads amounts from the balance change.
- **Opt-in fork test** `test_deposit_fork.py` (uses the `fork_rpc` fixture; skips without `ETH_RPC_URL`): fund a random address with USDC by storage write, build the Theo farm with the real `WalletTools` pieces, execute every step on the fork, then assert sthUSD > 0, thUSD left ≤ 1.5% of the quote, and USDC spent = 100.
- **Wallet:** `executeTx.test.ts` for `addTokens`.
- **Manual:**
  - "What RWA airdrops can I farm?"
  - "Farm Theo with 100 dollars" → Approve.
  - "What's my balance" shows sthUSD.
  - "Buy 100 dollars of reUSD" → a KyberSwap card on Ethereum.
  - "Any airdrops on Avalanche?"

## 9. Merge plan

`feat-trending-avax` (`list_trending_tokens`) is being built in parallel. Whichever lands second rebases. Expected conflicts are all additive, so keep both sides:
- `TOOL_NAMES` and tool registration in `tools.py`.
- `prompt.py` bullets.
- `test_tools.py` (`TOOL_NAMES`).
- The end of `fakes.py`.
- `agent/lazyagent/data/` (both add files, but different ones).

## 10. Open items (not in the demo path)

1. **sthUSD price.** It has no Chainlink feed or fixed price, and KyberSwap probably has no USDC → sthUSD route, so balances may show "price unknown". The cheap fix is pricing via `convertToAssets` × the thUSD price; deferred.
2. **Whether DEX-bought thUSD earns the same points as minted thUSD.** The post says "hold thUSD or stake", which reads as yes. Unconfirmed: docs.theo.xyz blocks bots.
3. **Theo Core/Core+/Boost lock vaults** (higher multipliers): addresses unknown. Not used.
4. **Tori strUSD staking.** `strUSD.asset()` = trUSD, but the deposit path isn't checked, so Tori is hold-only.
5. **Suzaku S2.** Still accruing in Oct 2026? Listed as `unverified`.
6. **Re on Avalanche.** Liquidity is ~$6k; KyberSwap loses ~48%. Listed with `buyable: false`.
7. **Classification.** Tori and Avant are filed as `other` (DefiLlama files them as Basis Trading / Onchain Capital Allocator, not RWA). Re and Theo are RWA.
8. **Avant TGE date.** The docs say TBA; aggregators said Sept 2026.
9. **Re S2 end date.** "Approximately six months" from 2026-06-01; stored as `~2026-12`.
