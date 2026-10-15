# anvil — Sandbox chain

Anvil fork of Ethereum mainnet (chain id 1) plus a faucet. Needs `ETH_RPC_URL` (archive RPC) in the repo-root `.env`.

```bash
pnpm dev:sandbox                                   # Anvil :8545 + faucet :8547
uv run --directory anvil python scripts/seed.py    # random funded test wallet → anvil/.test-wallet.json
uv run --directory anvil python scripts/reset.py   # reset the fork
uv run --directory anvil pytest -q                 # tests (fork tests skip without ETH_RPC_URL)
```

Faucet: `POST http://localhost:8547/fund {"address": "0x…"}` → 100 ETH, 10,000 USDC/USDT/DAI, 1 WBTC, 5 WETH (balances written directly into token storage).
