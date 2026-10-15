# CLAUDE.md

LazyWallet — voice-powered AI wallet (hackathon project). See README.md for overview and INIT.md for the original brief.

## Current phase

Phase 2: minimum viable AI wallet. Spec: `docs/superpowers/specs/2026-10-14-lazywallet-mvp-agent-design.md` (Phase 1 design spec: `2026-10-14-lazywallet-design-phase-design.md`).

## Stack & layout

- pnpm workspace. `apps/landing` (Vite, React, TS, Tailwind v4), `apps/wallet` (+ shadcn/ui Radix, React Router, viem, wagmi, Vitest). Linting is oxlint (create-vite default).
- `agent/` — Python (uv), FastAPI WebSocket + `claude-agent-sdk`. Auth is the developer's Claude Code login (no API key). Built-in Claude Code tools are disabled; only the in-process `wallet` MCP tools exist.
- `anvil/` — Python (uv): Anvil fork of Ethereum mainnet (chain id 1) from `ETH_RPC_URL` in root `.env`, plus a faucet that writes token balances into storage.
- x402 is out of scope for the first phases.
- Use official / well-known frameworks at their latest stable versions. Don't reinvent what a framework provides.

## Commands

```bash
pnpm dev                    # both apps (landing :5173, wallet :5174)
pnpm dev:sandbox            # Anvil fork :8545 + faucet :8547 (needs ETH_RPC_URL)
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
  - Mock: `mock/walletconnect.ts` (WalletConnect), scheduled tasks, swaps. `mock/agent.ts` now only supplies `say()`/`confirm()` helpers for the WalletConnect mock.
- Never store a seed phrase unencrypted. Only `lw.vault` (encrypted) holds secrets; other `lw.*` keys are non-secret.
- Signing model: keys stay in the browser; every transaction goes through an Approve/Reject confirm card. Scheduled tasks only run while the tab is open.
- Network: Sandbox only (Anvil fork, chain id 1).
- The model never builds calldata — `agent/lazyagent/transfers.py` does. Every transfer goes through `propose_transfer` and the browser's Approve card.
- Unit tests cover pure logic (`*.test.ts` next to the module). UI is reviewed manually.

## Development motto

1. **Think before coding** — state assumptions, surface trade-offs, ask when unclear.
2. **Simplicity first** — minimum code that solves the problem; nothing speculative.
3. **Surgical changes** — touch only what the task needs; match existing style.
4. **Goal-driven execution** — define verifiable success criteria and loop until they pass.
