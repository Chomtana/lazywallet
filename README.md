# LazyWallet

A voice-powered AI wallet for newcomers and degens. Say what you want — check balances, send, swap, set price alerts, recurring buys or conditional orders — and approve each transaction in the chat. Runs in the browser; keys stay on your device.

> **Status: Phase 1 — design mockup.** The wallet UI is clickable end-to-end. Seed generation, the encrypted vault and voice are real; the AI agent, balances, transactions and WalletConnect are mocked. Everything runs against "Sandbox" (an Ethereum mainnet fork) only.

## Repo layout

| Path | What |
|---|---|
| `apps/landing` | Landing page (Vite + React + Tailwind) — http://localhost:5173 |
| `apps/wallet` | Wallet app (Vite + React + Tailwind + shadcn/ui + viem + wagmi) — http://localhost:5174 |
| `agent/` | Python Claude Agent SDK agent — Phase 2 |
| `anvil/` | Anvil mainnet-fork sandbox, seed scripts, faucet — Phase 2 |
| `docs/superpowers/` | Design specs and implementation plans |

## Getting started

Requires Node.js LTS and pnpm.

```bash
pnpm install
pnpm dev      # landing on :5173, wallet on :5174
pnpm test     # unit tests
pnpm build
pnpm lint
```

Voice input uses the browser's Web Speech API — use Chrome or Edge. Other browsers can still type.

## Try it

Create a wallet, then say or type:

- "What's my balance?"
- "Send 0.1 ETH to Alice"
- "Swap 100 USDC to ETH"
- "Alert me if ETH drops below 3000"
- "Buy ETH every Monday with 50 USDC"
- "If ETH < 3000, swap 500 USDC to ETH" → tap *Simulate trigger*

To try the dApp flow: QR button → Connect dApp → paste any WalletConnect v2 link (`wc:…@2?relay-protocol=…&symKey=…`).

## Roadmap

1. **Design** (current) — landing + clickable wallet mockup.
2. **Minimum viable AI wallet** — Python agent, Anvil sandbox, real transactions, real WalletConnect (Reown WalletKit).
3. Later — more chains, x402 payments.
