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
- The agent sends `progress` labels ("Thinking…" at turn start, one per wallet tool call — `TOOL_LABELS` in `agent/lazyagent/stream.py`; never name a chain). The wallet shows them in a progress bubble until reply text streams, and "Waiting for your approval" while a confirm card is open. Prompts typed or spoken while busy are queued in the wallet and sent one at a time after each `turn_end`; on disconnect they are marked "Not sent".
- Agent confirm cards carry `tx.steps` (`[{label, request}]`); the browser runs them in order (`chain/executeTx.ts` `executeSteps`).
- Swap and farm cards also carry `tx.summary` (`swaps.py` `swap_summary`, `airdrops.py` `farm_summary`; type `TxSummary`): the card shows You pay / (farm: swap stage) / You get with logos and USD, a via-or-program · fee line and a >5% price-impact warning; steps, route, price impact and the remaining rows (incl. custom-token address rows) sit under a collapsed Details. Minimum received, slippage and points notices are never shown (the checks stay in code). Cards without a summary (sends, WalletConnect) use the row layout.
- No "Sandbox" in the UI or the agent's everyday speech: network labels are plain chain names, the faucet is "Add funds", and the only indicator is the muted "Demo network" line in the Receive sheet. If asked directly, the agent says it's a fork of Ethereum and Avalanche mainnet where no real funds move (`prompt.py`).
- Token logos: built-ins carry CoinGecko URLs (`tokens.py`); custom tokens only when known without an extra call (GeckoTerminal symbol search, saved `lw.tokens` `logo`); otherwise the app draws initials (`components/TokenLogo.tsx`). Chain marks are inline SVGs in `components/ChainIcon.tsx`.
- Uniswap v4 recipe and addresses live in `agent/lazyagent/uniswap.py` (verified on a fork) — change them only with a fork test.
- Trending tokens (`list_trending_tokens`: Avalanche memecoins; RWA project tokens on Ethereum + Avalanche with XAUt0 pinned) come from GeckoTerminal via `agent/lazyagent/trending.py` (read-only, 60 s cache). Categories are a registry (`CATEGORY_NETWORKS` + `CATEGORY_TITLES`) — a new one is a change to `trending.py` plus a prompt line. The tool also sends a `tokens` message the app shows as `TokenListCard` (Buy chips send a normal "Buy 0.5 AVAX of COQ (0x…)" message); titles and spoken category names never name a chain. RWA project tokens are a CoinGecko snapshot in `agent/lazyagent/data/rwa_coingecko.json` — refresh with `uv run --directory agent python -m lazyagent.rwa_snapshot`. Curated `NOT_MEMES` / `NOT_RWA` lists are explained in `docs/research/2026-10-15-avalanche-trending-tokens.md`.
- Any other token or pair goes through KyberSwap (`agent/lazyagent/kyber.py`). Its calldata is untrusted: `verify()` decodes it against the request and it is simulated on the fork (within 5% of the quote) before a card is shown. Change the router address/ABI only with the fork tests (`tests/test_kyber_swap_fork.py`, one token per chain).
- Airdrops (`list_airdrops`, `propose_deposit`) live in `agent/lazyagent/airdrops.py`; the programs are curated by hand in `agent/lazyagent/data/airdrops.json` (each with `source_url`, `verified_at`) and enriched live (DefiLlama TVL, GeckoTerminal liquidity, 10 min cache). `list_airdrops` sends an `airdrops` card; titles never name a chain. Only entries with a `deposit` block are farmable, one per chain: Theo (USDC → thUSD on the pinned v4 pool, KyberSwap fallback, then `sthUSD.deposit`) and Avant (USDC → avUSD on KyberSwap, then `savUSD.deposit`), each ONE confirm card staking the swap's minimum, followed by a balance-change card. Avant is `featured` (ranked first). Avant Season 1 is a demo assumption (`demo_assumption` in the JSON) — never state its real dates. Change a deposit block only with `tests/test_deposit_fork.py`. Points only count on real mainnet — the Sandbox fork earns none; the agent doesn't volunteer this but never claims otherwise.
- Custom tokens: the wallet keeps bought tokens in `lw.tokens` (non-secret, per wallet) and sends them with every `user` message; the agent stays stateless (`agent/lazyagent/custom_tokens.py`).
- Dexalot recipe (Avalanche swaps) lives in `anvil/lazysandbox/dexalot.py` (signer patch, order signing) and `agent/lazyagent/dexalot.py` (calldata) — change only with a fork test.
- Quick actions (`chat/quickActions.ts`) are pills above the composer that send a normal user message (queued while busy). A "Get funds" button calls the faucet directly while the wallet's USD total is under $1,000 — read wallet-side with viem + Chainlink in `chain/portfolio.ts`, re-read after every agent turn; hidden when a read fails.
- Unit tests cover pure logic (`*.test.ts` next to the module). UI is reviewed manually.

## Development motto

1. **Think before coding** — state assumptions, surface trade-offs, ask when unclear.
2. **Simplicity first** — minimum code that solves the problem; nothing speculative.
3. **Surgical changes** — touch only what the task needs; match existing style.
4. **Goal-driven execution** — define verifiable success criteria and loop until they pass.
