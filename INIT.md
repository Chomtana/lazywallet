# LazyWallet

LazyWallet is a voice-powered AI wallet for newcomers and degen. User can use voice to check balances, transfer coins, swap coins, trade, bridge, or using any app (that support programmatic interface / pure smart contract interaction) on any chain. Degen can also use it to schedule trading, price monitoring, take action when certain condition match or periodic repeated task.

This is a hackathon project, we do not neccessary need to let user connect to external site since AI will do the job for them... So, it's best to be on web... Unless WalletConnect made it possible it's worth having connect wallet feature...

## Development Motto

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## Development Framework and Folder Structure

Folder Structure (Can use pnpm monorepo)

```
apps/landing/ -> pnpm vite + react + tailwind landing page frontend
apps/wallet/ -> pnpm vite + react + tailwind + viem + wagmi frontend
agent/ -> python claude agent sdk + x402 support
anvil/ -> Anvil ETH mainnet fork sandbox (Also for testnet mode of frontend will use this)
```

Please make sure you use latest stable version of most-well known (preferrably official) framework.

IMPORTANT: Use official/well-known framework where possible, do not reinvent the framework.

## Chain Anvil Sandbox

Ref: https://www.getfoundry.sh/anvil

Use ETH Mainnet Archive RPC from .env

Impersonate chain 1 for maximum compatibility

For dev security, make sure to create new random wallet for test and see ETH in the forked chain to get started

Reset on every loop if needed

Put seed scripts in the anvil/ folder (along with a faucet endpoint for seeding while hackathon presentation if needed)

## Development Phases

### 1. Design First

First, let design landing page and wallet (full flow mock up)... and I will give comment.

- Welcome page
- New wallet page (Enter Wallet Name and click next -> it will generate seed phrase and save locally -> show seed phrase for user to note down)
- Wallet page
  - In top navbar has [QR Code Button (Receive or Wallet connect)] ____ [Wallet drop down] ____ [Address book button]
  - In the center will be chat messages
  - In the bottom will be chat input box
  - If connected to external site, will have another bottom for Connected status, website and chain selector

Also write README.md and CLAUDE.md

Wait for my approval on design before proceeding to the next step.

### 2. Minimum Viable AI Wallet

Setup agent and anvil for minimum wallet transfer etc that doesn't interact with external protocol yet

### 3. Support Uniswap Tool

Support uniswap v4 swap tool
