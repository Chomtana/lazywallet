# LazyWallet

A voice-powered AI wallet for newcomers and degens. Say what you want — check balances, send, swap, set price alerts, recurring buys or conditional orders — and approve each transaction in the chat. Runs in the browser; keys stay on your device.

> **Status: Phase 3 — Uniswap v4 swaps.** The chat runs on a real Claude agent. Balances, ETH/ERC-20 sends and Uniswap v4 swaps are real on "Sandbox" (an Anvil fork of Ethereum mainnet). Bridges, scheduled tasks and WalletConnect are still mocked or "coming soon".

## Repo layout

| Path | What |
|---|---|
| `apps/landing` | Landing page (Vite + React + Tailwind) — http://localhost:5173 |
| `apps/wallet` | Wallet app (Vite + React + Tailwind + shadcn/ui + viem + wagmi) — http://localhost:5174 |
| `agent/` | Python agent (FastAPI + Claude Agent SDK) — ws://localhost:8787/ws |
| `anvil/` | Anvil mainnet fork :8545 + faucet :8547 |
| `docs/superpowers/` | Design specs and implementation plans |

## Getting started

Requires Node.js LTS, pnpm, [uv](https://docs.astral.sh/uv/), [Foundry](https://getfoundry.sh) (Anvil) and a logged-in [Claude Code](https://code.claude.com).

```bash
cp .env.example .env   # set ETH_RPC_URL to an Ethereum mainnet archive RPC
pnpm install
pnpm dev:sandbox       # terminal 1: Anvil fork + faucet
pnpm dev:agent         # terminal 2: AI agent
pnpm dev               # terminal 3: landing :5173, wallet :5174
pnpm test && pnpm test:py
```

Voice input uses the browser's Web Speech API — use Chrome or Edge. Other browsers can still type.

## Try it

Create a wallet, then say or type:

- "Give me test funds" (Sandbox faucet: 100 ETH + test tokens — also on Receive → **Get test funds**)
- "What's my balance?"
- "Send 0.1 ETH to Alice"
- "Send 50 USDC to Bob"
- "Swap 0.5 ETH to USDC"
- "Swap 100 USDC to ETH with 0.5% slippage"
- "Swap 0.01 ETH to LIT"

To try the (still mocked) dApp flow: QR button → Connect dApp → paste any WalletConnect v2 link (`wc:…@2?relay-protocol=…&symKey=…`).

## Roadmap

1. **Design** — landing + clickable wallet mockup. ✅
2. **Minimum viable AI wallet** — Python agent, Anvil sandbox, real balances and transfers. ✅
3. **Uniswap v4 swaps** (current) — best hookless route, approvals in one card.
4. Next — other protocols, real WalletConnect (Reown WalletKit), scheduled tasks, more chains, x402 payments.
