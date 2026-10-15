# LazyWallet — Phase 2 (Minimum Viable AI Wallet) Spec

Date: 2026-10-14
Status: Draft — awaiting user review
Builds on: `2026-10-14-lazywallet-design-phase-design.md` (Phase 1 UI, approved)

## 1. Goal

Replace the mocked agent with a real Claude agent and a real chain sandbox so a user can check balances and send ETH/ERC-20 tokens by voice or text, approve in the chat, and see the transaction confirm on an Anvil mainnet fork. No external protocol interaction yet (no swaps, bridges, dApps).

**Success criteria**
- `pnpm dev:sandbox` starts an Anvil mainnet fork (chain id 1) on :8545 and a faucet on :8547.
- `pnpm dev:agent` starts the agent server on :8787 using the developer's Claude Code login (no API key).
- `pnpm dev` starts landing + wallet as before.
- In the wallet: create wallet → "Get test funds" → "What's my balance?" shows real fork balances with USD values → "Send 0.1 ETH to Alice" → Approve → tx mined on Anvil → agent confirms in chat → balance reflects it.
- Unknown recipient / zero / over-balance / unsupported token / insufficient gas never produce a confirm card.
- `pnpm test` (Vitest) and `uv run pytest` in `agent/` and `anvil/` pass; chain-dependent tests skip when `ETH_RPC_URL` is missing.

## 2. Decisions

| Topic | Decision |
|---|---|
| Scope | Balances (ETH + USDC, USDT, DAI, WBTC, WETH) and sends of ETH/those tokens. Swap/bridge/schedule requests → "coming soon" |
| Signing | Unchanged: keys stay in the browser; agent proposes, browser signs with viem after Approve |
| Transport | One WebSocket per chat; `propose_transfer` tool awaits the browser's Approve/Reject + receipt |
| Agent runtime | Python, FastAPI + `claude-agent-sdk` (`ClaudeSDKClient`), built-in tools disabled (`tools=[]`), custom in-process MCP tools only |
| Auth | Claude Code login of the developer (SDK spawns the local `claude` CLI). No `ANTHROPIC_API_KEY` required. A public deployment would need an API key — out of scope |
| Model | `claude-sonnet-5-5` default, override with `AGENT_MODEL` env |
| Prices | Read-only Chainlink feeds on the fork (ETH/USD, BTC/USD); USDC/USDT/DAI = $1 |
| Chain | Anvil fork of Ethereum mainnet from `ETH_RPC_URL` (archive RPC), chain id 1, optional `FORK_BLOCK` |
| Faucet | Sets ETH via `anvil_setBalance`, tokens via `anvil_setStorageAt` on each token's balance mapping slot |
| x402 | Still out of scope |
| Tx history | Not in this phase (chat only) |

## 3. Repository layout (Phase 2 additions)

```
.env.example                 ETH_RPC_URL=, FORK_BLOCK= (optional), AGENT_MODEL= (optional)
package.json                 + scripts: dev:sandbox, dev:agent
anvil/
  pyproject.toml             uv project (python ≥3.12): fastapi, uvicorn, web3, pytest
  lazysandbox/tokens.py      token registry shared by faucet (address, decimals, balance slot)
  lazysandbox/faucet.py      FastAPI app: POST /fund {address} → ETH + tokens; GET /health
  lazysandbox/sandbox.py     entry: start anvil subprocess (fork) + faucet; reset on start
  scripts/seed.py            create random test wallet, fund it, write anvil/.test-wallet.json (gitignored)
  scripts/reset.py           anvil_reset to the fork
  tests/
agent/
  pyproject.toml             uv project: claude-agent-sdk, fastapi, uvicorn, web3, pytest, pytest-asyncio
  lazyagent/config.py        env: RPC URL, model, CORS origin
  lazyagent/chain.py         read-only chain access: ETH/ERC-20 balances, decimals, Chainlink prices, gas estimate
  lazyagent/tokens.py        token registry (symbol → address, decimals, price feed)
  lazyagent/transfers.py     pure: parse amount, resolve recipient, validate, build tx request + display rows
  lazyagent/session.py       per-connection session: SDK client, pending proposals, tool definitions
  lazyagent/server.py        FastAPI app, /ws endpoint, /health
  lazyagent/prompt.py        system prompt
  tests/
apps/wallet/src/
  agent/protocol.ts          message types (mirror of §5)
  agent/useAgentChat.ts      replaces useChat: socket lifecycle, streaming, confirm handling
  chain/client.ts            viem public + wallet clients for Sandbox, account from active mnemonic
  chain/executeTx.ts         send tx request, wait for receipt → tx_result
  chain/faucet.ts            POST /fund
```

Token registry exists in both Python packages (agent and anvil) — small, deliberately duplicated to keep the packages independent.

## 4. Agent

### 4.1 Tools (MCP server `wallet`, exposed as `mcp__wallet__*`)

| Tool | Input | Behaviour |
|---|---|---|
| `get_balances` | — (uses session's active address) | ETH + registry tokens with amounts and USD values; also emits a `balances` message to the browser so it renders the balance card |
| `resolve_recipient` | `name_or_address` | Case-insensitive match in the session's contacts, or valid 0x address (checksummed). Error text if unknown |
| `propose_transfer` | `token` (symbol), `amount` (decimal string), `to` (name or 0x) | Validates (recipient, amount > 0, token supported, balance ≥ amount, ETH left for gas). On failure returns an error result (no card). On success builds `{to, value, data}` + display rows, sends `confirm`, awaits `tx_result` (timeout 5 min), returns outcome text incl. hash and status |
| `unsupported_action` | `action` | Returns a fixed "coming soon in Sandbox" explanation for swap/bridge/schedule/dApp requests |

The model never writes calldata or raw hex values; `transfers.py` builds them deterministically.

### 4.2 System prompt (summary)
Voice-first wallet assistant on Sandbox (Ethereum mainnet fork, test funds). Short, spoken-friendly replies (1–2 sentences, no markdown tables). Always use tools for balances and transfers; never invent numbers or addresses. Every transfer goes through `propose_transfer`; the user approves in the app. Unsupported actions → `unsupported_action`.

### 4.3 Session
- One `ClaudeSDKClient` per WebSocket connection, created on connect, disconnected on close.
- Options: `tools=[]`, `mcp_servers={"wallet": ...}`, `allowed_tools=[all mcp__wallet__* tools]`, `system_prompt`, `model`, `strict_mcp_config=True`, `setting_sources` none (don't load user/project Claude settings), `max_turns` 10 per user message.
- Session state: active address, contacts (both refreshed from each `user` message), pending proposals keyed by id (asyncio Futures).
- Assistant text streamed to the browser as `text_delta` using the SDK's partial-message streaming (`include_partial_messages=True`), then `text_done`, then `turn_end` when the response completes.

## 5. WebSocket protocol (`/ws`)

Browser → agent:
```json
{"type":"user","text":"Send 0.1 ETH to Alice","spoken":true,"address":"0x…","contacts":[{"name":"Alice","address":"0x…"}]}
{"type":"tx_result","id":"p1","outcome":"approved","hash":"0x…","status":"success"}
{"type":"tx_result","id":"p1","outcome":"rejected"}
{"type":"tx_result","id":"p1","outcome":"approved","error":"insufficient funds"}
```
Agent → browser:
```json
{"type":"text_delta","text":"Here"}
{"type":"text_done"}
{"type":"balances","holdings":[{"symbol":"ETH","amount":2.5,"usdPrice":3200}]}
{"type":"confirm","id":"p1","tx":{"title":"Send 0.1 ETH","rows":[{"label":"To","value":"Alice (0x7099…79C8)"}],"request":{"to":"0x…","value":"100000000000000000","data":"0x"}}}
{"type":"error","message":"…"}
{"type":"turn_end"}
```
- `value` is a decimal string of wei. `holdings` matches the existing `Holding` type.
- Origin check: accept only the configured wallet origin (default `http://localhost:5174`).
- A `user` message while a turn is running is rejected with `error` ("Still working on your last request").

## 6. Browser changes

- `useAgentChat` replaces `useChat` in `WalletPage`; same `Message` rendering. Streaming text appends to the last assistant text bubble. `confirm` → existing `ConfirmCard`. Approve → `executeTx` → status card pending → success/failed → `tx_result` sent. Reject → `tx_result` rejected.
- Agent offline: a system text "Agent offline — run `pnpm dev:agent`"; reconnect with backoff (1s → 10s max); input stays enabled and messages sent while offline get the same notice.
- Spoken replies: speak the assistant text on `text_done`.
- `StatusCard` gains a `failed` state.
- Receive sheet: "Get test funds" button → faucet → toast with result.
- `chain/client.ts`: viem `createPublicClient`/`createWalletClient` with the existing `sandbox` chain; account via `mnemonicToAccount(active.mnemonic)`.
- Phase-1 `mock/agent.ts` stays only as the source of `say()`/`confirm()` helpers used by the WalletConnect mock; the chat no longer calls `respond()`. Scheduled-task UI unchanged (tasks are only created by the mock path, so the list will stay empty this phase).

## 7. Anvil sandbox

- `pnpm dev:sandbox` → `uv run --project anvil sandbox`: loads root `.env`, refuses to start without `ETH_RPC_URL`, starts `anvil --fork-url $ETH_RPC_URL [--fork-block-number $FORK_BLOCK] --chain-id 1 --port 8545`, waits for RPC readiness, starts faucet on :8547, stops anvil on exit.
- Faucet `POST /fund {"address"}`: sets 10 ETH; sets 10,000 USDC/USDT/DAI, 1 WBTC, 5 WETH via balance-slot storage writes; verifies each with `balanceOf`; returns funded amounts. CORS for the wallet origin. Only works against the local Anvil RPC.
- Balance slots are verified by a test against the fork (`balanceOf` equals the written amount). Known starting values: USDC 9, USDT 2, DAI 2, WBTC 0, WETH 3.
- `scripts/seed.py`: generates a random private key (never a well-known key), funds it, writes `anvil/.test-wallet.json` (gitignored) for integration tests and demos.
- `scripts/reset.py`: `anvil_reset` back to the fork.

## 8. Error handling

| Situation | Behaviour |
|---|---|
| Agent server down | Offline notice in chat; reconnect with backoff |
| Anvil down / RPC error | Tool returns error text; agent explains "Sandbox chain isn't reachable" |
| Claude CLI not logged in / SDK error | `error` message to browser with the SDK's text; server logs it |
| Unknown recipient, zero, over-balance, unsupported token, not enough ETH for gas | `propose_transfer` returns an error result; agent explains; no card |
| User ignores card for 5 min | Tool resolves "no response"; card stays but is marked expired on the next `turn_end` |
| Socket closes with pending proposal | Future cancelled; session closed |
| Tx reverts / send throws | `tx_result` with `status:"reverted"` or `error`; failed status card; agent explains |

## 9. Testing

- `anvil/tests`: faucet funds a random address and `balanceOf` matches (requires `ETH_RPC_URL`, starts its own Anvil on a spare port; skipped otherwise).
- `agent/tests`:
  - `transfers.py` unit tests: amount parsing (decimals, too many decimals, zero, negative), recipient resolution (name case, checksum, unknown), validation (over balance, gas reserve), tx building (ETH value; ERC-20 `transfer(address,uint256)` calldata).
  - Session tool loop with a fake browser: `propose_transfer` sends `confirm`, resolves on `tx_result`, times out, cancels on close — without calling Claude.
  - Chain integration (balances + Chainlink price) against a fork — skipped without `ETH_RPC_URL`.
- Wallet Vitest: protocol message handling in `useAgentChat` reducer, `executeTx` maps receipt/throw to `tx_result`.
- `agent/scripts/demo.py`: live end-to-end check through the real model using the Claude Code login (manual).

## 10. Out of scope
Swaps, bridges, dApp/WalletConnect real pairing, scheduled/conditional execution, multi-chain, transaction history page, x402, hosted deployment/auth.
