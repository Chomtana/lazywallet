# LazyWallet — KyberSwap + Custom Tokens Spec

Date: 2026-10-15
Status: Approved design — not yet implemented
Builds on: `2026-10-15-lazywallet-avalanche-dexalot-design.md` (Phase 4, merged to `main`)
Branch: `feat-kyber-custom-tokens` (worktree, from `main`)
Sibling: `2026-10-15-lazywallet-avax-trending-design.md` (built in parallel; the only interface between the two is a token **contract address**)

## 1. Goal

Let the user buy, hold, send and sell **any token** (memecoins included) on both Sandbox networks. Pairs the existing venues can't quote go through the KyberSwap aggregator; bought tokens are remembered by the wallet and behave like built-in tokens afterwards.

**Success criteria**
- "Buy 1 AVAX of COQ" (or with COQ's contract address) shows one confirm card routed through KyberSwap; Approve executes in the browser and the agent reports the amount received.
- After that, "what's my balance" lists COQ with a USD value, "send 1000 COQ to Bob" works, and "sell all my COQ for USDC" works.
- Same flow on Ethereum (e.g. PEPE).
- Built-in pairs still use Uniswap v4 (Ethereum) / Dexalot (Avalanche) exactly as before.
- Every confirm card for a custom token shows its contract address.
- `pnpm --filter wallet test`, `pnpm test:py`, `pnpm build && pnpm lint` pass; an opt-in fork test executes a real KyberSwap route on an Avalanche fork.

## 2. Decisions

| Topic | Decision |
|---|---|
| Venue choice | Keep Uniswap v4 (Ethereum) / Dexalot (Avalanche) when both tokens are built-in and the venue quotes the pair. Otherwise KyberSwap. Both networks |
| Kyber API | `https://aggregator-api.kyberswap.com/{chain}/api/v1` with chain slug `ethereum` / `avalanche`; `GET /routes`, `POST /route/build` with `skipSimulateTx: true` (Kyber would otherwise simulate on real mainnet, where sandbox wallets have no funds → 400). Header `x-client-id: lazywallet` |
| Router | Pinned `0x6131B5fae19EA4f9D964eAc0408E4408b66337b5` (MetaAggregationRouterV2, same on both chains). Any other `routerAddress` → refuse |
| Calldata trust | Kyber calldata is untrusted input. The model never sees or builds it; `kyber.py` verifies it (§5) before a card is shown |
| Custom token store | Wallet-side `lw.tokens` (non-secret), sent with every `user` message like `contacts`. Agent stays stateless |
| Token resolution | registry → saved `lw.tokens` → pasted contract address → symbol search (§4) |
| Prices | Built-in: unchanged. Custom: Kyber route 1 token → network USDC; no route → price unknown (not $0) |
| Slippage | Kyber on Sandbox: default **90%** (`SANDBOX_KYBER_SLIPPAGE_BPS`, tied to the Sandbox, not the global default — no MEV on a private fork). The user override (0.01–5%) still applies. Uniswap/Dexalot unchanged |
| Out of scope | Removing/hiding tokens, token logos, new token UI, Kyber on non-Sandbox networks, Arena bonding-curve buys |

Verified on 2026-10-15: a Kyber route for 1 AVAX → COQ (via LFJ) built with `skipSimulateTx` simulates successfully on a fresh Avalanche fork and returns exactly the quoted amount (~177k gas). Kyber rejects Anvil's well-known dev account `0xf39F…2266` ("wallets invalid") — tests must use a random address.

## 3. Custom token store (wallet)

New `apps/wallet/src/lib/tokens.ts`:

```ts
type CustomToken = { chainId: number; address: string; symbol: string; decimals: number }
```

- Stored under `lw.tokens` as `{ [walletAddressLowercase]: CustomToken[] }`. Add-only, deduplicated by `(chainId, address lowercase)`.
- `storage.ts` gets the `tokens: 'lw.tokens'` key.
- A Kyber confirm card's `tx` carries `addToken?: CustomToken` (the output token, only if it's not built-in). After the swap's last step succeeds, the browser saves it.
- Every `user` WebSocket message carries `tokens: CustomToken[]` for the active wallet, next to `contacts`.
- Unit tests (`tokens.test.ts`): add, dedupe (case-insensitive), per-wallet isolation, survives corrupt JSON (returns empty).

## 4. Token resolution (agent)

New `agent/lazyagent/custom_tokens.py`.

- `merge(network, saved) -> Network`: returns the network with saved tokens for its chain appended to `tokens` (built-ins win on symbol clash). `Session.handle` stores `msg["tokens"]` on `WalletContext`; tools use the merged networks for that turn, so `get_balances`, `propose_transfer` and `propose_swap` see custom tokens with no other change.
- `Token` gets `custom: bool = False`.
- Resolving the user's text for a token, per network:
  1. built-in registry, 2. saved tokens,
  3. `0x` + 40 hex → read `symbol()` / `decimals()` on that fork (fails → "That address isn't a token on <network>"),
  4. symbol search: GeckoTerminal `GET https://api.geckoterminal.com/api/v2/search/pools?query=<sym>&network=<eth|avax>`; among pools whose base token symbol matches exactly (case-insensitive), take the one with the highest `reserve_in_usd`; require ≥ $10,000 or ask the user for the contract address. Result is marked `matched_by_symbol`.
- Network choice for an unnamed custom token: resolve on both networks; exactly one hit → use it; both → the existing choice card.
- Prices: `RpcChain.price_usd` for a `custom` token asks Kyber for 1 token → network USDC (via an injectable price source); failure → `None`, shown as "price unknown" and excluded from totals.

## 5. KyberSwap swaps (agent)

New `agent/lazyagent/kyber.py`:

- `KyberClient` (injectable; tests use fixtures, no network; HTTP via stdlib `urllib` in `asyncio.to_thread` like `faucet.py`, no new dependency; GeckoTerminal search in §4 uses the same helper): `route(chain, token_in, token_out, amount)` and `build(chain, route_summary, sender, slippage_bps)`. Native token = `0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE`.
- `verify(build, request) -> Verified` refuses unless all hold:
  - `routerAddress` == pinned router; `value` == amount for native input, else 0.
  - calldata selector is one of the router's swap functions (`swap`, `swapSimpleMode`); decode with `eth_abi` and check the `SwapDescription`: `srcToken`/`dstToken` match, `amount` == input amount, `dstReceiver` == user, `feeReceivers` empty, `minReturnAmount` ≥ our computed minimum.
- Simulation: `eth_call` from the user's address on the fork. ERC-20 input: pass Anvil state overrides so the router allowance exists (the approve step hasn't run yet). Must succeed and the returned amount must be within **5%** of the quote — catches decimals/amount bugs that 90% slippage would hide.
- Steps: ERC-20 input → `approve(router, amount)` (skipped if allowance suffices; reuse the USDT reset rule), then the swap step. Native input → swap step only.
- Rows: same layout as `swap_rows`; Route = "KyberSwap via LFJ" (DEX names from the route, de-duplicated); add a `Token address` row per custom token, suffixed "(matched by symbol — verify)" when §4 step 4 was used.
- Any failure (no route, verify fail, simulation revert) → `TransferError` with a plain message; no card.
- `propose_swap` in `tools.py`: after resolving tokens, if the network's venue can't handle the pair (either token custom, or venue has no quote), use Kyber.
- Prompt: buying/selling any token is supported; prefer contract addresses when the user gives one; say "matched by symbol" tokens should be verified.

## 6. Testing

- pytest: resolution order, `merge`, GeckoTerminal search pick (fixture JSON), `verify` (good build; wrong router; wrong receiver; fee receiver; low minReturn; unknown selector), step building, rows.
- Vitest: `lib/tokens.ts`, `executeSteps` saving `addToken` only on success.
- Opt-in fork test (existing fork-test convention): fresh Avalanche fork, random funded address, swap 1 AVAX → COQ through the full `propose_swap` path; assert received within 5% of quote and COQ then appears in balances with `tokens` passed.
- Manual: the success-criteria script in the wallet app.
