# LazyWallet Phase 2 (Minimum Viable AI Wallet) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mock chat agent with a real Claude agent (Python) that reads balances from an Anvil mainnet fork and proposes ETH/ERC-20 transfers that the browser signs after the user approves.

**Architecture:** `anvil/` (Python, uv) launches an Anvil fork plus a FastAPI faucet. `agent/` (Python, uv) is a FastAPI WebSocket server; each connection owns a `ClaudeSDKClient` with built-in tools disabled and four in-process MCP wallet tools. `propose_transfer` sends a `confirm` card over the socket and awaits the browser's `tx_result`. `apps/wallet` swaps its mock chat hook for `useAgentChat`, which streams replies, signs with viem and reports receipts.

**Tech Stack:** Python ≥3.12 with uv, claude-agent-sdk 0.2.x, FastAPI, uvicorn, web3.py 8, python-dotenv, pytest + pytest-asyncio; Anvil (Foundry); React + viem in the wallet; Vitest.

**Spec:** `docs/superpowers/specs/2026-10-14-lazywallet-mvp-agent-design.md`

## Global Constraints

- Agent auth is the developer's Claude Code login (SDK spawns the local `claude` CLI). Never require or read `ANTHROPIC_API_KEY`.
- Default model `claude-sonnet-5-5`; override via `AGENT_MODEL`.
- Agent options: `tools=[]`, `strict_mcp_config=True`, `setting_sources=[]`, `include_partial_messages=True`, `max_turns=10`, only `mcp__wallet__*` tools in `allowed_tools`.
- Keys never leave the browser. The model never writes calldata or hex values; Python builds every tx request.
- Ports: Anvil 8545, faucet 8547, agent 8787, landing 5173, wallet 5174. Test forks use 8645 (anvil tests) and 8646 (agent tests).
- Chain: Anvil fork of Ethereum mainnet from `ETH_RPC_URL` (root `.env`), `--chain-id 1`, optional `FORK_BLOCK`.
- Tokens (address, decimals, balance slot): USDC `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` 6 slot 9; USDT `0xdAC17F958D2ee523a2206206994597C13D831ec7` 6 slot 2; DAI `0x6B175474E89094C44Da98b954EedeAC495271d0F` 18 slot 2; WBTC `0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599` 8 slot 0; WETH `0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2` 18 slot 3.
- Chainlink feeds (8 decimals): ETH/USD `0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419`, BTC/USD `0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c`. USDC/USDT/DAI priced at $1.
- Faucet amounts: 10 ETH, 10,000 USDC, 10,000 USDT, 10,000 DAI, 1 WBTC, 5 WETH.
- Approval wait timeout 300 s; CLI MCP tool timeout set to 360000 ms via options `env={"MCP_TOOL_TIMEOUT": "360000"}`.
- WebSocket origin allowlist default `http://localhost:5174` (`WALLET_ORIGINS`, comma-separated).
- Chain-dependent tests skip when `ETH_RPC_URL` is unset. No test calls Claude.
- x402, swaps, bridges, real WalletConnect, scheduled execution: out of scope.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Amount strings from voice or the model — `"0.1"`, `".5"`, `"1,000"`, `"1e18"`, `"-1"`, `"0.0000001"` for a 6-decimal token — are parsed exactly or rejected with a clear reason, never rounded silently. (Task 3)
2. Sending the whole ETH balance leaves nothing for gas → rejected with an explanation, no card. (Task 3)
3. A new message while a confirm card is pending → server says "Still working…", the UI shows a notice, the pending card stays approvable. (Task 6 + Task 9)
4. Agent, Anvil or the Claude login unavailable → a visible chat message, never a silent hang. (Task 6 + Task 9)
5. Tab closed or socket dropped during a pending approval → proposal cancelled, Claude client disconnected, waiting cards marked expired after reconnect. (Task 6 + Task 7)

---

## File Structure

```
.env.example                      ETH_RPC_URL, FORK_BLOCK, AGENT_MODEL
.gitignore                        + .venv, __pycache__, .pytest_cache, anvil/.test-wallet.json
package.json                      + dev:sandbox, dev:agent, test:py
anvil/
  pyproject.toml
  lazysandbox/__init__.py
  lazysandbox/tokens.py           token registry + faucet amounts
  lazysandbox/rpc.py              anvil_command, wait_for_rpc, root .env loading
  lazysandbox/faucet.py           balance_storage_key, to_word, fund(), create_app()
  lazysandbox/sandbox.py          main(): anvil subprocess + faucet server
  scripts/seed.py, scripts/reset.py
  tests/conftest.py, tests/test_rpc.py, tests/test_faucet.py
agent/
  pyproject.toml
  lazyagent/__init__.py
  lazyagent/config.py             Settings, load_settings()
  lazyagent/tokens.py             Token, TOKENS, ETH, find_token()
  lazyagent/transfers.py          pure parsing/validation/tx building/formatting
  lazyagent/chain.py              Chain protocol + RpcChain (web3 async)
  lazyagent/proposals.py          pending approval futures
  lazyagent/tools.py              WalletContext, WalletTools, build_mcp_server, TOOL_NAMES
  lazyagent/stream.py             translate(SDK message) → outgoing WS dicts
  lazyagent/session.py            Session (one per socket)
  lazyagent/prompt.py             SYSTEM_PROMPT
  lazyagent/claude.py             connect_claude() — real ClaudeSDKClient factory
  lazyagent/server.py             create_app(), main()
  scripts/demo.py                 live end-to-end check with real Claude
  tests/conftest.py, tests/fakes.py, tests/test_*.py
apps/wallet/src/
  types.ts                        + TxRequest, ConfirmState 'expired', status 'failed'
  agent/protocol.ts               ClientMsg, ServerMsg
  agent/chatReducer.ts            pure chat state machine
  agent/useAgentChat.ts           socket lifecycle, send/approve/reject/deliver
  chain/executeTx.ts              executeTx(), statusPatch()
  chain/client.ts                 txDepsFor(mnemonic)
  chain/faucet.ts                 requestFunds(address)
  chat/cards/ConfirmCard.tsx, StatusCard.tsx, chat/MessageItem.tsx, chat/ChatView.tsx (modify)
  components/QrSheet.tsx (modify), routes/WalletPage.tsx (modify)
  chat/useChat.ts (delete)
```

---

### Task 1: Sandbox launcher (anvil package skeleton, root scripts)

**Files:**
- Create: `anvil/pyproject.toml`, `anvil/lazysandbox/__init__.py`, `anvil/lazysandbox/tokens.py`, `anvil/lazysandbox/rpc.py`, `anvil/tests/test_rpc.py`
- Create: `.env.example`
- Modify: `.gitignore`, `package.json`

**Interfaces:**
- Produces: `lazysandbox.rpc.ROOT: Path` (repo root), `load_env() -> None`, `anvil_command(fork_url: str, fork_block: str | None, port: int) -> list[str]`, `wait_for_rpc(url: str, timeout: float) -> None` (raises `TimeoutError`); `lazysandbox.tokens.Token(symbol, address, decimals, balance_slot, faucet_amount)`, `TOKENS: list[Token]`, `ETH_FAUCET_AMOUNT = 10`.

- [ ] **Step 1: Package config**

`anvil/pyproject.toml`:
```toml
[project]
name = "lazysandbox"
version = "0.1.0"
description = "LazyWallet Anvil mainnet-fork sandbox and faucet"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.143",
  "uvicorn[standard]>=0.54",
  "web3>=8.0",
  "python-dotenv>=1.2",
]

[project.scripts]
sandbox = "lazysandbox.sandbox:main"

[dependency-groups]
dev = ["pytest>=9.1", "pytest-asyncio>=1.4", "httpx>=0.28"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["lazysandbox"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```
`anvil/lazysandbox/__init__.py`: empty.

`anvil/lazysandbox/tokens.py`:
```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    symbol: str
    address: str
    decimals: int
    balance_slot: int  # storage slot of the token's balance mapping
    faucet_amount: int  # whole tokens


TOKENS = [
    Token("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6, 9, 10_000),
    Token("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7", 6, 2, 10_000),
    Token("DAI", "0x6B175474E89094C44Da98b954EedeAC495271d0F", 18, 2, 10_000),
    Token("WBTC", "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", 8, 0, 1),
    Token("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 18, 3, 5),
]

ETH_FAUCET_AMOUNT = 10
```

- [ ] **Step 2: Write failing test**

`anvil/tests/test_rpc.py`:
```python
from lazysandbox.rpc import ROOT, anvil_command


def test_root_is_repo_root():
    assert (ROOT / "pnpm-workspace.yaml").exists()


def test_anvil_command_without_block():
    assert anvil_command("https://rpc.example", None, 8545) == [
        "anvil", "--fork-url", "https://rpc.example", "--chain-id", "1", "--port", "8545",
    ]


def test_anvil_command_with_block():
    cmd = anvil_command("https://rpc.example", "21000000", 8645)
    assert cmd[-2:] == ["--fork-block-number", "21000000"]
    assert "8645" in cmd
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd anvil && uv run pytest -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lazysandbox.rpc'`.

- [ ] **Step 4: Implement**

`anvil/lazysandbox/rpc.py`:
```python
import time
from pathlib import Path

from dotenv import load_dotenv
from web3 import HTTPProvider, Web3

ROOT = Path(__file__).resolve().parents[2]


def load_env() -> None:
    load_dotenv(ROOT / ".env")


def anvil_command(fork_url: str, fork_block: str | None, port: int) -> list[str]:
    cmd = ["anvil", "--fork-url", fork_url, "--chain-id", "1", "--port", str(port)]
    if fork_block:
        cmd += ["--fork-block-number", fork_block]
    return cmd


def wait_for_rpc(url: str, timeout: float) -> None:
    w3 = Web3(HTTPProvider(url))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if w3.eth.chain_id == 1:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Anvil at {url} did not become ready within {timeout:.0f}s")
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd anvil && uv run pytest -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Root config**

`.env.example`:
```
# Ethereum mainnet archive RPC used by the Anvil fork (required)
ETH_RPC_URL=
# Optional: pin the fork block for reproducible demos
FORK_BLOCK=
# Optional: agent model (default claude-sonnet-5-5). Auth uses your Claude Code login.
AGENT_MODEL=
```

Append to `.gitignore`:
```
.venv
__pycache__
.pytest_cache
anvil/.test-wallet.json
```

Add to root `package.json` scripts:
```json
"dev:sandbox": "uv run --directory anvil sandbox",
"dev:agent": "uv run --directory agent agent",
"test:py": "uv run --directory anvil pytest -q && uv run --directory agent pytest -q"
```

- [ ] **Step 7: Commit**

```bash
git add anvil .env.example .gitignore package.json
git commit -m "feat(anvil): add sandbox package skeleton and fork command"
```

---

### Task 2: Faucet, sandbox entrypoint, seed/reset scripts

**Files:**
- Create: `anvil/lazysandbox/faucet.py`, `anvil/lazysandbox/sandbox.py`, `anvil/scripts/seed.py`, `anvil/scripts/reset.py`
- Test: `anvil/tests/conftest.py`, `anvil/tests/test_faucet.py`

**Interfaces:**
- Consumes: Task 1 `TOKENS`, `ETH_FAUCET_AMOUNT`, `anvil_command`, `wait_for_rpc`, `load_env`, `ROOT`
- Produces: `balance_storage_key(holder: str, slot: int) -> str`, `to_word(value: int) -> str`, `async fund(w3: AsyncWeb3, address: str) -> dict[str, int]` (symbol → base units), `summarize(funded: dict[str, int]) -> str`, `create_app(rpc_url: str, allowed_origins: list[str]) -> FastAPI` with `POST /fund {"address"}` → `{"funded": {symbol: str(base units)}, "summary": str}` and `GET /health`.

- [ ] **Step 1: Write failing tests**

`anvil/tests/conftest.py`:
```python
import os
import subprocess

import pytest

from lazysandbox.rpc import anvil_command, load_env, wait_for_rpc

TEST_PORT = 8645


@pytest.fixture(scope="session")
def fork_rpc():
    load_env()
    url = os.environ.get("ETH_RPC_URL")
    if not url:
        pytest.skip("ETH_RPC_URL not set")
    proc = subprocess.Popen(
        anvil_command(url, os.environ.get("FORK_BLOCK") or None, TEST_PORT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    rpc = f"http://127.0.0.1:{TEST_PORT}"
    try:
        wait_for_rpc(rpc, 120)
        yield rpc
    finally:
        proc.terminate()
        proc.wait()
```

`anvil/tests/test_faucet.py`:
```python
from eth_abi import encode
from eth_account import Account
from fastapi.testclient import TestClient
from web3 import AsyncHTTPProvider, AsyncWeb3, Web3

from lazysandbox.faucet import balance_storage_key, create_app, fund, summarize, to_word
from lazysandbox.tokens import TOKENS

HOLDER = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"


def test_balance_storage_key_is_keccak_of_abi_encoded_holder_and_slot():
    expected = Web3.keccak(encode(["address", "uint256"], [HOLDER, 9])).to_0x_hex()
    assert balance_storage_key(HOLDER, 9) == expected


def test_to_word_pads_to_32_bytes():
    assert to_word(1) == "0x" + "00" * 31 + "01"


def test_summarize_formats_whole_tokens():
    funded = {"ETH": 10 * 10**18, "USDC": 10_000 * 10**6, "WBTC": 1 * 10**8}
    assert summarize(funded) == "10 ETH, 10,000 USDC, 1 WBTC"


def test_fund_rejects_invalid_address():
    client = TestClient(create_app("http://127.0.0.1:1", ["http://localhost:5174"]))
    res = client.post("/fund", json={"address": "nope"})
    assert res.status_code == 400


async def test_fund_sets_eth_and_token_balances(fork_rpc):
    w3 = AsyncWeb3(AsyncHTTPProvider(fork_rpc))
    address = Account.create().address
    funded = await fund(w3, address)
    assert funded["ETH"] == 10 * 10**18
    assert await w3.eth.get_balance(address) == 10 * 10**18
    for t in TOKENS:
        assert funded[t.symbol] == t.faucet_amount * 10**t.decimals
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd anvil && uv run pytest -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lazysandbox.faucet'`.

- [ ] **Step 3: Implement faucet**

`anvil/lazysandbox/faucet.py`:
```python
from eth_abi import encode
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from web3 import AsyncHTTPProvider, AsyncWeb3, Web3

from .tokens import ETH_FAUCET_AMOUNT, TOKENS

ERC20_BALANCE_OF = [
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "owner", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    }
]
DECIMALS = {"ETH": 18, **{t.symbol: t.decimals for t in TOKENS}}


def balance_storage_key(holder: str, slot: int) -> str:
    """Storage key of balances[holder] for a Solidity mapping declared at `slot`."""
    return Web3.keccak(encode(["address", "uint256"], [holder, slot])).to_0x_hex()


def to_word(value: int) -> str:
    return "0x" + value.to_bytes(32, "big").hex()


async def _rpc(w3: AsyncWeb3, method: str, params: list) -> None:
    res = await w3.provider.make_request(method, params)
    if "error" in res:
        raise RuntimeError(f"{method} failed: {res['error']}")


async def fund(w3: AsyncWeb3, address: str) -> dict[str, int]:
    holder = Web3.to_checksum_address(address)
    eth = ETH_FAUCET_AMOUNT * 10**18
    await _rpc(w3, "anvil_setBalance", [holder, hex(eth)])
    funded = {"ETH": eth}
    for t in TOKENS:
        amount = t.faucet_amount * 10**t.decimals
        await _rpc(w3, "anvil_setStorageAt", [t.address, balance_storage_key(holder, t.balance_slot), to_word(amount)])
        contract = w3.eth.contract(address=Web3.to_checksum_address(t.address), abi=ERC20_BALANCE_OF)
        actual = await contract.functions.balanceOf(holder).call()
        if actual != amount:
            raise RuntimeError(f"{t.symbol} balance slot {t.balance_slot} is wrong: balanceOf={actual}, expected {amount}")
        funded[t.symbol] = amount
    return funded


def summarize(funded: dict[str, int]) -> str:
    return ", ".join(f"{amount // 10 ** DECIMALS[symbol]:,} {symbol}" for symbol, amount in funded.items())


class FundRequest(BaseModel):
    address: str


def create_app(rpc_url: str, allowed_origins: list[str]) -> FastAPI:
    app = FastAPI(title="LazyWallet Sandbox Faucet")
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_methods=["*"], allow_headers=["*"])
    w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    @app.post("/fund")
    async def post_fund(req: FundRequest) -> dict:
        if not Web3.is_address(req.address):
            raise HTTPException(status_code=400, detail="Invalid address")
        try:
            funded = await fund(w3, req.address)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Sandbox chain error: {e}") from e
        return {"funded": {k: str(v) for k, v in funded.items()}, "summary": summarize(funded)}

    return app
```

- [ ] **Step 4: Run tests**

Run: `cd anvil && uv run pytest -q`
Expected: PASS for the 4 unit tests; `test_fund_sets_eth_and_token_balances` PASS if `ETH_RPC_URL` is set, otherwise SKIPPED. If a token's slot is wrong the test fails naming the token — fix that token's `balance_slot` in `tokens.py` (and the matching Global Constraints line) and re-run.

- [ ] **Step 5: Sandbox entrypoint and scripts**

`anvil/lazysandbox/sandbox.py`:
```python
import os
import subprocess
import sys

import uvicorn

from .faucet import create_app
from .rpc import anvil_command, load_env, wait_for_rpc

ANVIL_PORT = 8545
FAUCET_PORT = 8547


def main() -> None:
    load_env()
    fork_url = os.environ.get("ETH_RPC_URL")
    if not fork_url:
        sys.exit("ETH_RPC_URL is missing — add a mainnet archive RPC to .env (see .env.example).")
    origins = os.environ.get("WALLET_ORIGINS", "http://localhost:5174").split(",")
    proc = subprocess.Popen(anvil_command(fork_url, os.environ.get("FORK_BLOCK") or None, ANVIL_PORT))
    rpc = f"http://127.0.0.1:{ANVIL_PORT}"
    try:
        wait_for_rpc(rpc, 120)
        print(f"Sandbox ready: Anvil fork {rpc} (chain id 1), faucet http://127.0.0.1:{FAUCET_PORT}")
        uvicorn.run(create_app(rpc, origins), host="127.0.0.1", port=FAUCET_PORT)
    finally:
        proc.terminate()
        proc.wait()
```

`anvil/scripts/seed.py`:
```python
"""Create a fresh random test wallet on the running sandbox and fund it.

Usage: uv run --directory anvil python scripts/seed.py
Writes anvil/.test-wallet.json (gitignored).
"""

import asyncio
import json

from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3

from lazysandbox.faucet import fund, summarize
from lazysandbox.rpc import ROOT

RPC = "http://127.0.0.1:8545"


async def main() -> None:
    account = Account.create()
    funded = await fund(AsyncWeb3(AsyncHTTPProvider(RPC)), account.address)
    out = ROOT / "anvil" / ".test-wallet.json"
    out.write_text(json.dumps({"address": account.address, "private_key": account.key.to_0x_hex()}, indent=2))
    print(f"Test wallet {account.address} funded with {summarize(funded)} → {out}")


if __name__ == "__main__":
    asyncio.run(main())
```

`anvil/scripts/reset.py`:
```python
"""Reset the running sandbox back to the mainnet fork (drops all local transactions).

Usage: uv run --directory anvil python scripts/reset.py
"""

import os

from web3 import HTTPProvider, Web3

from lazysandbox.rpc import load_env

RPC = "http://127.0.0.1:8545"


def main() -> None:
    load_env()
    forking = {"jsonRpcUrl": os.environ["ETH_RPC_URL"]}
    if os.environ.get("FORK_BLOCK"):
        forking["blockNumber"] = int(os.environ["FORK_BLOCK"])
    res = Web3(HTTPProvider(RPC)).provider.make_request("anvil_reset", [{"forking": forking}])
    if "error" in res:
        raise SystemExit(f"Reset failed: {res['error']}")
    print("Sandbox reset to fork.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Verify**

Run: `cd anvil && uv run pytest -q` → pass/skip as in Step 4.
Run (only if `ETH_RPC_URL` is set): `pnpm dev:sandbox` in one terminal; in another `curl -s -X POST localhost:8547/fund -H 'content-type: application/json' -d '{"address":"0x70997970C51812dc3A010C7d01b50e0d17dc79C8"}'`
Expected: JSON with `"summary": "10 ETH, 10,000 USDC, 10,000 USDT, 10,000 DAI, 1 WBTC, 5 WETH"`. Then `uv run --directory anvil python scripts/seed.py` prints a funded test wallet. Stop the sandbox.

- [ ] **Step 7: Commit**

```bash
git add anvil
git commit -m "feat(anvil): add faucet, sandbox launcher, seed and reset scripts"
```

---

### Task 3: Agent package — tokens and transfer rules (pure)

**Files:**
- Create: `agent/pyproject.toml`, `agent/lazyagent/__init__.py`, `agent/lazyagent/tokens.py`, `agent/lazyagent/transfers.py`
- Test: `agent/tests/test_transfers.py`

**Interfaces:**
- Produces:
  - `tokens.Token(symbol: str, address: str | None, decimals: int, price_feed: str | None, fixed_price: float | None)`; `ETH: Token` (address None); `TOKENS: list[Token]` (ETH first); `find_token(symbol: str) -> Token | None`; `ETH_USD_FEED`, `BTC_USD_FEED`.
  - `transfers.TransferError(Exception)`; `parse_amount(text: str, decimals: int) -> int`; `format_units(amount: int, decimals: int) -> str`; `short(address: str) -> str`; `format_usd(value: float) -> str`; `resolve_recipient(name_or_address: str, contacts: list[dict]) -> tuple[str, str | None]`; `gas_units(token: Token) -> int`; `validate(token: Token, amount: int, balance: int, eth_balance: int, gas_cost: int) -> None`; `build_request(token: Token, to: str, amount: int) -> dict` (`{"to", "value": str, "data"}`); `display_rows(token, amount, to, name, price, gas_cost, eth_price) -> list[dict]`.

- [ ] **Step 1: Package config**

`agent/pyproject.toml`:
```toml
[project]
name = "lazyagent"
version = "0.1.0"
description = "LazyWallet voice AI agent (Claude Agent SDK)"
requires-python = ">=3.12"
dependencies = [
  "claude-agent-sdk>=0.2.166",
  "fastapi>=0.143",
  "uvicorn[standard]>=0.54",
  "web3>=8.0",
  "python-dotenv>=1.2",
]

[project.scripts]
agent = "lazyagent.server:main"

[dependency-groups]
dev = ["pytest>=9.1", "pytest-asyncio>=1.4", "httpx>=0.28"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["lazyagent"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```
`agent/lazyagent/__init__.py`: empty.

`agent/lazyagent/tokens.py`:
```python
from dataclasses import dataclass

ETH_USD_FEED = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
BTC_USD_FEED = "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c"


@dataclass(frozen=True)
class Token:
    symbol: str
    address: str | None  # None = native ETH
    decimals: int
    price_feed: str | None = None
    fixed_price: float | None = None


ETH = Token("ETH", None, 18, price_feed=ETH_USD_FEED)

TOKENS = [
    ETH,
    Token("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6, fixed_price=1.0),
    Token("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7", 6, fixed_price=1.0),
    Token("DAI", "0x6B175474E89094C44Da98b954EedeAC495271d0F", 18, fixed_price=1.0),
    Token("WBTC", "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", 8, price_feed=BTC_USD_FEED),
    Token("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 18, price_feed=ETH_USD_FEED),
]


def find_token(symbol: str) -> Token | None:
    s = symbol.strip().upper()
    return next((t for t in TOKENS if t.symbol == s), None)
```

- [ ] **Step 2: Write failing tests**

`agent/tests/test_transfers.py`:
```python
import pytest

from lazyagent.tokens import ETH, find_token
from lazyagent.transfers import (
    TransferError,
    build_request,
    display_rows,
    format_units,
    parse_amount,
    resolve_recipient,
    validate,
)

USDC = find_token("usdc")
ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
CONTACTS = [{"name": "Alice", "address": ALICE}]


@pytest.mark.parametrize(
    ("text", "decimals", "expected"),
    [("0.1", 18, 10**17), (".5", 18, 5 * 10**17), ("1,000", 6, 10**9), ("  2 ", 8, 2 * 10**8), ("1.5", 6, 1_500_000)],
)
def test_parse_amount_valid(text, decimals, expected):
    assert parse_amount(text, decimals) == expected


@pytest.mark.parametrize("text", ["0", "0.000", "-1", "1e18", "abc", "", "1.2.3"])
def test_parse_amount_invalid(text):
    with pytest.raises(TransferError):
        parse_amount(text, 18)


def test_parse_amount_too_many_decimals():
    with pytest.raises(TransferError, match="6 decimal places"):
        parse_amount("0.0000001", 6)


def test_format_units():
    assert format_units(10 * 10**18, 18) == "10"
    assert format_units(1_500_000, 6) == "1.5"
    assert format_units(0, 18) == "0"


def test_resolve_recipient_by_name_case_insensitive():
    assert resolve_recipient("alice", CONTACTS) == (ALICE, "Alice")


def test_resolve_recipient_by_address_checksums():
    assert resolve_recipient(ALICE.lower(), CONTACTS) == (ALICE, "Alice")
    other = "0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc"
    assert resolve_recipient(other, []) == ("0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC", None)


def test_resolve_recipient_unknown():
    with pytest.raises(TransferError, match="address book"):
        resolve_recipient("charlie", CONTACTS)


def test_validate_eth_over_balance():
    with pytest.raises(TransferError, match="only have 1 ETH"):
        validate(ETH, 2 * 10**18, 10**18, 10**18, 21_000 * 10**9)


def test_validate_eth_whole_balance_leaves_no_gas():
    with pytest.raises(TransferError, match="network fee"):
        validate(ETH, 10**18, 10**18, 10**18, 21_000 * 10**9)


def test_validate_token_over_balance():
    with pytest.raises(TransferError, match="only have 5 USDC"):
        validate(USDC, 6 * 10**6, 5 * 10**6, 10**18, 10**14)


def test_validate_token_needs_eth_for_gas():
    with pytest.raises(TransferError, match="ETH for the network fee"):
        validate(USDC, 10**6, 5 * 10**6, 0, 10**14)


def test_validate_ok():
    validate(ETH, 10**17, 10**18, 10**18, 21_000 * 10**9)
    validate(USDC, 10**6, 5 * 10**6, 10**18, 10**14)


def test_build_request_eth():
    assert build_request(ETH, ALICE, 10**17) == {"to": ALICE, "value": str(10**17), "data": "0x"}


def test_build_request_erc20_transfer_calldata():
    req = build_request(USDC, ALICE, 1_500_000)
    assert req["to"] == USDC.address
    assert req["value"] == "0"
    assert req["data"] == (
        "0xa9059cbb"
        + "00000000000000000000000070997970c51812dc3a010c7d01b50e0d17dc79c8"
        + "000000000000000000000000000000000000000000000000000000000016e360"
    )


def test_display_rows():
    rows = display_rows(ETH, 10**17, ALICE, "Alice", 3200.0, 21_000 * 10**9, 3200.0)
    assert rows == [
        {"label": "To", "value": "Alice (0x7099…79C8)"},
        {"label": "Amount", "value": "0.1 ETH ($320.00)"},
        {"label": "Network fee", "value": "~$0.07"},
        {"label": "Network", "value": "Sandbox"},
    ]
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd agent && uv run pytest -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lazyagent.transfers'`.

- [ ] **Step 4: Implement**

`agent/lazyagent/transfers.py`:
```python
import re
from decimal import Decimal

from eth_abi import encode
from web3 import Web3

from .tokens import Token

ERC20_TRANSFER_SELECTOR = "a9059cbb"
_AMOUNT = re.compile(r"^\d*\.?\d+$")


class TransferError(Exception):
    """A user-facing reason a transfer can't be proposed."""


def parse_amount(text: str, decimals: int) -> int:
    cleaned = text.strip().replace(",", "")
    if not _AMOUNT.match(cleaned):
        raise TransferError(f'"{text}" isn\'t a valid amount.')
    value = Decimal(cleaned)
    if value <= 0:
        raise TransferError("The amount needs to be more than 0.")
    base = value.scaleb(decimals)
    if base != base.to_integral_value():
        raise TransferError(f"That token supports at most {decimals} decimal places.")
    return int(base)


def format_units(amount: int, decimals: int) -> str:
    return format(Decimal(amount).scaleb(-decimals).normalize(), "f")


def short(address: str) -> str:
    return f"{address[:6]}…{address[-4:]}"


def format_usd(value: float) -> str:
    return f"${value:,.2f}"


def resolve_recipient(name_or_address: str, contacts: list[dict]) -> tuple[str, str | None]:
    query = name_or_address.strip()
    for c in contacts:
        if c.get("name", "").lower() == query.lower():
            return Web3.to_checksum_address(c["address"]), c["name"]
    if Web3.is_address(query):
        address = Web3.to_checksum_address(query)
        name = next((c["name"] for c in contacts if c.get("address", "").lower() == address.lower()), None)
        return address, name
    raise TransferError(f'I don\'t know "{query}" yet. Add them in the address book, then try again.')


def gas_units(token: Token) -> int:
    return 21_000 if token.address is None else 100_000


def validate(token: Token, amount: int, balance: int, eth_balance: int, gas_cost: int) -> None:
    have = f"{format_units(balance, token.decimals)} {token.symbol}"
    if amount > balance:
        raise TransferError(f"You only have {have}.")
    if token.address is None:
        if amount + gas_cost > eth_balance:
            raise TransferError(
                f"That leaves nothing for the network fee (~{format_units(gas_cost, 18)} ETH). Try a slightly smaller amount."
            )
    elif gas_cost > eth_balance:
        raise TransferError("You need a little ETH for the network fee. Get test funds from the Receive screen.")


def build_request(token: Token, to: str, amount: int) -> dict:
    if token.address is None:
        return {"to": to, "value": str(amount), "data": "0x"}
    calldata = ERC20_TRANSFER_SELECTOR + encode(["address", "uint256"], [to, amount]).hex()
    return {"to": token.address, "value": "0", "data": "0x" + calldata}


def display_rows(
    token: Token, amount: int, to: str, name: str | None, price: float, gas_cost: int, eth_price: float
) -> list[dict]:
    human = format_units(amount, token.decimals)
    usd = float(Decimal(amount).scaleb(-token.decimals)) * price
    fee = float(Decimal(gas_cost).scaleb(-18)) * eth_price
    return [
        {"label": "To", "value": f"{name} ({short(to)})" if name else short(to)},
        {"label": "Amount", "value": f"{human} {token.symbol} ({format_usd(usd)})"},
        {"label": "Network fee", "value": f"~{format_usd(fee)}"},
        {"label": "Network", "value": "Sandbox"},
    ]
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd agent && uv run pytest -q`
Expected: PASS (all transfer tests).

- [ ] **Step 6: Commit**

```bash
git add agent
git commit -m "feat(agent): add token registry and transfer rules"
```

---

### Task 4: Chain access (web3, read-only)

**Files:**
- Create: `agent/lazyagent/config.py`, `agent/lazyagent/chain.py`
- Test: `agent/tests/conftest.py`, `agent/tests/test_chain.py`, `agent/tests/test_config.py`

**Interfaces:**
- Consumes: Task 3 `Token`, `ETH`, `find_token`
- Produces:
  - `config.ROOT: Path`, `config.Settings(rpc_url: str, model: str, allowed_origins: tuple[str, ...], port: int)`, `config.load_settings() -> Settings`
  - `chain.Chain` (Protocol): `async eth_balance(address) -> int`, `async token_balance(token, address) -> int`, `async price_usd(token) -> float`, `async gas_price() -> int`
  - `chain.RpcChain(rpc_url: str)` implementing `Chain`

- [ ] **Step 1: Write failing tests**

`agent/tests/test_config.py`:
```python
from lazyagent.config import ROOT, load_settings


def test_defaults(monkeypatch):
    monkeypatch.setattr("lazyagent.config.load_dotenv", lambda *a, **k: None)
    for key in ("SANDBOX_RPC_URL", "AGENT_MODEL", "WALLET_ORIGINS", "AGENT_PORT"):
        monkeypatch.delenv(key, raising=False)
    s = load_settings()
    assert s.rpc_url == "http://127.0.0.1:8545"
    assert s.model == "claude-sonnet-5-5"
    assert s.allowed_origins == ("http://localhost:5174",)
    assert s.port == 8787


def test_empty_model_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("AGENT_MODEL", "")
    assert load_settings().model == "claude-sonnet-5-5"


def test_root_is_repo_root():
    assert (ROOT / "pnpm-workspace.yaml").exists()
```

`agent/tests/conftest.py`:
```python
import os
import subprocess
import time

import pytest
from web3 import HTTPProvider, Web3

from lazyagent.config import ROOT

TEST_PORT = 8646


@pytest.fixture(scope="session")
def fork_rpc():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    url = os.environ.get("ETH_RPC_URL")
    if not url:
        pytest.skip("ETH_RPC_URL not set")
    cmd = ["anvil", "--fork-url", url, "--chain-id", "1", "--port", str(TEST_PORT)]
    if os.environ.get("FORK_BLOCK"):
        cmd += ["--fork-block-number", os.environ["FORK_BLOCK"]]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = f"http://127.0.0.1:{TEST_PORT}"
    w3 = Web3(HTTPProvider(rpc))
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                if w3.eth.chain_id == 1:
                    break
            except Exception:
                time.sleep(0.5)
        else:
            raise TimeoutError("test fork did not start")
        yield rpc
    finally:
        proc.terminate()
        proc.wait()
```

`agent/tests/test_chain.py`:
```python
from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3

from lazyagent.chain import RpcChain
from lazyagent.tokens import ETH, find_token


async def test_balances_prices_and_gas(fork_rpc):
    chain = RpcChain(fork_rpc)
    address = Account.create().address
    w3 = AsyncWeb3(AsyncHTTPProvider(fork_rpc))
    await w3.provider.make_request("anvil_setBalance", [address, hex(3 * 10**18)])

    assert await chain.eth_balance(address) == 3 * 10**18
    assert await chain.token_balance(find_token("USDC"), address) == 0
    assert 100 < await chain.price_usd(ETH) < 100_000
    assert 1_000 < await chain.price_usd(find_token("WBTC")) < 1_000_000
    assert await chain.price_usd(find_token("DAI")) == 1.0
    assert await chain.gas_price() > 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd agent && uv run pytest -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lazyagent.config'`.

- [ ] **Step 3: Implement**

`agent/lazyagent/config.py`:
```python
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "claude-sonnet-5-5"


@dataclass(frozen=True)
class Settings:
    rpc_url: str
    model: str
    allowed_origins: tuple[str, ...]
    port: int


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    return Settings(
        rpc_url=os.environ.get("SANDBOX_RPC_URL") or "http://127.0.0.1:8545",
        model=os.environ.get("AGENT_MODEL") or DEFAULT_MODEL,
        allowed_origins=tuple((os.environ.get("WALLET_ORIGINS") or "http://localhost:5174").split(",")),
        port=int(os.environ.get("AGENT_PORT") or 8787),
    )
```
`test_defaults` patches `load_dotenv` out so a developer's own `.env` can't change the defaults it checks.

`agent/lazyagent/chain.py`:
```python
from typing import Protocol

from web3 import AsyncHTTPProvider, AsyncWeb3, Web3

from .tokens import Token

ERC20_ABI = [
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "owner", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    }
]
AGGREGATOR_ABI = [
    {
        "name": "latestRoundData",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [
            {"name": "roundId", "type": "uint80"},
            {"name": "answer", "type": "int256"},
            {"name": "startedAt", "type": "uint256"},
            {"name": "updatedAt", "type": "uint256"},
            {"name": "answeredInRound", "type": "uint80"},
        ],
    }
]
FEED_DECIMALS = 8


class Chain(Protocol):
    async def eth_balance(self, address: str) -> int: ...
    async def token_balance(self, token: Token, address: str) -> int: ...
    async def price_usd(self, token: Token) -> float: ...
    async def gas_price(self) -> int: ...


class RpcChain:
    def __init__(self, rpc_url: str):
        self.w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))

    async def eth_balance(self, address: str) -> int:
        return await self.w3.eth.get_balance(Web3.to_checksum_address(address))

    async def token_balance(self, token: Token, address: str) -> int:
        contract = self.w3.eth.contract(address=Web3.to_checksum_address(token.address), abi=ERC20_ABI)
        return await contract.functions.balanceOf(Web3.to_checksum_address(address)).call()

    async def price_usd(self, token: Token) -> float:
        if token.fixed_price is not None:
            return token.fixed_price
        feed = self.w3.eth.contract(address=Web3.to_checksum_address(token.price_feed), abi=AGGREGATOR_ABI)
        _, answer, _, _, _ = await feed.functions.latestRoundData().call()
        return answer / 10**FEED_DECIMALS

    async def gas_price(self) -> int:
        return await self.w3.eth.gas_price
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd agent && uv run pytest -q`
Expected: PASS (config + transfers); `test_balances_prices_and_gas` PASS with `ETH_RPC_URL`, otherwise SKIPPED.

- [ ] **Step 5: Commit**

```bash
git add agent
git commit -m "feat(agent): add settings and read-only chain access"
```

---

### Task 5: Proposals and wallet tools

**Files:**
- Create: `agent/lazyagent/proposals.py`, `agent/lazyagent/tools.py`
- Test: `agent/tests/fakes.py`, `agent/tests/test_proposals.py`, `agent/tests/test_tools.py`

**Interfaces:**
- Consumes: Task 3 transfers/tokens, Task 4 `Chain`
- Produces:
  - `proposals.Proposals`: `new() -> tuple[str, asyncio.Future]` (ids `p1`, `p2`, …), `resolve(id: str, result: dict) -> bool`, `async wait(id: str, fut, timeout: float) -> dict | None` (None on timeout), `cancel_all() -> None`
  - `tools.Send = Callable[[dict], Awaitable[None]]`; `tools.WalletContext(address: str | None = None, contacts: list[dict] = [])`; `tools.WalletTools(chain, send, ctx, proposals, approval_timeout: float = 300)` with async methods `get_balances(args)`, `resolve_recipient(args)`, `propose_transfer(args)`, `unsupported_action(args)` each returning an MCP result dict `{"content": [{"type": "text", "text": str}], "is_error"?: True}`; `tools.TOOL_NAMES: list[str]`; `tools.build_mcp_server(t: WalletTools)`.

- [ ] **Step 1: Write failing tests**

`agent/tests/fakes.py`:
```python
from lazyagent.tokens import Token

PRICES = {"ETH": 3200.0, "WETH": 3200.0, "WBTC": 64000.0}


class FakeChain:
    def __init__(self, eth: int = 10 * 10**18, tokens: dict[str, int] | None = None, gas_price: int = 10**9):
        self.eth = eth
        self.tokens = tokens or {}
        self.gp = gas_price
        self.fail = False

    async def eth_balance(self, address: str) -> int:
        if self.fail:
            raise ConnectionError("connection refused")
        return self.eth

    async def token_balance(self, token: Token, address: str) -> int:
        return self.tokens.get(token.symbol, 0)

    async def price_usd(self, token: Token) -> float:
        return PRICES.get(token.symbol, 1.0)

    async def gas_price(self) -> int:
        return self.gp


class Outbox:
    def __init__(self):
        self.messages: list[dict] = []

    async def __call__(self, msg: dict) -> None:
        self.messages.append(msg)

    def of_type(self, kind: str) -> list[dict]:
        return [m for m in self.messages if m["type"] == kind]
```

`agent/tests/test_proposals.py`:
```python
import asyncio

import pytest

from lazyagent.proposals import Proposals


async def test_resolve_delivers_result():
    p = Proposals()
    pid, fut = p.new()
    assert pid == "p1"
    asyncio.get_running_loop().call_soon(p.resolve, pid, {"outcome": "approved"})
    assert await p.wait(pid, fut, 1) == {"outcome": "approved"}


async def test_wait_times_out_with_none():
    p = Proposals()
    pid, fut = p.new()
    assert await p.wait(pid, fut, 0.01) is None
    assert p.resolve(pid, {"outcome": "approved"}) is False


async def test_unknown_id_is_ignored():
    assert Proposals().resolve("p9", {}) is False


async def test_cancel_all_cancels_waiters():
    p = Proposals()
    pid, fut = p.new()
    task = asyncio.create_task(p.wait(pid, fut, 5))
    await asyncio.sleep(0)
    p.cancel_all()
    with pytest.raises(asyncio.CancelledError):
        await task
```

`agent/tests/test_tools.py`:
```python
import asyncio

from fakes import FakeChain, Outbox

from lazyagent.proposals import Proposals
from lazyagent.tools import TOOL_NAMES, WalletContext, WalletTools, build_mcp_server

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"


def make(chain=None, timeout=5.0):
    out = Outbox()
    ctx = WalletContext(address=ME, contacts=[{"name": "Alice", "address": ALICE}])
    proposals = Proposals()
    tools = WalletTools(chain or FakeChain(tokens={"USDC": 500 * 10**6}), out, ctx, proposals, approval_timeout=timeout)
    return tools, out, proposals


def text(result):
    return result["content"][0]["text"]


async def wait_for_confirm(out):
    for _ in range(100):
        if out.of_type("confirm"):
            return out.of_type("confirm")[0]
        await asyncio.sleep(0)
    raise AssertionError("no confirm sent")


async def test_get_balances_emits_card_and_summary():
    tools, out, _ = make()
    result = await tools.get_balances({})
    [card] = out.of_type("balances")
    assert card["holdings"] == [
        {"symbol": "ETH", "amount": 10.0, "usdPrice": 3200.0},
        {"symbol": "USDC", "amount": 500.0, "usdPrice": 1.0},
    ]
    assert "ETH 10 ($32,000.00)" in text(result)
    assert "Total $32,500.00" in text(result)


async def test_get_balances_without_address_is_error():
    tools, _, _ = make()
    tools.ctx.address = None
    assert (await tools.get_balances({}))["is_error"] is True


async def test_resolve_recipient():
    tools, _, _ = make()
    assert ALICE in text(await tools.resolve_recipient({"name_or_address": "alice"}))
    assert (await tools.resolve_recipient({"name_or_address": "bob"}))["is_error"] is True


async def test_propose_transfer_approved_flow():
    tools, out, proposals = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "ETH", "amount": "0.1", "to": "Alice"}))
    confirm = await wait_for_confirm(out)
    assert confirm["tx"]["title"] == "Send 0.1 ETH"
    assert confirm["tx"]["request"] == {"to": ALICE, "value": str(10**17), "data": "0x"}
    proposals.resolve(confirm["id"], {"outcome": "approved", "hash": "0xabc", "status": "success"})
    result = await task
    assert "Sent 0.1 ETH to Alice" in text(result)
    assert "0xabc" in text(result)


async def test_propose_transfer_rejected():
    tools, out, proposals = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "USDC", "amount": "10", "to": ALICE}))
    confirm = await wait_for_confirm(out)
    proposals.resolve(confirm["id"], {"outcome": "rejected"})
    assert "rejected" in text(await task)


async def test_propose_transfer_reverted_and_send_error():
    tools, out, proposals = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "ETH", "amount": "1", "to": "Alice"}))
    confirm = await wait_for_confirm(out)
    proposals.resolve(confirm["id"], {"outcome": "approved", "hash": "0xdef", "status": "reverted"})
    assert "reverted" in text(await task)

    tools, out, proposals = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "ETH", "amount": "1", "to": "Alice"}))
    confirm = await wait_for_confirm(out)
    proposals.resolve(confirm["id"], {"outcome": "approved", "error": "insufficient funds"})
    assert "insufficient funds" in text(await task)


async def test_propose_transfer_timeout():
    tools, out, _ = make(timeout=0.01)
    result = await tools.propose_transfer({"token": "ETH", "amount": "0.1", "to": "Alice"})
    assert out.of_type("confirm")
    assert "didn't respond" in text(result)


async def test_propose_transfer_validation_errors_send_no_card():
    cases = [
        ({"token": "DOGE", "amount": "1", "to": "Alice"}, "ETH, USDC"),
        ({"token": "ETH", "amount": "0", "to": "Alice"}, "more than 0"),
        ({"token": "ETH", "amount": "1", "to": "charlie"}, "address book"),
        ({"token": "ETH", "amount": "10", "to": "Alice"}, "network fee"),
        ({"token": "USDC", "amount": "501", "to": "Alice"}, "only have 500 USDC"),
    ]
    for args, fragment in cases:
        tools, out, _ = make()
        result = await tools.propose_transfer(args)
        assert result["is_error"] is True, args
        assert fragment in text(result), (args, text(result))
        assert not out.of_type("confirm")


async def test_propose_transfer_chain_unreachable():
    chain = FakeChain()
    chain.fail = True
    tools, out, _ = make(chain=chain)
    result = await tools.propose_transfer({"token": "ETH", "amount": "0.1", "to": "Alice"})
    assert result["is_error"] is True
    assert "Sandbox chain" in text(result)


async def test_unsupported_action():
    tools, _, _ = make()
    assert "coming soon" in text(await tools.unsupported_action({"action": "swap"})).lower()


def test_mcp_server_and_names():
    tools, _, _ = make()
    assert build_mcp_server(tools)["name"] == "wallet"
    assert TOOL_NAMES == [
        "mcp__wallet__get_balances",
        "mcp__wallet__resolve_recipient",
        "mcp__wallet__propose_transfer",
        "mcp__wallet__unsupported_action",
    ]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd agent && uv run pytest -q`
Expected: FAIL — `ModuleNotFoundError` for `lazyagent.proposals` / `lazyagent.tools`.

- [ ] **Step 3: Implement**

`agent/lazyagent/proposals.py`:
```python
import asyncio


class Proposals:
    """Transfers waiting for the user's Approve/Reject in the browser."""

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future] = {}
        self._seq = 0

    def new(self) -> tuple[str, asyncio.Future]:
        self._seq += 1
        pid = f"p{self._seq}"
        fut = asyncio.get_running_loop().create_future()
        self._pending[pid] = fut
        return pid, fut

    def resolve(self, pid: str, result: dict) -> bool:
        fut = self._pending.get(pid)
        if fut is None or fut.done():
            return False
        fut.set_result(result)
        return True

    async def wait(self, pid: str, fut: asyncio.Future, timeout: float) -> dict | None:
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout)
        except TimeoutError:
            return None
        finally:
            self._pending.pop(pid, None)

    def cancel_all(self) -> None:
        for fut in self._pending.values():
            fut.cancel()
        self._pending.clear()
```

`agent/lazyagent/tools.py`:
```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal

from claude_agent_sdk import create_sdk_mcp_server, tool

from .chain import Chain
from .proposals import Proposals
from .tokens import ETH, TOKENS, find_token
from .transfers import (
    TransferError,
    build_request,
    display_rows,
    format_units,
    format_usd,
    gas_units,
    parse_amount,
    resolve_recipient,
    short,
    validate,
)

Send = Callable[[dict], Awaitable[None]]
SERVER_NAME = "wallet"
TOOL_NAMES = [
    f"mcp__{SERVER_NAME}__{n}" for n in ("get_balances", "resolve_recipient", "propose_transfer", "unsupported_action")
]
SUPPORTED = ", ".join(t.symbol for t in TOKENS)


def ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


@dataclass
class WalletContext:
    address: str | None = None
    contacts: list[dict] = field(default_factory=list)


class WalletTools:
    def __init__(self, chain: Chain, send: Send, ctx: WalletContext, proposals: Proposals, approval_timeout: float = 300):
        self.chain = chain
        self.send = send
        self.ctx = ctx
        self.proposals = proposals
        self.approval_timeout = approval_timeout

    async def get_balances(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        try:
            holdings = []
            for t in TOKENS:
                raw = await (self.chain.eth_balance(self.ctx.address) if t.address is None else self.chain.token_balance(t, self.ctx.address))
                if raw == 0 and t is not ETH:
                    continue
                holdings.append({"symbol": t.symbol, "amount": float(Decimal(raw).scaleb(-t.decimals)), "usdPrice": await self.chain.price_usd(t), "raw": raw, "decimals": t.decimals})
        except Exception as e:
            return err(f"The Sandbox chain isn't reachable right now ({e}).")
        await self.send({"type": "balances", "holdings": [{k: h[k] for k in ("symbol", "amount", "usdPrice")} for h in holdings]})
        parts = [f"{h['symbol']} {format_units(h['raw'], h['decimals'])} ({format_usd(h['amount'] * h['usdPrice'])})" for h in holdings]
        total = sum(h["amount"] * h["usdPrice"] for h in holdings)
        return ok(f"Balances shown to the user as a card: {', '.join(parts)}. Total {format_usd(total)}.")

    async def resolve_recipient(self, args: dict) -> dict:
        try:
            address, name = resolve_recipient(str(args.get("name_or_address", "")), self.ctx.contacts)
        except TransferError as e:
            return err(str(e))
        return ok(f"{name or 'Address'} → {address}")

    async def propose_transfer(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        token = find_token(str(args.get("token", "")))
        if token is None:
            return err(f"I can only send {SUPPORTED} in Sandbox.")
        try:
            amount = parse_amount(str(args.get("amount", "")), token.decimals)
            to, name = resolve_recipient(str(args.get("to", "")), self.ctx.contacts)
            eth_balance = await self.chain.eth_balance(self.ctx.address)
            balance = eth_balance if token.address is None else await self.chain.token_balance(token, self.ctx.address)
            gas_cost = gas_units(token) * await self.chain.gas_price()
            validate(token, amount, balance, eth_balance, gas_cost)
            price = await self.chain.price_usd(token)
            eth_price = await self.chain.price_usd(ETH)
        except TransferError as e:
            return err(str(e))
        except Exception as e:
            return err(f"The Sandbox chain isn't reachable right now ({e}).")

        human = f"{format_units(amount, token.decimals)} {token.symbol}"
        label = name or short(to)
        pid, fut = self.proposals.new()
        await self.send(
            {
                "type": "confirm",
                "id": pid,
                "tx": {
                    "title": f"Send {human}",
                    "rows": display_rows(token, amount, to, name, price, gas_cost, eth_price),
                    "request": build_request(token, to, amount),
                },
            }
        )
        result = await self.proposals.wait(pid, fut, self.approval_timeout)
        if result is None:
            return ok("The user didn't respond to the confirmation within 5 minutes, so nothing was sent.")
        if result.get("outcome") == "rejected":
            return ok("The user rejected the transfer. Nothing was sent.")
        if result.get("error"):
            return ok(f"The transfer failed before it was sent: {result['error']}")
        if result.get("status") == "reverted":
            return ok(f"The transfer of {human} to {label} was mined but reverted. Tx {result.get('hash')}.")
        return ok(f"Sent {human} to {label}. Confirmed on Sandbox, tx {result.get('hash')}.")

    async def unsupported_action(self, args: dict) -> dict:
        action = str(args.get("action", "That"))
        return ok(f"{action} is coming soon. Right now LazyWallet can check balances and send {SUPPORTED} on Sandbox.")


def build_mcp_server(t: WalletTools):
    return create_sdk_mcp_server(
        name=SERVER_NAME,
        version="0.1.0",
        tools=[
            tool("get_balances", "Show the active wallet's balances (ETH and supported tokens) with USD values.", {"type": "object", "properties": {}})(t.get_balances),
            tool(
                "resolve_recipient",
                "Look up an address-book name or validate a 0x address.",
                {"type": "object", "properties": {"name_or_address": {"type": "string"}}, "required": ["name_or_address"]},
            )(t.resolve_recipient),
            tool(
                "propose_transfer",
                "Propose sending ETH or a supported token. Shows a confirmation card and waits for the user to approve or reject; returns the outcome.",
                {
                    "type": "object",
                    "properties": {
                        "token": {"type": "string", "description": f"One of {SUPPORTED}"},
                        "amount": {"type": "string", "description": "Decimal amount in whole tokens, e.g. '0.1'"},
                        "to": {"type": "string", "description": "Address-book name or 0x address"},
                    },
                    "required": ["token", "amount", "to"],
                },
            )(t.propose_transfer),
            tool(
                "unsupported_action",
                "Use for swaps, bridging, scheduling, price alerts, dApps or anything other than balances and sends.",
                {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]},
            )(t.unsupported_action),
        ],
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd agent && uv run pytest -q`
Expected: PASS. (`agent/tests/` has no `__init__.py`, so pytest's default `prepend` import mode puts it on `sys.path` and `from fakes import …` resolves.)

- [ ] **Step 5: Commit**

```bash
git add agent
git commit -m "feat(agent): add approval proposals and wallet tools"
```

---

### Task 6: Streaming, session, WebSocket server, Claude client

**Files:**
- Create: `agent/lazyagent/stream.py`, `agent/lazyagent/session.py`, `agent/lazyagent/prompt.py`, `agent/lazyagent/claude.py`, `agent/lazyagent/server.py`
- Test: `agent/tests/test_stream.py`, `agent/tests/test_server.py`

**Interfaces:**
- Consumes: Task 4 `Settings`, `load_settings`, `RpcChain`, `Chain`; Task 5 `WalletTools`, `WalletContext`, `Proposals`, `build_mcp_server`, `TOOL_NAMES`
- Produces:
  - `stream.translate(msg) -> list[dict]`
  - `session.ClientFactory = Callable[[WalletTools], Awaitable[AgentClient]]` where `AgentClient` has `async query(text)`, `receive_response()` (async iterator), `async disconnect()`
  - `session.Session(send, chain, client_factory, approval_timeout=300)` with `async handle(msg: dict)`, `async close()`
  - `claude.connect_claude(tools: WalletTools, settings: Settings) -> ClaudeSDKClient`
  - `server.create_app(chain, client_factory, allowed_origins, approval_timeout=300) -> FastAPI`, `server.main()`

- [ ] **Step 1: Write failing tests**

`agent/tests/test_stream.py`:
```python
from claude_agent_sdk import AssistantMessage, ResultMessage, StreamEvent, TextBlock, ToolUseBlock

from lazyagent.stream import translate


def delta(text, parent=None):
    return StreamEvent(
        uuid="u", session_id="s", parent_tool_use_id=parent,
        event={"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
    )


def test_text_delta():
    assert translate(delta("Hi")) == [{"type": "text_delta", "text": "Hi"}]


def test_ignores_other_stream_events_and_subagent_text():
    assert translate(StreamEvent(uuid="u", session_id="s", event={"type": "message_start"})) == []
    assert translate(delta("x", parent="tool1")) == []


def test_text_done_after_assistant_text_only():
    assert translate(AssistantMessage(content=[TextBlock(text="Hi")], model="m")) == [{"type": "text_done"}]
    assert translate(AssistantMessage(content=[ToolUseBlock(id="t", name="x", input={})], model="m")) == []


def test_errors():
    assert translate(AssistantMessage(content=[], model="m", error="authentication_failed"))[0]["type"] == "error"
    result = ResultMessage(subtype="error_during_execution", duration_ms=1, duration_api_ms=1, is_error=True, num_turns=1, session_id="s", result="boom")
    assert translate(result) == [{"type": "error", "message": "boom"}]
    ok = ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s")
    assert translate(ok) == []
```

`agent/tests/test_server.py`:
```python
import time

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, StreamEvent, TextBlock
from fakes import FakeChain
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from lazyagent.server import create_app

ORIGIN = "http://localhost:5174"
ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
USER = {"type": "user", "text": "send 0.1 eth to alice", "spoken": False, "address": ME, "contacts": [{"name": "Alice", "address": ALICE}]}


class ScriptedClient:
    """Stands in for ClaudeSDKClient: calls propose_transfer, then speaks the tool's result."""

    instances: list["ScriptedClient"] = []

    def __init__(self, tools):
        self.tools = tools
        self.disconnected = False
        ScriptedClient.instances.append(self)

    async def query(self, text):
        self.text = text

    async def receive_response(self):
        result = await self.tools.propose_transfer({"token": "ETH", "amount": "0.1", "to": "Alice"})
        reply = result["content"][0]["text"]
        yield StreamEvent(uuid="u", session_id="s", event={"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": reply}})
        yield AssistantMessage(content=[TextBlock(text=reply)], model="test")
        yield ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s")

    async def disconnect(self):
        self.disconnected = True


async def scripted_factory(tools):
    return ScriptedClient(tools)


async def failing_factory(tools):
    raise RuntimeError("Claude Code is not logged in")


def client(factory=scripted_factory):
    return TestClient(create_app(FakeChain(), factory, (ORIGIN,)))


def test_rejects_other_origins():
    with pytest.raises(WebSocketDisconnect):
        with client().websocket_connect("/ws", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()


def test_transfer_round_trip():
    with client().websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
        ws.send_json(USER)
        confirm = ws.receive_json()
        assert confirm["type"] == "confirm"
        assert confirm["tx"]["request"]["to"] == ALICE
        ws.send_json({"type": "tx_result", "id": confirm["id"], "outcome": "approved", "hash": "0xabc", "status": "success"})
        delta = ws.receive_json()
        assert delta["type"] == "text_delta"
        assert "Sent 0.1 ETH to Alice" in delta["text"]
        assert ws.receive_json() == {"type": "text_done"}
        assert ws.receive_json() == {"type": "turn_end"}


def test_busy_while_waiting_for_approval():
    with client().websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
        ws.send_json(USER)
        confirm = ws.receive_json()
        ws.send_json(USER)
        assert ws.receive_json() == {"type": "error", "message": "Still working on your last request."}
        ws.send_json({"type": "tx_result", "id": confirm["id"], "outcome": "rejected"})
        assert ws.receive_json()["type"] == "text_delta"


def test_invalid_json_is_reported():
    with client().websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
        ws.send_text("not json")
        assert ws.receive_json()["type"] == "error"


def test_claude_unavailable_reports_error_then_turn_end():
    with client(failing_factory).websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
        ws.send_json(USER)
        err = ws.receive_json()
        assert err["type"] == "error"
        assert "not logged in" in err["message"]
        assert ws.receive_json() == {"type": "turn_end"}


def test_disconnect_cancels_pending_and_closes_client():
    ScriptedClient.instances.clear()
    with client().websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
        ws.send_json(USER)
        assert ws.receive_json()["type"] == "confirm"
    deadline = time.monotonic() + 2
    while not ScriptedClient.instances[0].disconnected and time.monotonic() < deadline:
        time.sleep(0.01)
    assert ScriptedClient.instances[0].disconnected


def test_health():
    assert client().get("/health").json() == {"ok": True}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd agent && uv run pytest -q`
Expected: FAIL — `ModuleNotFoundError` for `lazyagent.stream` / `lazyagent.server`.

- [ ] **Step 3: Implement**

`agent/lazyagent/stream.py`:
```python
from claude_agent_sdk import AssistantMessage, ResultMessage, StreamEvent, TextBlock


def translate(msg) -> list[dict]:
    """Turn one Claude Agent SDK message into the WebSocket messages the wallet understands."""
    if isinstance(msg, StreamEvent):
        ev = msg.event
        if msg.parent_tool_use_id is None and ev.get("type") == "content_block_delta":
            d = ev.get("delta", {})
            if d.get("type") == "text_delta" and d.get("text"):
                return [{"type": "text_delta", "text": d["text"]}]
        return []
    if isinstance(msg, AssistantMessage):
        if msg.error:
            return [{"type": "error", "message": f"Claude couldn't answer ({msg.error})."}]
        if any(isinstance(b, TextBlock) for b in msg.content):
            return [{"type": "text_done"}]
        return []
    if isinstance(msg, ResultMessage) and msg.is_error:
        return [{"type": "error", "message": msg.result or "; ".join(msg.errors or []) or "The agent hit an error."}]
    return []
```

`agent/lazyagent/prompt.py`:
```python
SYSTEM_PROMPT = """\
You are LazyWallet, a voice-first crypto wallet assistant. The user talks to you, often by voice, and your replies are read aloud.

Environment: Sandbox — a local fork of Ethereum mainnet with test funds. Nothing here costs real money.

How to work:
- Keep replies short and spoken-friendly: one or two sentences, no markdown, no tables, no lists.
- Always use tools for facts. Never invent balances, prices, addresses or transaction hashes.
- "What's my balance" and similar → get_balances. The app shows a balance card, so just summarise the total and anything notable.
- Every send goes through propose_transfer with the token symbol, a plain decimal amount, and the recipient name or 0x address exactly as the user said it. The app shows a confirmation card and the user approves or rejects it there; the tool returns the outcome. Report it in one short sentence.
- If propose_transfer returns an error, explain it plainly and suggest the fix.
- Swaps, bridging, schedules, price alerts, dApps or anything else → unsupported_action.
- Never ask for seed phrases or private keys.
"""
```

`agent/lazyagent/session.py`:
```python
import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any, Protocol

from .chain import Chain
from .proposals import Proposals
from .stream import translate
from .tools import Send, WalletContext, WalletTools

log = logging.getLogger(__name__)
BUSY = "Still working on your last request."


class AgentClient(Protocol):
    async def query(self, prompt: str) -> None: ...
    def receive_response(self) -> Any: ...
    async def disconnect(self) -> None: ...


ClientFactory = Callable[[WalletTools], Awaitable[AgentClient]]


class Session:
    """One browser connection: wallet context, pending approvals and a lazily created Claude client."""

    def __init__(self, send: Send, chain: Chain, client_factory: ClientFactory, approval_timeout: float = 300):
        self._send = send
        self._factory = client_factory
        self.ctx = WalletContext()
        self.proposals = Proposals()
        self.tools = WalletTools(chain, send, self.ctx, self.proposals, approval_timeout)
        self._client: AgentClient | None = None
        self._turn: asyncio.Task | None = None

    async def handle(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "user":
            if self._turn and not self._turn.done():
                await self._send({"type": "error", "message": BUSY})
                return
            self.ctx.address = msg.get("address")
            self.ctx.contacts = list(msg.get("contacts") or [])
            self._turn = asyncio.create_task(self._run(str(msg.get("text", ""))))
        elif kind == "tx_result":
            self.proposals.resolve(str(msg.get("id", "")), msg)
        else:
            await self._send({"type": "error", "message": f"Unknown message type: {kind}"})

    async def _run(self, text: str) -> None:
        try:
            if self._client is None:
                self._client = await self._factory(self.tools)
            await self._client.query(text)
            async for m in self._client.receive_response():
                for out in translate(m):
                    await self._send(out)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("agent turn failed")
            await self._send({"type": "error", "message": f"Agent error: {e}"})
        await self._send({"type": "turn_end"})

    async def close(self) -> None:
        self.proposals.cancel_all()
        if self._turn and not self._turn.done():
            self._turn.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._turn
        if self._client is not None:
            with suppress(Exception):
                await self._client.disconnect()
```

`agent/lazyagent/claude.py`:
```python
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from .config import Settings
from .prompt import SYSTEM_PROMPT
from .tools import SERVER_NAME, TOOL_NAMES, WalletTools, build_mcp_server

APPROVAL_TOOL_TIMEOUT_MS = "360000"  # > the 300 s approval wait in propose_transfer


async def connect_claude(tools: WalletTools, settings: Settings) -> ClaudeSDKClient:
    """Start a Claude Code session (uses the developer's Claude Code login) with only the wallet tools."""
    options = ClaudeAgentOptions(
        model=settings.model,
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        mcp_servers={SERVER_NAME: build_mcp_server(tools)},
        allowed_tools=TOOL_NAMES,
        strict_mcp_config=True,
        setting_sources=[],
        include_partial_messages=True,
        max_turns=10,
        env={"MCP_TOOL_TIMEOUT": APPROVAL_TOOL_TIMEOUT_MS},
    )
    client = ClaudeSDKClient(options=options)
    await client.connect()
    return client
```

`agent/lazyagent/server.py`:
```python
import logging

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .chain import Chain, RpcChain
from .claude import connect_claude
from .config import load_settings
from .session import ClientFactory, Session


def create_app(chain: Chain, client_factory: ClientFactory, allowed_origins: tuple[str, ...], approval_timeout: float = 300) -> FastAPI:
    app = FastAPI(title="LazyWallet Agent")

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        if ws.headers.get("origin") not in allowed_origins:
            await ws.close(code=1008)
            return
        await ws.accept()
        session = Session(ws.send_json, chain, client_factory, approval_timeout)
        try:
            while True:
                try:
                    msg = await ws.receive_json()
                except ValueError:
                    await ws.send_json({"type": "error", "message": "Invalid message."})
                    continue
                await session.handle(msg)
        except WebSocketDisconnect:
            pass
        finally:
            await session.close()

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()

    async def factory(tools):
        return await connect_claude(tools, settings)

    app = create_app(RpcChain(settings.rpc_url), factory, settings.allowed_origins)
    print(f"LazyWallet agent on ws://127.0.0.1:{settings.port}/ws (model {settings.model}, chain {settings.rpc_url})")
    uvicorn.run(app, host="127.0.0.1", port=settings.port)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd agent && uv run pytest -q`
Expected: PASS (all agent tests; chain test skipped without `ETH_RPC_URL`).

- [ ] **Step 5: Smoke the server process**

Run: `pnpm dev:agent` (background), then `curl -s localhost:8787/health`
Expected: `{"ok":true}`. Stop it.

- [ ] **Step 6: Commit**

```bash
git add agent
git commit -m "feat(agent): add websocket session server with Claude client"
```

---

### Task 7: Wallet — protocol types and chat reducer

**Files:**
- Modify: `apps/wallet/src/types.ts`
- Create: `apps/wallet/src/agent/protocol.ts`, `apps/wallet/src/agent/chatReducer.ts`
- Test: `apps/wallet/src/agent/chatReducer.test.ts`

**Interfaces:**
- Produces:
  - `types.ts`: `TxRequest = { to: Address; value: string; data: \`0x${string}\` }`; `TxDraft.request?: TxRequest`; `ConfirmState` adds `'expired'`; status message `state` adds `'failed'`.
  - `protocol.ts`: `ClientMsg`, `ServerMsg` (per spec §5).
  - `chatReducer.ts`: `ChatState = { messages: Message[]; streamingId: string | null; busy: boolean; online: boolean; seq: number }`, `initialChat: ChatState`, `ChatEvent` union (`local`, `server`, `busy`, `online`, `update`), `chatReducer(state, event): ChatState`.

- [ ] **Step 1: Update shared types**

In `apps/wallet/src/types.ts`:
- Add after `DappInfo`:
```ts
export type TxRequest = { to: Address; value: string; data: `0x${string}` }
```
- In `TxDraft` add the field `request?: TxRequest` after `explanation?: string`.
- Replace `export type ConfirmState = 'waiting' | 'approved' | 'rejected'` with `export type ConfirmState = 'waiting' | 'approved' | 'rejected' | 'expired'`.
- In the status member of `Message`, replace `state: 'pending' | 'success'` with `state: 'pending' | 'success' | 'failed'`.

`apps/wallet/src/agent/protocol.ts`:
```ts
import type { Address, Holding, TxDraft, TxRequest } from '@/types'

export type ClientMsg =
  | {
      type: 'user'
      text: string
      spoken: boolean
      address: Address
      contacts: { name: string; address: Address }[]
    }
  | {
      type: 'tx_result'
      id: string
      outcome: 'approved' | 'rejected'
      hash?: string
      status?: 'success' | 'reverted'
      error?: string
    }

export type ServerMsg =
  | { type: 'text_delta'; text: string }
  | { type: 'text_done' }
  | { type: 'balances'; holdings: Holding[] }
  | { type: 'confirm'; id: string; tx: TxDraft & { request: TxRequest } }
  | { type: 'error'; message: string }
  | { type: 'turn_end' }
```

- [ ] **Step 2: Write failing test**

`apps/wallet/src/agent/chatReducer.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import type { Message } from '@/types'
import { chatReducer, initialChat, type ChatEvent, type ChatState } from './chatReducer'

const run = (events: ChatEvent[], from: ChatState = initialChat) => events.reduce(chatReducer, from)
const server = (msg: Extract<ChatEvent, { type: 'server' }>['msg']): ChatEvent => ({ type: 'server', msg })
const confirmMsg = server({
  type: 'confirm',
  id: 'p1',
  tx: { title: 'Send 0.1 ETH', rows: [], request: { to: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', value: '1', data: '0x' } },
})

describe('chatReducer', () => {
  it('streams deltas into one assistant bubble and ends it on text_done', () => {
    const s = run([server({ type: 'text_delta', text: 'Hel' }), server({ type: 'text_delta', text: 'lo' }), server({ type: 'text_done' })])
    expect(s.messages).toHaveLength(1)
    expect(s.messages[0]).toMatchObject({ role: 'assistant', kind: 'text', text: 'Hello' })
    expect(s.streamingId).toBeNull()
  })

  it('starts a new bubble after text_done', () => {
    const s = run([
      server({ type: 'text_delta', text: 'One' }),
      server({ type: 'text_done' }),
      server({ type: 'text_delta', text: 'Two' }),
    ])
    expect(s.messages.map((m) => (m.kind === 'text' ? m.text : ''))).toEqual(['One', 'Two'])
    expect(new Set(s.messages.map((m) => m.id)).size).toBe(2)
  })

  it('adds balance and confirm cards', () => {
    const s = run([server({ type: 'balances', holdings: [{ symbol: 'ETH', amount: 1, usdPrice: 3000 }] }), confirmMsg])
    expect(s.messages[0].kind).toBe('balance')
    expect(s.messages[1]).toMatchObject({ id: 'p1', kind: 'confirm', state: 'waiting' })
  })

  it('turn_end clears busy and expires cards still waiting for the agent', () => {
    const s = run([{ type: 'busy', busy: true }, confirmMsg, server({ type: 'turn_end' })])
    expect(s.busy).toBe(false)
    expect((s.messages[0] as Extract<Message, { kind: 'confirm' }>).state).toBe('expired')
  })

  it('going offline clears busy and expires waiting agent cards, but not mock cards', () => {
    const mock: Message = { id: 'm1', role: 'assistant', kind: 'confirm', state: 'waiting', tx: { title: 'Mock', rows: [] } }
    const s = run([{ type: 'busy', busy: true }, { type: 'local', messages: [mock] }, confirmMsg, { type: 'online', online: false }])
    expect(s.busy).toBe(false)
    expect(s.online).toBe(false)
    expect(s.messages.map((m) => (m.kind === 'confirm' ? m.state : ''))).toEqual(['waiting', 'expired'])
  })

  it('error ends streaming and shows the message', () => {
    const s = run([server({ type: 'text_delta', text: 'x' }), server({ type: 'error', message: 'boom' })])
    expect(s.streamingId).toBeNull()
    expect(s.messages[1]).toMatchObject({ kind: 'text', text: 'boom' })
  })

  it('update patches one message', () => {
    const s = run([confirmMsg, { type: 'update', id: 'p1', patch: { state: 'approved' } }])
    expect(s.messages[0]).toMatchObject({ state: 'approved' })
  })
})
```

- [ ] **Step 3: Run to verify it fails**

Run: `pnpm --filter wallet test`
Expected: FAIL — cannot resolve `./chatReducer`.

- [ ] **Step 4: Implement**

`apps/wallet/src/agent/chatReducer.ts`:
```ts
import type { Message } from '@/types'
import type { ServerMsg } from './protocol'

export type ChatState = {
  messages: Message[]
  streamingId: string | null
  busy: boolean
  online: boolean
  seq: number
}

export type ChatEvent =
  | { type: 'local'; messages: Message[] }
  | { type: 'server'; msg: ServerMsg }
  | { type: 'busy'; busy: boolean }
  | { type: 'online'; online: boolean }
  | { type: 'update'; id: string; patch: Partial<Message> }

export const initialChat: ChatState = { messages: [], streamingId: null, busy: false, online: false, seq: 0 }

// Agent cards (they carry a tx request) can no longer be answered once the agent's turn or session is gone.
function expireAgentCards(messages: Message[]): Message[] {
  return messages.map((m) => (m.kind === 'confirm' && m.state === 'waiting' && m.tx.request ? { ...m, state: 'expired' } : m))
}

function onServer(s: ChatState, msg: ServerMsg): ChatState {
  const nextId = `a${s.seq}`
  switch (msg.type) {
    case 'text_delta':
      if (s.streamingId) {
        return {
          ...s,
          messages: s.messages.map((m) => (m.id === s.streamingId && m.kind === 'text' ? { ...m, text: m.text + msg.text } : m)),
        }
      }
      return {
        ...s,
        seq: s.seq + 1,
        streamingId: nextId,
        messages: [...s.messages, { id: nextId, role: 'assistant', kind: 'text', text: msg.text }],
      }
    case 'text_done':
      return { ...s, streamingId: null }
    case 'balances':
      return {
        ...s,
        seq: s.seq + 1,
        streamingId: null,
        messages: [...s.messages, { id: nextId, role: 'assistant', kind: 'balance', holdings: msg.holdings }],
      }
    case 'confirm':
      return {
        ...s,
        streamingId: null,
        messages: [...s.messages, { id: msg.id, role: 'assistant', kind: 'confirm', tx: msg.tx, state: 'waiting' }],
      }
    case 'error':
      return {
        ...s,
        seq: s.seq + 1,
        streamingId: null,
        messages: [...s.messages, { id: nextId, role: 'assistant', kind: 'text', text: msg.message }],
      }
    case 'turn_end':
      return { ...s, busy: false, streamingId: null, messages: expireAgentCards(s.messages) }
  }
}

export function chatReducer(s: ChatState, e: ChatEvent): ChatState {
  switch (e.type) {
    case 'local':
      return { ...s, messages: [...s.messages, ...e.messages] }
    case 'server':
      return onServer(s, e.msg)
    case 'busy':
      return { ...s, busy: e.busy }
    case 'online':
      return e.online
        ? { ...s, online: true }
        : { ...s, online: false, busy: false, streamingId: null, messages: expireAgentCards(s.messages) }
    case 'update':
      return { ...s, messages: s.messages.map((m) => (m.id === e.id ? ({ ...m, ...e.patch } as Message) : m)) }
  }
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `pnpm --filter wallet test && pnpm --filter wallet build`
Expected: tests PASS. Build may fail in `ConfirmCard`/`StatusCard` only if they exhaustively switch on the old unions — they don't (ternaries), so build passes.

- [ ] **Step 6: Commit**

```bash
git add apps/wallet/src
git commit -m "feat(wallet): add agent protocol types and chat reducer"
```

---

### Task 8: Wallet — transaction execution and faucet client

**Files:**
- Create: `apps/wallet/src/chain/executeTx.ts`, `apps/wallet/src/chain/client.ts`, `apps/wallet/src/chain/faucet.ts`
- Modify: `apps/wallet/.env.example`
- Test: `apps/wallet/src/chain/executeTx.test.ts`, `apps/wallet/src/chain/faucet.test.ts`

**Interfaces:**
- Consumes: Task 7 `TxRequest`; existing `sandbox` chain from `@/lib/wagmi`
- Produces:
  - `TxDeps = { send(req: TxRequest): Promise<\`0x${string}\`>; wait(hash: \`0x${string}\`): Promise<'success' | 'reverted'> }`
  - `TxOutcome = { hash?: string; status?: 'success' | 'reverted'; error?: string }`
  - `executeTx(req: TxRequest, deps: TxDeps): Promise<TxOutcome>`
  - `statusPatch(o: TxOutcome): { state: 'success' | 'failed'; text: string; hash?: string }`
  - `txDepsFor(mnemonic: string): TxDeps`
  - `requestFunds(address: Address): Promise<string>` (summary text; throws `Error` with a user-facing message)

- [ ] **Step 1: Write failing tests**

`apps/wallet/src/chain/executeTx.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import type { TxRequest } from '@/types'
import { executeTx, statusPatch, type TxDeps } from './executeTx'

const req: TxRequest = { to: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', value: '100', data: '0x' }
const HASH = '0xabc' as const

describe('executeTx', () => {
  it('returns hash and receipt status', async () => {
    const deps: TxDeps = { send: async () => HASH, wait: async () => 'success' }
    expect(await executeTx(req, deps)).toEqual({ hash: HASH, status: 'success' })
  })

  it('reports a revert', async () => {
    const deps: TxDeps = { send: async () => HASH, wait: async () => 'reverted' }
    expect(await executeTx(req, deps)).toEqual({ hash: HASH, status: 'reverted' })
  })

  it('reports send errors using the short message when present', async () => {
    const deps: TxDeps = {
      send: async () => {
        throw Object.assign(new Error('long details'), { shortMessage: 'insufficient funds' })
      },
      wait: async () => 'success',
    }
    expect(await executeTx(req, deps)).toEqual({ error: 'insufficient funds' })
  })

  it('reports receipt errors with the hash', async () => {
    const deps: TxDeps = {
      send: async () => HASH,
      wait: async () => {
        throw new Error('timeout')
      },
    }
    expect(await executeTx(req, deps)).toEqual({ hash: HASH, error: 'timeout' })
  })
})

describe('statusPatch', () => {
  it('maps outcomes to status card states', () => {
    expect(statusPatch({ hash: HASH, status: 'success' })).toEqual({ state: 'success', text: 'Confirmed on Sandbox.', hash: HASH })
    expect(statusPatch({ hash: HASH, status: 'reverted' })).toEqual({ state: 'failed', text: 'Transaction reverted.', hash: HASH })
    expect(statusPatch({ error: 'nope' })).toEqual({ state: 'failed', text: 'Failed: nope', hash: undefined })
  })
})
```

`apps/wallet/src/chain/faucet.test.ts`:
```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { requestFunds } from './faucet'

const ADDRESS = '0x70997970C51812dc3A010C7d01b50e0d17dc79C8'

afterEach(() => vi.unstubAllGlobals())

describe('requestFunds', () => {
  it('returns the faucet summary', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ summary: '10 ETH' }), { status: 200 })))
    expect(await requestFunds(ADDRESS)).toBe('10 ETH')
  })

  it('explains when the sandbox is not running', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    await expect(requestFunds(ADDRESS)).rejects.toThrow('pnpm dev:sandbox')
  })

  it('surfaces faucet errors', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'Sandbox chain error: x' }), { status: 502 })))
    await expect(requestFunds(ADDRESS)).rejects.toThrow('Sandbox chain error: x')
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm --filter wallet test`
Expected: FAIL — cannot resolve `./executeTx` / `./faucet`.

- [ ] **Step 3: Implement**

`apps/wallet/src/chain/executeTx.ts`:
```ts
import type { TxRequest } from '@/types'

type Hash = `0x${string}`

export type TxDeps = {
  send: (req: TxRequest) => Promise<Hash>
  wait: (hash: Hash) => Promise<'success' | 'reverted'>
}

export type TxOutcome = { hash?: string; status?: 'success' | 'reverted'; error?: string }

function messageOf(e: unknown): string {
  if (e && typeof e === 'object' && 'shortMessage' in e && typeof e.shortMessage === 'string') return e.shortMessage
  return e instanceof Error ? e.message : String(e)
}

export async function executeTx(req: TxRequest, deps: TxDeps): Promise<TxOutcome> {
  let hash: Hash
  try {
    hash = await deps.send(req)
  } catch (e) {
    return { error: messageOf(e) }
  }
  try {
    return { hash, status: await deps.wait(hash) }
  } catch (e) {
    return { hash, error: messageOf(e) }
  }
}

export function statusPatch(o: TxOutcome): { state: 'success' | 'failed'; text: string; hash?: string } {
  if (o.error) return { state: 'failed', text: `Failed: ${o.error}`, hash: o.hash }
  if (o.status === 'reverted') return { state: 'failed', text: 'Transaction reverted.', hash: o.hash }
  return { state: 'success', text: 'Confirmed on Sandbox.', hash: o.hash }
}
```

`apps/wallet/src/chain/client.ts`:
```ts
import { createPublicClient, createWalletClient, http } from 'viem'
import { mnemonicToAccount } from 'viem/accounts'
import { sandbox } from '@/lib/wagmi'
import type { TxDeps } from './executeTx'

export function txDepsFor(mnemonic: string): TxDeps {
  const transport = http(sandbox.rpcUrls.default.http[0])
  const wallet = createWalletClient({ account: mnemonicToAccount(mnemonic), chain: sandbox, transport })
  const reader = createPublicClient({ chain: sandbox, transport })
  return {
    send: (req) => wallet.sendTransaction({ to: req.to, value: BigInt(req.value), data: req.data }),
    wait: async (hash) => (await reader.waitForTransactionReceipt({ hash })).status,
  }
}
```

`apps/wallet/src/chain/faucet.ts`:
```ts
import type { Address } from '@/types'

const FAUCET_URL: string = import.meta.env.VITE_FAUCET_URL ?? 'http://localhost:8547'

export async function requestFunds(address: Address): Promise<string> {
  let res: Response
  try {
    res = await fetch(`${FAUCET_URL}/fund`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ address }),
    })
  } catch {
    throw new Error('Sandbox faucet is offline — run `pnpm dev:sandbox`.')
  }
  const body = (await res.json().catch(() => ({}))) as { summary?: string; detail?: string }
  if (!res.ok) throw new Error(body.detail ?? `Faucet error (${res.status})`)
  return body.summary ?? 'test funds'
}
```

Replace `apps/wallet/.env.example`:
```
VITE_SANDBOX_RPC_URL=http://localhost:8545
VITE_AGENT_WS_URL=ws://localhost:8787/ws
VITE_FAUCET_URL=http://localhost:8547
```

- [ ] **Step 4: Run to verify it passes**

Run: `pnpm --filter wallet test && pnpm --filter wallet build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/wallet
git commit -m "feat(wallet): add transaction executor and faucet client"
```

---

### Task 9: Wallet — agent chat hook and UI wiring

**Files:**
- Create: `apps/wallet/src/agent/useAgentChat.ts`
- Modify: `apps/wallet/src/chat/cards/ConfirmCard.tsx`, `apps/wallet/src/chat/cards/StatusCard.tsx`, `apps/wallet/src/chat/MessageItem.tsx`, `apps/wallet/src/components/QrSheet.tsx`, `apps/wallet/src/routes/WalletPage.tsx`
- Delete: `apps/wallet/src/chat/useChat.ts`

**Interfaces:**
- Consumes: Task 7 `chatReducer`, `initialChat`, `ClientMsg`, `ServerMsg`; Task 8 `executeTx`, `statusPatch`, `txDepsFor`, `requestFunds`; existing `say` (`@/mock/agent`), `speak` (`@/voice/speech`), `uid`, `txHash` (`@/lib/format`)
- Produces: `useAgentChat({ address?: Address; mnemonic?: string; contacts: Contact[]; speakEnabled: boolean }) → { messages, busy, online, send(text, spoken?), approve(id), reject(id), deliver(reply: AgentReply) }`

- [ ] **Step 1: Hook**

`apps/wallet/src/agent/useAgentChat.ts`:
```ts
import { useEffect, useReducer, useRef } from 'react'
import { executeTx, statusPatch } from '@/chain/executeTx'
import { txDepsFor } from '@/chain/client'
import { txHash, uid } from '@/lib/format'
import { say } from '@/mock/agent'
import type { Address, AgentReply, Contact, Message } from '@/types'
import { speak } from '@/voice/speech'
import { chatReducer, initialChat } from './chatReducer'
import type { ClientMsg, ServerMsg } from './protocol'

const AGENT_WS_URL: string = import.meta.env.VITE_AGENT_WS_URL ?? 'ws://localhost:8787/ws'
const OFFLINE_TEXT = 'Agent offline — run `pnpm dev:agent`, then try again.'
const BUSY_TEXT = 'Still working on your last request — approve or reject any open card first.'
const THINK_MS = 500
const MOCK_CONFIRM_MS = 1500
const MAX_RETRY_MS = 10_000

type Options = { address?: Address; mnemonic?: string; contacts: Contact[]; speakEnabled: boolean }

export function useAgentChat(options: Options) {
  const [state, dispatch] = useReducer(chatReducer, initialChat)
  const wsRef = useRef<WebSocket | null>(null)
  const spokenRef = useRef('')
  const optsRef = useRef(options)
  const stateRef = useRef(state)

  useEffect(() => {
    optsRef.current = options
    stateRef.current = state
  })

  useEffect(() => {
    let disposed = false
    let wasOnline = false
    let retryMs = 1000
    let timer: number | undefined

    function connect() {
      const ws = new WebSocket(AGENT_WS_URL)
      wsRef.current = ws
      ws.onopen = () => {
        retryMs = 1000
        wasOnline = true
        dispatch({ type: 'online', online: true })
      }
      ws.onmessage = (e) => {
        const msg = JSON.parse(String(e.data)) as ServerMsg
        if (msg.type === 'text_delta') spokenRef.current += msg.text
        if (msg.type === 'text_done' || msg.type === 'error') {
          speak(msg.type === 'error' ? msg.message : spokenRef.current, optsRef.current.speakEnabled)
          spokenRef.current = ''
        }
        dispatch({ type: 'server', msg })
      }
      ws.onclose = () => {
        wsRef.current = null
        if (disposed) return
        if (wasOnline) {
          wasOnline = false
          dispatch({ type: 'online', online: false })
          dispatch({ type: 'local', messages: [say(OFFLINE_TEXT)] })
        }
        timer = window.setTimeout(connect, retryMs)
        retryMs = Math.min(retryMs * 2, MAX_RETRY_MS)
      }
    }

    connect()
    return () => {
      disposed = true
      window.clearTimeout(timer)
      wsRef.current?.close()
    }
  }, [])

  function sendJson(msg: ClientMsg): boolean {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return false
    ws.send(JSON.stringify(msg))
    return true
  }

  function deliver(reply: AgentReply) {
    window.setTimeout(() => {
      dispatch({ type: 'local', messages: reply.messages })
      const text = reply.messages.flatMap((m) => (m.role === 'assistant' && m.kind === 'text' ? [m.text] : [])).join(' ')
      speak(text, optsRef.current.speakEnabled)
    }, THINK_MS)
  }

  function send(text: string, spoken = false) {
    const t = text.trim()
    const { address, contacts } = optsRef.current
    if (!t || !address) return
    dispatch({ type: 'local', messages: [{ id: uid(), role: 'user', kind: 'text', text: t, spoken }] })
    if (stateRef.current.busy) return deliver({ messages: [say(BUSY_TEXT)] })
    const sent = sendJson({
      type: 'user',
      text: t,
      spoken,
      address,
      contacts: contacts.map((c) => ({ name: c.name, address: c.address })),
    })
    if (!sent) return deliver({ messages: [say(OFFLINE_TEXT)] })
    dispatch({ type: 'busy', busy: true })
  }

  function findWaitingConfirm(id: string) {
    const m = stateRef.current.messages.find((x) => x.id === id)
    return m && m.kind === 'confirm' && m.state === 'waiting' ? m : null
  }

  async function approve(id: string) {
    const m = findWaitingConfirm(id)
    if (!m) return
    dispatch({ type: 'update', id, patch: { state: 'approved' } })
    const statusId = uid()
    const pending: Message = { id: statusId, role: 'assistant', kind: 'status', state: 'pending', text: 'Submitting to Sandbox…' }
    dispatch({ type: 'local', messages: [pending] })
    if (!m.tx.request) {
      // Phase-1 WalletConnect mock card: no real transaction.
      window.setTimeout(
        () => dispatch({ type: 'update', id: statusId, patch: { state: 'success', text: 'Done! Transaction confirmed.', hash: txHash() } }),
        MOCK_CONFIRM_MS,
      )
      return
    }
    const { mnemonic } = optsRef.current
    const outcome = mnemonic ? await executeTx(m.tx.request, txDepsFor(mnemonic)) : { error: 'No wallet is unlocked.' }
    dispatch({ type: 'update', id: statusId, patch: statusPatch(outcome) })
    sendJson({ type: 'tx_result', id, outcome: 'approved', ...outcome })
  }

  function reject(id: string) {
    const m = findWaitingConfirm(id)
    if (!m) return
    dispatch({ type: 'update', id, patch: { state: 'rejected' } })
    if (m.tx.request) sendJson({ type: 'tx_result', id, outcome: 'rejected' })
    else deliver({ messages: [say('Cancelled — nothing was sent.')] })
  }

  return { messages: state.messages, busy: state.busy, online: state.online, send, approve, reject, deliver }
}
```

- [ ] **Step 2: Cards**

In `apps/wallet/src/chat/cards/ConfirmCard.tsx` replace the non-waiting badge block:
```tsx
        <Badge variant={state === 'approved' ? 'default' : 'secondary'} className="mt-4">
          {state === 'approved' ? 'Approved' : 'Rejected'}
        </Badge>
```
with:
```tsx
        <Badge variant={state === 'approved' ? 'default' : 'secondary'} className="mt-4">
          {BADGE[state]}
        </Badge>
```
and add above the component:
```tsx
const BADGE: Record<Exclude<ConfirmState, 'waiting'>, string> = {
  approved: 'Approved',
  rejected: 'Rejected',
  expired: 'Expired — ask again',
}
```

Replace `apps/wallet/src/chat/cards/StatusCard.tsx`:
```tsx
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { shortAddress } from '@/lib/format'

type Props = { state: 'pending' | 'success' | 'failed'; text: string; hash?: string }

const ICON = {
  pending: <Loader2 className="size-5 animate-spin text-muted-foreground" />,
  success: <CheckCircle2 className="size-5 text-primary" />,
  failed: <XCircle className="size-5 text-destructive" />,
}

export function StatusCard({ state, text, hash }: Props) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border bg-card p-4">
      {ICON[state]}
      <div className="min-w-0">
        <p>{text}</p>
        {hash && <p className="truncate font-mono text-xs text-muted-foreground">Tx {shortAddress(hash)}</p>}
      </div>
    </div>
  )
}
```

In `apps/wallet/src/chat/MessageItem.tsx` make simulate optional: change `onSimulate: (task: Task) => void` to `onSimulate?: (task: Task) => void`.

- [ ] **Step 3: Faucet button in Receive**

In `apps/wallet/src/components/QrSheet.tsx`:
- Change the lucide import to `import { Camera, ClipboardPaste, Copy, Droplets } from 'lucide-react'` and add `import { requestFunds } from '@/chain/faucet'`.
- Add state and handler inside the component, after `const [proposal, setProposal] = ...`:
```tsx
  const [funding, setFunding] = useState(false)

  async function fund() {
    setFunding(true)
    try {
      toast.success(`Added ${await requestFunds(address)}`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Faucet failed')
    } finally {
      setFunding(false)
    }
  }
```
- In the Receive tab, insert after the "Copy address" button:
```tsx
              <Button className="w-full" onClick={fund} disabled={funding}>
                <Droplets /> {funding ? 'Adding test funds…' : 'Get test funds'}
              </Button>
```

- [ ] **Step 4: Wire the wallet page**

In `apps/wallet/src/routes/WalletPage.tsx`:
- Replace `import { useChat } from '@/chat/useChat'` with `import { useAgentChat } from '@/agent/useAgentChat'`.
- Replace `import { say, simulateTrigger } from '@/mock/agent'` with `import { say } from '@/mock/agent'`.
- Replace the line `const chat = useChat({ contacts, speakEnabled, onTask: (t) => setTasks((prev) => [...prev, t]) })` with:
```tsx
  const chat = useAgentChat({ address: active?.address, mnemonic: active?.mnemonic, contacts, speakEnabled })
```
- Remove the `onSimulate={(t) => chat.deliver(simulateTrigger(t))}` prop from `<ChatView>`.

Delete `apps/wallet/src/chat/useChat.ts`.

- [ ] **Step 5: Verify**

Run: `pnpm --filter wallet test && pnpm --filter wallet build && pnpm --filter wallet lint`
Expected: all pass (lint: only the pre-existing shadcn `only-export-components` warnings).

Manual (agent and sandbox running, see Task 10 for env): open the wallet → create wallet → Receive → Get test funds → toast "Added 10 ETH, 10,000 USDC, …" → "What's my balance?" → balance card with real amounts → "Send 0.1 ETH to Alice" → Approve → status "Confirmed on Sandbox." → agent says it was sent. Stop the agent → chat shows the offline notice; restart → messages work again.

- [ ] **Step 6: Commit**

```bash
git add -A apps/wallet
git commit -m "feat(wallet): connect chat to the real agent and sign transfers with viem"
```

---

### Task 10: Live demo script, docs, full verification

**Files:**
- Create: `agent/scripts/demo.py`, `agent/README.md` (replace), `anvil/README.md` (replace)
- Modify: `README.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: Task 6 `Session`, `connect_claude`; Task 4 `RpcChain`, `load_settings`, `ROOT`

- [ ] **Step 1: Demo script**

`agent/scripts/demo.py`:
```python
"""Live end-to-end check through the real model, using your Claude Code login.

Prereqs: `pnpm dev:sandbox` running, and a test wallet from
`uv run --directory anvil python scripts/seed.py`.
Usage: uv run --directory agent python scripts/demo.py
"""

import asyncio
import json

from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3

from lazyagent.chain import RpcChain
from lazyagent.claude import connect_claude
from lazyagent.config import ROOT, load_settings
from lazyagent.session import Session

ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
PROMPTS = ["What's my balance?", "Send 0.01 ETH to Alice", "Swap 10 USDC for ETH"]


async def main() -> None:
    settings = load_settings()
    wallet = json.loads((ROOT / "anvil" / ".test-wallet.json").read_text())
    w3 = AsyncWeb3(AsyncHTTPProvider(settings.rpc_url))
    turn_done = asyncio.Event()
    session: Session

    async def approve(msg: dict) -> None:
        req = msg["tx"]["request"]
        tx = {
            "from": wallet["address"],
            "to": req["to"],
            "value": int(req["value"]),
            "data": req["data"],
            "chainId": 1,
            "nonce": await w3.eth.get_transaction_count(wallet["address"]),
            "gasPrice": await w3.eth.gas_price,
        }
        tx["gas"] = await w3.eth.estimate_gas(tx)
        signed = Account.sign_transaction(tx, wallet["private_key"])
        tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)
        status = "success" if receipt["status"] == 1 else "reverted"
        print(f"\n  [auto-approved, {status}: {tx_hash.to_0x_hex()}]")
        await session.handle({"type": "tx_result", "id": msg["id"], "outcome": "approved", "hash": tx_hash.to_0x_hex(), "status": status})

    async def send(msg: dict) -> None:
        kind = msg["type"]
        if kind == "text_delta":
            print(msg["text"], end="", flush=True)
        elif kind == "confirm":
            print(f"\n  [confirm card: {msg['tx']['title']}]", end="")
            asyncio.create_task(approve(msg))
        elif kind == "balances":
            print(f"\n  [balance card: {msg['holdings']}]")
        elif kind == "error":
            print(f"\n  [error: {msg['message']}]")
        elif kind == "turn_end":
            print()
            turn_done.set()

    async def factory(tools):
        return await connect_claude(tools, settings)

    session = Session(send, RpcChain(settings.rpc_url), factory)
    try:
        for prompt in PROMPTS:
            print(f"\n> {prompt}")
            turn_done.clear()
            await session.handle(
                {"type": "user", "text": prompt, "spoken": False, "address": wallet["address"], "contacts": [{"name": "Alice", "address": ALICE}]}
            )
            await turn_done.wait()
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Docs**

`anvil/README.md`:
````markdown
# anvil — Sandbox chain

Anvil fork of Ethereum mainnet (chain id 1) plus a faucet. Needs `ETH_RPC_URL` (archive RPC) in the repo-root `.env`.

```bash
pnpm dev:sandbox                                   # Anvil :8545 + faucet :8547
uv run --directory anvil python scripts/seed.py    # random funded test wallet → anvil/.test-wallet.json
uv run --directory anvil python scripts/reset.py   # reset the fork
uv run --directory anvil pytest -q                 # tests (fork tests skip without ETH_RPC_URL)
```

Faucet: `POST http://localhost:8547/fund {"address": "0x…"}` → 10 ETH, 10,000 USDC/USDT/DAI, 1 WBTC, 5 WETH (balances written directly into token storage).
````

`agent/README.md`:
````markdown
# agent — LazyWallet AI agent

FastAPI WebSocket server (`ws://localhost:8787/ws`) running Claude through the Claude Agent SDK. Uses your **Claude Code login** (no API key). Built-in Claude Code tools are disabled; the agent only has wallet tools: `get_balances`, `resolve_recipient`, `propose_transfer`, `unsupported_action`.

```bash
claude                                            # once: make sure Claude Code is logged in
pnpm dev:agent                                    # start the agent (needs pnpm dev:sandbox)
uv run --directory agent pytest -q                # tests (no Claude calls; fork tests skip without ETH_RPC_URL)
uv run --directory agent python scripts/demo.py   # live check with the real model + seeded test wallet
```

Env (repo-root `.env`, all optional): `AGENT_MODEL` (default `claude-sonnet-5-5`), `SANDBOX_RPC_URL`, `WALLET_ORIGINS`, `AGENT_PORT`. If `ANTHROPIC_API_KEY` is set in your shell, Claude Code uses it instead of your login.
````

In `README.md`:
- Replace the status note with:
```markdown
> **Status: Phase 2 — minimum viable AI wallet.** The chat runs on a real Claude agent. Balances and ETH/ERC-20 sends are real on "Sandbox" (an Anvil fork of Ethereum mainnet). Swaps, bridges, scheduled tasks and WalletConnect are still mocked or "coming soon".
```
- In the repo layout table, change the `agent/` row to `Python agent (FastAPI + Claude Agent SDK) — ws://localhost:8787/ws` and the `anvil/` row to `Anvil mainnet fork :8545 + faucet :8547`.
- Replace the "Getting started" section with:
````markdown
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

Voice input uses the browser's Web Speech API — use Chrome or Edge.
````
- Replace the "Try it" list with: create a wallet → Receive → **Get test funds**; then "What's my balance?", "Send 0.1 ETH to Alice", "Send 50 USDC to Bob".
- In the roadmap mark Phase 2 as current.

In `CLAUDE.md`:
- "Current phase" → `Phase 2: minimum viable AI wallet. Spec: docs/superpowers/specs/2026-10-14-lazywallet-mvp-agent-design.md.`
- "Stack & layout": replace the placeholder line with `agent/` (Python, uv, FastAPI + claude-agent-sdk; Claude Code login, built-in tools disabled, wallet MCP tools only) and `anvil/` (Python, uv; Anvil fork chain id 1 + faucet).
- Commands: add `pnpm dev:sandbox`, `pnpm dev:agent`, `pnpm test:py`.
- Real vs mock boundary: Real adds `agent/` (balances, transfers), `chain/` (viem signing), faucet. Mock: WalletConnect, scheduled tasks, swaps.
- Add: "The model never builds calldata — `agent/lazyagent/transfers.py` does. Every transfer goes through `propose_transfer` and the browser's Approve."

- [ ] **Step 3: Full verification**

Run:
```bash
pnpm test && pnpm build && pnpm lint && pnpm test:py
```
Expected: all pass (fork tests skipped if `ETH_RPC_URL` missing).

With `ETH_RPC_URL` set and Claude Code logged in:
```bash
pnpm dev:sandbox &                                   # wait for "Sandbox ready"
uv run --directory anvil python scripts/seed.py
uv run --directory agent python scripts/demo.py
```
Expected: a balance summary, a confirm card for 0.01 ETH that auto-approves with `success`, a spoken-style confirmation, and a "coming soon" reply for the swap. Then run the manual wallet walkthrough from Task 9 Step 5. Stop all servers.

- [ ] **Step 4: Commit**

```bash
git add agent anvil README.md CLAUDE.md
git commit -m "docs: phase 2 setup, agent/anvil READMEs and live demo script"
```
