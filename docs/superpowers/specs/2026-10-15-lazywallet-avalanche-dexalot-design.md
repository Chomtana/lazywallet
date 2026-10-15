# LazyWallet — Phase 4 (Avalanche + Dexalot) Spec

Date: 2026-10-15
Status: Draft — awaiting user review
Builds on: `2026-10-15-lazywallet-uniswap-v4-swap-design.md` (Phase 3)
Branch: `phase4-avalanche`

## 1. Goal

Add Avalanche C-Chain next to Ethereum in the Sandbox so the user can hold, send and swap on both **without ever adding or switching a chain**. Swaps on Avalanche go through Dexalot SimpleSwap (RFQ) against Dexalot's real contracts and live prices.

**Success criteria**
- `pnpm dev:sandbox` runs two forks (Ethereum :8545, Avalanche :8546) and one faucet; one "give me test funds" funds both.
- "What's my balance" shows one card with holdings from both networks and a combined total.
- "Swap 1 AVAX to USDC" and "Swap 10 USDC to AVAX" each produce one confirm card; Approve executes in the browser from the user's own key and the agent reports the exact amount received.
- "Send 10 USDC to Bob" with enough USDC on both networks shows a choice card (Ethereum / Avalanche); tapping or saying a network continues to the confirm card.
- Ethereum sends and Uniswap v4 swaps behave as in Phase 3.
- `pnpm test`, `pnpm test:py`, `pnpm build && pnpm lint` pass; fork tests execute real Dexalot `simpleSwap`s with sandbox-signed orders.

## 2. Decisions

| Topic | Decision |
|---|---|
| Networks | Ethereum (chain 1, :8545, as today) and Avalanche C-Chain mainnet fork (chain 43114, :8546). Both always on; no network picker |
| Avalanche fork RPC | `AVAX_RPC_URL` in root `.env`, default `https://api.avax.network/ext/bc/C/rpc` (verified to fork) |
| Avalanche tokens | AVAX (native), USDC, USDT (Avalanche symbol `USDt`), BTC.b, WETH.e — see §3 |
| Prices (Avalanche) | Chainlink: AVAX/USD, BTC/USD (BTC.b), ETH/USD (WETH.e); USDC/USDT fixed $1 |
| Avalanche swap venue | Dexalot SimpleSwap only. Ethereum keeps Uniswap v4 |
| Quote source | **Sandbox-signed only.** Live indicative price from Dexalot's public `pairprice` (no funds needed); order signed by a sandbox key that the forked Dexalot RFQ contracts are patched to trust. Real Dexalot firm quotes are deferred to a future real-network mode (on a fork they add nothing, and the patch makes them invalid there) |
| Quote expiry | Fork block timestamp + 15 min (covers the 5-min approval timeout). No "quote on approve" protocol needed |
| Slippage | None: the contract pays exactly the signed `makerAmount`. Card shows "Receive exactly X" |
| Network choice | Explicit network → native token → token on one network only → network with enough balance → else ask with a choice card |
| Choice UI | New generic `choice` message: buttons + still answerable by voice/text; tap sends the option's reply text as a normal user message |
| Approvals (Dexalot) | ERC-20 input: `approve(maker, amount)` sized to the swap, skipped if allowance suffices (USDT approve-to-0 rule applies to Ethereum USDT only; Avalanche USDt is a standard ERC-20 — verify in fork test) |
| Calldata | Agent's `dexalot.py` builds all calldata; the sandbox only returns `{order, signature, maker}` |

## 3. Verified Avalanche mainnet addresses

Checked on mainnet 2026-10-15 (`symbol()`, `decimals()`, feed `description()`).

| Token | Address | Decimals |
|---|---|---|
| USDC | `0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E` | 6 |
| USDt | `0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7` | 6 |
| BTC.b | `0x152b9d0FdC40C096757F570A51E494bd4b943E50` | 8 |
| WETH.e | `0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB` | 18 |

| Chainlink feed | Address |
|---|---|
| AVAX / USD | `0x0A77230d17318075983913bC2145DB16C7366156` |
| BTC / USD | `0x2779D32d5166BAaa2B2b658333bA7e6Ec0C65743` |
| ETH / USD | `0x976B3D034E162d8bD72D6b9C989d545b839003b0` |

| Dexalot | Address / value |
|---|---|
| DexalotRouter (= `trustedForwarder()` of the RFQ makers) | `0xf00240e5256e72771b46d095666594E0f40D085c` |
| RFQ makers | `DexalotRouter.getAllowedRFQs()` — 10 contracts today, e.g. `0x1FDb2b265d2A5C4302A75cAd682222E4e7bCc313` (used in the spike) |
| Real swap signer (spike) | `0x08ea7d927d13802C3bc4b35B10e394f34a53Fa72` |
| Public API | `https://api.dexalot.com` — `GET /api/rfq/pairs?chainid=43114`, `GET /api/rfq/pairprice?chainid&pair&amount&isbase&side&taker` (needs header `Origin: https://app.dexalot.com`) |

Faucet balance slots for Avalanche tokens are found and verified by the faucet's existing `balanceOf` check (same as Ethereum tokens).

## 4. Dexalot RFQ recipe (verified on a fork)

Source: `Dexalot/contracts` `contracts/DexalotRFQ.sol`.

- `simpleSwap(Order _order, bytes _signature)` payable; `Order = (uint256 nonceAndMeta, uint128 expiry, address makerAsset, address takerAsset, address maker, address taker, uint256 makerAmount, uint256 takerAmount)`.
- Checks: `block.timestamp <= expiry` (`RF-QE-02`), `taker == msg.sender` (`RF-IMS-01`), nonce bitmap unused (`RF-IN-01`), EIP-712 signature recovers to `swapSigner` (`RF-IS-01`).
- EIP-712 domain `{name: "Dexalot", version: "2", chainId: 43114, verifyingContract: maker}`; type `Order(uint256 nonceAndMeta,uint128 expiry,address makerAsset,address takerAsset,address maker,address taker,uint256 makerAmount,uint256 takerAmount)`.
- `nonceAndMeta = (taker << 96) | random 64-bit nonce`; byte at bits 88–95 (`slipInfo`) = 0 so no slippage adjustment.
- Native AVAX = `address(0)`; AVAX input sends `value = takerAmount`; ERC-20 input needs `approve(maker, takerAmount)`.
- `pairprice` `side=1` = sell base, `side=0` = buy base; `quoteAmount` is in whole quote-token units.
- **Sandbox signer patch:** `swapSigner` is `immutable`, so it lives in runtime bytecode, not storage. Patch with `anvil_setCode`, replacing every occurrence of the real signer's 20 bytes with the sandbox signer's (spike: 2 occurrences; afterwards `swapSigner()` returns the sandbox key).
- Spike results: AVAX→USDC 1 AVAX → 9.574 USDC (104,565 gas); USDC→AVAX 4.788 USDC → 0.5 AVAX (95,528 gas); both sent by a faucet-funded user with its own key.
- web3.py needs `ExtraDataToPOAMiddleware` to read Avalanche blocks.

## 5. Sandbox (`anvil/`)

- `sandbox.py` starts two Anvil processes (`ETH_RPC_URL` → :8545 chain 1; `AVAX_RPC_URL` → :8546 chain 43114) and one faucet on :8547.
- `tokens.py` gains a per-network token list (address, decimals, balance slot, faucet amount). Avalanche faucet: 100 AVAX, 10,000 USDC, 10,000 USDt, 1 BTC.b, 5 WETH.e.
- `POST /fund {address}` funds both networks; response `summary` groups by network: `"Ethereum: 100 ETH, 10,000 USDC, … · Avalanche: 100 AVAX, 10,000 USDC, …"`.
- New `dexalot.py` (sandbox side):
  - At startup: generate a sandbox signer key (process memory only), read `getAllowedRFQs()`, and for each maker that has `swapSigner()`: patch bytecode, then assert `swapSigner()` equals the sandbox address. Any failure → log loudly and mark Dexalot unavailable (quote endpoint returns 503).
  - Makers whose signer isn't in their runtime bytecode (e.g. an EIP-1967 proxy maker) are skipped; startup fails only if no maker can be patched.
  - `POST /dexalot/quote {pair, side, amount, taker}` → fetch `pairprice`; pick the patched maker holding the most of the output token; refuse if it holds less than `makerAmount` (409, "not enough liquidity on Sandbox"); build and sign the order (expiry = fork timestamp + 15 min) → `{maker, order, signature, price}`.
- All sandbox endpoints keep refusing when the target RPC isn't Anvil.

## 6. Agent (`agent/`)

### 6.1 Networks
- New `networks.py`: `Network(key, name, chain_id, rpc_url, native: Token, tokens: list[Token], swap_venue: "uniswap" | "dexalot")`, registry `NETWORKS = [ETHEREUM, AVALANCHE]`.
- `tokens.py`: `TOKENS` becomes per network; `find_token(symbol, network)`; symbol matching is case-insensitive and accepts `USDT` for Avalanche `USDt`.
- Pure `resolve_network(symbol, explicit, balances) -> Network | Choice` implementing the rule in §2; `Choice` carries the options with balances.
- `config.py`: `SANDBOX_AVAX_RPC_URL` (sandbox default `http://127.0.0.1:8546`).
- `Session` / `WalletTools` hold one `RpcChain` per network; `RpcChain` injects `ExtraDataToPOAMiddleware` for Avalanche.

### 6.2 Tools
- `propose_transfer` and `propose_swap` gain optional `network`; balances and faucet always cover both.
- `get_balances`: both networks in parallel; holdings carry `network`; if a network is unreachable, show the rest and say which is down.
- `propose_transfer`: resolve network, then the existing flow on that network's chain (gas in its native token).
- `propose_swap`: resolve network; Ethereum → existing Uniswap v4 path; Avalanche → Dexalot path:
  1. Check balance and gas reserve (AVAX); pair lookup happens in the sandbox service (404 lists available pairs).
  2. `POST /dexalot/quote` on the sandbox.
  3. Steps: optional `Approve {token}` then `Swap {in} → {out}` (`simpleSwap` calldata, value for AVAX input). Each step carries `chainId`.
  4. Rows: Network, From, Pay, Receive exactly, Rate, Route "Dexalot · sandbox-signed at live price", Network fee.
  5. After success: report received amount (balance delta) and fresh balances.
- On ambiguity the tool sends a `choice` message itself, then returns an error telling the model it asked the user to choose.
- `request_test_funds`: one call, summary by network.
- `unsupported_action` text updated (bridging still unsupported).

### 6.3 New module `dexalot.py` (agent side)
Pure helpers: pair lookup, order → `simpleSwap` calldata, approval step, outcome hints for `RF-QE-02` / `RF-IS-01` / `RF-IN-01`. HTTP client for `/api/rfq/pairs` and the sandbox quote endpoint.

### 6.4 Prompt
Sandbox is two forks (Ethereum and Avalanche); same address on both. Pass `network` only if the user named one or answered a network choice. Swaps on Avalanche use Dexalot; quotes are sandbox-signed at Dexalot's live price. When a tool says it asked the user to choose, ask the question in one sentence and stop.

## 7. Protocol

- `TxRequest` gains `chainId: number` (agent always sets it).
- New agent → browser message: `{type: "choice", id, question, options: [{label, detail, reply}]}`.
- Balance holdings gain `network: string`.
- No other protocol changes.

## 8. Wallet (`apps/wallet/`)

- `lib/wagmi.ts`: `sandboxChains = { 1: ethereumFork, 43114: avalancheFork }` (RPC from `VITE_SANDBOX_RPC_URL` / `VITE_AVAX_RPC_URL`, defaults :8545 / :8546).
- `chain/client.ts`: `txDepsFor(mnemonic)` sends/waits on the client for each request's `chainId`.
- `executeSteps` unchanged in shape; `statusPatch` / `progressText` name the network ("Confirmed on Avalanche (Sandbox).").
- Confirm card: network shown in the card's Network row from the steps' `chainId`.
- Balance card: network label per row, combined total.
- New `ChoiceCard` (shadcn `Button`s): question, one button per option (label + detail). Tap → send `reply` as a user message; card then locks with the chosen option highlighted. Any other user message also locks open choice cards.
- `types.ts`: `TxRequest.chainId`, `Holding.network`, message kind `choice` `{ question; options; chosen? }`.

## 9. Error handling

| Situation | Behaviour |
|---|---|
| A fork is down | That network's tools say it's unreachable and how to start it; the other keeps working; balances show the reachable one + note |
| Dexalot `pairprice` fails | "Dexalot isn't quoting {pair} right now — try again shortly." No card |
| Pair not offered | Error lists the available pairs |
| Maker short of output on fork | "Dexalot doesn't have enough {token} on Sandbox for that size — try a smaller amount." |
| Ambiguous network | Choice card + model asks |
| Not enough native gas | Existing reserve checks with AVAX/ETH as appropriate |
| Revert `RF-QE-02` / `RF-IS-01` / `RF-IN-01` | Reverted outcome + "ask again for a fresh quote" |
| Signer patch failed at startup | Loud log; Dexalot swaps say "Dexalot swaps are unavailable on this Sandbox" |
| Target RPC isn't Anvil | Faucet and signer refuse (existing `is_sandbox`, per network) |

## 10. Code layout

| Path | Change |
|---|---|
| `anvil/lazysandbox/sandbox.py` | Two Anvil processes |
| `anvil/lazysandbox/tokens.py` | Per-network tokens |
| `anvil/lazysandbox/faucet.py` | Fund both networks; mount Dexalot routes |
| `anvil/lazysandbox/dexalot.py` | New: signer patch + quote signing |
| `agent/lazyagent/networks.py` | New: registry + `resolve_network` |
| `agent/lazyagent/tokens.py` | Per-network tokens, Avalanche feeds |
| `agent/lazyagent/dexalot.py` | New: calldata, approvals, API client |
| `agent/lazyagent/chain.py` | POA middleware option |
| `agent/lazyagent/tools.py`, `session.py`, `config.py`, `prompt.py`, `faucet.py` | Network-aware |
| `apps/wallet/src/lib/wagmi.ts`, `chain/client.ts`, `chain/executeTx.ts` | Per-chain clients, network wording |
| `apps/wallet/src/types.ts`, `agent/useAgentChat.ts` | `chainId`, `network`, `choice` |
| `apps/wallet/src/components/…` | `ChoiceCard`, network badge, balance labels |
| `.env.example`, `CLAUDE.md`, `README.md` | `AVAX_RPC_URL`, two forks, Phase 4 |

## 11. Testing

- **pytest (no network):** `resolve_network` rules; `dexalot.py` calldata for a fixed order, approval logic, AVAX value, price-reply parsing and failures; sandbox signature recovers to the sandbox key; bytecode patch replaces all occurrences and fails on zero; tools with fakes — two-network balances, Avalanche transfer, Avalanche swap → Dexalot, Ethereum swap → Uniswap, ambiguity → `choice` message.
- **Fork integration (marked like Phase 3's):** patch makes `swapSigner()` = sandbox key; AVAX→USDC and USDC→AVAX via `/dexalot/quote` + `simpleSwap` from a faucet-funded user's own key receive exactly `makerAmount`; `/fund` sets every Avalanche balance.
- **Vitest:** `executeSteps` routes by `chainId`; `statusPatch` names the network; choice-card lock logic.
- **Manual:** two-network balance card; AVAX↔USDC swaps; ambiguous USDC send → tap Avalanche → confirm; Phase 3 Ethereum swap still works.

## 12. Out of scope

- Real (non-fork) networks and real Dexalot firm quotes; "quote on approve".
- Bridging between Ethereum and Avalanche; Avalanche L1s / ICM / ICTT; x402 (deferred, core story — next phases).
- Dexalot order-book (CLOB) trading on the Dexalot L1; partial fills; multi-hop RFQ.
- Uniswap or other DEXes on Avalanche; WAVAX wrap/unwrap.
