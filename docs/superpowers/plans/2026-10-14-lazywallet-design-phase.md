# LazyWallet Phase 1 (Design Mockup) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a clickable, mock-data mockup of the LazyWallet landing page and full wallet flow (real seed/vault/voice, mocked agent/chain/WalletConnect), plus README.md and CLAUDE.md.

**Architecture:** pnpm monorepo with two Vite + React + TypeScript apps. `apps/wallet` keeps the encrypted vault in localStorage and the decrypted vault in a React context; a pure `mock/agent.ts` maps user text to scripted chat messages; UI is shadcn/ui on Tailwind v4 with React Router. `apps/landing` is a single static page. No network calls are made in this phase.

**Tech Stack:** pnpm workspaces, Vite, React, TypeScript, Tailwind CSS v4 (`@tailwindcss/vite`), shadcn/ui (Radix), React Router, viem, wagmi + @tanstack/react-query, @scure/bip39, qrcode.react, lucide-react, sonner, Vitest + jsdom.

**Spec:** `docs/superpowers/specs/2026-10-14-lazywallet-design-phase-design.md`

## Global Constraints

- Use latest stable versions via official scaffolders (`pnpm create vite@latest`, `pnpm dlx shadcn@latest`). Versions seen on 2026-10-14: vite 8.3, react 19.3, react-router 8.4, tailwindcss 4.3, viem 2.57, wagmi 3.7, vitest 5.0, shadcn 4.21, typescript 7.0. If an API in this plan differs in the installed major version, look it up with context7 and adapt — don't downgrade.
- Do not use `baseUrl` in tsconfig (removed in TypeScript 7); use `paths` only.
- Dark-only UI. `<html class="dark">`. Accent neon lime `#B6FF3B`, background `#0A0B0A`, surfaces `#141614` / `#1C1F1C`, border `#262A26`. Fonts: Inter (sans), JetBrains Mono (amounts, addresses, hashes only).
- Wallet chat column max width 720px, mobile-first, 16px side gutter.
- Ports: landing `5173`, wallet `5174` (`strictPort: true`).
- Network: Sandbox only (chain id 1, Anvil fork). No real mainnet, no multi-chain, no RPC/HTTP calls in Phase 1.
- Seed phrases are never written to storage in plaintext — only the encrypted vault (PBKDF2-SHA256 210,000 iterations → AES-GCM 256).
- x402, agent backend, Anvil scripts, real WalletConnect pairing: out of scope.
- shadcn/ui: choose **Radix** as the primitive library and **Neutral** base color when prompted. Don't use `asChild`; navigate with `useNavigate()`.
- Tests: the spec excludes UI tests; this plan adds Vitest unit tests for pure logic modules only (vault, storage, agent, parsing, validation, routing rules).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Wrong password at Unlock or Show-seed → shows "Wrong password", no crash, stored vault untouched. (Task 3 test)
2. Imperfect seed input on Import — extra spaces/newlines/capitals, 11 words, misspelled word, a wallet already added — is normalized or rejected with a clear message. (Task 3 + Task 5)
3. Voice transcripts with capitals, trailing punctuation and thousands separators ("Send 0.1 ETH to Alice.", "$3,000") behave exactly like typed text. (Task 6 test)
4. Send to an unknown name, more than the balance, or zero → explanatory text, never a confirm card. (Task 6 test)
5. Browser without SpeechRecognition (Firefox) or with broken/blocked localStorage → app still renders, typing works, mic is disabled with an explanation, failed saves are reported. (Task 2 + Task 7 tests)

---

## File Structure

```
package.json                     root scripts (dev/build/lint/test)
pnpm-workspace.yaml
.gitignore
README.md, CLAUDE.md             (Task 12)
agent/README.md, anvil/README.md placeholders (Task 12)
apps/landing/
  index.html, vite.config.ts, .env.example
  src/main.tsx, src/App.tsx, src/index.css
  src/components/{Hero,VoiceDemo,Audience,HowItWorks}.tsx
apps/wallet/
  index.html, vite.config.ts, components.json, .env.example
  src/main.tsx                   providers (wagmi, react-query, wallet)
  src/App.tsx                    router + toaster
  src/index.css                  tailwind + shadcn tokens (dark theme)
  src/types.ts                   shared domain + chat message types
  src/lib/utils.ts               shadcn cn() (generated)
  src/lib/storage.ts             safe localStorage JSON helpers + keys
  src/lib/useStored.ts           React hook persisting state to localStorage
  src/lib/format.ts              shortAddress, formatUsd, formatAmount, hostOf, uid, txHash
  src/lib/vault.ts               mnemonic helpers + vault encrypt/decrypt
  src/lib/password.ts            password rules
  src/lib/contacts.ts            contact validation
  src/lib/wagmi.ts               wagmi config with Sandbox chain
  src/state/wallet-context.ts    context type + useWallet()
  src/state/WalletProvider.tsx   vault state & actions
  src/routes/redirect.ts         pure routing rules
  src/routes/GuardedLayout.tsx
  src/routes/{Welcome,Unlock,Create,Import,WalletPage}.tsx
  src/components/{Logo,AuthLayout,StepHeader,NameForm,PasswordStep,SeedPhrase}.tsx
  src/components/{TopBar,WalletMenu,ShowSeedDialog,DeleteWalletDialog}.tsx
  src/components/{AddressBookSheet,TasksSheet,QrSheet,ConnectedBar}.tsx
  src/components/ui/*            shadcn generated
  src/chat/useChat.ts            chat state, approve/reject, mock delays
  src/chat/{ChatView,MessageItem,InputBar}.tsx
  src/chat/cards/{TextBubble,BalanceCard,ConfirmCard,StatusCard,TaskCard}.tsx
  src/chat/cards/task-icons.ts
  src/mock/fixtures.ts           holdings, default contacts, example prompts, Uniswap dapp
  src/mock/agent.ts              respond(), simulateTrigger(), say(), confirm()
  src/mock/walletconnect.ts      isWcUri(), mockProposal(), dappRequest()
  src/voice/speech.ts            getRecognitionCtor(), useSpeechRecognition(), speak()
```

---

### Task 1: Monorepo + wallet app scaffold with theme

**Files:**
- Create: `package.json`, `pnpm-workspace.yaml`, `.gitignore`
- Create (scaffolded): `apps/wallet/*`
- Modify: `apps/wallet/vite.config.ts`, `apps/wallet/tsconfig.json`, `apps/wallet/tsconfig.app.json`, `apps/wallet/index.html`, `apps/wallet/src/index.css`, `apps/wallet/src/main.tsx`, `apps/wallet/src/App.tsx`, `apps/wallet/package.json`
- Create: `apps/wallet/src/lib/wagmi.ts`, `apps/wallet/.env.example`

**Interfaces:**
- Produces: `@/` import alias → `apps/wallet/src`; shadcn components at `@/components/ui/*`; `cn()` at `@/lib/utils`; `wagmiConfig`, `sandbox` from `@/lib/wagmi`; `pnpm --filter wallet test` runs Vitest (jsdom default).

- [ ] **Step 1: Root workspace files**

`package.json`:
```json
{
  "name": "lazywallet",
  "private": true,
  "packageManager": "pnpm@10.11.0",
  "scripts": {
    "dev": "pnpm -r --parallel --if-present run dev",
    "build": "pnpm -r --if-present run build",
    "lint": "pnpm -r --if-present run lint",
    "test": "pnpm -r --if-present run test"
  }
}
```

`pnpm-workspace.yaml`:
```yaml
packages:
  - "apps/*"
```

`.gitignore`:
```
node_modules
dist
.env
.env.local
.DS_Store
*.log
```

- [ ] **Step 2: Scaffold the wallet app**

Run from repo root:
```bash
pnpm create vite@latest apps/wallet --template react-ts
```
Answer "No" to any "install and start now" prompt. Then:
```bash
cd apps/wallet
pnpm install
pnpm add tailwindcss @tailwindcss/vite viem wagmi @tanstack/react-query @scure/bip39 react-router qrcode.react lucide-react
pnpm add -D @types/node vitest jsdom
```
If pnpm reports ignored build scripts, run `pnpm approve-builds` and approve them.

- [ ] **Step 3: Vite config with alias, port, Tailwind, Vitest**

Replace `apps/wallet/vite.config.ts`:
```ts
/// <reference types="vitest/config" />
import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: { port: 5174, strictPort: true },
  test: { environment: 'jsdom' },
})
```
(If the template uses a different React plugin package name, keep the template's import.)

In both `apps/wallet/tsconfig.json` and `apps/wallet/tsconfig.app.json`, add under `compilerOptions` (create the key in `tsconfig.json` if missing):
```json
"paths": { "@/*": ["./src/*"] }
```

Add to `apps/wallet/package.json` scripts: `"test": "vitest run"`.

- [ ] **Step 4: Tailwind entry + shadcn init**

Replace `apps/wallet/src/index.css` with:
```css
@import "tailwindcss";
```
Run in `apps/wallet`:
```bash
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add button input label badge checkbox dialog dropdown-menu sheet tabs textarea sonner
```
Choose Radix and Neutral when asked.

- [ ] **Step 5: Dark lime theme**

In `apps/wallet/src/index.css` (now generated by shadcn), replace the whole `.dark { ... }` block with:
```css
.dark {
  --background: #0a0b0a;
  --foreground: #edefea;
  --card: #141614;
  --card-foreground: #edefea;
  --popover: #141614;
  --popover-foreground: #edefea;
  --primary: #b6ff3b;
  --primary-foreground: #0a0b0a;
  --secondary: #1c1f1c;
  --secondary-foreground: #edefea;
  --muted: #1c1f1c;
  --muted-foreground: #8a918a;
  --accent: #1c1f1c;
  --accent-foreground: #edefea;
  --destructive: #ff5a5a;
  --border: #262a26;
  --input: #262a26;
  --ring: #b6ff3b;
}
```
Set `--radius: 1rem;` in the `:root` block. Inside the existing `@theme inline { ... }` block add:
```css
  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
```

In `apps/wallet/index.html`: set `<html lang="en" class="dark">`, `<title>LazyWallet</title>`, and add in `<head>`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
```

- [ ] **Step 6: wagmi config + providers**

`apps/wallet/src/lib/wagmi.ts`:
```ts
import { createConfig, http } from 'wagmi'
import { defineChain } from 'viem'

export const sandbox = defineChain({
  id: 1,
  name: 'Sandbox (Ethereum fork)',
  nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
  rpcUrls: { default: { http: [import.meta.env.VITE_SANDBOX_RPC_URL ?? 'http://localhost:8545'] } },
})

export const wagmiConfig = createConfig({
  chains: [sandbox],
  transports: { [sandbox.id]: http() },
})
```

`apps/wallet/.env.example`:
```
VITE_SANDBOX_RPC_URL=http://localhost:8545
```

Replace `apps/wallet/src/main.tsx`:
```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { WagmiProvider } from 'wagmi'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { wagmiConfig } from '@/lib/wagmi'
import App from './App'
import './index.css'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <WagmiProvider config={wagmiConfig}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </WagmiProvider>
  </StrictMode>,
)
```

Replace `apps/wallet/src/App.tsx` (temporary until Task 4):
```tsx
import { Button } from '@/components/ui/button'

export default function App() {
  return (
    <div className="flex min-h-dvh items-center justify-center">
      <Button size="lg">LazyWallet</Button>
    </div>
  )
}
```
Delete `src/App.css` and template assets that are now unused (`src/assets/react.svg`, `public/vite.svg` if referenced nowhere).

- [ ] **Step 7: Verify**

Run: `pnpm --filter wallet build && pnpm --filter wallet lint`
Expected: both succeed.
Run: `pnpm --filter wallet dev`, open http://localhost:5174
Expected: near-black page with a lime "LazyWallet" button in Inter.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: scaffold pnpm monorepo and wallet app with dark lime theme"
```

---

### Task 2: Storage, formatting helpers

**Files:**
- Create: `apps/wallet/src/lib/storage.ts`, `apps/wallet/src/lib/useStored.ts`, `apps/wallet/src/lib/format.ts`
- Test: `apps/wallet/src/lib/storage.test.ts`, `apps/wallet/src/lib/format.test.ts`

**Interfaces:**
- Produces:
  - `KEYS = { vault, active, contacts, tasks, speak }` (string constants)
  - `readJSON<T>(key: string, fallback: T): T`
  - `writeJSON(key: string, value: unknown): boolean`
  - `removeKey(key: string): void`
  - `useStored<T>(key: string, initial: T): readonly [T, Dispatch<SetStateAction<T>>]`
  - `shortAddress(a: string): string`, `formatUsd(n: number): string`, `formatAmount(n: number): string`, `hostOf(url: string): string`, `uid(): string`, `txHash(): string`

- [ ] **Step 1: Write failing tests**

`apps/wallet/src/lib/storage.test.ts`:
```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { readJSON, removeKey, writeJSON } from './storage'

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('storage', () => {
  it('round-trips JSON', () => {
    expect(writeJSON('k', { a: 1 })).toBe(true)
    expect(readJSON('k', null)).toEqual({ a: 1 })
  })

  it('returns fallback for missing key', () => {
    expect(readJSON('missing', 42)).toBe(42)
  })

  it('returns fallback for corrupt JSON', () => {
    localStorage.setItem('k', '{not json')
    expect(readJSON('k', 'fallback')).toBe('fallback')
  })

  it('returns fallback when storage throws on read', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(readJSON('k', 'fallback')).toBe('fallback')
  })

  it('reports false when storage throws on write', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    expect(writeJSON('k', 1)).toBe(false)
  })

  it('removeKey never throws', () => {
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(() => removeKey('k')).not.toThrow()
  })
})
```

`apps/wallet/src/lib/format.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { formatAmount, formatUsd, hostOf, shortAddress, txHash } from './format'

describe('format', () => {
  it('shortens addresses', () => {
    expect(shortAddress('0x70997970C51812dc3A010C7d01b50e0d17dc79C8')).toBe('0x7099…79C8')
    expect(shortAddress('0x1234')).toBe('0x1234')
  })

  it('formats USD', () => {
    expect(formatUsd(1234.5)).toBe('$1,234.50')
  })

  it('formats amounts to 6 significant digits without trailing zeros', () => {
    expect(formatAmount(0.031171875)).toBe('0.0311719')
    expect(formatAmount(1500)).toBe('1500')
    expect(formatAmount(2.5)).toBe('2.5')
  })

  it('extracts host, falling back to input', () => {
    expect(hostOf('https://app.uniswap.org/swap')).toBe('app.uniswap.org')
    expect(hostOf('not a url')).toBe('not a url')
  })

  it('makes 32-byte hex hashes', () => {
    expect(txHash()).toMatch(/^0x[0-9a-f]{64}$/)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter wallet test`
Expected: FAIL — cannot resolve `./storage` / `./format`.

- [ ] **Step 3: Implement**

`apps/wallet/src/lib/storage.ts`:
```ts
export const KEYS = {
  vault: 'lw.vault',
  active: 'lw.active',
  contacts: 'lw.contacts',
  tasks: 'lw.tasks',
  speak: 'lw.speak',
} as const

export function readJSON<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}

export function writeJSON(key: string, value: unknown): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(value))
    return true
  } catch {
    return false
  }
}

export function removeKey(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    // storage unavailable — nothing to remove
  }
}
```

`apps/wallet/src/lib/useStored.ts`:
```ts
import { useEffect, useState } from 'react'
import { readJSON, writeJSON } from './storage'

export function useStored<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => readJSON(key, initial))
  useEffect(() => {
    writeJSON(key, value)
  }, [key, value])
  return [value, setValue] as const
}
```

`apps/wallet/src/lib/format.ts`:
```ts
const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export function shortAddress(a: string): string {
  return a.length > 12 ? `${a.slice(0, 6)}…${a.slice(-4)}` : a
}

export function formatUsd(n: number): string {
  return usd.format(n)
}

export function formatAmount(n: number): string {
  return Number(n.toPrecision(6)).toString()
}

export function hostOf(url: string): string {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

export function uid(): string {
  return crypto.randomUUID()
}

export function txHash(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32))
  return '0x' + Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter wallet test`
Expected: PASS (all storage + format tests).

- [ ] **Step 5: Commit**

```bash
git add apps/wallet/src/lib
git commit -m "feat(wallet): add safe storage and formatting helpers"
```

---

### Task 3: Vault (mnemonics + encryption) and password rules

**Files:**
- Create: `apps/wallet/src/types.ts`, `apps/wallet/src/lib/vault.ts`, `apps/wallet/src/lib/password.ts`
- Test: `apps/wallet/src/lib/vault.test.ts`, `apps/wallet/src/lib/password.test.ts`

**Interfaces:**
- Consumes: `uid()` from `@/lib/format`
- Produces (`src/types.ts`, full file — later tasks import from here):
```ts
export type Address = `0x${string}`
export type StoredWallet = { id: string; name: string; mnemonic: string; address: Address }
export type Vault = { wallets: StoredWallet[] }
export type EncryptedVault = { v: 1; salt: string; iv: string; data: string }
export type Contact = { id: string; name: string; address: Address }
export type Holding = { symbol: string; amount: number; usdPrice: number }
export type DappInfo = { name: string; url: string; icon: string }
export type TxDraft = {
  title: string
  rows: { label: string; value: string }[]
  dapp?: DappInfo
  explanation?: string
}
export type TaskKind = 'dca' | 'alert' | 'conditional'
export type Task = {
  id: string
  kind: TaskKind
  description: string
  schedule: string
  status: 'active' | 'paused'
  trigger?: TxDraft
}
export type ConfirmState = 'waiting' | 'approved' | 'rejected'
export type Message =
  | { id: string; role: 'user'; kind: 'text'; text: string; spoken?: boolean }
  | { id: string; role: 'assistant'; kind: 'text'; text: string }
  | { id: string; role: 'assistant'; kind: 'balance'; holdings: Holding[] }
  | { id: string; role: 'assistant'; kind: 'confirm'; tx: TxDraft; state: ConfirmState }
  | { id: string; role: 'assistant'; kind: 'status'; state: 'pending' | 'success'; text: string; hash?: string }
  | { id: string; role: 'assistant'; kind: 'task'; task: Task }
export type AssistantMessage = Exclude<Message, { role: 'user' }>
export type AgentReply = { messages: Message[]; newTask?: Task }
```
- Produces (`lib/vault.ts`): `newMnemonic(): string`, `normalizeMnemonic(input: string): string`, `isValidMnemonic(m: string): boolean`, `addressFromMnemonic(m: string): Address`, `walletFromMnemonic(name: string, mnemonic: string): StoredWallet`, `encryptVault(v: Vault, password: string): Promise<EncryptedVault>`, `decryptVault(e: EncryptedVault, password: string): Promise<Vault>` (throws `WrongPasswordError`), `class WrongPasswordError`
- Produces (`lib/password.ts`): `validatePassword(pw: string, confirm: string): string | null`

- [ ] **Step 1: Create `src/types.ts`** with exactly the content in Interfaces above.

- [ ] **Step 2: Write failing tests**

`apps/wallet/src/lib/vault.test.ts`:
```ts
// @vitest-environment node
import { describe, expect, it } from 'vitest'
import {
  WrongPasswordError,
  decryptVault,
  encryptVault,
  isValidMnemonic,
  newMnemonic,
  normalizeMnemonic,
  walletFromMnemonic,
} from './vault'

const TEST_MNEMONIC = 'test test test test test test test test test test test junk'

describe('mnemonics', () => {
  it('generates a valid 12-word mnemonic', () => {
    const m = newMnemonic()
    expect(m.split(' ')).toHaveLength(12)
    expect(isValidMnemonic(m)).toBe(true)
  })

  it('normalizes spacing, newlines and case', () => {
    expect(normalizeMnemonic('  Test test\n\ntest  TEST ')).toBe('test test test test')
  })

  it('rejects wrong word count and misspelled words', () => {
    expect(isValidMnemonic('test test test test test test test test test test test')).toBe(false)
    expect(isValidMnemonic('test test test test test test test test test test test junkk')).toBe(false)
  })

  it('derives the standard first account', () => {
    const w = walletFromMnemonic('  Main ', TEST_MNEMONIC)
    expect(w.name).toBe('Main')
    expect(w.address).toBe('0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266')
    expect(w.id).toBeTruthy()
  })
})

describe('vault encryption', () => {
  const vault = { wallets: [walletFromMnemonic('Main', TEST_MNEMONIC)] }

  it('round-trips with the right password', async () => {
    const enc = await encryptVault(vault, 'hunter22')
    expect(await decryptVault(enc, 'hunter22')).toEqual(vault)
  })

  it('throws WrongPasswordError with the wrong password', async () => {
    const enc = await encryptVault(vault, 'hunter22')
    await expect(decryptVault(enc, 'nope')).rejects.toBeInstanceOf(WrongPasswordError)
  })

  it('does not contain the plaintext mnemonic', async () => {
    const enc = await encryptVault(vault, 'hunter22')
    expect(JSON.stringify(enc)).not.toContain('junk')
  })

  it('uses a fresh salt and iv each time', async () => {
    const a = await encryptVault(vault, 'hunter22')
    const b = await encryptVault(vault, 'hunter22')
    expect(a.salt).not.toBe(b.salt)
    expect(a.iv).not.toBe(b.iv)
  })
})
```

`apps/wallet/src/lib/password.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { validatePassword } from './password'

describe('validatePassword', () => {
  it('requires 8+ characters', () => {
    expect(validatePassword('short', 'short')).toBe('Use at least 8 characters')
  })
  it('requires matching confirmation', () => {
    expect(validatePassword('longenough', 'different')).toBe('Passwords do not match')
  })
  it('accepts a good password', () => {
    expect(validatePassword('longenough', 'longenough')).toBeNull()
  })
})
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pnpm --filter wallet test`
Expected: FAIL — cannot resolve `./vault` / `./password`.

- [ ] **Step 4: Implement**

`apps/wallet/src/lib/vault.ts`:
```ts
import { english, generateMnemonic, mnemonicToAccount } from 'viem/accounts'
import { validateMnemonic } from '@scure/bip39'
import type { Address, EncryptedVault, StoredWallet, Vault } from '@/types'
import { uid } from './format'

const ITERATIONS = 210_000

export class WrongPasswordError extends Error {
  constructor() {
    super('Wrong password')
    this.name = 'WrongPasswordError'
  }
}

export function newMnemonic(): string {
  return generateMnemonic(english)
}

export function normalizeMnemonic(input: string): string {
  return input.trim().toLowerCase().split(/\s+/).join(' ')
}

export function isValidMnemonic(m: string): boolean {
  const count = m.split(' ').length
  return (count === 12 || count === 24) && validateMnemonic(m, english)
}

export function addressFromMnemonic(m: string): Address {
  return mnemonicToAccount(m).address
}

export function walletFromMnemonic(name: string, mnemonic: string): StoredWallet {
  return { id: uid(), name: name.trim(), mnemonic, address: addressFromMnemonic(mnemonic) }
}

const toB64 = (bytes: Uint8Array) => btoa(String.fromCharCode(...bytes))
const fromB64 = (s: string) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0))

async function deriveKey(password: string, salt: Uint8Array<ArrayBuffer>): Promise<CryptoKey> {
  const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, [
    'deriveKey',
  ])
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: ITERATIONS, hash: 'SHA-256' },
    base,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  )
}

export async function encryptVault(vault: Vault, password: string): Promise<EncryptedVault> {
  const salt = crypto.getRandomValues(new Uint8Array(16))
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const key = await deriveKey(password, salt)
  const data = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    new TextEncoder().encode(JSON.stringify(vault)),
  )
  return { v: 1, salt: toB64(salt), iv: toB64(iv), data: toB64(new Uint8Array(data)) }
}

export async function decryptVault(enc: EncryptedVault, password: string): Promise<Vault> {
  const key = await deriveKey(password, fromB64(enc.salt))
  try {
    const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: fromB64(enc.iv) }, key, fromB64(enc.data))
    return JSON.parse(new TextDecoder().decode(plain)) as Vault
  } catch {
    throw new WrongPasswordError()
  }
}
```
If TypeScript rejects the `Uint8Array<ArrayBuffer>` annotation in the installed version, use `Uint8Array` instead.

`apps/wallet/src/lib/password.ts`:
```ts
export function validatePassword(pw: string, confirm: string): string | null {
  if (pw.length < 8) return 'Use at least 8 characters'
  if (pw !== confirm) return 'Passwords do not match'
  return null
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pnpm --filter wallet test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/wallet/src/types.ts apps/wallet/src/lib
git commit -m "feat(wallet): add mnemonic helpers and encrypted vault"
```

---

### Task 4: Wallet state, routing guard, Welcome and Unlock

**Files:**
- Create: `apps/wallet/src/state/wallet-context.ts`, `apps/wallet/src/state/WalletProvider.tsx`
- Create: `apps/wallet/src/routes/redirect.ts`, `apps/wallet/src/routes/GuardedLayout.tsx`, `apps/wallet/src/routes/Welcome.tsx`, `apps/wallet/src/routes/Unlock.tsx`, `apps/wallet/src/routes/WalletPage.tsx`
- Create: `apps/wallet/src/components/Logo.tsx`, `apps/wallet/src/components/AuthLayout.tsx`
- Modify: `apps/wallet/src/App.tsx`
- Test: `apps/wallet/src/routes/redirect.test.ts`

**Interfaces:**
- Consumes: `KEYS`, `readJSON`, `writeJSON`, `removeKey` (Task 2); vault functions + types (Task 3)
- Produces:
  - `type Status = 'none' | 'locked' | 'unlocked'`
  - `useWallet(): WalletCtx` where
```ts
type WalletCtx = {
  status: Status
  wallets: StoredWallet[]
  active: StoredWallet | null
  addWallet(name: string, mnemonic: string, newPassword?: string): Promise<boolean>
  unlock(password: string): Promise<void>        // throws WrongPasswordError
  verifyPassword(password: string): Promise<boolean>
  lock(): void
  setActive(id: string): void
  deleteWallet(id: string): Promise<void>
  resetAll(): void
}
```
  - `redirectFor(status: Status, path: string): string | null`
  - `<AuthLayout>` and `<Logo className?>` components

- [ ] **Step 1: Write failing test**

`apps/wallet/src/routes/redirect.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { redirectFor } from './redirect'

describe('redirectFor', () => {
  it.each([
    ['none', '/', '/welcome'],
    ['locked', '/', '/unlock'],
    ['unlocked', '/', null],
    ['none', '/unlock', '/welcome'],
    ['locked', '/unlock', null],
    ['unlocked', '/unlock', '/'],
    ['none', '/welcome', null],
    ['locked', '/welcome', '/unlock'],
    ['unlocked', '/welcome', '/'],
    ['none', '/create', null],
    ['locked', '/create', '/unlock'],
    ['unlocked', '/create', null],
    ['locked', '/import', '/unlock'],
    ['unlocked', '/import', null],
  ] as const)('%s at %s → %s', (status, path, expected) => {
    expect(redirectFor(status, path)).toBe(expected)
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm --filter wallet test`
Expected: FAIL — cannot resolve `./redirect`.

- [ ] **Step 3: Implement redirect + context**

`apps/wallet/src/state/wallet-context.ts`:
```ts
import { createContext, useContext } from 'react'
import type { StoredWallet } from '@/types'

export type Status = 'none' | 'locked' | 'unlocked'

export type WalletCtx = {
  status: Status
  wallets: StoredWallet[]
  active: StoredWallet | null
  addWallet(name: string, mnemonic: string, newPassword?: string): Promise<boolean>
  unlock(password: string): Promise<void>
  verifyPassword(password: string): Promise<boolean>
  lock(): void
  setActive(id: string): void
  deleteWallet(id: string): Promise<void>
  resetAll(): void
}

export const WalletContext = createContext<WalletCtx | null>(null)

export function useWallet(): WalletCtx {
  const ctx = useContext(WalletContext)
  if (!ctx) throw new Error('useWallet must be used inside <WalletProvider>')
  return ctx
}
```

`apps/wallet/src/routes/redirect.ts`:
```ts
import type { Status } from '@/state/wallet-context'

// Locked users must never reach /create or /import: creating a new vault there would overwrite the locked one.
export function redirectFor(status: Status, path: string): string | null {
  switch (path) {
    case '/':
      return status === 'none' ? '/welcome' : status === 'locked' ? '/unlock' : null
    case '/unlock':
      return status === 'none' ? '/welcome' : status === 'unlocked' ? '/' : null
    case '/welcome':
      return status === 'locked' ? '/unlock' : status === 'unlocked' ? '/' : null
    case '/create':
    case '/import':
      return status === 'locked' ? '/unlock' : null
    default:
      return null
  }
}
```

`apps/wallet/src/state/WalletProvider.tsx`:
```tsx
import { useState, type ReactNode } from 'react'
import { KEYS, readJSON, removeKey, writeJSON } from '@/lib/storage'
import { decryptVault, encryptVault, walletFromMnemonic } from '@/lib/vault'
import type { EncryptedVault, Vault } from '@/types'
import { WalletContext, type Status, type WalletCtx } from './wallet-context'

const loadEncrypted = () => readJSON<EncryptedVault | null>(KEYS.vault, null)

export function WalletProvider({ children }: { children: ReactNode }) {
  const [vault, setVault] = useState<Vault | null>(null)
  const [password, setPassword] = useState<string | null>(null)
  const [hasStored, setHasStored] = useState(() => loadEncrypted() !== null)
  const [activeId, setActiveId] = useState<string | null>(() => readJSON<string | null>(KEYS.active, null))

  const status: Status = vault ? 'unlocked' : hasStored ? 'locked' : 'none'
  const wallets = vault?.wallets ?? []
  const active = wallets.find((w) => w.id === activeId) ?? wallets[0] ?? null

  function setActive(id: string) {
    setActiveId(id)
    writeJSON(KEYS.active, id)
  }

  async function persist(next: Vault, pw: string): Promise<boolean> {
    const ok = writeJSON(KEYS.vault, await encryptVault(next, pw))
    if (ok) {
      setVault(next)
      setPassword(pw)
      setHasStored(true)
    }
    return ok
  }

  async function addWallet(name: string, mnemonic: string, newPassword?: string) {
    const pw = password ?? newPassword
    if (!pw) throw new Error('A password is required to create the vault')
    const wallet = walletFromMnemonic(name, mnemonic)
    const ok = await persist({ wallets: [...wallets, wallet] }, pw)
    if (ok) setActive(wallet.id)
    return ok
  }

  async function unlock(pw: string) {
    const enc = loadEncrypted()
    if (!enc) throw new Error('No vault on this device')
    setVault(await decryptVault(enc, pw))
    setPassword(pw)
  }

  async function verifyPassword(pw: string) {
    const enc = loadEncrypted()
    if (!enc) return false
    try {
      await decryptVault(enc, pw)
      return true
    } catch {
      return false
    }
  }

  function lock() {
    setVault(null)
    setPassword(null)
  }

  function resetAll() {
    removeKey(KEYS.vault)
    removeKey(KEYS.active)
    setVault(null)
    setPassword(null)
    setHasStored(false)
    setActiveId(null)
  }

  async function deleteWallet(id: string) {
    const rest = wallets.filter((w) => w.id !== id)
    if (rest.length === 0) return resetAll()
    if (password) await persist({ wallets: rest }, password)
  }

  const value: WalletCtx = {
    status,
    wallets,
    active,
    addWallet,
    unlock,
    verifyPassword,
    lock,
    setActive,
    deleteWallet,
    resetAll,
  }
  return <WalletContext value={value}>{children}</WalletContext>
}
```
(React 19 supports `<Context value>`; if lint/TS complains, use `<WalletContext.Provider value={value}>`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter wallet test`
Expected: PASS.

- [ ] **Step 5: Layout components**

`apps/wallet/src/components/Logo.tsx`:
```tsx
import { Mic } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className="flex size-8 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <Mic className="size-4" />
      </span>
      <span className="text-lg font-semibold tracking-tight">LazyWallet</span>
    </div>
  )
}
```

`apps/wallet/src/components/AuthLayout.tsx`:
```tsx
import type { ReactNode } from 'react'
import { Logo } from './Logo'

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="w-full max-w-md space-y-8">
        <Logo className="justify-center" />
        <div className="space-y-6 rounded-2xl border bg-card p-6 sm:p-8">{children}</div>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Routes**

`apps/wallet/src/routes/GuardedLayout.tsx`:
```tsx
import { Navigate, Outlet, useLocation } from 'react-router'
import { useWallet } from '@/state/wallet-context'
import { redirectFor } from './redirect'

export function GuardedLayout() {
  const { status } = useWallet()
  const { pathname } = useLocation()
  const to = redirectFor(status, pathname)
  return to ? <Navigate to={to} replace /> : <Outlet />
}
```

`apps/wallet/src/routes/Welcome.tsx`:
```tsx
import { useNavigate } from 'react-router'
import { AuthLayout } from '@/components/AuthLayout'
import { Button } from '@/components/ui/button'

export default function Welcome() {
  const navigate = useNavigate()
  return (
    <AuthLayout>
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Just say it.</h1>
        <p className="text-muted-foreground">
          Your voice-powered AI wallet. Talk to check balances, send, swap and automate trades.
        </p>
      </div>
      <div className="grid gap-3">
        <Button size="lg" onClick={() => navigate('/create')}>
          Create new wallet
        </Button>
        <Button size="lg" variant="secondary" onClick={() => navigate('/import')}>
          Import seed phrase
        </Button>
      </div>
    </AuthLayout>
  )
}
```

`apps/wallet/src/routes/Unlock.tsx`:
```tsx
import { useState, type FormEvent } from 'react'
import { AuthLayout } from '@/components/AuthLayout'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { WrongPasswordError } from '@/lib/vault'
import { useWallet } from '@/state/wallet-context'

export default function Unlock() {
  const { unlock, resetAll } = useWallet()
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await unlock(password)
    } catch (err) {
      setError(err instanceof WrongPasswordError ? 'Wrong password' : 'Could not unlock this wallet')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout>
      <div className="space-y-1 text-center">
        <h1 className="text-2xl font-semibold">Welcome back</h1>
        <p className="text-sm text-muted-foreground">Enter your password to unlock.</p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoFocus
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" size="lg" className="w-full" disabled={busy || !password}>
          {busy ? 'Unlocking…' : 'Unlock'}
        </Button>
      </form>
      <Button variant="ghost" className="w-full text-muted-foreground" onClick={() => setConfirmReset(true)}>
        Forgot password? Reset all wallets
      </Button>
      <Dialog open={confirmReset} onOpenChange={setConfirmReset}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset LazyWallet?</DialogTitle>
            <DialogDescription>
              This deletes every wallet on this device. You can only get them back with their seed phrases.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setConfirmReset(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={resetAll}>
              Reset everything
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AuthLayout>
  )
}
```

`apps/wallet/src/routes/WalletPage.tsx` (temporary until Task 8):
```tsx
import { Button } from '@/components/ui/button'
import { useWallet } from '@/state/wallet-context'

export default function WalletPage() {
  const { active, lock } = useWallet()
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4">
      <p className="font-mono">{active?.address}</p>
      <Button onClick={lock}>Lock</Button>
    </div>
  )
}
```

Replace `apps/wallet/src/App.tsx`:
```tsx
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'
import { Toaster } from '@/components/ui/sonner'
import { GuardedLayout } from '@/routes/GuardedLayout'
import Unlock from '@/routes/Unlock'
import WalletPage from '@/routes/WalletPage'
import Welcome from '@/routes/Welcome'
import { WalletProvider } from '@/state/WalletProvider'

const router = createBrowserRouter([
  {
    element: <GuardedLayout />,
    children: [
      { path: '/', element: <WalletPage /> },
      { path: '/welcome', element: <Welcome /> },
      { path: '/unlock', element: <Unlock /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])

export default function App() {
  return (
    <WalletProvider>
      <RouterProvider router={router} />
      <Toaster theme="dark" position="top-center" />
    </WalletProvider>
  )
}
```

- [ ] **Step 7: Verify**

Run: `pnpm --filter wallet test && pnpm --filter wallet build && pnpm --filter wallet lint`
Expected: all pass. `pnpm --filter wallet dev` → http://localhost:5174 redirects to `/welcome` and shows both buttons.

- [ ] **Step 8: Commit**

```bash
git add apps/wallet/src
git commit -m "feat(wallet): add vault state, route guard, welcome and unlock screens"
```

---

### Task 5: Create and Import wallet flows

**Files:**
- Create: `apps/wallet/src/components/StepHeader.tsx`, `NameForm.tsx`, `PasswordStep.tsx`, `SeedPhrase.tsx`
- Create: `apps/wallet/src/routes/Create.tsx`, `apps/wallet/src/routes/Import.tsx`
- Modify: `apps/wallet/src/App.tsx` (add routes)

**Interfaces:**
- Consumes: `useWallet()` (Task 4), `newMnemonic`, `normalizeMnemonic`, `isValidMnemonic`, `addressFromMnemonic` (Task 3), `validatePassword` (Task 3), `AuthLayout` (Task 4)
- Produces: `<SeedPhrase mnemonic: string />` (reused in Task 9), `<StepHeader step total title subtitle? />`, `<NameForm initial onSubmit(name) />`, `<PasswordStep onSubmit(pw) />`

- [ ] **Step 1: Shared step components**

`apps/wallet/src/components/StepHeader.tsx`:
```tsx
type Props = { step: number; total: number; title: string; subtitle?: string }

export function StepHeader({ step, total, title, subtitle }: Props) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase tracking-wider text-primary">
        Step {step} of {total}
      </p>
      <h1 className="text-2xl font-semibold">{title}</h1>
      {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
    </div>
  )
}
```

`apps/wallet/src/components/NameForm.tsx`:
```tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function NameForm({ initial, onSubmit }: { initial: string; onSubmit: (name: string) => void }) {
  const [name, setName] = useState(initial)
  const trimmed = name.trim()
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (trimmed) onSubmit(trimmed)
      }}
      className="space-y-4"
    >
      <div className="space-y-2">
        <Label htmlFor="wallet-name">Wallet name</Label>
        <Input
          id="wallet-name"
          autoFocus
          maxLength={32}
          placeholder="e.g. Main"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      <Button type="submit" size="lg" className="w-full" disabled={!trimmed}>
        Continue
      </Button>
    </form>
  )
}
```

`apps/wallet/src/components/PasswordStep.tsx`:
```tsx
import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { validatePassword } from '@/lib/password'

export function PasswordStep({ onSubmit, busy }: { onSubmit: (password: string) => void; busy?: boolean }) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)

  function submit(e: FormEvent) {
    e.preventDefault()
    const err = validatePassword(password, confirm)
    setError(err)
    if (!err) onSubmit(password)
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input id="password" type="password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password-confirm">Confirm password</Label>
        <Input id="password-confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      </div>
      <p className="text-xs text-muted-foreground">
        Encrypts your wallets on this device. We can't recover it for you.
      </p>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" size="lg" className="w-full" disabled={busy}>
        Continue
      </Button>
    </form>
  )
}
```

`apps/wallet/src/components/SeedPhrase.tsx`:
```tsx
import { useState } from 'react'
import { Copy, Eye } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function SeedPhrase({ mnemonic }: { mnemonic: string }) {
  const [revealed, setRevealed] = useState(false)
  const words = mnemonic.split(' ')

  async function copy() {
    try {
      await navigator.clipboard.writeText(mnemonic)
      toast.success('Seed phrase copied')
    } catch {
      toast.error('Copy failed — write it down instead')
    }
  }

  return (
    <div className="space-y-3">
      <div className="relative">
        <ol className={cn('grid grid-cols-2 gap-2 sm:grid-cols-3', !revealed && 'select-none blur-md')}>
          {words.map((word, i) => (
            <li key={i} className="flex items-center gap-2 rounded-lg bg-secondary px-3 py-2 font-mono text-sm">
              <span className="w-5 text-right text-muted-foreground">{i + 1}</span>
              {word}
            </li>
          ))}
        </ol>
        {!revealed && (
          <button
            type="button"
            onClick={() => setRevealed(true)}
            className="absolute inset-0 flex items-center justify-center gap-2 rounded-lg text-sm font-medium"
          >
            <Eye className="size-4" />
            Tap to reveal
          </button>
        )}
      </div>
      <Button type="button" variant="secondary" className="w-full" onClick={copy} disabled={!revealed}>
        <Copy className="size-4" />
        Copy
      </Button>
    </div>
  )
}
```

- [ ] **Step 2: Create flow**

`apps/wallet/src/routes/Create.tsx`:
```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { AuthLayout } from '@/components/AuthLayout'
import { NameForm } from '@/components/NameForm'
import { PasswordStep } from '@/components/PasswordStep'
import { SeedPhrase } from '@/components/SeedPhrase'
import { StepHeader } from '@/components/StepHeader'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { newMnemonic } from '@/lib/vault'
import { useWallet } from '@/state/wallet-context'

type Step = 'name' | 'password' | 'seed'

export default function Create() {
  const { status, addWallet } = useWallet()
  const navigate = useNavigate()
  const needsPassword = status !== 'unlocked'
  const steps: Step[] = needsPassword ? ['name', 'password', 'seed'] : ['name', 'seed']
  const [step, setStep] = useState<Step>('name')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [mnemonic] = useState(() => newMnemonic())
  const [savedIt, setSavedIt] = useState(false)
  const [busy, setBusy] = useState(false)
  const stepNo = steps.indexOf(step) + 1

  function back() {
    const i = steps.indexOf(step)
    if (i > 0) setStep(steps[i - 1])
    else navigate(status === 'unlocked' ? '/' : '/welcome')
  }

  async function finish() {
    setBusy(true)
    const ok = await addWallet(name, mnemonic, password || undefined)
    setBusy(false)
    if (ok) navigate('/')
    else toast.error("Couldn't save the wallet — browser storage is unavailable.")
  }

  return (
    <AuthLayout>
      {step === 'name' && (
        <>
          <StepHeader step={stepNo} total={steps.length} title="Name your wallet" subtitle="Only you see this name." />
          <NameForm
            initial={name}
            onSubmit={(v) => {
              setName(v)
              setStep(needsPassword ? 'password' : 'seed')
            }}
          />
        </>
      )}
      {step === 'password' && (
        <>
          <StepHeader step={stepNo} total={steps.length} title="Set a password" subtitle="You'll use it to unlock LazyWallet on this device." />
          <PasswordStep
            onSubmit={(pw) => {
              setPassword(pw)
              setStep('seed')
            }}
          />
        </>
      )}
      {step === 'seed' && (
        <>
          <StepHeader
            step={stepNo}
            total={steps.length}
            title="Write down your seed phrase"
            subtitle="These 12 words are the only way to recover your wallet. Never share them."
          />
          <SeedPhrase mnemonic={mnemonic} />
          <label className="flex items-center gap-3 text-sm">
            <Checkbox checked={savedIt} onCheckedChange={(v) => setSavedIt(v === true)} />
            I've written it down somewhere safe
          </label>
          <Button size="lg" className="w-full" disabled={!savedIt || busy} onClick={finish}>
            {busy ? 'Saving…' : 'Open my wallet'}
          </Button>
        </>
      )}
      <Button variant="ghost" className="w-full" onClick={back}>
        Back
      </Button>
    </AuthLayout>
  )
}
```

- [ ] **Step 3: Import flow**

`apps/wallet/src/routes/Import.tsx`:
```tsx
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { AuthLayout } from '@/components/AuthLayout'
import { NameForm } from '@/components/NameForm'
import { PasswordStep } from '@/components/PasswordStep'
import { StepHeader } from '@/components/StepHeader'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { addressFromMnemonic, isValidMnemonic, normalizeMnemonic } from '@/lib/vault'
import { useWallet } from '@/state/wallet-context'

type Step = 'name' | 'phrase' | 'password'

export default function Import() {
  const { status, wallets, addWallet } = useWallet()
  const navigate = useNavigate()
  const needsPassword = status !== 'unlocked'
  const steps: Step[] = needsPassword ? ['name', 'phrase', 'password'] : ['name', 'phrase']
  const [step, setStep] = useState<Step>('name')
  const [name, setName] = useState('')
  const [phrase, setPhrase] = useState('')
  const [phraseError, setPhraseError] = useState<string | null>(null)
  const [mnemonic, setMnemonic] = useState('')
  const [busy, setBusy] = useState(false)
  const stepNo = steps.indexOf(step) + 1

  function back() {
    const i = steps.indexOf(step)
    if (i > 0) setStep(steps[i - 1])
    else navigate(status === 'unlocked' ? '/' : '/welcome')
  }

  async function save(m: string, password?: string) {
    setBusy(true)
    const ok = await addWallet(name, m, password)
    setBusy(false)
    if (ok) navigate('/')
    else toast.error("Couldn't save the wallet — browser storage is unavailable.")
  }

  function submitPhrase(e: FormEvent) {
    e.preventDefault()
    const m = normalizeMnemonic(phrase)
    if (!isValidMnemonic(m)) {
      setPhraseError("That doesn't look like a valid 12 or 24-word seed phrase. Check the spelling and word order.")
      return
    }
    const address = addressFromMnemonic(m)
    if (wallets.some((w) => w.address === address)) {
      setPhraseError('This wallet is already in LazyWallet.')
      return
    }
    setPhraseError(null)
    setMnemonic(m)
    if (needsPassword) setStep('password')
    else void save(m)
  }

  return (
    <AuthLayout>
      {step === 'name' && (
        <>
          <StepHeader step={stepNo} total={steps.length} title="Name your wallet" subtitle="Only you see this name." />
          <NameForm
            initial={name}
            onSubmit={(v) => {
              setName(v)
              setStep('phrase')
            }}
          />
        </>
      )}
      {step === 'phrase' && (
        <>
          <StepHeader step={stepNo} total={steps.length} title="Enter your seed phrase" subtitle="12 or 24 words, separated by spaces." />
          <form onSubmit={submitPhrase} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="phrase">Seed phrase</Label>
              <Textarea
                id="phrase"
                autoFocus
                rows={4}
                spellCheck={false}
                autoComplete="off"
                className="font-mono"
                value={phrase}
                onChange={(e) => setPhrase(e.target.value)}
              />
            </div>
            {phraseError && <p className="text-sm text-destructive">{phraseError}</p>}
            <Button type="submit" size="lg" className="w-full" disabled={!phrase.trim() || busy}>
              Continue
            </Button>
          </form>
        </>
      )}
      {step === 'password' && (
        <>
          <StepHeader step={stepNo} total={steps.length} title="Set a password" subtitle="You'll use it to unlock LazyWallet on this device." />
          <PasswordStep busy={busy} onSubmit={(pw) => void save(mnemonic, pw)} />
        </>
      )}
      <Button variant="ghost" className="w-full" onClick={back}>
        Back
      </Button>
    </AuthLayout>
  )
}
```

- [ ] **Step 4: Register routes**

In `apps/wallet/src/App.tsx` add imports and two children:
```tsx
import Create from '@/routes/Create'
import Import from '@/routes/Import'
```
```tsx
      { path: '/create', element: <Create /> },
      { path: '/import', element: <Import /> },
```

- [ ] **Step 5: Verify**

Run: `pnpm --filter wallet test && pnpm --filter wallet build && pnpm --filter wallet lint` → all pass.
Manual (`pnpm --filter wallet dev`):
1. Welcome → Create → name "Main" → password `hunter222` ×2 → seed blurred → reveal → Copy works → checkbox → Open my wallet → address page.
2. DevTools → Application → localStorage `lw.vault` contains only `v/salt/iv/data`, no seed words.
3. Reload → `/unlock`; wrong password → "Wrong password"; right password → wallet page.
4. Lock → Welcome is not reachable (`/welcome` redirects to `/unlock`).
5. Unlock → visit `/import` → name → paste `  Test test test test test test test test test test test JUNK ` → wallet added with no password step. Repeat same phrase → "already in LazyWallet". 11 words → validation error.

- [ ] **Step 6: Commit**

```bash
git add apps/wallet/src
git commit -m "feat(wallet): add create and import wallet flows"
```

---

### Task 6: Mock agent

**Files:**
- Create: `apps/wallet/src/mock/fixtures.ts`, `apps/wallet/src/mock/agent.ts`
- Test: `apps/wallet/src/mock/agent.test.ts`

**Interfaces:**
- Consumes: types from `@/types`; `uid`, `formatAmount`, `formatUsd`, `shortAddress` (Task 2)
- Produces:
  - fixtures: `HOLDINGS: Holding[]`, `PORTFOLIO_USD: number`, `DEFAULT_CONTACTS: Contact[]`, `EXAMPLES: string[]`, `UNISWAP: DappInfo`
  - agent: `type AgentContext = { contacts: Contact[]; holdings: Holding[] }`, `respond(input: string, ctx: AgentContext): AgentReply`, `simulateTrigger(task: Task): AgentReply`, `say(text: string): Message`, `confirm(tx: TxDraft): Message`

- [ ] **Step 1: Fixtures**

`apps/wallet/src/mock/fixtures.ts`:
```ts
import type { Contact, DappInfo, Holding } from '@/types'

export const HOLDINGS: Holding[] = [
  { symbol: 'ETH', amount: 2.5, usdPrice: 3200 },
  { symbol: 'USDC', amount: 1500, usdPrice: 1 },
  { symbol: 'WBTC', amount: 0.05, usdPrice: 64000 },
]

export const PORTFOLIO_USD = HOLDINGS.reduce((sum, h) => sum + h.amount * h.usdPrice, 0)

// Anvil's default accounts #1 and #2 — they exist on the Sandbox fork.
export const DEFAULT_CONTACTS: Contact[] = [
  { id: 'alice', name: 'Alice', address: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8' },
  { id: 'bob', name: 'Bob', address: '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC' },
]

export const EXAMPLES = [
  "What's my balance?",
  'Send 0.1 ETH to Alice',
  'Swap 100 USDC to ETH',
  'Alert me if ETH drops below 3000',
  'Buy ETH every Monday with 50 USDC',
  'If ETH < 3000, swap 500 USDC to ETH',
]

export const UNISWAP: DappInfo = { name: 'Uniswap', url: 'https://app.uniswap.org', icon: '🦄' }
```

- [ ] **Step 2: Write failing tests**

`apps/wallet/src/mock/agent.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import type { AgentReply, Contact } from '@/types'
import { respond, simulateTrigger } from './agent'
import { HOLDINGS } from './fixtures'

const contacts: Contact[] = [{ id: '1', name: 'Alice', address: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8' }]
const ctx = { contacts, holdings: HOLDINGS }

function confirmOf(reply: AgentReply) {
  const m = reply.messages.find((x) => x.kind === 'confirm')
  if (!m || m.kind !== 'confirm') throw new Error('expected a confirm card')
  return m.tx
}
const textOf = (reply: AgentReply) =>
  reply.messages.flatMap((m) => (m.role === 'assistant' && m.kind === 'text' ? [m.text] : [])).join(' ')
const hasConfirm = (reply: AgentReply) => reply.messages.some((m) => m.kind === 'confirm')
const row = (tx: { rows: { label: string; value: string }[] }, label: string) =>
  tx.rows.find((r) => r.label === label)?.value ?? ''

describe('respond', () => {
  it('shows balances', () => {
    const r = respond("What's my balance?", ctx)
    expect(r.messages.some((m) => m.kind === 'balance')).toBe(true)
  })

  it('sends to a contact, tolerating voice punctuation and capitals', () => {
    const tx = confirmOf(respond('Send 0.1 ETH to Alice.', ctx))
    expect(tx.title).toBe('Send 0.1 ETH')
    expect(row(tx, 'To')).toContain('Alice')
  })

  it('sends to a raw address and shows it checksummed', () => {
    const tx = confirmOf(respond('send 1 usdc to 0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc', ctx))
    expect(row(tx, 'To')).toBe('0x3C44…93BC')
  })

  it('refuses unknown recipients without a confirm card', () => {
    const r = respond('send 0.1 eth to charlie', ctx)
    expect(hasConfirm(r)).toBe(false)
    expect(textOf(r)).toMatch(/address book/i)
  })

  it('refuses amounts above the balance or zero', () => {
    expect(hasConfirm(respond('send 10 eth to alice', ctx))).toBe(false)
    expect(textOf(respond('send 10 eth to alice', ctx))).toMatch(/only have 2.5 ETH/)
    expect(hasConfirm(respond('send 0 eth to alice', ctx))).toBe(false)
  })

  it('quotes swaps', () => {
    const tx = confirmOf(respond('Swap 100 USDC to ETH', ctx))
    expect(row(tx, 'You receive')).toContain('0.0311563 ETH')
    expect(row(tx, 'Route')).toBe('Uniswap v3')
  })

  it('refuses unsupported swap tokens', () => {
    const r = respond('swap 1 doge to eth', ctx)
    expect(hasConfirm(r)).toBe(false)
    expect(textOf(r)).toMatch(/ETH, USDC and WBTC/)
  })

  it('explains bridging is not available', () => {
    expect(textOf(respond('Bridge 0.05 ETH to Base', ctx))).toMatch(/coming soon/i)
  })

  it('creates a DCA task', () => {
    const r = respond('Buy ETH every Monday with 50 USDC', ctx)
    expect(r.newTask).toMatchObject({ kind: 'dca', schedule: 'Every Monday', status: 'active' })
  })

  it('creates a price alert from a spoken amount with separators', () => {
    const r = respond('Alert me if ETH drops below $3,000.', ctx)
    expect(r.newTask?.kind).toBe('alert')
    expect(r.newTask?.description).toContain('$3,000')
  })

  it('creates a conditional order that can be simulated', () => {
    const r = respond('If ETH < 3000, swap 500 USDC to ETH', ctx)
    expect(r.newTask?.kind).toBe('conditional')
    expect(r.newTask?.trigger?.title).toBe('Swap 500 USDC → ETH')
    const fired = simulateTrigger(r.newTask!)
    expect(confirmOf(fired).title).toBe('Swap 500 USDC → ETH')
  })

  it('falls back with examples', () => {
    expect(textOf(respond('make me rich', ctx))).toMatch(/Try:/)
  })
})
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pnpm --filter wallet test`
Expected: FAIL — cannot resolve `./agent`.

- [ ] **Step 4: Implement**

`apps/wallet/src/mock/agent.ts`:
```ts
import { getAddress, isAddress } from 'viem'
import { formatAmount, formatUsd, shortAddress, uid } from '@/lib/format'
import type { AgentReply, Contact, Holding, Message, Task, TxDraft } from '@/types'

export type AgentContext = { contacts: Contact[]; holdings: Holding[] }

const NUM = '(\\d+(?:\\.\\d+)?)'
const SYM = '([a-z]+)'
const DAYS = 'day|week|monday|tuesday|wednesday|thursday|friday|saturday|sunday'
const BELOW = '(?:<|is below|drops below|falls below|goes below|below|under)'

const CONDITIONAL = new RegExp(`^if ${SYM} ${BELOW} \\$?${NUM},? (?:then )?swap ${NUM} ?${SYM} (?:to|for|into) ${SYM}$`)
const ALERT = new RegExp(`(?:alert|notify|tell) me (?:if|when) ${SYM} ${BELOW} \\$?${NUM}`)
const DCA = new RegExp(`buy ${SYM} every (${DAYS}) with ${NUM} ?${SYM}`)
const SEND = new RegExp(`^(?:send|transfer|pay) ${NUM} ?${SYM} to (.+)$`)
const SWAP = new RegExp(`^swap ${NUM} ?${SYM} (?:to|for|into) ${SYM}$`)

const FALLBACK =
  'I can\'t do that yet. Try: "What\'s my balance?", "Send 0.1 ETH to Alice", "Swap 100 USDC to ETH" or "Alert me if ETH drops below 3000".'

export const say = (text: string): Message => ({ id: uid(), role: 'assistant', kind: 'text', text })
export const confirm = (tx: TxDraft): Message => ({ id: uid(), role: 'assistant', kind: 'confirm', tx, state: 'waiting' })

// Voice transcripts arrive capitalised, punctuated and with thousands separators.
function normalize(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/(\d),(?=\d{3}\b)/g, '$1')
    .replace(/[.!?]+$/, '')
    .replace(/\s+/g, ' ')
}

const usdLabel = (n: number) => `$${n.toLocaleString('en-US')}`
const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

function findHolding(ctx: AgentContext, symbol: string) {
  return ctx.holdings.find((h) => h.symbol === symbol.toUpperCase())
}

function checkSpend(ctx: AgentContext, amount: number, symbol: string): Holding | string {
  const sym = symbol.toUpperCase()
  if (amount <= 0) return 'The amount needs to be more than 0.'
  const holding = findHolding(ctx, symbol)
  if (!holding) return `You don't have any ${sym}.`
  if (amount > holding.amount) return `You only have ${formatAmount(holding.amount)} ${sym}, so I can't use ${formatAmount(amount)}.`
  return holding
}

function send(ctx: AgentContext, amount: number, symbol: string, recipient: string): AgentReply {
  const holding = checkSpend(ctx, amount, symbol)
  if (typeof holding === 'string') return { messages: [say(holding)] }
  const contact = ctx.contacts.find((c) => c.name.toLowerCase() === recipient)
  const address = contact?.address ?? (isAddress(recipient) ? getAddress(recipient) : null)
  if (!address) {
    return {
      messages: [say(`I don't know "${recipient}" yet. Add them in the address book (top right), then try again.`)],
    }
  }
  const sym = holding.symbol
  const to = contact ? `${contact.name} (${shortAddress(address)})` : shortAddress(address)
  return {
    messages: [
      say(`Here's the transfer. Check it and approve when you're ready.`),
      confirm({
        title: `Send ${formatAmount(amount)} ${sym}`,
        rows: [
          { label: 'To', value: to },
          { label: 'Amount', value: `${formatAmount(amount)} ${sym} (${formatUsd(amount * holding.usdPrice)})` },
          { label: 'Network fee', value: '~$1.20' },
          { label: 'Network', value: 'Sandbox' },
        ],
      }),
    ],
  }
}

function swapDraft(ctx: AgentContext, amount: number, from: string, to: string): TxDraft | string {
  const a = findHolding(ctx, from)
  const b = findHolding(ctx, to)
  if (!a || !b) return 'I can only swap ETH, USDC and WBTC in Sandbox for now.'
  if (a.symbol === b.symbol) return 'Pick two different tokens to swap.'
  const out = ((amount * a.usdPrice) / b.usdPrice) * 0.997
  return {
    title: `Swap ${formatAmount(amount)} ${a.symbol} → ${b.symbol}`,
    rows: [
      { label: 'You pay', value: `${formatAmount(amount)} ${a.symbol}` },
      { label: 'You receive', value: `≈ ${formatAmount(out)} ${b.symbol}` },
      { label: 'Minimum received', value: `${formatAmount(out * 0.995)} ${b.symbol}` },
      { label: 'Route', value: 'Uniswap v3' },
      { label: 'Price impact', value: '0.05%' },
      { label: 'Network fee', value: '~$4.80' },
    ],
  }
}

function swap(ctx: AgentContext, amount: number, from: string, to: string): AgentReply {
  const draft = swapDraft(ctx, amount, from, to)
  if (typeof draft === 'string') return { messages: [say(draft)] }
  const holding = checkSpend(ctx, amount, from)
  if (typeof holding === 'string') return { messages: [say(holding)] }
  return { messages: [say("Here's the best quote I found:"), confirm(draft)] }
}

function newTask(task: Omit<Task, 'id' | 'status'>): AgentReply {
  const full: Task = { ...task, id: uid(), status: 'active' }
  return {
    messages: [
      say("Done — I'll take care of it while this tab is open."),
      { id: uid(), role: 'assistant', kind: 'task', task: full },
    ],
    newTask: full,
  }
}

export function respond(input: string, ctx: AgentContext): AgentReply {
  const text = normalize(input)
  let m: RegExpMatchArray | null

  if ((m = text.match(CONDITIONAL))) {
    const [, watch, price, amount, from, to] = m
    const trigger = swapDraft(ctx, Number(amount), from, to)
    if (typeof trigger === 'string') return { messages: [say(trigger)] }
    return newTask({
      kind: 'conditional',
      description: `${trigger.title} when ${watch.toUpperCase()} < ${usdLabel(Number(price))}`,
      schedule: 'Checks price every minute',
      trigger,
    })
  }
  if ((m = text.match(ALERT))) {
    const [, sym, price] = m
    return newTask({
      kind: 'alert',
      description: `Price alert: ${sym.toUpperCase()} below ${usdLabel(Number(price))}`,
      schedule: 'Checks price every minute',
    })
  }
  if ((m = text.match(DCA))) {
    const [, buy, period, amount, payWith] = m
    return newTask({
      kind: 'dca',
      description: `Buy ${buy.toUpperCase()} with ${formatAmount(Number(amount))} ${payWith.toUpperCase()}`,
      schedule: `Every ${capitalize(period)}`,
    })
  }
  if (/\bbridge\b/.test(text)) {
    return {
      messages: [say("Bridging and other chains are coming soon. Right now you're in Sandbox, an Ethereum mainnet fork.")],
    }
  }
  if ((m = text.match(SEND))) return send(ctx, Number(m[1]), m[2], m[3])
  if ((m = text.match(SWAP))) return swap(ctx, Number(m[1]), m[2], m[3])
  if (/\b(balance|portfolio|how much)\b/.test(text)) {
    return {
      messages: [say("Here's what you have:"), { id: uid(), role: 'assistant', kind: 'balance', holdings: ctx.holdings }],
    }
  }
  return { messages: [say(FALLBACK)] }
}

export function simulateTrigger(task: Task): AgentReply {
  if (!task.trigger) return { messages: [] }
  return { messages: [say(`Condition met: ${task.description}. Approve to execute.`), confirm(task.trigger)] }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pnpm --filter wallet test`
Expected: PASS. If the swap amount assertion fails, recompute: 100 × 1 / 3200 × 0.997 = 0.03115625 → `formatAmount` → `0.0311563`.

- [ ] **Step 6: Commit**

```bash
git add apps/wallet/src/mock
git commit -m "feat(wallet): add scripted mock agent"
```

---

### Task 7: Voice (speech recognition + spoken replies)

**Files:**
- Create: `apps/wallet/src/voice/speech.ts`
- Test: `apps/wallet/src/voice/speech.test.ts`

**Interfaces:**
- Produces: `getRecognitionCtor(w?: object): RecognitionCtor | null`, `useSpeechRecognition(onFinal: (text: string) => void): { supported: boolean; listening: boolean; interim: string; error: string; start(): void; stop(): void }`, `speak(text: string, enabled: boolean): void`

- [ ] **Step 1: Write failing tests**

`apps/wallet/src/voice/speech.test.ts`:
```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { getRecognitionCtor, speak } from './speech'

afterEach(() => vi.unstubAllGlobals())

describe('getRecognitionCtor', () => {
  it('returns null when unsupported (e.g. Firefox)', () => {
    expect(getRecognitionCtor({})).toBeNull()
  })
  it('prefers the standard constructor, falls back to webkit', () => {
    class A {}
    class B {}
    expect(getRecognitionCtor({ SpeechRecognition: A, webkitSpeechRecognition: B })).toBe(A)
    expect(getRecognitionCtor({ webkitSpeechRecognition: B })).toBe(B)
  })
})

describe('speak', () => {
  it('does nothing when speech synthesis is missing', () => {
    expect(() => speak('hello', true)).not.toThrow()
  })

  it('speaks only when enabled', () => {
    const synth = { cancel: vi.fn(), speak: vi.fn() }
    vi.stubGlobal('speechSynthesis', synth)
    vi.stubGlobal(
      'SpeechSynthesisUtterance',
      class {
        text: string
        constructor(text: string) {
          this.text = text
        }
      },
    )
    speak('hello', false)
    expect(synth.speak).not.toHaveBeenCalled()
    speak('hello', true)
    expect(synth.cancel).toHaveBeenCalled()
    expect(synth.speak).toHaveBeenCalledWith(expect.objectContaining({ text: 'hello' }))
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm --filter wallet test`
Expected: FAIL — cannot resolve `./speech`.

- [ ] **Step 3: Implement**

`apps/wallet/src/voice/speech.ts`:
```ts
import { useEffect, useRef, useState } from 'react'

type RecognitionResultList = ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>
interface Recognition {
  lang: string
  interimResults: boolean
  continuous: boolean
  start(): void
  stop(): void
  onresult: ((e: { resultIndex: number; results: RecognitionResultList }) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
}
type RecognitionCtor = new () => Recognition

export function getRecognitionCtor(w: object = window): RecognitionCtor | null {
  const g = w as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return g.SpeechRecognition ?? g.webkitSpeechRecognition ?? null
}

function canSpeak(): boolean {
  return typeof globalThis.speechSynthesis !== 'undefined' && typeof globalThis.SpeechSynthesisUtterance !== 'undefined'
}

export function speak(text: string, enabled: boolean): void {
  if (!enabled || !text || !canSpeak()) return
  globalThis.speechSynthesis.cancel()
  globalThis.speechSynthesis.speak(new SpeechSynthesisUtterance(text))
}

export function useSpeechRecognition(onFinal: (text: string) => void) {
  const Ctor = getRecognitionCtor()
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState('')
  const recRef = useRef<Recognition | null>(null)
  const onFinalRef = useRef(onFinal)

  useEffect(() => {
    onFinalRef.current = onFinal
  })
  useEffect(() => () => recRef.current?.stop(), [])

  function start() {
    if (!Ctor || recRef.current) return
    if (canSpeak()) globalThis.speechSynthesis.cancel()
    const rec = new Ctor()
    rec.lang = 'en-US'
    rec.interimResults = true
    rec.continuous = false
    let finalText = ''
    rec.onresult = (e) => {
      let live = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const result = e.results[i]
        if (result.isFinal) finalText += result[0].transcript
        else live += result[0].transcript
      }
      setInterim(finalText + live)
    }
    rec.onerror = (e) =>
      setError(e.error === 'not-allowed' ? 'Microphone permission was denied.' : `Voice error: ${e.error}`)
    rec.onend = () => {
      recRef.current = null
      setListening(false)
      setInterim('')
      if (finalText.trim()) onFinalRef.current(finalText.trim())
    }
    recRef.current = rec
    setError('')
    setListening(true)
    rec.start()
  }

  function stop() {
    recRef.current?.stop()
  }

  return { supported: Ctor !== null, listening, interim, error, start, stop }
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `pnpm --filter wallet test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/wallet/src/voice
git commit -m "feat(wallet): add speech recognition and spoken replies"
```

---

### Task 8: Chat UI and main wallet layout

**Files:**
- Create: `apps/wallet/src/chat/useChat.ts`, `ChatView.tsx`, `MessageItem.tsx`, `InputBar.tsx`
- Create: `apps/wallet/src/chat/cards/TextBubble.tsx`, `BalanceCard.tsx`, `ConfirmCard.tsx`, `StatusCard.tsx`, `TaskCard.tsx`, `task-icons.ts`
- Create: `apps/wallet/src/components/TopBar.tsx`
- Modify (replace): `apps/wallet/src/routes/WalletPage.tsx`

**Interfaces:**
- Consumes: `respond`, `simulateTrigger`, `say` (Task 6); `HOLDINGS`, `EXAMPLES`, `DEFAULT_CONTACTS` (Task 6); `speak`, `useSpeechRecognition` (Task 7); `useStored`, `KEYS` (Task 2); `txHash`, `uid`, `formatUsd`, `formatAmount`, `shortAddress`, `hostOf` (Task 2)
- Produces:
  - `useChat({ contacts, speakEnabled, onTask }): { messages: Message[]; send(text: string, spoken?: boolean): void; deliver(reply: AgentReply): void; approve(id: string): void; reject(id: string): void }`
  - `<TopBar left? center right? />`
  - `<TaskCard task onSimulate? />`, `TASK_ICONS: Record<TaskKind, LucideIcon>`

- [ ] **Step 1: Chat state hook**

`apps/wallet/src/chat/useChat.ts`:
```ts
import { useState } from 'react'
import { txHash, uid } from '@/lib/format'
import { respond, say } from '@/mock/agent'
import { HOLDINGS } from '@/mock/fixtures'
import type { AgentReply, Contact, Message, Task } from '@/types'
import { speak } from '@/voice/speech'

type Options = { contacts: Contact[]; speakEnabled: boolean; onTask: (task: Task) => void }

const THINK_MS = 500
const CONFIRM_MS = 1500

export function useChat({ contacts, speakEnabled, onTask }: Options) {
  const [messages, setMessages] = useState<Message[]>([])

  const push = (...ms: Message[]) => setMessages((prev) => [...prev, ...ms])
  const update = (id: string, patch: Partial<Message>) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? ({ ...m, ...patch } as Message) : m)))

  function deliver(reply: AgentReply) {
    window.setTimeout(() => {
      push(...reply.messages)
      if (reply.newTask) onTask(reply.newTask)
      const spokenText = reply.messages
        .flatMap((m) => (m.role === 'assistant' && m.kind === 'text' ? [m.text] : []))
        .join(' ')
      speak(spokenText, speakEnabled)
    }, THINK_MS)
  }

  function send(text: string, spoken = false) {
    if (!text.trim()) return
    push({ id: uid(), role: 'user', kind: 'text', text, spoken })
    deliver(respond(text, { contacts, holdings: HOLDINGS }))
  }

  function approve(id: string) {
    update(id, { state: 'approved' })
    const statusId = uid()
    push({ id: statusId, role: 'assistant', kind: 'status', state: 'pending', text: 'Submitting to Sandbox…' })
    window.setTimeout(
      () => update(statusId, { state: 'success', text: 'Done! Transaction confirmed.', hash: txHash() }),
      CONFIRM_MS,
    )
  }

  function reject(id: string) {
    update(id, { state: 'rejected' })
    push(say('Cancelled — nothing was sent.'))
  }

  return { messages, send, deliver, approve, reject }
}
```

- [ ] **Step 2: Cards**

`apps/wallet/src/chat/cards/task-icons.ts`:
```ts
import { Bell, Repeat, Zap, type LucideIcon } from 'lucide-react'
import type { TaskKind } from '@/types'

export const TASK_ICONS: Record<TaskKind, LucideIcon> = { dca: Repeat, alert: Bell, conditional: Zap }
```

`apps/wallet/src/chat/cards/TextBubble.tsx`:
```tsx
import { Volume2 } from 'lucide-react'
import { speak } from '@/voice/speech'

export function TextBubble({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2">
      <div className="rounded-2xl rounded-bl-md bg-card px-4 py-2.5">{text}</div>
      <button
        type="button"
        aria-label="Read aloud"
        onClick={() => speak(text, true)}
        className="mt-2 text-muted-foreground opacity-60 transition hover:text-primary hover:opacity-100"
      >
        <Volume2 className="size-4" />
      </button>
    </div>
  )
}
```

`apps/wallet/src/chat/cards/BalanceCard.tsx`:
```tsx
import { formatAmount, formatUsd } from '@/lib/format'
import type { Holding } from '@/types'

export function BalanceCard({ holdings }: { holdings: Holding[] }) {
  const total = holdings.reduce((sum, h) => sum + h.amount * h.usdPrice, 0)
  return (
    <div className="rounded-2xl border bg-card p-4">
      <p className="text-sm text-muted-foreground">Total balance</p>
      <p className="mt-1 font-mono text-3xl font-semibold">{formatUsd(total)}</p>
      <ul className="mt-4 divide-y">
        {holdings.map((h) => (
          <li key={h.symbol} className="flex items-center justify-between py-2.5">
            <span className="font-medium">{h.symbol}</span>
            <span className="text-right">
              <span className="block font-mono">{formatAmount(h.amount)}</span>
              <span className="block text-xs text-muted-foreground">{formatUsd(h.amount * h.usdPrice)}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

`apps/wallet/src/chat/cards/ConfirmCard.tsx`:
```tsx
import { Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { hostOf } from '@/lib/format'
import type { ConfirmState, TxDraft } from '@/types'

type Props = { tx: TxDraft; state: ConfirmState; onApprove: () => void; onReject: () => void }

export function ConfirmCard({ tx, state, onApprove, onReject }: Props) {
  return (
    <div className="rounded-2xl border bg-card p-4">
      {tx.dapp && (
        <div className="mb-3 flex items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-full bg-secondary text-lg">{tx.dapp.icon}</span>
          <div className="min-w-0">
            <p className="font-medium">{tx.dapp.name}</p>
            <p className="truncate text-xs text-muted-foreground">{hostOf(tx.dapp.url)}</p>
          </div>
        </div>
      )}
      <p className="font-semibold">{tx.title}</p>
      {tx.explanation && (
        <p className="mt-2 rounded-xl bg-secondary p-3 text-sm">
          <Sparkles className="mr-1.5 inline size-3.5 text-primary" />
          {tx.explanation}
        </p>
      )}
      <dl className="mt-3 space-y-2 text-sm">
        {tx.rows.map((r) => (
          <div key={r.label} className="flex justify-between gap-4">
            <dt className="text-muted-foreground">{r.label}</dt>
            <dd className="text-right font-mono">{r.value}</dd>
          </div>
        ))}
      </dl>
      {state === 'waiting' ? (
        <div className="mt-4 grid grid-cols-2 gap-2">
          <Button variant="secondary" onClick={onReject}>
            Reject
          </Button>
          <Button onClick={onApprove}>Approve</Button>
        </div>
      ) : (
        <Badge variant={state === 'approved' ? 'default' : 'secondary'} className="mt-4">
          {state === 'approved' ? 'Approved' : 'Rejected'}
        </Badge>
      )}
    </div>
  )
}
```

`apps/wallet/src/chat/cards/StatusCard.tsx`:
```tsx
import { CheckCircle2, Loader2 } from 'lucide-react'
import { shortAddress } from '@/lib/format'

type Props = { state: 'pending' | 'success'; text: string; hash?: string }

export function StatusCard({ state, text, hash }: Props) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border bg-card p-4">
      {state === 'pending' ? (
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      ) : (
        <CheckCircle2 className="size-5 text-primary" />
      )}
      <div className="min-w-0">
        <p>{text}</p>
        {hash && <p className="truncate font-mono text-xs text-muted-foreground">Tx {shortAddress(hash)}</p>}
      </div>
    </div>
  )
}
```

`apps/wallet/src/chat/cards/TaskCard.tsx`:
```tsx
import { Button } from '@/components/ui/button'
import type { Task } from '@/types'
import { TASK_ICONS } from './task-icons'

export function TaskCard({ task, onSimulate }: { task: Task; onSimulate?: (task: Task) => void }) {
  const Icon = TASK_ICONS[task.kind]
  return (
    <div className="rounded-2xl border bg-card p-4">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
          <Icon className="size-4" />
        </span>
        <div className="min-w-0">
          <p className="font-medium">{task.description}</p>
          <p className="text-sm text-muted-foreground">{task.schedule}</p>
        </div>
      </div>
      {task.trigger && onSimulate && (
        <Button variant="secondary" size="sm" className="mt-3" onClick={() => onSimulate(task)}>
          Simulate trigger
        </Button>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Message list**

`apps/wallet/src/chat/MessageItem.tsx`:
```tsx
import { Mic } from 'lucide-react'
import type { AssistantMessage, Message, Task } from '@/types'
import { BalanceCard } from './cards/BalanceCard'
import { ConfirmCard } from './cards/ConfirmCard'
import { StatusCard } from './cards/StatusCard'
import { TaskCard } from './cards/TaskCard'
import { TextBubble } from './cards/TextBubble'

export type MessageActions = {
  onApprove: (id: string) => void
  onReject: (id: string) => void
  onSimulate: (task: Task) => void
}

function AssistantBody({ message, onApprove, onReject, onSimulate }: { message: AssistantMessage } & MessageActions) {
  switch (message.kind) {
    case 'text':
      return <TextBubble text={message.text} />
    case 'balance':
      return <BalanceCard holdings={message.holdings} />
    case 'confirm':
      return (
        <ConfirmCard
          tx={message.tx}
          state={message.state}
          onApprove={() => onApprove(message.id)}
          onReject={() => onReject(message.id)}
        />
      )
    case 'status':
      return <StatusCard state={message.state} text={message.text} hash={message.hash} />
    case 'task':
      return <TaskCard task={message.task} onSimulate={onSimulate} />
  }
}

export function MessageItem({ message, ...actions }: { message: Message } & MessageActions) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-primary-foreground">
          {message.spoken && <Mic className="mr-1.5 inline size-3.5 align-[-2px]" />}
          {message.text}
        </div>
      </div>
    )
  }
  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[85%]">
        <AssistantBody message={message} {...actions} />
      </div>
    </div>
  )
}
```

`apps/wallet/src/chat/ChatView.tsx`:
```tsx
import { useEffect, useRef } from 'react'
import { EXAMPLES } from '@/mock/fixtures'
import type { Message } from '@/types'
import { MessageItem, type MessageActions } from './MessageItem'

type Props = { messages: Message[]; onPick: (text: string) => void } & MessageActions

export function ChatView({ messages, onPick, ...actions }: Props) {
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="mx-auto flex h-full max-w-[720px] flex-col items-center justify-center gap-6 px-4 text-center">
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold">What should I do?</h2>
          <p className="text-muted-foreground">Tap the mic and just say it — or type.</p>
        </div>
        <div className="flex flex-wrap justify-center gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => onPick(ex)}
              className="rounded-full border px-4 py-2 text-sm text-muted-foreground transition hover:border-primary hover:text-foreground"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-[720px] flex-col gap-3 px-4 py-6">
      {messages.map((m) => (
        <MessageItem key={m.id} message={m} {...actions} />
      ))}
      <div ref={endRef} />
    </div>
  )
}
```

- [ ] **Step 4: Input bar with mic**

`apps/wallet/src/chat/InputBar.tsx`:
```tsx
import { useState, type FormEvent } from 'react'
import { ArrowUp, Mic, Square, Volume2, VolumeX } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useSpeechRecognition } from '@/voice/speech'

type Props = {
  onSend: (text: string, spoken: boolean) => void
  speakEnabled: boolean
  onToggleSpeak: () => void
}

export function InputBar({ onSend, speakEnabled, onToggleSpeak }: Props) {
  const [text, setText] = useState('')
  const voice = useSpeechRecognition((t) => onSend(t, true))
  const hasText = text.trim().length > 0

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!hasText) return
    onSend(text.trim(), false)
    setText('')
  }

  return (
    <div className="space-y-2">
      {(voice.listening || voice.error) && (
        <p className={cn('px-2 text-sm', voice.error ? 'text-destructive' : 'text-muted-foreground')}>
          {voice.error || voice.interim || 'Listening…'}
        </p>
      )}
      <form onSubmit={submit} className="flex items-center gap-2 rounded-full border bg-card p-1.5 pl-4">
        <input
          aria-label="Message"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Say or type what you want…"
          className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground"
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={onToggleSpeak}
          aria-label={speakEnabled ? 'Mute spoken replies' : 'Speak replies aloud'}
        >
          {speakEnabled ? <Volume2 /> : <VolumeX />}
        </Button>
        {hasText ? (
          <Button type="submit" size="icon" className="size-11 rounded-full" aria-label="Send">
            <ArrowUp />
          </Button>
        ) : (
          <Button
            type="button"
            size="icon"
            className={cn('size-11 rounded-full', voice.listening && 'animate-pulse')}
            onClick={voice.listening ? voice.stop : voice.start}
            disabled={!voice.supported}
            aria-label={voice.listening ? 'Stop listening' : 'Start talking'}
          >
            {voice.listening ? <Square /> : <Mic />}
          </Button>
        )}
      </form>
      {!voice.supported && (
        <p className="px-2 text-xs text-muted-foreground">
          Voice input isn't supported in this browser — try Chrome or Edge. You can still type.
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Top bar + wallet page**

`apps/wallet/src/components/TopBar.tsx`:
```tsx
import type { ReactNode } from 'react'

export function TopBar({ left, center, right }: { left?: ReactNode; center: ReactNode; right?: ReactNode }) {
  return (
    <header className="border-b">
      <div className="mx-auto flex h-16 w-full max-w-[720px] items-center gap-2 px-4">
        <div className="flex w-10 justify-start">{left}</div>
        <div className="flex min-w-0 flex-1 justify-center">{center}</div>
        <div className="flex w-10 justify-end">{right}</div>
      </div>
    </header>
  )
}
```

Replace `apps/wallet/src/routes/WalletPage.tsx`:
```tsx
import { ChatView } from '@/chat/ChatView'
import { InputBar } from '@/chat/InputBar'
import { useChat } from '@/chat/useChat'
import { TopBar } from '@/components/TopBar'
import { Badge } from '@/components/ui/badge'
import { KEYS } from '@/lib/storage'
import { useStored } from '@/lib/useStored'
import { simulateTrigger } from '@/mock/agent'
import { DEFAULT_CONTACTS } from '@/mock/fixtures'
import { useWallet } from '@/state/wallet-context'
import type { Contact, Task } from '@/types'

export default function WalletPage() {
  const { active } = useWallet()
  const [contacts] = useStored<Contact[]>(KEYS.contacts, DEFAULT_CONTACTS)
  const [, setTasks] = useStored<Task[]>(KEYS.tasks, [])
  const [speakEnabled, setSpeakEnabled] = useStored<boolean>(KEYS.speak, true)
  const chat = useChat({ contacts, speakEnabled, onTask: (t) => setTasks((prev) => [...prev, t]) })

  if (!active) return null

  return (
    <div className="flex h-dvh flex-col">
      <TopBar
        center={
          <div className="flex items-center gap-2">
            <span className="font-medium">{active.name}</span>
            <Badge variant="secondary">Sandbox</Badge>
          </div>
        }
      />
      <main className="flex-1 overflow-y-auto">
        <ChatView
          messages={chat.messages}
          onPick={(t) => chat.send(t)}
          onApprove={chat.approve}
          onReject={chat.reject}
          onSimulate={(t) => chat.deliver(simulateTrigger(t))}
        />
      </main>
      <div className="mx-auto w-full max-w-[720px] px-4 pb-4">
        <InputBar onSend={chat.send} speakEnabled={speakEnabled} onToggleSpeak={() => setSpeakEnabled((v) => !v)} />
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Verify**

Run: `pnpm --filter wallet test && pnpm --filter wallet build && pnpm --filter wallet lint` → all pass.
Manual in Chrome: unlock → empty state chips → click each chip; Send → Approve → spinner → "Done!" with hash; Reject → "Cancelled"; conditional → "Simulate trigger" → confirm card; mic → speak "what's my balance" → balance card, reply spoken; speaker toggle mutes. In Firefox: mic disabled with the "not supported" hint, typing works.

- [ ] **Step 7: Commit**

```bash
git add apps/wallet/src
git commit -m "feat(wallet): add chat UI with mock agent, voice input and confirm cards"
```

---

### Task 9: Wallet menu, address book, scheduled tasks

**Files:**
- Create: `apps/wallet/src/lib/contacts.ts`, test `apps/wallet/src/lib/contacts.test.ts`
- Create: `apps/wallet/src/components/WalletMenu.tsx`, `ShowSeedDialog.tsx`, `DeleteWalletDialog.tsx`, `AddressBookSheet.tsx`, `TasksSheet.tsx`
- Modify (replace): `apps/wallet/src/routes/WalletPage.tsx`

**Interfaces:**
- Consumes: `useWallet()` (Task 4), `SeedPhrase` (Task 5), `TASK_ICONS` (Task 8), `PORTFOLIO_USD` (Task 6)
- Produces: `validateContact(name: string, address: string, contacts: Contact[], editingId: string | null): string | null`; components `<WalletMenu onOpenTasks onShowSeed onDelete />`, `<ShowSeedDialog open onOpenChange />`, `<DeleteWalletDialog open onOpenChange />`, `<AddressBookSheet open onOpenChange contacts onChange />`, `<TasksSheet open onOpenChange tasks onChange />`

- [ ] **Step 1: Write failing test**

`apps/wallet/src/lib/contacts.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import type { Contact } from '@/types'
import { validateContact } from './contacts'

const alice: Contact = { id: 'a', name: 'Alice', address: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8' }
const ok = '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC'

describe('validateContact', () => {
  it('requires a name', () => {
    expect(validateContact('  ', ok, [], null)).toBe('Enter a name')
  })
  it('requires a valid address (bad checksum rejected)', () => {
    expect(validateContact('Bob', '0x123', [], null)).toBe('Enter a valid 0x address')
    expect(validateContact('Bob', '0x3c44CdDdB6a900fa2b585dd299e03d12FA4293BC', [], null)).toBe(
      'Enter a valid 0x address',
    )
  })
  it('rejects duplicate names case-insensitively', () => {
    expect(validateContact('alice', ok, [alice], null)).toBe('You already have a contact named alice')
  })
  it('allows keeping the same name when editing', () => {
    expect(validateContact('Alice', ok, [alice], 'a')).toBeNull()
  })
  it('accepts lowercase addresses', () => {
    expect(validateContact('Bob', ok.toLowerCase(), [alice], null)).toBeNull()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm --filter wallet test` → FAIL (cannot resolve `./contacts`).

- [ ] **Step 3: Implement validation**

`apps/wallet/src/lib/contacts.ts`:
```ts
import { isAddress } from 'viem'
import type { Contact } from '@/types'

export function validateContact(
  name: string,
  address: string,
  contacts: Contact[],
  editingId: string | null,
): string | null {
  const n = name.trim()
  if (!n) return 'Enter a name'
  if (!isAddress(address.trim())) return 'Enter a valid 0x address'
  if (contacts.some((c) => c.id !== editingId && c.name.toLowerCase() === n.toLowerCase())) {
    return `You already have a contact named ${n}`
  }
  return null
}
```

Run: `pnpm --filter wallet test` → PASS.

- [ ] **Step 4: Wallet menu and dialogs**

`apps/wallet/src/components/WalletMenu.tsx`:
```tsx
import { Check, ChevronDown, Download, KeyRound, ListTodo, Lock, Plus, Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { formatUsd, shortAddress } from '@/lib/format'
import { PORTFOLIO_USD } from '@/mock/fixtures'
import { useWallet } from '@/state/wallet-context'

type Props = { onOpenTasks: () => void; onShowSeed: () => void; onDelete: () => void }

export function WalletMenu({ onOpenTasks, onShowSeed, onDelete }: Props) {
  const { wallets, active, setActive, lock } = useWallet()
  const navigate = useNavigate()
  if (!active) return null

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger className="flex min-w-0 items-center gap-2 rounded-full border px-3 py-1.5 text-sm hover:bg-secondary">
        <span className="truncate font-medium">{active.name}</span>
        <span className="font-mono text-xs text-muted-foreground">{shortAddress(active.address)}</span>
        <Badge variant="secondary" className="hidden sm:inline-flex">
          Sandbox
        </Badge>
        <ChevronDown className="size-4 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="center" className="w-72">
        <DropdownMenuLabel>Wallets</DropdownMenuLabel>
        {wallets.map((w) => (
          <DropdownMenuItem key={w.id} onSelect={() => setActive(w.id)}>
            <div className="min-w-0 flex-1">
              <p className="truncate">{w.name}</p>
              <p className="font-mono text-xs text-muted-foreground">
                {shortAddress(w.address)} · {formatUsd(PORTFOLIO_USD)}
              </p>
            </div>
            {w.id === active.id && <Check className="size-4 text-primary" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate('/create')}>
          <Plus /> Add new wallet
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate('/import')}>
          <Download /> Import seed phrase
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onOpenTasks}>
          <ListTodo /> Scheduled tasks
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={onShowSeed}>
          <KeyRound /> Show seed phrase
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={lock}>
          <Lock /> Lock
        </DropdownMenuItem>
        <DropdownMenuItem variant="destructive" onSelect={onDelete}>
          <Trash2 /> Delete wallet
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
```

`apps/wallet/src/components/ShowSeedDialog.tsx`:
```tsx
import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useWallet } from '@/state/wallet-context'
import { SeedPhrase } from './SeedPhrase'

export function ShowSeedDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { active, verifyPassword } = useWallet()
  const [password, setPassword] = useState('')
  const [verified, setVerified] = useState(false)
  const [error, setError] = useState('')

  function handleOpenChange(v: boolean) {
    if (!v) {
      setPassword('')
      setVerified(false)
      setError('')
    }
    onOpenChange(v)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (await verifyPassword(password)) setVerified(true)
    else setError('Wrong password')
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Seed phrase — {active?.name}</DialogTitle>
          <DialogDescription>Anyone with these words controls this wallet.</DialogDescription>
        </DialogHeader>
        {verified && active ? (
          <SeedPhrase mnemonic={active.mnemonic} />
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <Label htmlFor="seed-password">Enter your password</Label>
            <Input
              id="seed-password"
              type="password"
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={!password}>
              Show
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
```

`apps/wallet/src/components/DeleteWalletDialog.tsx`:
```tsx
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useWallet } from '@/state/wallet-context'

export function DeleteWalletDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { active, wallets, deleteWallet } = useWallet()
  const isLast = wallets.length === 1

  async function confirmDelete() {
    if (active) await deleteWallet(active.id)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete “{active?.name}”?</DialogTitle>
          <DialogDescription>
            {isLast
              ? "This is your only wallet, so LazyWallet will reset. You'll need the seed phrase to get it back."
              : "It will be removed from this device. You'll need the seed phrase to get it back."}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={confirmDelete}>
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 5: Address book and tasks sheets**

`apps/wallet/src/components/AddressBookSheet.tsx`:
```tsx
import { useState, type FormEvent } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { validateContact } from '@/lib/contacts'
import { shortAddress, uid } from '@/lib/format'
import type { Address, Contact } from '@/types'

type Props = {
  open: boolean
  onOpenChange: (v: boolean) => void
  contacts: Contact[]
  onChange: (contacts: Contact[]) => void
}

export function AddressBookSheet({ open, onOpenChange, contacts, onChange }: Props) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [error, setError] = useState<string | null>(null)

  function reset() {
    setEditingId(null)
    setName('')
    setAddress('')
    setError(null)
  }

  function save(e: FormEvent) {
    e.preventDefault()
    const err = validateContact(name, address, contacts, editingId)
    setError(err)
    if (err) return
    const entry: Contact = { id: editingId ?? uid(), name: name.trim(), address: address.trim() as Address }
    onChange(editingId ? contacts.map((c) => (c.id === editingId ? entry : c)) : [...contacts, entry])
    reset()
  }

  function edit(c: Contact) {
    setEditingId(c.id)
    setName(c.name)
    setAddress(c.address)
    setError(null)
  }

  return (
    <Sheet
      open={open}
      onOpenChange={(v) => {
        if (!v) reset()
        onOpenChange(v)
      }}
    >
      <SheetContent side="right" className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Address book</SheetTitle>
          <SheetDescription>Say a name — “send 0.1 ETH to Alice” — and I'll use the address saved here.</SheetDescription>
        </SheetHeader>
        <div className="flex-1 space-y-6 overflow-y-auto px-4 pb-4">
          <form onSubmit={save} className="space-y-3 rounded-2xl border p-4">
            <div className="space-y-2">
              <Label htmlFor="contact-name">Name</Label>
              <Input id="contact-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contact-address">Address</Label>
              <Input
                id="contact-address"
                className="font-mono"
                placeholder="0x…"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex gap-2">
              {editingId && (
                <Button type="button" variant="secondary" onClick={reset}>
                  Cancel
                </Button>
              )}
              <Button type="submit" className="flex-1">
                {editingId ? 'Save' : 'Add contact'}
              </Button>
            </div>
          </form>
          {contacts.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground">No contacts yet.</p>
          ) : (
            <ul className="divide-y">
              {contacts.map((c) => (
                <li key={c.id} className="flex items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{c.name}</p>
                    <p className="font-mono text-xs text-muted-foreground">{shortAddress(c.address)}</p>
                  </div>
                  <Button size="icon" variant="ghost" aria-label={`Edit ${c.name}`} onClick={() => edit(c)}>
                    <Pencil />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={`Delete ${c.name}`}
                    onClick={() => onChange(contacts.filter((x) => x.id !== c.id))}
                  >
                    <Trash2 />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
```

`apps/wallet/src/components/TasksSheet.tsx`:
```tsx
import { Pause, Play, Trash2 } from 'lucide-react'
import { TASK_ICONS } from '@/chat/cards/task-icons'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import type { Task } from '@/types'

type Props = { open: boolean; onOpenChange: (v: boolean) => void; tasks: Task[]; onChange: (tasks: Task[]) => void }

export function TasksSheet({ open, onOpenChange, tasks, onChange }: Props) {
  const toggle = (id: string) =>
    onChange(tasks.map((t) => (t.id === id ? { ...t, status: t.status === 'active' ? 'paused' : 'active' } : t)))

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Scheduled tasks</SheetTitle>
          <SheetDescription>Tasks run only while this tab is open. You approve every transaction.</SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto px-4 pb-4">
          {tasks.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No tasks yet. Try “Alert me if ETH drops below 3000”.
            </p>
          ) : (
            <ul className="divide-y">
              {tasks.map((t) => {
                const Icon = TASK_ICONS[t.kind]
                return (
                  <li key={t.id} className="flex items-center gap-3 py-3">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                      <Icon className="size-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{t.description}</p>
                      <p className="text-xs text-muted-foreground">{t.schedule}</p>
                      {t.status === 'paused' && (
                        <Badge variant="secondary" className="mt-1">
                          Paused
                        </Badge>
                      )}
                    </div>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={t.status === 'active' ? 'Pause task' : 'Resume task'}
                      onClick={() => toggle(t.id)}
                    >
                      {t.status === 'active' ? <Pause /> : <Play />}
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Delete task"
                      onClick={() => onChange(tasks.filter((x) => x.id !== t.id))}
                    >
                      <Trash2 />
                    </Button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
```

- [ ] **Step 6: Wire into wallet page**

Replace `apps/wallet/src/routes/WalletPage.tsx`:
```tsx
import { useState } from 'react'
import { BookUser, Zap } from 'lucide-react'
import { ChatView } from '@/chat/ChatView'
import { InputBar } from '@/chat/InputBar'
import { useChat } from '@/chat/useChat'
import { AddressBookSheet } from '@/components/AddressBookSheet'
import { DeleteWalletDialog } from '@/components/DeleteWalletDialog'
import { ShowSeedDialog } from '@/components/ShowSeedDialog'
import { TasksSheet } from '@/components/TasksSheet'
import { TopBar } from '@/components/TopBar'
import { Button } from '@/components/ui/button'
import { WalletMenu } from '@/components/WalletMenu'
import { KEYS } from '@/lib/storage'
import { useStored } from '@/lib/useStored'
import { simulateTrigger } from '@/mock/agent'
import { DEFAULT_CONTACTS } from '@/mock/fixtures'
import { useWallet } from '@/state/wallet-context'
import type { Contact, Task } from '@/types'

type Panel = 'contacts' | 'tasks' | 'seed' | 'delete' | null

export default function WalletPage() {
  const { active } = useWallet()
  const [contacts, setContacts] = useStored<Contact[]>(KEYS.contacts, DEFAULT_CONTACTS)
  const [tasks, setTasks] = useStored<Task[]>(KEYS.tasks, [])
  const [speakEnabled, setSpeakEnabled] = useStored<boolean>(KEYS.speak, true)
  const [panel, setPanel] = useState<Panel>(null)
  const chat = useChat({ contacts, speakEnabled, onTask: (t) => setTasks((prev) => [...prev, t]) })
  const activeTasks = tasks.filter((t) => t.status === 'active').length
  const panelProps = (p: Exclude<Panel, null>) => ({
    open: panel === p,
    onOpenChange: (v: boolean) => setPanel(v ? p : null),
  })

  if (!active) return null

  return (
    <div className="flex h-dvh flex-col">
      <TopBar
        center={
          <WalletMenu
            onOpenTasks={() => setPanel('tasks')}
            onShowSeed={() => setPanel('seed')}
            onDelete={() => setPanel('delete')}
          />
        }
        right={
          <Button variant="ghost" size="icon" aria-label="Address book" onClick={() => setPanel('contacts')}>
            <BookUser />
          </Button>
        }
      />
      <main className="flex-1 overflow-y-auto">
        <ChatView
          messages={chat.messages}
          onPick={(t) => chat.send(t)}
          onApprove={chat.approve}
          onReject={chat.reject}
          onSimulate={(t) => chat.deliver(simulateTrigger(t))}
        />
      </main>
      <div className="mx-auto w-full max-w-[720px] space-y-2 px-4 pb-4">
        {activeTasks > 0 && (
          <button
            type="button"
            onClick={() => setPanel('tasks')}
            className="flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <Zap className="size-3.5 text-primary" />
            {activeTasks} active {activeTasks === 1 ? 'task' : 'tasks'}
          </button>
        )}
        <InputBar onSend={chat.send} speakEnabled={speakEnabled} onToggleSpeak={() => setSpeakEnabled((v) => !v)} />
      </div>
      <AddressBookSheet {...panelProps('contacts')} contacts={contacts} onChange={setContacts} />
      <TasksSheet {...panelProps('tasks')} tasks={tasks} onChange={setTasks} />
      <ShowSeedDialog {...panelProps('seed')} />
      <DeleteWalletDialog {...panelProps('delete')} />
    </div>
  )
}
```

- [ ] **Step 7: Verify**

Run: `pnpm --filter wallet test && pnpm --filter wallet build && pnpm --filter wallet lint` → all pass.
Manual: dropdown lists wallets and switches; Add new → Create flow skips password; Show seed with wrong then right password; Lock → Unlock; address book add "Carol" with a valid address → "send 0.1 eth to carol" yields confirm; invalid address / duplicate name show errors; create an alert → "1 active task" chip → sheet → pause/resume/delete; Delete the last wallet → returns to Welcome.

- [ ] **Step 8: Commit**

```bash
git add apps/wallet/src
git commit -m "feat(wallet): add wallet menu, address book and scheduled tasks"
```

---

### Task 10: Receive / Connect dApp sheet, WalletConnect mock, Connected bar

**Files:**
- Create: `apps/wallet/src/mock/walletconnect.ts`, test `apps/wallet/src/mock/walletconnect.test.ts`
- Create: `apps/wallet/src/components/QrSheet.tsx`, `apps/wallet/src/components/ConnectedBar.tsx`
- Modify (replace): `apps/wallet/src/routes/WalletPage.tsx`

**Interfaces:**
- Consumes: `say`, `confirm` (Task 6), `UNISWAP` (Task 6), `hostOf`, `shortAddress` (Task 2)
- Produces: `type Proposal = { dapp: DappInfo; chain: string; methods: string[] }`, `isWcUri(input: string): boolean`, `mockProposal(): Proposal`, `dappRequest(dapp: DappInfo): AgentReply`; components `<QrSheet open onOpenChange address onConnect />`, `<ConnectedBar dapp onDisconnect />`

- [ ] **Step 1: Write failing test**

`apps/wallet/src/mock/walletconnect.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { UNISWAP } from './fixtures'
import { dappRequest, isWcUri } from './walletconnect'

const topic = 'a'.repeat(64)
const valid = `wc:${topic}@2?relay-protocol=irn&symKey=${'b'.repeat(64)}&expiryTimestamp=1760000000`

describe('isWcUri', () => {
  it('accepts a v2 pairing URI, tolerating surrounding whitespace', () => {
    expect(isWcUri(valid)).toBe(true)
    expect(isWcUri(`  ${valid}\n`)).toBe(true)
  })
  it('rejects v1 URIs, missing params and non-wc text', () => {
    expect(isWcUri(`wc:${topic}@1?bridge=https%3A%2F%2Fbridge&key=abc`)).toBe(false)
    expect(isWcUri(`wc:${topic}@2?relay-protocol=irn`)).toBe(false)
    expect(isWcUri('https://app.uniswap.org')).toBe(false)
    expect(isWcUri('')).toBe(false)
  })
})

describe('dappRequest', () => {
  it('produces an explained confirm card from the dapp', () => {
    const reply = dappRequest(UNISWAP)
    const card = reply.messages.find((m) => m.kind === 'confirm')
    if (!card || card.kind !== 'confirm') throw new Error('expected confirm')
    expect(card.tx.dapp).toEqual(UNISWAP)
    expect(card.tx.explanation).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm --filter wallet test` → FAIL (cannot resolve `./walletconnect`).

- [ ] **Step 3: Implement mock**

`apps/wallet/src/mock/walletconnect.ts`:
```ts
import { shortAddress } from '@/lib/format'
import type { AgentReply, DappInfo } from '@/types'
import { confirm, say } from './agent'
import { UNISWAP } from './fixtures'

export type Proposal = { dapp: DappInfo; chain: string; methods: string[] }

const UNIVERSAL_ROUTER = '0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD'

// WalletConnect v2 pairing URI: wc:{64-hex topic}@2?relay-protocol=...&symKey=...
export function isWcUri(input: string): boolean {
  return /^wc:[0-9a-f]{64}@2\?(?=.*\brelay-protocol=)(?=.*\bsymKey=)/i.test(input.trim())
}

export function mockProposal(): Proposal {
  return { dapp: UNISWAP, chain: 'Sandbox (eip155:1)', methods: ['eth_sendTransaction', 'personal_sign'] }
}

export function dappRequest(dapp: DappInfo): AgentReply {
  return {
    messages: [
      say(`${dapp.name} is asking you to approve a transaction. Here's what it does:`),
      confirm({
        title: 'Swap 0.05 ETH → USDC',
        dapp,
        explanation: `This swaps 0.05 ETH for about 159.5 USDC on ${dapp.name}. It only spends the 0.05 ETH shown — no unlimited token approval.`,
        rows: [
          { label: 'Method', value: 'eth_sendTransaction' },
          { label: 'Contract', value: shortAddress(UNIVERSAL_ROUTER) },
          { label: 'Value', value: '0.05 ETH' },
          { label: 'Network fee', value: '~$3.10' },
        ],
      }),
    ],
  }
}
```

Run: `pnpm --filter wallet test` → PASS.

- [ ] **Step 4: QR sheet and Connected bar**

`apps/wallet/src/components/QrSheet.tsx`:
```tsx
import { useState, type FormEvent } from 'react'
import { Camera, ClipboardPaste, Copy } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { hostOf } from '@/lib/format'
import { isWcUri, mockProposal, type Proposal } from '@/mock/walletconnect'
import type { Address, DappInfo } from '@/types'

type Props = {
  open: boolean
  onOpenChange: (v: boolean) => void
  address: Address
  onConnect: (dapp: DappInfo) => void
}

export function QrSheet({ open, onOpenChange, address, onConnect }: Props) {
  const [uri, setUri] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [proposal, setProposal] = useState<Proposal | null>(null)

  async function copyAddress() {
    try {
      await navigator.clipboard.writeText(address)
      toast.success('Address copied')
    } catch {
      toast.error('Copy failed')
    }
  }

  async function paste() {
    try {
      setUri(await navigator.clipboard.readText())
    } catch {
      toast.error('Clipboard access was blocked — paste manually')
    }
  }

  function connect(e: FormEvent) {
    e.preventDefault()
    if (!isWcUri(uri)) {
      setError("That isn't a WalletConnect link — it should start with wc:")
      return
    }
    setError(null)
    setProposal(mockProposal())
  }

  function approve() {
    if (proposal) onConnect(proposal.dapp)
    setProposal(null)
    setUri('')
    onOpenChange(false)
  }

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="left" className="w-full sm:max-w-md">
          <SheetHeader>
            <SheetTitle>Receive or connect</SheetTitle>
          </SheetHeader>
          <Tabs defaultValue="receive" className="px-4 pb-4">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="receive">Receive</TabsTrigger>
              <TabsTrigger value="connect">Connect dApp</TabsTrigger>
            </TabsList>
            <TabsContent value="receive" className="space-y-4 pt-4">
              <div className="mx-auto w-fit rounded-2xl bg-white p-4">
                <QRCodeSVG value={address} size={200} />
              </div>
              <p className="break-all text-center font-mono text-sm">{address}</p>
              <Button variant="secondary" className="w-full" onClick={copyAddress}>
                <Copy /> Copy address
              </Button>
              <p className="text-center text-xs text-muted-foreground">
                Sandbox · Ethereum mainnet fork. Don't send real funds here.
              </p>
            </TabsContent>
            <TabsContent value="connect" className="space-y-4 pt-4">
              <p className="text-sm text-muted-foreground">
                On the dApp, choose WalletConnect, copy its link, and paste it here.
              </p>
              <form onSubmit={connect} className="space-y-3">
                <Label htmlFor="wc-uri">WalletConnect link</Label>
                <div className="flex gap-2">
                  <Input
                    id="wc-uri"
                    className="font-mono"
                    placeholder="wc:…"
                    value={uri}
                    onChange={(e) => setUri(e.target.value)}
                  />
                  <Button type="button" variant="secondary" size="icon" aria-label="Paste" onClick={paste}>
                    <ClipboardPaste />
                  </Button>
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                <Button type="submit" className="w-full" disabled={!uri.trim()}>
                  Connect
                </Button>
              </form>
              <Button variant="ghost" className="w-full" disabled>
                <Camera /> Scan QR — coming soon
              </Button>
            </TabsContent>
          </Tabs>
        </SheetContent>
      </Sheet>
      <Dialog open={proposal !== null} onOpenChange={(v) => !v && setProposal(null)}>
        <DialogContent>
          {proposal && (
            <>
              <DialogHeader>
                <div className="flex items-center gap-3">
                  <span className="flex size-10 items-center justify-center rounded-full bg-secondary text-xl">
                    {proposal.dapp.icon}
                  </span>
                  <div>
                    <DialogTitle>{proposal.dapp.name} wants to connect</DialogTitle>
                    <DialogDescription>{hostOf(proposal.dapp.url)}</DialogDescription>
                  </div>
                </div>
              </DialogHeader>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Network</dt>
                  <dd>{proposal.chain}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Can request</dt>
                  <dd className="text-right font-mono">{proposal.methods.join(', ')}</dd>
                </div>
              </dl>
              <p className="text-xs text-muted-foreground">
                It can only ask. Every request shows up in your chat for you to approve.
              </p>
              <DialogFooter>
                <Button variant="secondary" onClick={() => setProposal(null)}>
                  Reject
                </Button>
                <Button onClick={approve}>Approve</Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
```

`apps/wallet/src/components/ConnectedBar.tsx`:
```tsx
import { Check, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { hostOf } from '@/lib/format'
import type { DappInfo } from '@/types'

export function ConnectedBar({ dapp, onDisconnect }: { dapp: DappInfo; onDisconnect: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border bg-card px-3 py-2 text-sm">
      <span className="relative flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary">
        {dapp.icon}
        <span className="absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full bg-primary ring-2 ring-card" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-medium">Connected to {dapp.name}</p>
        <p className="truncate text-xs text-muted-foreground">{hostOf(dapp.url)}</p>
      </div>
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger className="flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs">
          Sandbox <ChevronDown className="size-3" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>Network</DropdownMenuLabel>
          <DropdownMenuItem>
            Sandbox (Ethereum fork)
            <Check className="ml-auto size-4 text-primary" />
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <Button variant="ghost" size="sm" onClick={onDisconnect}>
        Disconnect
      </Button>
    </div>
  )
}
```

- [ ] **Step 5: Final wallet page**

Replace `apps/wallet/src/routes/WalletPage.tsx`:
```tsx
import { useEffect, useRef, useState } from 'react'
import { BookUser, QrCode, Zap } from 'lucide-react'
import { ChatView } from '@/chat/ChatView'
import { InputBar } from '@/chat/InputBar'
import { useChat } from '@/chat/useChat'
import { AddressBookSheet } from '@/components/AddressBookSheet'
import { ConnectedBar } from '@/components/ConnectedBar'
import { DeleteWalletDialog } from '@/components/DeleteWalletDialog'
import { QrSheet } from '@/components/QrSheet'
import { ShowSeedDialog } from '@/components/ShowSeedDialog'
import { TasksSheet } from '@/components/TasksSheet'
import { TopBar } from '@/components/TopBar'
import { Button } from '@/components/ui/button'
import { WalletMenu } from '@/components/WalletMenu'
import { KEYS } from '@/lib/storage'
import { useStored } from '@/lib/useStored'
import { say, simulateTrigger } from '@/mock/agent'
import { DEFAULT_CONTACTS } from '@/mock/fixtures'
import { dappRequest } from '@/mock/walletconnect'
import { useWallet } from '@/state/wallet-context'
import type { Contact, DappInfo, Task } from '@/types'

type Panel = 'qr' | 'contacts' | 'tasks' | 'seed' | 'delete' | null

const DAPP_REQUEST_DELAY_MS = 3000

export default function WalletPage() {
  const { active } = useWallet()
  const [contacts, setContacts] = useStored<Contact[]>(KEYS.contacts, DEFAULT_CONTACTS)
  const [tasks, setTasks] = useStored<Task[]>(KEYS.tasks, [])
  const [speakEnabled, setSpeakEnabled] = useStored<boolean>(KEYS.speak, true)
  const [panel, setPanel] = useState<Panel>(null)
  const [session, setSession] = useState<DappInfo | null>(null)
  const requestTimer = useRef<number | undefined>(undefined)
  const chat = useChat({ contacts, speakEnabled, onTask: (t) => setTasks((prev) => [...prev, t]) })
  const activeTasks = tasks.filter((t) => t.status === 'active').length
  const panelProps = (p: Exclude<Panel, null>) => ({
    open: panel === p,
    onOpenChange: (v: boolean) => setPanel(v ? p : null),
  })

  useEffect(() => () => window.clearTimeout(requestTimer.current), [])

  function connect(dapp: DappInfo) {
    setSession(dapp)
    chat.deliver({ messages: [say(`Connected to ${dapp.name}. I'll explain anything it asks you to sign.`)] })
    window.clearTimeout(requestTimer.current)
    requestTimer.current = window.setTimeout(() => chat.deliver(dappRequest(dapp)), DAPP_REQUEST_DELAY_MS)
  }

  function disconnect() {
    window.clearTimeout(requestTimer.current)
    if (session) chat.deliver({ messages: [say(`Disconnected from ${session.name}.`)] })
    setSession(null)
  }

  if (!active) return null

  return (
    <div className="flex h-dvh flex-col">
      <TopBar
        left={
          <Button variant="ghost" size="icon" aria-label="Receive or connect dApp" onClick={() => setPanel('qr')}>
            <QrCode />
          </Button>
        }
        center={
          <WalletMenu
            onOpenTasks={() => setPanel('tasks')}
            onShowSeed={() => setPanel('seed')}
            onDelete={() => setPanel('delete')}
          />
        }
        right={
          <Button variant="ghost" size="icon" aria-label="Address book" onClick={() => setPanel('contacts')}>
            <BookUser />
          </Button>
        }
      />
      <main className="flex-1 overflow-y-auto">
        <ChatView
          messages={chat.messages}
          onPick={(t) => chat.send(t)}
          onApprove={chat.approve}
          onReject={chat.reject}
          onSimulate={(t) => chat.deliver(simulateTrigger(t))}
        />
      </main>
      <div className="mx-auto w-full max-w-[720px] space-y-2 px-4 pb-4">
        {activeTasks > 0 && (
          <button
            type="button"
            onClick={() => setPanel('tasks')}
            className="flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <Zap className="size-3.5 text-primary" />
            {activeTasks} active {activeTasks === 1 ? 'task' : 'tasks'}
          </button>
        )}
        {session && <ConnectedBar dapp={session} onDisconnect={disconnect} />}
        <InputBar onSend={chat.send} speakEnabled={speakEnabled} onToggleSpeak={() => setSpeakEnabled((v) => !v)} />
      </div>
      <QrSheet {...panelProps('qr')} address={active.address} onConnect={connect} />
      <AddressBookSheet {...panelProps('contacts')} contacts={contacts} onChange={setContacts} />
      <TasksSheet {...panelProps('tasks')} tasks={tasks} onChange={setTasks} />
      <ShowSeedDialog {...panelProps('seed')} />
      <DeleteWalletDialog {...panelProps('delete')} />
    </div>
  )
}
```

- [ ] **Step 6: Verify**

Run: `pnpm --filter wallet test && pnpm --filter wallet build && pnpm --filter wallet lint` → all pass.
Manual: QR button → Receive shows QR + address + copy. Connect tab → paste `hello` → error; paste `wc:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@2?relay-protocol=irn&symKey=bb` → proposal dialog → Approve → Connected bar + "Connected to Uniswap" → after ~3 s a dapp confirm card with explanation → Approve works. Disconnect before 3 s → no request arrives. Check layout at 375px width (no horizontal scroll).

- [ ] **Step 7: Commit**

```bash
git add apps/wallet/src
git commit -m "feat(wallet): add receive/connect sheet, WalletConnect mock and connected bar"
```

---

### Task 11: Landing page

**Files:**
- Create (scaffolded): `apps/landing/*`
- Modify: `apps/landing/vite.config.ts`, `apps/landing/index.html`, `apps/landing/src/index.css`, `apps/landing/src/main.tsx`, `apps/landing/src/App.tsx`
- Create: `apps/landing/src/components/Hero.tsx`, `VoiceDemo.tsx`, `Audience.tsx`, `HowItWorks.tsx`, `apps/landing/.env.example`

**Interfaces:**
- Produces: landing at http://localhost:5173 linking to `VITE_WALLET_URL` (default `http://localhost:5174`).

- [ ] **Step 1: Scaffold**

```bash
pnpm create vite@latest apps/landing --template react-ts
cd apps/landing
pnpm install
pnpm add tailwindcss @tailwindcss/vite lucide-react
```

Replace `apps/landing/vite.config.ts`:
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, strictPort: true },
})
```

`apps/landing/.env.example`:
```
VITE_WALLET_URL=http://localhost:5174
```

In `apps/landing/index.html`: `<html lang="en" class="dark">`, `<title>LazyWallet — Just say it.</title>`, `<meta name="description" content="Voice-powered AI wallet. Talk to send, swap and automate trades." />`, and the same Google Fonts `<link>` tags as Task 1 Step 5.

Delete `src/App.css`, `src/assets/react.svg` and any unused template asset references.

- [ ] **Step 2: Theme**

Replace `apps/landing/src/index.css`:
```css
@import "tailwindcss";

@theme {
  --color-background: #0a0b0a;
  --color-foreground: #edefea;
  --color-card: #141614;
  --color-secondary: #1c1f1c;
  --color-muted-foreground: #8a918a;
  --color-border: #262a26;
  --color-primary: #b6ff3b;
  --color-primary-foreground: #0a0b0a;
  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}

@layer base {
  *,
  ::before,
  ::after {
    border-color: var(--color-border);
  }
  body {
    background-color: var(--color-background);
    color: var(--color-foreground);
    font-family: var(--font-sans);
    -webkit-font-smoothing: antialiased;
  }
}

@keyframes wave {
  0%,
  100% {
    transform: scaleY(0.35);
  }
  50% {
    transform: scaleY(1);
  }
}
```

- [ ] **Step 3: Components**

`apps/landing/src/components/VoiceDemo.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { Mic } from 'lucide-react'

const PHASE_MS = 2200
const BARS = Array.from({ length: 24 }, (_, i) => i)

export function VoiceDemo() {
  const [phase, setPhase] = useState(0)

  useEffect(() => {
    const t = window.setInterval(() => setPhase((p) => (p + 1) % 3), PHASE_MS)
    return () => window.clearInterval(t)
  }, [])

  return (
    <div className="mx-auto w-full max-w-sm space-y-4 rounded-3xl border bg-card p-5 shadow-[0_0_80px_-20px_rgba(182,255,59,0.35)]">
      <div className="flex h-14 items-center justify-center gap-1" aria-hidden>
        {BARS.map((i) => (
          <span
            key={i}
            className="w-1 origin-center rounded-full bg-primary transition-opacity motion-safe:animate-[wave_1s_ease-in-out_infinite]"
            style={{ height: `${20 + ((i * 37) % 28)}px`, animationDelay: `${i * 60}ms`, opacity: phase === 0 ? 1 : 0.2 }}
          />
        ))}
      </div>
      <div className={`flex justify-end transition-opacity duration-500 ${phase >= 1 ? 'opacity-100' : 'opacity-0'}`}>
        <p className="rounded-2xl rounded-br-md bg-primary px-4 py-2 text-sm text-primary-foreground">
          <Mic className="mr-1 inline size-3.5 align-[-2px]" />
          Swap 100 USDC to ETH
        </p>
      </div>
      <div className={`rounded-2xl border bg-background p-4 text-sm transition-opacity duration-500 ${phase === 2 ? 'opacity-100' : 'opacity-0'}`}>
        <p className="font-semibold">Swap 100 USDC → ETH</p>
        <dl className="mt-2 space-y-1">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">You receive</dt>
            <dd className="font-mono">≈ 0.0311563 ETH</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Route</dt>
            <dd className="font-mono">Uniswap v3</dd>
          </div>
        </dl>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <span className="rounded-full bg-secondary py-1.5 text-center">Reject</span>
          <span className="rounded-full bg-primary py-1.5 text-center font-medium text-primary-foreground">Approve</span>
        </div>
      </div>
    </div>
  )
}
```

`apps/landing/src/components/Hero.tsx`:
```tsx
import { ArrowRight } from 'lucide-react'
import { VoiceDemo } from './VoiceDemo'

export function Hero({ walletUrl }: { walletUrl: string }) {
  return (
    <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 md:grid-cols-2 md:py-28">
      <div className="space-y-6">
        <p className="inline-flex rounded-full border px-3 py-1 text-xs text-muted-foreground">Voice-powered AI wallet</p>
        <h1 className="text-5xl font-semibold tracking-tight md:text-6xl">Just say it.</h1>
        <p className="max-w-md text-lg text-muted-foreground">
          Check balances, send, swap and automate trades by talking to your wallet. You approve every transaction.
        </p>
        <a
          href={walletUrl}
          className="inline-flex h-12 items-center gap-2 rounded-full bg-primary px-6 font-medium text-primary-foreground transition hover:opacity-90"
        >
          Launch Wallet <ArrowRight className="size-4" />
        </a>
      </div>
      <VoiceDemo />
    </section>
  )
}
```

`apps/landing/src/components/Audience.tsx`:
```tsx
import { Sparkles, Zap, type LucideIcon } from 'lucide-react'

const GROUPS: { icon: LucideIcon; title: string; points: string[] }[] = [
  {
    icon: Sparkles,
    title: 'New to crypto',
    points: [
      'No DeFi dashboards to learn — just ask.',
      '“Send 20 USDC to Alice” uses your address book.',
      'Every transaction is explained in plain words before you approve.',
    ],
  },
  {
    icon: Zap,
    title: 'Degens',
    points: [
      'Price alerts and conditional orders by voice.',
      'Recurring buys: “Buy ETH every Monday with 50 USDC”.',
      'Connect any dApp with WalletConnect and let the AI read the fine print.',
    ],
  },
]

export function Audience() {
  return (
    <section className="mx-auto grid max-w-6xl gap-4 px-4 py-16 md:grid-cols-2">
      {GROUPS.map(({ icon: Icon, title, points }) => (
        <div key={title} className="space-y-4 rounded-3xl border bg-card p-6 md:p-8">
          <span className="flex size-10 items-center justify-center rounded-full bg-primary/15 text-primary">
            <Icon className="size-5" />
          </span>
          <h2 className="text-2xl font-semibold">{title}</h2>
          <ul className="space-y-2 text-muted-foreground">
            {points.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}
```

`apps/landing/src/components/HowItWorks.tsx`:
```tsx
import { Check, Eye, Mic, type LucideIcon } from 'lucide-react'

const STEPS: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: Mic, title: 'Speak', text: 'Tap the mic and say what you want.' },
  { icon: Eye, title: 'Review', text: 'LazyWallet shows exactly what will happen.' },
  { icon: Check, title: 'Approve', text: 'One tap. Your keys never leave your device.' },
]

export function HowItWorks() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16">
      <h2 className="mb-8 text-center text-3xl font-semibold">How it works</h2>
      <ol className="grid gap-4 md:grid-cols-3">
        {STEPS.map(({ icon: Icon, title, text }, i) => (
          <li key={title} className="space-y-3 rounded-3xl border bg-card p-6">
            <div className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <Icon className="size-5" />
              </span>
              <span className="font-mono text-sm text-muted-foreground">0{i + 1}</span>
            </div>
            <h3 className="text-xl font-semibold">{title}</h3>
            <p className="text-muted-foreground">{text}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
```

Replace `apps/landing/src/App.tsx`:
```tsx
import { Mic } from 'lucide-react'
import { Audience } from './components/Audience'
import { Hero } from './components/Hero'
import { HowItWorks } from './components/HowItWorks'

const WALLET_URL: string = import.meta.env.VITE_WALLET_URL ?? 'http://localhost:5174'

export default function App() {
  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <Mic className="size-4" />
          </span>
          <span className="text-lg font-semibold tracking-tight">LazyWallet</span>
        </div>
        <a href={WALLET_URL} className="rounded-full border px-4 py-1.5 text-sm hover:border-primary">
          Launch
        </a>
      </header>
      <main>
        <Hero walletUrl={WALLET_URL} />
        <Audience />
        <HowItWorks />
      </main>
      <footer className="mx-auto max-w-6xl border-t px-4 py-8 text-sm text-muted-foreground">
        LazyWallet · Hackathon project · Sandbox demo on an Ethereum mainnet fork
      </footer>
    </div>
  )
}
```

Ensure `apps/landing/src/main.tsx` imports `./index.css` and renders `<App />` (template default).

- [ ] **Step 4: Verify**

Run: `pnpm --filter landing build && pnpm --filter landing lint` → pass.
Manual: `pnpm dev` from root starts both apps; http://localhost:5173 shows hero with cycling voice demo; Launch opens the wallet; layout fine at 375px.

- [ ] **Step 5: Commit**

```bash
git add apps/landing
git commit -m "feat(landing): add landing page with voice demo"
```

---

### Task 12: README, CLAUDE.md, placeholders, final verification

**Files:**
- Create: `README.md`, `CLAUDE.md`, `agent/README.md`, `anvil/README.md`

- [ ] **Step 1: Placeholders**

`agent/README.md`:
```markdown
# agent

Python AI agent (Claude Agent SDK). Planned for Phase 2 — not started.
```

`anvil/README.md`:
```markdown
# anvil

Anvil Ethereum-mainnet fork sandbox (chain id 1) with seed scripts and a faucet endpoint. Planned for Phase 2 — not started.
```

- [ ] **Step 2: README.md**

```markdown
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
```

- [ ] **Step 3: CLAUDE.md**

```markdown
# CLAUDE.md

LazyWallet — voice-powered AI wallet (hackathon project). See README.md for overview and INIT.md for the original brief.

## Current phase

Phase 1: design mockup. Spec: `docs/superpowers/specs/2026-10-14-lazywallet-design-phase-design.md`. **Do not start Phase 2 work until the user approves the design.**

## Stack & layout

- pnpm workspace. `apps/landing` (Vite, React, TS, Tailwind v4), `apps/wallet` (+ shadcn/ui Radix, React Router, viem, wagmi, Vitest).
- `agent/` (Python, Claude Agent SDK) and `anvil/` (Anvil mainnet fork, chain id 1) are placeholders until Phase 2.
- x402 is out of scope for the first phases.
- Use official / well-known frameworks at their latest stable versions. Don't reinvent what a framework provides.

## Commands

```bash
pnpm dev                    # both apps (landing :5173, wallet :5174)
pnpm --filter wallet test   # Vitest unit tests
pnpm build && pnpm lint
```

## Wallet app conventions

- Import alias `@/` → `apps/wallet/src`. shadcn components live in `src/components/ui` (generated; add more with `pnpm dlx shadcn@latest add <name>`).
- Theme: dark-only, tokens in `src/index.css` (`.dark` block). Lime accent `#B6FF3B` used sparingly. Mono font only for amounts/addresses/hashes.
- Domain and chat message types: `src/types.ts`.
- Real vs mock boundary:
  - Real: `lib/vault.ts` (mnemonics, PBKDF2 + AES-GCM vault), `voice/speech.ts` (Web Speech API).
  - Mock: `mock/agent.ts` (scripted replies), `mock/fixtures.ts` (balances, contacts), `mock/walletconnect.ts`.
- Never store a seed phrase unencrypted. Only `lw.vault` (encrypted) holds secrets; other `lw.*` keys are non-secret.
- Signing model: keys stay in the browser; every transaction goes through an Approve/Reject confirm card. Scheduled tasks only run while the tab is open.
- Network: Sandbox only (Anvil fork, chain id 1).
- Unit tests cover pure logic (`*.test.ts` next to the module). UI is reviewed manually.

## Development motto

1. **Think before coding** — state assumptions, surface trade-offs, ask when unclear.
2. **Simplicity first** — minimum code that solves the problem; nothing speculative.
3. **Surgical changes** — touch only what the task needs; match existing style.
4. **Goal-driven execution** — define verifiable success criteria and loop until they pass.
```

- [ ] **Step 4: Full verification**

Run from repo root:
```bash
pnpm install && pnpm test && pnpm build && pnpm lint
```
Expected: all succeed.
Then `pnpm dev` and walk the spec §9 path: landing → Launch → create wallet → seed → chat → every scenario in spec §6.2 → lock → unlock → import second wallet → switch → address book CRUD → scheduled tasks → WalletConnect mock → disconnect. Reload: unlock required; localStorage `lw.vault` has no plaintext words.

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md agent anvil
git commit -m "docs: add README, CLAUDE.md and phase 2 placeholders"
```
