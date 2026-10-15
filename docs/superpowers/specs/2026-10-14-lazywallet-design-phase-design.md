# LazyWallet — Phase 1 (Design) Spec

Date: 2026-10-14
Status: Draft — awaiting user review

## 1. Goal

Deliver a clickable, mock-data mockup of the LazyWallet landing page and the full wallet flow, built in the real stack so it can be reused in Phase 2. Plus `README.md` and `CLAUDE.md`. The user reviews the running UI in a browser and comments before any further phase starts.

**Success criteria**
- `pnpm dev` (root) runs both `apps/landing` and `apps/wallet` locally.
- Every screen and scenario in §5 and §6 is reachable by clicking/typing/speaking — no dead ends.
- Seed generation, encrypted vault, unlock, and voice (STT + TTS) work for real in the browser; chain, agent, and WalletConnect are mocked.
- `pnpm build` and `pnpm lint` pass for both apps.

## 2. Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Mockup form | Clickable app with mock data, real stack |
| Signing model (future phases) | Key stays in the browser; agent proposes tx → in-chat confirm card → user approves. Scheduled/conditional tasks run only while the wallet tab is open |
| Voice | Push-to-talk mic + live transcript; AI replies shown as text and spoken aloud (toggle) |
| Chains | Sandbox only (Anvil mainnet fork, chain id 1) for now; no real mainnet, no multi-chain in UI |
| Wallets | Multiple local wallets; create new and import seed phrase |
| Seed storage | Password-encrypted vault (WebCrypto PBKDF2 + AES-GCM) in localStorage; Unlock screen |
| WalletConnect | Included. Feasible on web via Reown WalletKit (`@reown/walletkit`): pair with `wc:` URI → `session_proposal` → approve namespaces → handle `session_request`. Needs a Reown project ID. **Mocked in Phase 1.** |
| x402 | Out of scope for the first few phases |
| UI kit | shadcn/ui on Tailwind v4, React Router |
| Style | Dark-only, neon lime accent, clean and spacious (not dense) |

Known caveat (for later phases): with WalletConnect, a dapp reads real mainnet state while our wallet sends txs to the Anvil fork. Demo with dapps whose relevant state matches the fork.

## 3. Repository layout (Phase 1)

```
apps/landing/   Vite + React + TypeScript + Tailwind v4 (+ shadcn/ui)
apps/wallet/    Vite + React + TypeScript + Tailwind v4 + shadcn/ui + React Router + viem + wagmi
agent/          (empty placeholder README — Phase 2)
anvil/          (empty placeholder README — Phase 2)
docs/superpowers/specs/
README.md
CLAUDE.md
pnpm-workspace.yaml, package.json (root scripts: dev, build, lint)
```

All dependency versions: latest stable, checked at scaffold time (official scaffolders: `pnpm create vite`, `shadcn` CLI). wagmi is installed and configured with a single Sandbox chain (chain id 1, RPC placeholder `http://localhost:8545`) but no live calls are made in Phase 1.

## 4. Visual style

- Dark-only. Background near-black (~`#0A0B0A`), surfaces soft charcoal (~`#141614` / `#1C1F1C`), hairline borders.
- Single accent: neon lime (~`#B6FF3B`), used sparingly — mic button, primary CTAs, success states, active indicators.
- Rounded cards (radius ~16px), generous spacing, large readable type (Inter or system sans). Monospace (e.g. JetBrains Mono) only for amounts, addresses, hashes.
- Mobile-first. Wallet chat column centered, max ~720px on desktop.
- Colors defined as Tailwind/shadcn CSS variables in one theme file per app.

## 5. Screens

### 5.1 Landing (`apps/landing`)
Single page:
- Hero: "Just say it." + subline (voice-powered AI wallet) + **Launch Wallet** CTA (links to wallet app URL from env, default `http://localhost:5174`).
- Animated voice demo: waveform → transcript "Swap 100 USDC to ETH" → confirm card appearing.
- Two audience blocks: **Newcomers** (talk instead of learning DeFi UIs) / **Degens** (schedule trades, price alerts, conditional orders).
- How it works: 3 steps (Speak → Review → Approve).
- Footer.

### 5.2 Wallet (`apps/wallet`) routes

| Route | Screen |
|---|---|
| `/welcome` | Logo, tagline, **Create new wallet**, **Import seed phrase** |
| `/create` | Stepper: 1) Wallet name → 2) Set password (+confirm) → 3) Seed phrase shown (12 words, blurred until tap, copy button, "I've written it down" checkbox) → Finish |
| `/import` | Stepper: 1) Wallet name → 2) Paste 12/24 words (validated) → 3) Set password → Finish |
| `/unlock` | Password field → Unlock; "Forgot? Reset all wallets" (with confirm dialog) |
| `/` | Main wallet (chat) — requires unlocked vault, else redirect to `/unlock` or `/welcome` |

Routing guard: no vault → `/welcome`; vault but locked → `/unlock`.

### 5.3 Main wallet layout
- **Top bar**: `[QR button]` — `[Wallet dropdown]` — `[Address book button]`; small "Sandbox" badge.
- **QR sheet** (from QR button), two tabs:
  - *Receive*: QR of address, copy address, "Sandbox · Ethereum (fork)" note.
  - *Connect dApp*: paste `wc:` URI (camera scan button shown, may be stubbed) → mock session proposal dialog (dapp name/icon/url, requested chain + methods, Approve/Reject).
- **Wallet dropdown**: list of wallets (name, short address, total USD), check on active; actions: Add new, Import, Scheduled tasks, Show seed phrase (password re-prompt), Lock, Delete wallet (confirm).
- **Address book** (sheet): list contacts (name, short address); add/edit/delete; empty state.
- **Scheduled tasks** (sheet): list of tasks (type icon, description, next run / condition, status), pause/resume, delete; note "Tasks run while this tab is open".
- **Chat area**: message list with types:
  - user text (with mic icon if spoken)
  - assistant text (with speaker replay)
  - balance card
  - tx confirm card (action, from/to, amount, est. gas, Approve / Reject)
  - tx status (pending spinner → success with hash / failure)
  - quote card (swap route, price impact, min received)
  - task card (scheduled/conditional)
  - dapp request card (WalletConnect request + plain-language AI explanation, Approve / Reject)
  - Empty state: greeting + example command chips.
- **Connected bar** (only when a mock dapp session exists), above input: dapp icon + site name, chain selector (Sandbox only), Disconnect.
- **Input bar**: text field, send button, large lime push-to-talk mic (hold or tap-to-toggle), live transcript while listening, speaker toggle for spoken replies.

## 6. Mock behaviour

### 6.1 Real in Phase 1
- **Mnemonic & address**: viem `generateMnemonic(english)`, `mnemonicToAccount`.
- **Vault**: `{ wallets: [{ id, name, mnemonic, address }] }` encrypted with password via WebCrypto (PBKDF2-SHA256 → AES-GCM), stored in localStorage; decrypted vault kept in memory only; Lock clears memory.
- **Voice**: Web Speech API `SpeechRecognition` (where supported; otherwise mic shows "not supported in this browser") and `speechSynthesis` for replies.
- Address book, active wallet, speaker toggle, scheduled tasks list: plain localStorage (non-secret).

### 6.2 Mocked (`mockAgent`)
A single module mapping user text (keyword match) to a scripted sequence of chat messages, with small delays to feel real. Balances are fixed fixture values per wallet.

| Input (examples) | Response |
|---|---|
| "what's my balance" | Balance card: ETH, USDC, WBTC + USD totals |
| "send 0.1 ETH to Alice" | Resolve Alice from address book (or ask to add if missing) → confirm card → on Approve: pending → success + fake hash |
| "swap 100 USDC to ETH" | Quote card (Uniswap route) → confirm → success |
| "bridge 0.05 ETH to Base" | Text: multi-chain coming soon, Sandbox is Ethereum only |
| "buy ETH every Monday with 50 USDC" | Task card (DCA) + added to Scheduled tasks |
| "alert me if ETH drops below 3000" | Task card (price alert) |
| "if ETH < 3000 swap 500 USDC to ETH" | Task card (conditional order); a "Simulate trigger" action fires a confirm card |
| WalletConnect: paste any `wc:` URI | Fake "Uniswap" proposal → Connected bar → after a few seconds a fake `eth_sendTransaction` request card with AI explanation |
| anything else | Friendly fallback listing example commands |

Rejecting any confirm card yields an assistant "Cancelled" message.

## 7. Docs

- **README.md**: what LazyWallet is, monorepo layout, prerequisites (Node LTS, pnpm, Foundry later), `pnpm install` / `pnpm dev`, current phase status, roadmap (Phase 1 design → Phase 2 MVP AI wallet → …), note x402 deferred.
- **CLAUDE.md**: project summary, stack & folder structure, Development Motto (from INIT.md), conventions (TypeScript, shadcn components in `src/components/ui`, theme tokens, mock vs real boundaries), commands, "do not reinvent frameworks" rule, current phase and its gate (wait for user approval before next phase).

## 8. Out of scope (Phase 1)
Agent backend (Python Claude Agent SDK), x402, Anvil fork & seed/faucet scripts, any real RPC/chain call, real WalletConnect pairing, multi-chain, real mainnet, automated tests beyond build/lint (UI is reviewed manually by the user).

## 9. Verification
1. `pnpm install && pnpm build && pnpm lint` succeed.
2. Run both apps; walk through: landing → Launch → create wallet → seed shown → chat → each §6.2 scenario → lock → unlock → import second wallet → switch wallets → address book CRUD → scheduled tasks → WalletConnect mock → disconnect.
3. Reload page: vault persists encrypted (localStorage contains no plaintext mnemonic), unlock required.
