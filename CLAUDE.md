# CLAUDE.md

LazyWallet — voice-powered AI wallet (hackathon project). See README.md for overview and INIT.md for the original brief.

## Current phase

Phase 4: Avalanche + Dexalot. Spec: `docs/superpowers/specs/2026-10-15-lazywallet-avalanche-dexalot-design.md`.

## Stack & layout

- pnpm workspace. `apps/landing` (Vite, React, TS, Tailwind v4), `apps/wallet` (+ shadcn/ui Radix, React Router, viem, wagmi, Vitest). Linting is oxlint (create-vite default).
- `agent/` — Python (uv), FastAPI WebSocket + `claude-agent-sdk`. Auth is the developer's Claude Code login (no API key). Built-in Claude Code tools are disabled; only the in-process `wallet` MCP tools exist.
- `anvil/` — Python (uv): Anvil forks of Ethereum mainnet (chain id 1, :8545, from `ETH_RPC_URL`) and Avalanche C-Chain (chain id 43114, :8546, from `AVAX_RPC_URL`, default public RPC), plus a faucet/sandbox service (:8547) that writes token balances and serves sandbox-signed Dexalot quotes.
- x402 is deferred to a later phase (still a core story).
- Use official / well-known frameworks at their latest stable versions. Don't reinvent what a framework provides.

## Commands

```bash
pnpm dev                    # both apps (landing :5173, wallet :5174)
pnpm dev:sandbox            # Anvil forks :8545 (Ethereum) + :8546 (Avalanche) + faucet :8547
pnpm dev:agent              # agent ws://localhost:8787/ws
pnpm --filter wallet test   # Vitest unit tests
pnpm test:py                # pytest for anvil/ and agent/
pnpm build && pnpm lint
```

## Wallet app conventions

- Import alias `@/` → `apps/wallet/src`. shadcn components live in `src/components/ui` (generated; add more with `pnpm dlx shadcn@latest add <name>`).
- Theme: dark-only, tokens in `src/index.css` (`.dark` block). Lime accent `#B6FF3B` used sparingly. Mono font only for amounts/addresses/hashes.
- Domain and chat message types: `src/types.ts`.
- Real vs mock boundary:
  - Real: `lib/vault.ts` (mnemonics, PBKDF2 + AES-GCM vault), `voice/speech.ts` (Web Speech API), `agent/useAgentChat.ts` (chat over the agent WebSocket), `chain/` (viem signing, faucet).
  - Mock: `mock/walletconnect.ts` (WalletConnect), scheduled tasks. `mock/agent.ts` now only supplies `say()`/`confirm()` helpers for the WalletConnect mock.
- Never store a seed phrase unencrypted. Only `lw.vault` (encrypted) holds secrets; other `lw.*` keys are non-secret.
- Signing model: keys stay in the browser; every transaction goes through an Approve/Reject confirm card. Scheduled tasks only run while the tab is open.
- Networks: Sandbox only — Ethereum fork (1) and Avalanche fork (43114), both always on; every agent step carries `chainId`.
- The model never builds calldata — `agent/lazyagent/transfers.py` does. Every transfer goes through `propose_transfer` and the browser's Approve card.
- Agent confirm cards carry `tx.steps` (`[{label, request}]`); the browser runs them in order (`chain/executeTx.ts` `executeSteps`).
- Uniswap v4 recipe and addresses live in `agent/lazyagent/uniswap.py` (verified on a fork) — change them only with a fork test.
- Any other token or pair goes through KyberSwap (`agent/lazyagent/kyber.py`). Its calldata is untrusted: `verify()` decodes it against the request and it is simulated on the fork (within 5% of the quote) before a card is shown. Change the router address/ABI only with the fork tests (`tests/test_kyber_swap_fork.py`, one token per chain).
- Custom tokens: the wallet keeps bought tokens in `lw.tokens` (non-secret, per wallet) and sends them with every `user` message; the agent stays stateless (`agent/lazyagent/custom_tokens.py`).
- Dexalot recipe (Avalanche swaps) lives in `anvil/lazysandbox/dexalot.py` (signer patch, order signing) and `agent/lazyagent/dexalot.py` (calldata) — change only with a fork test.
- Unit tests cover pure logic (`*.test.ts` next to the module). UI is reviewed manually.

## Development motto

1. **Think before coding** — state assumptions, surface trade-offs, ask when unclear.
2. **Simplicity first** — minimum code that solves the problem; nothing speculative.
3. **Surgical changes** — touch only what the task needs; match existing style.
4. **Goal-driven execution** — define verifiable success criteria and loop until they pass.
