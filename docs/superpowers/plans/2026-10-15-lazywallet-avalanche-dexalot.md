# LazyWallet Phase 4 — Avalanche + Dexalot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run an Avalanche C-Chain fork next to the Ethereum fork so the user can see balances, send and swap (via Dexalot SimpleSwap) on both networks with no chain switching, plus a tappable network-choice card.

**Architecture:** The sandbox (`anvil/`) runs two Anvil forks and one faucet service; on the Avalanche fork it patches Dexalot's RFQ makers' immutable `swapSigner` (bytecode) to a sandbox key and serves `POST /dexalot/quote` (live Dexalot price → sandbox-signed order). The agent gets a network registry, one `RpcChain` per network, network resolution with a `choice` message, and a Dexalot calldata module. The wallet signs each step on the client for that step's `chainId` and renders a `ChoiceCard`.

**Tech Stack:** Python 3.12+ (uv, FastAPI, web3.py 8, eth-account, pytest-asyncio), Anvil (Foundry), React + TypeScript + viem + Vitest, shadcn/ui.

**Spec:** `docs/superpowers/specs/2026-10-15-lazywallet-avalanche-dexalot-design.md`

## Global Constraints

- Networks: Ethereum fork chain id `1` on `:8545`; Avalanche fork chain id `43114` on `:8546`; faucet/sandbox service `:8547`.
- Avalanche fork source: `AVAX_RPC_URL` (root `.env`), default `https://api.avax.network/ext/bc/C/rpc`. Agent/wallet reach the local fork via `SANDBOX_AVAX_RPC_URL` / `VITE_SANDBOX_AVAX_RPC_URL` (default `http://127.0.0.1:8546` / `http://localhost:8546`).
- Avalanche tokens (symbol used in app → address, decimals, balance slot, faucet amount): AVAX native (100); USDC `0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E` 6, slot 9, 10,000; USDT (on-chain `USDt`) `0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7` 6, slot 51, 10,000; BTC.b `0x152b9d0FdC40C096757F570A51E494bd4b943E50` 8, slot 0, 1; WETH.e `0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB` 18, slot 0, 5.
- Chainlink on Avalanche: AVAX/USD `0x0A77230d17318075983913bC2145DB16C7366156`, BTC/USD `0x2779D32d5166BAaa2B2b658333bA7e6Ec0C65743`, ETH/USD `0x976B3D034E162d8bD72D6b9C989d545b839003b0`.
- Dexalot: router `0xf00240e5256e72771b46d095666594E0f40D085c` (`getAllowedRFQs()`), API `https://api.dexalot.com` with header `Origin: https://app.dexalot.com`; EIP-712 domain `{name "Dexalot", version "2", chainId 43114, verifyingContract maker}`.
- Sandbox-signed orders only; expiry = fork block timestamp + 15 min; `nonceAndMeta = (taker << 96) | random 64-bit`.
- The model never builds calldata. The sandbox only returns `{maker, order, signature, pair, price}`; agent `dexalot.py` builds `approve` + `simpleSwap` calldata.
- Every step request the agent sends carries `chainId`. Card row `Network` value = `"<Network> (Sandbox)"`.
- web3.py on Avalanche needs `ExtraDataToPOAMiddleware` (`layer=0`).
- Keys stay in the browser; secrets never stored unencrypted. Sandbox signer key lives in process memory only.
- Spec deviations decided while planning (record in spec, Task 12): pair lookup/pricing lives in the sandbox service (agent doesn't call Dexalot's API); agent env var is `SANDBOX_AVAX_RPC_URL`; network shown via the card's `Network` row (no separate badge); `network` argument only on `propose_transfer` / `propose_swap` (balances and faucet always cover both).

## Review Focus

- Selling an amount whose quote rounds to 0 output (e.g. "swap 0.000001 USDC to AVAX") must refuse with a clear error, never produce a card that pays nothing → test in Task 2 (`maker_amount` of `"0"` raises) and Task 3 (`quote` raises 502 on zero output).
- A tapped choice must not leave the card tappable again, and a typed answer must lock it too → tests in Task 11 (reducer closes on user message; `turn_end` keeps it open).
- One fork down must not break the other network: balances still show the reachable network → test in Task 7 (`get_balances` with failing Avalanche fake).
- Two holdings with the same symbol on different networks (USDC) must both render (React key collision) and both be summed → Task 11 BalanceCard uses `network:symbol` key; Task 7 test asserts two USDC holdings.
- An Avalanche-only pair that Dexalot doesn't list (e.g. "swap AVAX to BTC.b") must return the available pairs, not a stack trace → test in Task 2 (`match_pair` error lists names) and Task 8 (tool surfaces sandbox 404 detail).

---

## File structure

| File | Responsibility |
|---|---|
| `anvil/lazysandbox/rpc.py` | `anvil_command`/`wait_for_rpc` take a chain id; `AVAX_PUBLIC_RPC` |
| `anvil/lazysandbox/sandbox.py` | Start both forks + service |
| `anvil/lazysandbox/tokens.py` | Ethereum + Avalanche faucet tokens |
| `anvil/lazysandbox/faucet.py` | `/fund` both networks; `/dexalot/quote`; lifespan runs the signer patch |
| `anvil/lazysandbox/dexalot.py` (new) | Pure: bytecode patch, pair matching, order build/sign. I/O: `DexalotSandbox` (patch makers, quote) |
| `agent/lazyagent/tokens.py` | Avalanche tokens; `find_token(symbol, tokens=TOKENS)` |
| `agent/lazyagent/networks.py` (new) | `Network`, `NETWORKS`, `find_network`, `candidates`, `pick_network`, `Choice` |
| `agent/lazyagent/chain.py` | `RpcChain(rpc_url, poa=False)` |
| `agent/lazyagent/config.py` | `avax_rpc_url` setting |
| `agent/lazyagent/dexalot.py` (new) | `simpleSwap` calldata, steps, rows, `SandboxQuotes` client |
| `agent/lazyagent/transfers.py`, `swaps.py` | `native` / `network` wording params |
| `agent/lazyagent/tools.py` | Multi-network tools, choice message, Dexalot swap path |
| `agent/lazyagent/session.py`, `server.py`, `prompt.py` | Wiring + prompt |
| `apps/wallet/src/chain/networks.ts` (new) | viem chain defs + `networkName` |
| `apps/wallet/src/lib/wagmi.ts`, `chain/client.ts`, `chain/executeTx.ts` | Per-chain clients and wording |
| `apps/wallet/src/types.ts`, `agent/protocol.ts`, `agent/chatReducer.ts`, `agent/useAgentChat.ts` | `chainId`, `network`, `choice` |
| `apps/wallet/src/chat/cards/ChoiceCard.tsx` (new), `BalanceCard.tsx`, `MessageItem.tsx`, `ChatView.tsx`, `routes/WalletPage.tsx` | UI |

---

### Task 1: Sandbox runs two forks and funds both

**Files:**
- Modify: `anvil/lazysandbox/rpc.py`, `anvil/lazysandbox/sandbox.py`, `anvil/lazysandbox/tokens.py`, `anvil/lazysandbox/faucet.py`, `anvil/tests/conftest.py`, `.env.example`
- Test: `anvil/tests/test_rpc.py`, `anvil/tests/test_faucet.py`

**Interfaces:**
- Produces: `anvil_command(fork_url, fork_block, port, chain_id=1) -> list[str]`; `wait_for_rpc(url, timeout, chain_id=1)`; `AVAX_PUBLIC_RPC`, `AVAX_CHAIN_ID = 43114`; `AVAX_TOKENS`, `AVAX_FAUCET_AMOUNT`; `fund(w3, address, tokens=TOKENS, native_amount=ETH_FAUCET_AMOUNT, native="ETH") -> dict[str,int]`; `summarize_networks(parts: list[tuple[str, dict[str,int]]]) -> str`; `create_app(rpc_url, allowed_origins, avax_rpc_url=None)`; pytest fixture `avax_fork_rpc` (port 8648).

- [ ] **Step 1: Write failing tests**

Append to `anvil/tests/test_rpc.py`:

```python
def test_anvil_command_with_chain_id():
    assert anvil_command("https://rpc.example", None, 8546, 43114) == [
        "anvil", "--fork-url", "https://rpc.example", "--chain-id", "43114", "--port", "8546",
    ]
```

Append to `anvil/tests/test_faucet.py` (and add `summarize_networks` to the import from `lazysandbox.faucet`, `AVAX_TOKENS` to the import from `lazysandbox.tokens`):

```python
def test_summarize_networks_single_network_keeps_old_format():
    assert summarize_networks([("Ethereum", {"ETH": 10**18})]) == "1 ETH"


def test_summarize_networks_groups_by_network():
    parts = [("Ethereum", {"ETH": 100 * 10**18}), ("Avalanche", {"AVAX": 100 * 10**18, "BTC.b": 10**8})]
    assert summarize_networks(parts) == "Ethereum: 100 ETH · Avalanche: 100 AVAX, 1 BTC.b"


async def test_fund_sets_avalanche_balances(avax_fork_rpc):
    w3 = AsyncWeb3(AsyncHTTPProvider(avax_fork_rpc))
    address = Account.create().address
    funded = await fund(w3, address, AVAX_TOKENS, 100, "AVAX")
    assert funded["AVAX"] == 100 * 10**18
    assert await w3.eth.get_balance(address) == 100 * 10**18
    for t in AVAX_TOKENS:
        assert funded[t.symbol] == t.faucet_amount * 10**t.decimals
```

Replace `anvil/tests/conftest.py` with:

```python
import os
import subprocess

import pytest

from lazysandbox.rpc import AVAX_CHAIN_ID, AVAX_PUBLIC_RPC, anvil_command, load_env, wait_for_rpc

TEST_PORT = 8645
AVAX_TEST_PORT = 8648


def _fork(cmd: list[str], rpc: str, chain_id: int):
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for_rpc(rpc, 120, chain_id)
        yield rpc
    finally:
        proc.terminate()
        proc.wait()


@pytest.fixture(scope="session")
def fork_rpc():
    load_env()
    url = os.environ.get("ETH_RPC_URL")
    if not url:
        pytest.skip("ETH_RPC_URL not set")
    cmd = anvil_command(url, os.environ.get("FORK_BLOCK") or None, TEST_PORT)
    yield from _fork(cmd, f"http://127.0.0.1:{TEST_PORT}", 1)


@pytest.fixture(scope="session")
def avax_fork_rpc():
    load_env()
    url = os.environ.get("AVAX_RPC_URL") or AVAX_PUBLIC_RPC
    cmd = anvil_command(url, None, AVAX_TEST_PORT, AVAX_CHAIN_ID)
    yield from _fork(cmd, f"http://127.0.0.1:{AVAX_TEST_PORT}", AVAX_CHAIN_ID)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory anvil pytest -q`
Expected: FAIL — `ImportError: cannot import name 'AVAX_CHAIN_ID'` (and `summarize_networks`).

- [ ] **Step 3: Implement**

`anvil/lazysandbox/rpc.py` — replace `anvil_command` and `wait_for_rpc`, add constants:

```python
AVAX_PUBLIC_RPC = "https://api.avax.network/ext/bc/C/rpc"
AVAX_CHAIN_ID = 43114


def anvil_command(fork_url: str, fork_block: str | None, port: int, chain_id: int = 1) -> list[str]:
    cmd = ["anvil", "--fork-url", fork_url, "--chain-id", str(chain_id), "--port", str(port)]
    if fork_block:
        cmd += ["--fork-block-number", fork_block]
    return cmd


def wait_for_rpc(url: str, timeout: float, chain_id: int = 1) -> None:
    w3 = Web3(HTTPProvider(url))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if w3.eth.chain_id == chain_id:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Anvil at {url} did not become ready within {timeout:.0f}s")
```

`anvil/lazysandbox/tokens.py` — append:

```python
AVAX_TOKENS = [
    Token("USDC", "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E", 6, 9, 10_000),
    Token("USDT", "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7", 6, 51, 10_000),  # on-chain symbol USDt
    Token("BTC.b", "0x152b9d0FdC40C096757F570A51E494bd4b943E50", 8, 0, 1),
    Token("WETH.e", "0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB", 18, 0, 5),
]

AVAX_FAUCET_AMOUNT = 100
```

`anvil/lazysandbox/faucet.py` — change imports, `DECIMALS`, `fund`, add `summarize_networks`, change `create_app`:

```python
from .tokens import AVAX_FAUCET_AMOUNT, AVAX_TOKENS, ETH_FAUCET_AMOUNT, TOKENS

DECIMALS = {"ETH": 18, "AVAX": 18, **{t.symbol: t.decimals for t in TOKENS + AVAX_TOKENS}}


async def fund(w3: AsyncWeb3, address: str, tokens=TOKENS, native_amount: int = ETH_FAUCET_AMOUNT, native: str = "ETH") -> dict[str, int]:
    holder = Web3.to_checksum_address(address)
    amount_native = native_amount * 10**18
    await _rpc(w3, "anvil_setBalance", [holder, hex(amount_native)])
    funded = {native: amount_native}
    for t in tokens:
        amount = t.faucet_amount * 10**t.decimals
        await _rpc(w3, "anvil_setStorageAt", [t.address, balance_storage_key(holder, t.balance_slot), to_word(amount)])
        contract = w3.eth.contract(address=Web3.to_checksum_address(t.address), abi=ERC20_BALANCE_OF)
        actual = await contract.functions.balanceOf(holder).call()
        if actual != amount:
            raise RuntimeError(f"{t.symbol} balance slot {t.balance_slot} is wrong: balanceOf={actual}, expected {amount}")
        funded[t.symbol] = amount
    return funded


def summarize_networks(parts: list[tuple[str, dict[str, int]]]) -> str:
    if len(parts) == 1:
        return summarize(parts[0][1])
    return " · ".join(f"{name}: {summarize(funded)}" for name, funded in parts)
```

In `create_app`, change the signature and `/fund`:

```python
def create_app(rpc_url: str, allowed_origins: list[str], avax_rpc_url: str | None = None) -> FastAPI:
    app = FastAPI(title="LazyWallet Sandbox Faucet")
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_methods=["*"], allow_headers=["*"])
    w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
    avax_w3 = AsyncWeb3(AsyncHTTPProvider(avax_rpc_url)) if avax_rpc_url else None

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    @app.post("/fund")
    async def post_fund(req: FundRequest) -> dict:
        if not Web3.is_address(req.address):
            raise HTTPException(status_code=400, detail="Invalid address")
        try:
            parts = [("Ethereum", await fund(w3, req.address))]
            if avax_w3:
                parts.append(("Avalanche", await fund(avax_w3, req.address, AVAX_TOKENS, AVAX_FAUCET_AMOUNT, "AVAX")))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Sandbox chain error: {e}") from e
        return {"funded": {name: {k: str(v) for k, v in f.items()} for name, f in parts}, "summary": summarize_networks(parts)}

    return app
```

`anvil/lazysandbox/sandbox.py` — replace with:

```python
import os
import subprocess
import sys

import uvicorn

from .faucet import create_app
from .rpc import AVAX_CHAIN_ID, AVAX_PUBLIC_RPC, anvil_command, load_env, wait_for_rpc

ANVIL_PORT = 8545
AVAX_PORT = 8546
FAUCET_PORT = 8547


def main() -> None:
    load_env()
    fork_url = os.environ.get("ETH_RPC_URL")
    if not fork_url:
        sys.exit("ETH_RPC_URL is missing — add a mainnet archive RPC to .env (see .env.example).")
    avax_url = os.environ.get("AVAX_RPC_URL") or AVAX_PUBLIC_RPC
    origins = os.environ.get("WALLET_ORIGINS", "http://localhost:5174").split(",")
    procs = [
        subprocess.Popen(anvil_command(fork_url, os.environ.get("FORK_BLOCK") or None, ANVIL_PORT)),
        subprocess.Popen(anvil_command(avax_url, None, AVAX_PORT, AVAX_CHAIN_ID)),
    ]
    rpc = f"http://127.0.0.1:{ANVIL_PORT}"
    avax_rpc = f"http://127.0.0.1:{AVAX_PORT}"
    try:
        wait_for_rpc(rpc, 120)
        wait_for_rpc(avax_rpc, 120, AVAX_CHAIN_ID)
        print(
            f"Sandbox ready: Ethereum fork {rpc} (chain id 1), Avalanche fork {avax_rpc} (chain id {AVAX_CHAIN_ID}), "
            f"faucet http://127.0.0.1:{FAUCET_PORT}",
            flush=True,
        )
        uvicorn.run(create_app(rpc, origins, avax_rpc), host="127.0.0.1", port=FAUCET_PORT)
    finally:
        for p in procs:
            p.terminate()
            p.wait()
```

`.env.example` — append:

```
# Optional: Avalanche C-Chain RPC the Avalanche fork starts from (default: public api.avax.network)
AVAX_RPC_URL=
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory anvil pytest -q`
Expected: PASS (fork tests need network; `test_fund_sets_avalanche_balances` forks the public Avalanche RPC).

- [ ] **Step 5: Commit**

```bash
git add anvil .env.example
git commit -m "feat(sandbox): run an Avalanche C-Chain fork and fund both networks"
```

---

### Task 2: Sandbox Dexalot order logic (pure)

**Files:**
- Create: `anvil/lazysandbox/dexalot.py`
- Test: `anvil/tests/test_dexalot.py`

**Interfaces:**
- Produces (all in `lazysandbox.dexalot`): `NATIVE`, `ROUTER`, `API`, `API_HEADERS`, `EXPIRY_S = 900`, `CHAIN_ID = 43114`; `class QuoteError(Exception)` with `.status: int`; `@dataclass Pair(name, base, quote, base_symbol, quote_symbol, base_decimals, quote_decimals)`; `patch_code(code_hex, old, new) -> tuple[str, int]`; `parse_pairs(data: dict) -> list[Pair]`; `match_pair(pairs, token_in, token_out) -> tuple[Pair, int, bool]` (`side`, `is_base` = token_in is the pair's base); `to_raw(amount: str, decimals) -> int`; `maker_amount(price: dict, pair, is_base) -> int`; `build_order(maker, taker, token_in, token_out, amount_in, amount_out, now, nonce=None) -> dict[str, int|str]`; `typed_data(order) -> dict`; `sign_order(key, order) -> str`.

- [ ] **Step 1: Write the failing tests**

`anvil/tests/test_dexalot.py`:

```python
import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data

from lazysandbox.dexalot import (
    NATIVE, Pair, QuoteError, build_order, maker_amount, match_pair, parse_pairs, patch_code, sign_order, to_raw, typed_data,
)

USDC = "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E"
USDT = "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7"
BTCB = "0x152b9d0FdC40C096757F570A51E494bd4b943E50"
OLD = "0x08ea7d927d13802C3bc4b35B10e394f34a53Fa72"
NEW = "0x458e84C455c1D358EE67D0EE4D144d9B169AEb34"
TAKER = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
MAKER = "0x1FDb2b265d2A5C4302A75cAd682222E4e7bCc313"
PAIRS_JSON = {
    "AVAX/USDC": {"base": "AVAX", "quote": "USDC", "baseAddress": NATIVE, "quoteAddress": USDC, "baseDecimals": 18, "quoteDecimals": 6},
    "BTC.b/USDC": {"base": "BTC.b", "quote": "USDC", "baseAddress": BTCB, "quoteAddress": USDC, "baseDecimals": 8, "quoteDecimals": 6},
}


def test_patch_code_replaces_every_aligned_occurrence():
    word = "7f" + "00" * 12 + OLD[2:].lower()
    code = "0x6080" + word + "5b" + word
    patched, n = patch_code(code, OLD, NEW)
    assert n == 2
    assert OLD[2:].lower() not in patched and patched.count(NEW[2:].lower()) == 2
    assert len(patched) == len(code)


def test_patch_code_counts_zero_when_absent():
    assert patch_code("0x6080", OLD, NEW) == ("0x6080", 0)


def test_match_pair_selling_base_and_quote():
    pairs = parse_pairs(PAIRS_JSON)
    pair, side, is_base = match_pair(pairs, NATIVE, USDC)
    assert (pair.name, side, is_base) == ("AVAX/USDC", 1, True)
    pair, side, is_base = match_pair(pairs, USDC.lower(), NATIVE)
    assert (pair.name, side, is_base) == ("AVAX/USDC", 0, False)


def test_match_pair_unknown_lists_available():
    with pytest.raises(QuoteError, match="AVAX/USDC, BTC.b/USDC") as e:
        match_pair(parse_pairs(PAIRS_JSON), NATIVE, BTCB)
    assert e.value.status == 404


def test_maker_amount_uses_the_other_side():
    pair = parse_pairs(PAIRS_JSON)[0]
    reply = {"success": True, "baseAmount": "1.045915699194644911", "quoteAmount": "10"}
    assert maker_amount(reply, pair, True) == 10_000_000
    assert maker_amount(reply, pair, False) == 1_045_915_699_194_644_911
    assert to_raw("9.5749999", 6) == 9_574_999


def test_maker_amount_refuses_failed_or_zero_quotes():
    pair = parse_pairs(PAIRS_JSON)[0]
    with pytest.raises(QuoteError) as e:
        maker_amount({"success": False}, pair, True)
    assert e.value.status == 502
    with pytest.raises(QuoteError, match="too small"):
        maker_amount({"success": True, "quoteAmount": "0", "baseAmount": "0"}, pair, True)


def test_build_order_layout():
    order = build_order(MAKER, TAKER, NATIVE, USDC, 10**18, 9_574_000, now=1_000, nonce=7)
    assert order["nonceAndMeta"] == (int(TAKER, 16) << 96) | 7
    assert (order["nonceAndMeta"] >> 88) & 0xFF == 0  # slipInfo byte must stay 0
    assert order["expiry"] == 1_000 + 900
    assert (order["makerAsset"], order["takerAsset"]) == (USDC, NATIVE)
    assert (order["makerAmount"], order["takerAmount"]) == (9_574_000, 10**18)


def test_sign_order_recovers_to_signer():
    signer = Account.create()
    order = build_order(MAKER, TAKER, NATIVE, USDC, 10**18, 9_574_000, now=1_000, nonce=7)
    sig = sign_order(signer.key, order)
    assert Account.recover_message(encode_typed_data(full_message=typed_data(order)), signature=sig) == signer.address
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory anvil pytest tests/test_dexalot.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lazysandbox.dexalot'`.

- [ ] **Step 3: Implement**

`anvil/lazysandbox/dexalot.py`:

```python
"""Dexalot SimpleSwap on the Avalanche fork: sandbox-signed orders at Dexalot's live price.

Dexalot only signs firm quotes for addresses holding real mainnet funds, so on the fork we patch the RFQ
makers' immutable swapSigner to a sandbox key and sign orders ourselves. Never used on a real network."""

import secrets
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from eth_account import Account
from web3 import Web3

CHAIN_ID = 43114
NATIVE = "0x0000000000000000000000000000000000000000"
ROUTER = "0xf00240e5256e72771b46d095666594E0f40D085c"
API = "https://api.dexalot.com"
API_HEADERS = {"Origin": "https://app.dexalot.com", "User-Agent": "lazywallet-sandbox"}
EXPIRY_S = 15 * 60
ORDER_FIELDS = [
    ("nonceAndMeta", "uint256"), ("expiry", "uint128"), ("makerAsset", "address"), ("takerAsset", "address"),
    ("maker", "address"), ("taker", "address"), ("makerAmount", "uint256"), ("takerAmount", "uint256"),
]


class QuoteError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Pair:
    name: str
    base: str
    quote: str
    base_symbol: str
    quote_symbol: str
    base_decimals: int
    quote_decimals: int


def patch_code(code: str, old: str, new: str) -> tuple[str, int]:
    """Replace every byte-aligned occurrence of address `old` in runtime bytecode with `new`."""
    body = bytes.fromhex(code.removeprefix("0x"))
    o, n = bytes.fromhex(old.removeprefix("0x")), bytes.fromhex(new.removeprefix("0x"))
    return "0x" + body.replace(o, n).hex(), body.count(o)


def parse_pairs(data: dict) -> list[Pair]:
    return [
        Pair(name, p["baseAddress"], p["quoteAddress"], p["base"], p["quote"], int(p["baseDecimals"]), int(p["quoteDecimals"]))
        for name, p in data.items()
    ]


def match_pair(pairs: list[Pair], token_in: str, token_out: str) -> tuple[Pair, int, bool]:
    """Pair for selling token_in for token_out: side 1 sells the base, side 0 buys it."""
    tin, tout = token_in.lower(), token_out.lower()
    for p in pairs:
        if (p.base.lower(), p.quote.lower()) == (tin, tout):
            return p, 1, True
        if (p.base.lower(), p.quote.lower()) == (tout, tin):
            return p, 0, False
    raise QuoteError(404, f"Dexalot doesn't offer that pair. Available: {', '.join(p.name for p in pairs)}.")


def to_raw(amount: str, decimals: int) -> int:
    return int(Decimal(amount).scaleb(decimals).to_integral_value(ROUND_DOWN))


def maker_amount(price: dict, pair: Pair, is_base: bool) -> int:
    """Output of a pairprice reply: selling the base pays out quote tokens, selling the quote pays out base tokens."""
    if not price.get("success"):
        raise QuoteError(502, f"Dexalot isn't quoting {pair.name} right now — try again shortly.")
    out = to_raw(price["quoteAmount"], pair.quote_decimals) if is_base else to_raw(price["baseAmount"], pair.base_decimals)
    if out <= 0:
        raise QuoteError(502, "That amount is too small for Dexalot to quote.")
    return out


def build_order(maker: str, taker: str, token_in: str, token_out: str, amount_in: int, amount_out: int, now: int, nonce: int | None = None) -> dict:
    return {
        "nonceAndMeta": (int(taker, 16) << 96) | (secrets.randbits(64) if nonce is None else nonce),
        "expiry": now + EXPIRY_S,
        "makerAsset": Web3.to_checksum_address(token_out),
        "takerAsset": Web3.to_checksum_address(token_in),
        "maker": Web3.to_checksum_address(maker),
        "taker": Web3.to_checksum_address(taker),
        "makerAmount": amount_out,
        "takerAmount": amount_in,
    }


def typed_data(order: dict) -> dict:
    return {
        "domain": {"name": "Dexalot", "version": "2", "chainId": CHAIN_ID, "verifyingContract": order["maker"]},
        "types": {"Order": [{"name": n, "type": t} for n, t in ORDER_FIELDS]},
        "primaryType": "Order",
        "message": order,
    }


def sign_order(key, order: dict) -> str:
    return Account.sign_typed_data(key, full_message=typed_data(order)).signature.to_0x_hex()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory anvil pytest tests/test_dexalot.py -q`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add anvil/lazysandbox/dexalot.py anvil/tests/test_dexalot.py
git commit -m "feat(sandbox): Dexalot order building, signing and signer bytecode patch"
```

---

### Task 3: Sandbox Dexalot service — patch makers at startup, `POST /dexalot/quote`

**Files:**
- Modify: `anvil/lazysandbox/dexalot.py`, `anvil/lazysandbox/faucet.py`
- Test: `anvil/tests/test_dexalot.py`, `anvil/tests/test_dexalot_fork.py` (new)

**Interfaces:**
- Consumes: Task 2 helpers; Task 1 `create_app(rpc_url, allowed_origins, avax_rpc_url=None)`.
- Produces: `avalanche_w3(url) -> AsyncWeb3` (POA middleware); `class DexalotSandbox(w3, api=API)` with `.signer`, `.makers: list[str]`, `.error: str | None`, `async setup()`, `async quote(token_in, token_out, amount_in: int, taker) -> dict`. HTTP: `POST /dexalot/quote {token_in, token_out, amount_in (decimal string of raw units), taker}` → 200 `{maker, order: {field: str}, signature, pair, price}`; errors 400 invalid address/amount, 404 pair, 409 liquidity, 502 Dexalot not quoting, 503 unavailable.

- [ ] **Step 1: Write failing tests**

Append to `anvil/tests/test_dexalot.py`:

```python
from fastapi.testclient import TestClient
from web3 import AsyncHTTPProvider, AsyncWeb3

from lazysandbox.dexalot import DexalotSandbox
from lazysandbox.faucet import create_app


async def test_quote_refuses_while_unavailable():
    d = DexalotSandbox(AsyncWeb3(AsyncHTTPProvider("http://127.0.0.1:1")))
    d.error = "signer patch failed"
    with pytest.raises(QuoteError, match="unavailable") as e:
        await d.quote(NATIVE, USDC, 10**18, TAKER)
    assert e.value.status == 503


def test_quote_endpoint_without_avalanche_is_503():
    client = TestClient(create_app("http://127.0.0.1:1", ["http://localhost:5174"]))
    res = client.post("/dexalot/quote", json={"token_in": NATIVE, "token_out": USDC, "amount_in": "1", "taker": TAKER})
    assert res.status_code == 503


def test_quote_endpoint_validates_input():
    client = TestClient(create_app("http://127.0.0.1:1", ["http://localhost:5174"], "http://127.0.0.1:1"))
    res = client.post("/dexalot/quote", json={"token_in": "nope", "token_out": USDC, "amount_in": "1", "taker": TAKER})
    assert res.status_code == 400
    res = client.post("/dexalot/quote", json={"token_in": NATIVE, "token_out": USDC, "amount_in": "-1", "taker": TAKER})
    assert res.status_code == 400
```

`anvil/tests/test_dexalot_fork.py`:

```python
from eth_account import Account

from lazysandbox.dexalot import NATIVE, DexalotSandbox, avalanche_w3

USDC = "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E"
RFQ_ABI = [
    {"name": "swapSigner", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "address"}]},
    {
        "name": "simpleSwap", "type": "function", "stateMutability": "payable", "outputs": [],
        "inputs": [
            {"name": "_order", "type": "tuple", "components": [
                {"name": n, "type": t} for n, t in [
                    ("nonceAndMeta", "uint256"), ("expiry", "uint128"), ("makerAsset", "address"), ("takerAsset", "address"),
                    ("maker", "address"), ("taker", "address"), ("makerAmount", "uint256"), ("takerAmount", "uint256"),
                ]
            ]},
            {"name": "_signature", "type": "bytes"},
        ],
    },
]
BALANCE_OF = [{"name": "balanceOf", "type": "function", "stateMutability": "view", "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}]}]


async def test_setup_patches_every_maker(avax_fork_rpc):
    w3 = avalanche_w3(avax_fork_rpc)
    d = DexalotSandbox(w3)
    await d.setup()
    assert d.error is None and len(d.makers) >= 1
    for m in d.makers:
        assert await w3.eth.contract(address=m, abi=RFQ_ABI).functions.swapSigner().call() == d.signer.address


async def test_sandbox_signed_quote_executes(avax_fork_rpc):
    w3 = avalanche_w3(avax_fork_rpc)
    d = DexalotSandbox(w3)
    await d.setup()
    user = Account.create()
    await w3.provider.make_request("anvil_setBalance", [user.address, hex(10 * 10**18)])
    q = await d.quote(NATIVE, USDC, 10**18, user.address)
    o = q["order"]
    order = (int(o["nonceAndMeta"]), int(o["expiry"]), o["makerAsset"], o["takerAsset"], o["maker"], o["taker"], int(o["makerAmount"]), int(o["takerAmount"]))
    rfq = w3.eth.contract(address=q["maker"], abi=RFQ_ABI)
    tx = await rfq.functions.simpleSwap(order, bytes.fromhex(q["signature"][2:])).build_transaction(
        {"from": user.address, "value": 10**18, "nonce": await w3.eth.get_transaction_count(user.address)}
    )
    receipt = await w3.eth.wait_for_transaction_receipt(await w3.eth.send_raw_transaction(user.sign_transaction(tx).raw_transaction))
    assert receipt["status"] == 1
    usdc = w3.eth.contract(address=USDC, abi=BALANCE_OF)
    assert await usdc.functions.balanceOf(user.address).call() == int(o["makerAmount"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory anvil pytest tests/test_dexalot.py tests/test_dexalot_fork.py -q`
Expected: FAIL — `ImportError: cannot import name 'DexalotSandbox'`.

- [ ] **Step 3: Implement**

Append to `anvil/lazysandbox/dexalot.py` (add imports at top: `import asyncio`, `import json`, `import time`, `import urllib.error`, `import urllib.parse`, `import urllib.request`, `from web3 import AsyncHTTPProvider, AsyncWeb3`, `from web3.middleware import ExtraDataToPOAMiddleware`):

```python
PAIRS_TTL_S = 3600
ROUTER_ABI = [{"name": "getAllowedRFQs", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "address[]"}]}]
SIGNER_ABI = [{"name": "swapSigner", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "address"}]}]
BALANCE_OF = [{"name": "balanceOf", "type": "function", "stateMutability": "view", "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}]}]


def avalanche_w3(url: str) -> AsyncWeb3:
    w3 = AsyncWeb3(AsyncHTTPProvider(url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)  # Avalanche blocks carry long extraData
    return w3


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=API_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.loads(res.read())
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise QuoteError(502, f"Dexalot's API isn't reachable right now ({e}).") from e


class DexalotSandbox:
    def __init__(self, w3: AsyncWeb3, api: str = API):
        self.w3 = w3
        self.api = api
        self.signer = Account.create()  # process memory only
        self.makers: list[str] = []
        self.error: str | None = "not set up yet"
        self._pairs: list[Pair] = []
        self._pairs_at = 0.0

    async def _rpc(self, method: str, params: list) -> None:
        res = await self.w3.provider.make_request(method, params)
        if "error" in res:
            raise RuntimeError(f"{method} failed: {res['error']}")

    async def setup(self) -> None:
        """Make every Dexalot RFQ maker on the fork trust the sandbox signer (swapSigner is immutable → bytecode)."""
        router = self.w3.eth.contract(address=ROUTER, abi=ROUTER_ABI)
        makers = []
        for m in await router.functions.getAllowedRFQs().call():
            rfq = self.w3.eth.contract(address=m, abi=SIGNER_ABI)
            try:
                old = await rfq.functions.swapSigner().call()
            except Exception:
                continue  # not a signer-based maker
            code = (await self.w3.eth.get_code(m)).to_0x_hex()
            patched, n = patch_code(code, old, self.signer.address)
            if n == 0:
                raise RuntimeError(f"signer {old} not found in {m} bytecode")
            await self._rpc("anvil_setCode", [m, patched])
            if (await rfq.functions.swapSigner().call()).lower() != self.signer.address.lower():
                raise RuntimeError(f"patched {m} still reports another swapSigner")
            makers.append(m)
        if not makers:
            raise RuntimeError("no Dexalot RFQ makers found")
        self.makers, self.error = makers, None

    async def pairs(self) -> list[Pair]:
        if not self._pairs or time.monotonic() - self._pairs_at > PAIRS_TTL_S:
            self._pairs = parse_pairs(await asyncio.to_thread(_get_json, f"{self.api}/api/rfq/pairs?chainid={CHAIN_ID}"))
            self._pairs_at = time.monotonic()
        return self._pairs

    async def _holding(self, maker: str, token: str) -> int:
        if token.lower() == NATIVE:
            return await self.w3.eth.get_balance(maker)
        return await self.w3.eth.contract(address=Web3.to_checksum_address(token), abi=BALANCE_OF).functions.balanceOf(maker).call()

    async def quote(self, token_in: str, token_out: str, amount_in: int, taker: str) -> dict:
        if self.error:
            raise QuoteError(503, f"Dexalot swaps are unavailable on this Sandbox ({self.error}).")
        pair, side, is_base = match_pair(await self.pairs(), token_in, token_out)
        decimals = pair.base_decimals if is_base else pair.quote_decimals
        query = urllib.parse.urlencode({
            "chainid": CHAIN_ID, "pair": pair.name, "amount": format(Decimal(amount_in).scaleb(-decimals).normalize(), "f"),
            "isbase": 1 if is_base else 0, "side": side, "taker": taker,
        })
        price = await asyncio.to_thread(_get_json, f"{self.api}/api/rfq/pairprice?{query}")
        out = maker_amount(price, pair, is_base)
        holding, maker = max([(await self._holding(m, token_out), m) for m in self.makers])
        if holding < out:
            symbol = pair.quote_symbol if is_base else pair.base_symbol
            raise QuoteError(409, f"Dexalot doesn't have enough {symbol} on Sandbox for that size — try a smaller amount.")
        now = (await self.w3.eth.get_block("latest"))["timestamp"]
        order = build_order(maker, taker, token_in, token_out, amount_in, out, now)
        return {
            "maker": order["maker"],
            "order": {k: str(v) for k, v in order.items()},
            "signature": sign_order(self.signer.key, order),
            "pair": pair.name,
            "price": price.get("price"),
        }
```

In `anvil/lazysandbox/faucet.py`: add imports `from contextlib import asynccontextmanager` and `from .dexalot import DexalotSandbox, QuoteError, avalanche_w3`; add a request model; build the app with a lifespan and the new route:

```python
class QuoteRequest(BaseModel):
    token_in: str
    token_out: str
    amount_in: str
    taker: str


def create_app(rpc_url: str, allowed_origins: list[str], avax_rpc_url: str | None = None) -> FastAPI:
    w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
    avax_w3 = avalanche_w3(avax_rpc_url) if avax_rpc_url else None
    dexalot = DexalotSandbox(avax_w3) if avax_w3 else None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if dexalot:
            try:
                await dexalot.setup()
                print(f"Dexalot RFQ: {len(dexalot.makers)} makers trust sandbox signer {dexalot.signer.address}", flush=True)
            except Exception as e:
                dexalot.error = str(e)
                print(f"Dexalot RFQ signer patch FAILED — Avalanche swaps disabled: {e}", flush=True)
        yield

    app = FastAPI(title="LazyWallet Sandbox Faucet", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_methods=["*"], allow_headers=["*"])

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    @app.post("/fund")
    async def post_fund(req: FundRequest) -> dict:
        if not Web3.is_address(req.address):
            raise HTTPException(status_code=400, detail="Invalid address")
        try:
            parts = [("Ethereum", await fund(w3, req.address))]
            if avax_w3:
                parts.append(("Avalanche", await fund(avax_w3, req.address, AVAX_TOKENS, AVAX_FAUCET_AMOUNT, "AVAX")))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Sandbox chain error: {e}") from e
        return {"funded": {name: {k: str(v) for k, v in f.items()} for name, f in parts}, "summary": summarize_networks(parts)}

    @app.post("/dexalot/quote")
    async def post_quote(req: QuoteRequest) -> dict:
        if dexalot is None:
            raise HTTPException(status_code=503, detail="The Avalanche Sandbox isn't configured.")
        if not all(Web3.is_address(a) for a in (req.token_in, req.token_out, req.taker)):
            raise HTTPException(status_code=400, detail="Invalid address")
        if not req.amount_in.isdigit() or int(req.amount_in) <= 0:
            raise HTTPException(status_code=400, detail="amount_in must be a positive integer of raw token units")
        try:
            return await dexalot.quote(req.token_in, req.token_out, int(req.amount_in), req.taker)
        except QuoteError as e:
            raise HTTPException(status_code=e.status, detail=str(e)) from e

    return app
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory anvil pytest -q`
Expected: PASS (fork tests need network access to the public Avalanche RPC and `api.dexalot.com`).

- [ ] **Step 5: Commit**

```bash
git add anvil
git commit -m "feat(sandbox): patch Dexalot RFQ signer on the Avalanche fork and serve sandbox-signed quotes"
```

---

### Task 4: Agent token and network registry

**Files:**
- Modify: `agent/lazyagent/tokens.py`
- Create: `agent/lazyagent/networks.py`
- Test: `agent/tests/test_tokens.py`, `agent/tests/test_networks.py` (new)

**Interfaces:**
- Produces: `AVAX: Token`, `AVAX_TOKENS: list[Token]` (AVAX first); `find_token(symbol, tokens=TOKENS) -> Token | None` (case-insensitive on both sides); `Network(key, name, chain_id, native, tokens, swap_venue)` with property `label` → `"Ethereum (Sandbox)"`; `ETHEREUM`, `AVALANCHE`, `NETWORKS`; `find_network(text) -> Network | None` (accepts key, name, "eth", "avax", case-insensitive); `candidates(symbols, networks) -> list[Network]`; `Choice(networks: tuple[Network, ...])`; `pick_network(cands, enough: dict[str, bool]) -> Network | Choice`.

- [ ] **Step 1: Write failing tests**

Append to `agent/tests/test_tokens.py` (extend the import with `AVAX, AVAX_TOKENS`):

```python
def test_avalanche_tokens():
    assert [t.symbol for t in AVAX_TOKENS] == ["AVAX", "USDC", "USDT", "BTC.b", "WETH.e"]
    assert AVAX.address is None and AVAX.price_feed == "0x0A77230d17318075983913bC2145DB16C7366156"
    assert find_token("btc.b", AVAX_TOKENS).decimals == 8
    assert find_token("usdt", AVAX_TOKENS).address == "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7"
    assert find_token("ETH", AVAX_TOKENS) is None
    assert find_token("USDC").address == "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # default stays Ethereum
```

`agent/tests/test_networks.py`:

```python
from lazyagent.networks import AVALANCHE, ETHEREUM, NETWORKS, Choice, candidates, find_network, pick_network


def test_registry():
    assert [n.key for n in NETWORKS] == ["ethereum", "avalanche"]
    assert (ETHEREUM.chain_id, AVALANCHE.chain_id) == (1, 43114)
    assert AVALANCHE.native.symbol == "AVAX" and AVALANCHE.swap_venue == "dexalot"
    assert ETHEREUM.label == "Ethereum (Sandbox)"


def test_find_network_aliases():
    assert find_network("Avalanche") is AVALANCHE
    assert find_network(" avax ") is AVALANCHE
    assert find_network("eth") is ETHEREUM
    assert find_network("solana") is None
    assert find_network(None) is None


def test_candidates_need_every_symbol():
    assert candidates(["ETH"], NETWORKS) == [ETHEREUM]
    assert candidates(["avax", "usdc"], NETWORKS) == [AVALANCHE]
    assert candidates(["USDC"], NETWORKS) == [ETHEREUM, AVALANCHE]
    assert candidates(["USDC", "LIT"], NETWORKS) == [ETHEREUM]
    assert candidates(["DOGE"], NETWORKS) == []
    assert candidates(["USDC"], [ETHEREUM]) == [ETHEREUM]


def test_pick_network():
    both = [ETHEREUM, AVALANCHE]
    assert pick_network([AVALANCHE], {}) is AVALANCHE
    assert pick_network(both, {"ethereum": False, "avalanche": True}) is AVALANCHE
    assert pick_network(both, {"ethereum": True, "avalanche": True}) == Choice((ETHEREUM, AVALANCHE))
    assert pick_network(both, {"ethereum": False, "avalanche": False}) == Choice((ETHEREUM, AVALANCHE))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory agent pytest tests/test_tokens.py tests/test_networks.py -q`
Expected: FAIL — `ImportError: cannot import name 'AVAX'`.

- [ ] **Step 3: Implement**

`agent/lazyagent/tokens.py` — append constants and tokens, replace `find_token`:

```python
AVAX_USD_FEED = "0x0A77230d17318075983913bC2145DB16C7366156"
AVAX_BTC_USD_FEED = "0x2779D32d5166BAaa2B2b658333bA7e6Ec0C65743"
AVAX_ETH_USD_FEED = "0x976B3D034E162d8bD72D6b9C989d545b839003b0"

AVAX = Token("AVAX", None, 18, price_feed=AVAX_USD_FEED)

AVAX_TOKENS = [
    AVAX,
    Token("USDC", "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E", 6, fixed_price=1.0),
    Token("USDT", "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7", 6, fixed_price=1.0),  # on-chain symbol USDt
    Token("BTC.b", "0x152b9d0FdC40C096757F570A51E494bd4b943E50", 8, price_feed=AVAX_BTC_USD_FEED),
    Token("WETH.e", "0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB", 18, price_feed=AVAX_ETH_USD_FEED),
]


def find_token(symbol: str, tokens: list[Token] | tuple[Token, ...] = TOKENS) -> Token | None:
    s = symbol.strip().upper()
    return next((t for t in tokens if t.symbol.upper() == s), None)
```

`agent/lazyagent/networks.py`:

```python
from dataclasses import dataclass

from .tokens import AVAX, AVAX_TOKENS, ETH, TOKENS, Token, find_token


@dataclass(frozen=True)
class Network:
    key: str
    name: str
    chain_id: int
    native: Token
    tokens: tuple[Token, ...]
    swap_venue: str  # "uniswap" | "dexalot"

    @property
    def label(self) -> str:
        return f"{self.name} (Sandbox)"


ETHEREUM = Network("ethereum", "Ethereum", 1, ETH, tuple(TOKENS), "uniswap")
AVALANCHE = Network("avalanche", "Avalanche", 43114, AVAX, tuple(AVAX_TOKENS), "dexalot")
NETWORKS = [ETHEREUM, AVALANCHE]
_ALIASES = {"ethereum": ETHEREUM, "eth": ETHEREUM, "avalanche": AVALANCHE, "avax": AVALANCHE}


@dataclass(frozen=True)
class Choice:
    """More than one network fits; the user has to pick."""

    networks: tuple[Network, ...]


def find_network(text: str | None) -> Network | None:
    return _ALIASES.get(str(text or "").strip().lower())


def candidates(symbols: list[str], networks: list[Network]) -> list[Network]:
    return [n for n in networks if all(find_token(s, n.tokens) for s in symbols)]


def pick_network(cands: list[Network], enough: dict[str, bool]) -> Network | Choice:
    if len(cands) == 1:
        return cands[0]
    fits = [n for n in cands if enough.get(n.key)]
    return fits[0] if len(fits) == 1 else Choice(tuple(cands))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory agent pytest -q`
Expected: PASS (whole suite still green; fork tests may skip without `ETH_RPC_URL`).

- [ ] **Step 5: Commit**

```bash
git add agent/lazyagent/tokens.py agent/lazyagent/networks.py agent/tests/test_tokens.py agent/tests/test_networks.py
git commit -m "feat(agent): Avalanche tokens and network registry"
```

---

### Task 5: Agent reads the Avalanche fork (POA chain, settings, fixtures)

**Files:**
- Modify: `agent/lazyagent/chain.py`, `agent/lazyagent/config.py`, `agent/tests/conftest.py`
- Test: `agent/tests/test_config.py`, `agent/tests/test_chain_avalanche.py` (new)

**Interfaces:**
- Produces: `RpcChain(rpc_url, poa=False)`; `Settings.avax_rpc_url` (env `SANDBOX_AVAX_RPC_URL`, default `http://127.0.0.1:8546`); pytest fixtures `avax_fork_rpc` (port 8649) and `avax_sandbox` → `(rpc_url, sandbox_url)` (sandbox service on 8650, started from `anvil/`).

- [ ] **Step 1: Write failing tests**

In `agent/tests/test_config.py::test_defaults`, add `"SANDBOX_AVAX_RPC_URL"` to the deleted env keys and assert:

```python
    assert s.avax_rpc_url == "http://127.0.0.1:8546"
```

`agent/tests/test_chain_avalanche.py`:

```python
from lazyagent.chain import RpcChain
from lazyagent.tokens import AVAX, AVAX_TOKENS, find_token


async def test_avalanche_prices_blocks_and_calls(avax_fork_rpc):
    chain = RpcChain(avax_fork_rpc, poa=True)
    assert 1 < await chain.price_usd(AVAX) < 10_000
    assert 1_000 < await chain.price_usd(find_token("BTC.b", AVAX_TOKENS)) < 1_000_000
    assert 100 < await chain.price_usd(find_token("WETH.e", AVAX_TOKENS)) < 100_000
    assert await chain.block_timestamp() > 1_700_000_000
    assert await chain.is_sandbox() is True
    usdc = find_token("USDC", AVAX_TOKENS)
    assert int.from_bytes(await chain.call(usdc.address, "0x313ce567"), "big") == 6
```

Replace `agent/tests/conftest.py` with:

```python
import os
import subprocess
import time
import urllib.request

import pytest
from web3 import HTTPProvider, Web3

from lazyagent.config import ROOT

TEST_PORT = 8646
AVAX_TEST_PORT = 8649
SANDBOX_TEST_PORT = 8650
AVAX_PUBLIC_RPC = "https://api.avax.network/ext/bc/C/rpc"


def _wait(check, what: str, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"{what} did not start")


def _anvil(url: str, port: int, chain_id: int, block: str | None = None):
    cmd = ["anvil", "--fork-url", url, "--chain-id", str(chain_id), "--port", str(port)]
    if block:
        cmd += ["--fork-block-number", block]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = f"http://127.0.0.1:{port}"
    try:
        _wait(lambda: Web3(HTTPProvider(rpc)).eth.chain_id == chain_id, "test fork")
        yield rpc
    finally:
        proc.terminate()
        proc.wait()


@pytest.fixture(scope="session")
def fork_rpc():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    url = os.environ.get("ETH_RPC_URL")
    if not url:
        pytest.skip("ETH_RPC_URL not set")
    yield from _anvil(url, TEST_PORT, 1, os.environ.get("FORK_BLOCK") or None)


@pytest.fixture(scope="session")
def avax_fork_rpc():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    yield from _anvil(os.environ.get("AVAX_RPC_URL") or AVAX_PUBLIC_RPC, AVAX_TEST_PORT, 43114)


@pytest.fixture(scope="session")
def avax_sandbox(avax_fork_rpc):
    """The real sandbox service (anvil/) pointed at the Avalanche test fork, for end-to-end Dexalot swaps."""
    code = (
        "import uvicorn; from lazysandbox.faucet import create_app; "
        f"uvicorn.run(create_app('http://127.0.0.1:1', ['http://localhost:5174'], '{avax_fork_rpc}'), "
        f"host='127.0.0.1', port={SANDBOX_TEST_PORT}, log_level='warning')"
    )
    proc = subprocess.Popen(["uv", "run", "--directory", str(ROOT / "anvil"), "python", "-c", code])
    url = f"http://127.0.0.1:{SANDBOX_TEST_PORT}"
    try:
        # Startup (incl. the signer patch) finishes before the server answers /health.
        _wait(lambda: urllib.request.urlopen(f"{url}/health", timeout=2).status == 200, "sandbox service", 180)
        yield avax_fork_rpc, url
    finally:
        proc.terminate()
        proc.wait()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory agent pytest tests/test_config.py tests/test_chain_avalanche.py -q`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'avax_rpc_url'` and `TypeError: RpcChain.__init__() got an unexpected keyword argument 'poa'`.

- [ ] **Step 3: Implement**

`agent/lazyagent/chain.py` — add import `from web3.middleware import ExtraDataToPOAMiddleware` and change the constructor:

```python
class RpcChain:
    def __init__(self, rpc_url: str, poa: bool = False):
        self.w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        if poa:
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)  # Avalanche blocks carry long extraData
```

`agent/lazyagent/config.py` — add field `avax_rpc_url: str` to `Settings` (after `rpc_url`) and in `load_settings`:

```python
        avax_rpc_url=os.environ.get("SANDBOX_AVAX_RPC_URL") or "http://127.0.0.1:8546",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory agent pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/lazyagent/chain.py agent/lazyagent/config.py agent/tests/conftest.py agent/tests/test_config.py agent/tests/test_chain_avalanche.py
git commit -m "feat(agent): read the Avalanche fork (POA middleware, settings, test fixtures)"
```

---

### Task 6: Agent Dexalot calldata, steps, rows and quote client

**Files:**
- Create: `agent/lazyagent/dexalot.py`
- Test: `agent/tests/test_dexalot.py` (new)

**Interfaces:**
- Consumes: `Step` (`swaps.py`), `encode_erc20_approve(spender, amount)` (`uniswap.py`), `display_units`, `format_units`, `format_usd`, `short`, `TransferError`, `faucet._post(url, payload) -> (status, body)`.
- Produces: `NATIVE`; `asset_of(token) -> str`; `encode_simple_swap(order: dict[str, str], signature: str) -> str`; `dexalot_steps(token_in, token_out, quote: dict, allowance: int) -> list[Step]`; `dexalot_rows(sender, token_in, token_out, amount, received, fee_usd, network_label) -> list[dict]`; `DEXALOT_REVERT_HINT: str`; `GAS = {"approve": 60_000, "swap": 140_000}`; `class Quotes(Protocol)` with `async quote(token_in: str, token_out: str, amount_in: int, taker: str) -> dict`; `class SandboxQuotes(url)` implementing it (non-200 → `TransferError(detail)`; unreachable → `TransferError("The Sandbox service isn't reachable — start it with `pnpm dev:sandbox`.")`).

- [ ] **Step 1: Write the failing tests**

`agent/tests/test_dexalot.py`:

```python
import pytest
from test_faucet_client import serve
from web3 import Web3

from lazyagent.dexalot import NATIVE, SandboxQuotes, asset_of, dexalot_rows, dexalot_steps, encode_simple_swap
from lazyagent.tokens import AVAX, AVAX_TOKENS, find_token
from lazyagent.transfers import TransferError

USDC = find_token("USDC", AVAX_TOKENS)
MAKER = "0x1FDb2b265d2A5C4302A75cAd682222E4e7bCc313"
TAKER = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
SIG = "0x" + "11" * 65
ORDER = {
    "nonceAndMeta": str((int(TAKER, 16) << 96) | 7), "expiry": "1000", "makerAsset": USDC.address, "takerAsset": NATIVE,
    "maker": MAKER, "taker": TAKER, "makerAmount": "9574000", "takerAmount": str(10**18),
}
ABI = [{
    "name": "simpleSwap", "type": "function", "stateMutability": "payable", "outputs": [],
    "inputs": [
        {"name": "_order", "type": "tuple", "components": [
            {"name": n, "type": t} for n, t in [
                ("nonceAndMeta", "uint256"), ("expiry", "uint128"), ("makerAsset", "address"), ("takerAsset", "address"),
                ("maker", "address"), ("taker", "address"), ("makerAmount", "uint256"), ("takerAmount", "uint256"),
            ]
        ]},
        {"name": "_signature", "type": "bytes"},
    ],
}]


def test_simple_swap_calldata_matches_abi_encoding():
    c = Web3().eth.contract(abi=ABI)
    values = (int(ORDER["nonceAndMeta"]), 1000, USDC.address, NATIVE, MAKER, TAKER, 9574000, 10**18)
    assert encode_simple_swap(ORDER, SIG) == c.encode_abi("simpleSwap", args=[values, bytes.fromhex(SIG[2:])])


def test_avax_in_is_one_step_with_value():
    [step] = dexalot_steps(AVAX, USDC, {"maker": MAKER, "order": ORDER, "signature": SIG}, allowance=0)
    assert step.label == "Swap AVAX → USDC"
    assert step.request["to"] == MAKER and step.request["value"] == str(10**18)


def test_erc20_in_adds_sized_approval_only_when_needed():
    order = {**ORDER, "makerAsset": NATIVE, "takerAsset": USDC.address, "takerAmount": "10000000", "makerAmount": str(10**18)}
    quote = {"maker": MAKER, "order": order, "signature": SIG}
    steps = dexalot_steps(USDC, AVAX, quote, allowance=0)
    assert [s.label for s in steps] == ["Allow USDC", "Swap USDC → AVAX"]
    assert steps[0].request["to"] == USDC.address and steps[1].request["value"] == "0"
    assert [s.label for s in dexalot_steps(USDC, AVAX, quote, allowance=10_000_000)] == ["Swap USDC → AVAX"]


def test_rows():
    rows = dexalot_rows("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", AVAX, USDC, 10**18, 9_574_000, 0.01, "Avalanche (Sandbox)")
    assert {r["label"]: r["value"] for r in rows} == {
        "From": "0xf39F…2266", "You pay": "1 AVAX", "Receive exactly": "9.574 USDC", "Rate": "1 AVAX = 9.574 USDC",
        "Route": "Dexalot · sandbox-signed at live price", "Network fee": "~$0.01", "Network": "Avalanche (Sandbox)",
    }
    assert asset_of(AVAX) == NATIVE and asset_of(USDC) == USDC.address


async def test_sandbox_quotes_posts_and_surfaces_errors():
    server, received = serve(200, {"maker": MAKER, "order": ORDER, "signature": SIG})
    try:
        q = await SandboxQuotes(f"http://127.0.0.1:{server.server_port}").quote(NATIVE, USDC.address, 10**18, TAKER)
        assert q["maker"] == MAKER
        assert received == {"path": "/dexalot/quote", "body": {"token_in": NATIVE, "token_out": USDC.address, "amount_in": str(10**18), "taker": TAKER}}
    finally:
        server.shutdown()
    server, _ = serve(404, {"detail": "Dexalot doesn't offer that pair. Available: AVAX/USDC."})
    try:
        with pytest.raises(TransferError, match="Available: AVAX/USDC"):
            await SandboxQuotes(f"http://127.0.0.1:{server.server_port}").quote(NATIVE, USDC.address, 1, TAKER)
    finally:
        server.shutdown()
    with pytest.raises(TransferError, match="pnpm dev:sandbox"):
        await SandboxQuotes("http://127.0.0.1:1").quote(NATIVE, USDC.address, 1, TAKER)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory agent pytest tests/test_dexalot.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lazyagent.dexalot'`.

- [ ] **Step 3: Implement**

`agent/lazyagent/dexalot.py`:

```python
"""Dexalot SimpleSwap on Avalanche: calldata, confirm-card steps and the sandbox quote client.
The sandbox (anvil/) signs the order; this module only turns it into transactions."""

import asyncio
from typing import Protocol

from eth_abi import encode
from web3 import Web3

from .faucet import _post
from .swaps import Step, display_units
from .tokens import Token
from .transfers import TransferError, format_units, format_usd, short
from .uniswap import encode_erc20_approve

NATIVE = "0x0000000000000000000000000000000000000000"
ORDER_FIELDS = [
    ("nonceAndMeta", "uint256"), ("expiry", "uint128"), ("makerAsset", "address"), ("takerAsset", "address"),
    ("maker", "address"), ("taker", "address"), ("makerAmount", "uint256"), ("takerAmount", "uint256"),
]
ORDER_TUPLE = "(" + ",".join(t for _, t in ORDER_FIELDS) + ")"
SIMPLE_SWAP_SELECTOR = Web3.keccak(text=f"simpleSwap({ORDER_TUPLE},bytes)")[:4].hex()
GAS = {"approve": 60_000, "swap": 140_000}
DEXALOT_REVERT_HINT = " The Dexalot quote may have expired or already been used — ask again for a fresh one."


class Quotes(Protocol):
    async def quote(self, token_in: str, token_out: str, amount_in: int, taker: str) -> dict: ...


def asset_of(token: Token) -> str:
    return NATIVE if token.address is None else token.address


def encode_simple_swap(order: dict, signature: str) -> str:
    values = tuple(int(order[k]) if t.startswith("uint") else Web3.to_checksum_address(order[k]) for k, t in ORDER_FIELDS)
    args = encode([ORDER_TUPLE, "bytes"], [values, bytes.fromhex(signature.removeprefix("0x"))])
    return "0x" + SIMPLE_SWAP_SELECTOR + args.hex()


def dexalot_steps(token_in: Token, token_out: Token, quote: dict, allowance: int) -> list[Step]:
    amount = int(quote["order"]["takerAmount"])
    maker = quote["maker"]
    steps: list[Step] = []
    if token_in.address is not None and allowance < amount:
        steps.append(Step(f"Allow {token_in.symbol}", {"to": token_in.address, "value": "0", "data": encode_erc20_approve(maker, amount)}, GAS["approve"]))
    value = amount if token_in.address is None else 0
    data = encode_simple_swap(quote["order"], quote["signature"])
    steps.append(Step(f"Swap {token_in.symbol} → {token_out.symbol}", {"to": maker, "value": str(value), "data": data}, GAS["swap"]))
    return steps


def dexalot_rows(sender: str, token_in: Token, token_out: Token, amount: int, received: int, fee_usd: float, network_label: str) -> list[dict]:
    rate = received * 10**token_in.decimals // amount
    return [
        {"label": "From", "value": short(sender)},
        {"label": "You pay", "value": f"{format_units(amount, token_in.decimals)} {token_in.symbol}"},
        {"label": "Receive exactly", "value": f"{display_units(received, token_out.decimals)} {token_out.symbol}"},
        {"label": "Rate", "value": f"1 {token_in.symbol} = {display_units(rate, token_out.decimals)} {token_out.symbol}"},
        {"label": "Route", "value": "Dexalot · sandbox-signed at live price"},
        {"label": "Network fee", "value": f"~{format_usd(fee_usd)}"},
        {"label": "Network", "value": network_label},
    ]


class SandboxQuotes:
    """Asks the sandbox service (anvil/) for a sandbox-signed Dexalot order."""

    def __init__(self, url: str):
        self.url = url

    async def quote(self, token_in: str, token_out: str, amount_in: int, taker: str) -> dict:
        payload = {"token_in": token_in, "token_out": token_out, "amount_in": str(amount_in), "taker": taker}
        try:
            status, body = await asyncio.to_thread(_post, f"{self.url}/dexalot/quote", payload)
        except ConnectionError as e:
            raise TransferError("The Sandbox service isn't reachable — start it with `pnpm dev:sandbox`.") from e
        if status != 200:
            raise TransferError(body.get("detail") or f"Dexalot quote failed ({status}).")
        return body
```

Note: `display_units` lives in `swaps.py` (check its import list stays acyclic: `swaps.py` doesn't import `dexalot.py`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory agent pytest tests/test_dexalot.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add agent/lazyagent/dexalot.py agent/tests/test_dexalot.py
git commit -m "feat(agent): Dexalot simpleSwap calldata, steps, rows and sandbox quote client"
```

---

### Task 7: Multi-network balances, transfers, faucet and the choice message

**Files:**
- Modify: `agent/lazyagent/transfers.py`, `agent/lazyagent/swaps.py`, `agent/lazyagent/tools.py`
- Test: `agent/tests/test_tools.py`, `agent/tests/test_swap_tools.py`, `agent/tests/test_network_tools.py` (new)

**Interfaces:**
- Consumes: Task 4 registry; Task 6 `Quotes`.
- Produces: `WalletTools(chain, send, ctx, proposals, approval_timeout=300, fund=None, quoter=None, avalanche=None, dexalot=None)`; `.chains: dict[str, Chain]`; `.networks -> list[Network]`; `.supported() -> str`; `async _resolve(args, symbols, amount_text, verb) -> Network | dict`; `_steps_json(steps, net) -> list[dict]`; `validate(..., native="ETH")`; `display_rows(..., network="Sandbox")`; `check_swap_funds(..., native="ETH")`; `swap_rows(..., network="Sandbox")`. Server → browser `{"type": "choice", "id", "question", "options": [{"label", "detail", "reply"}]}`. Balance holdings gain `"network"` (network name). Every step request gains `"chainId"`.

- [ ] **Step 1: Write failing tests**

Update existing assertions:
- `agent/tests/test_tools.py::test_get_balances_emits_card_and_summary`: each expected holding gains `"network": "Ethereum"`.
- `agent/tests/test_tools.py::test_propose_transfer_approved_flow`: expected request becomes `{"to": ALICE, "value": str(10**17), "data": "0x", "chainId": 1}`.
- `agent/tests/test_swap_tools.py` wrap test (line ~105): expected request gains `"chainId": 1`.
- `agent/tests/test_swap_tools.py::test_confirmed_swap_shows_updated_balances`: expected holding gains `"network": "Ethereum"`.

`agent/tests/test_network_tools.py`:

```python
import asyncio

from fakes import FakeChain, Outbox

from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"


def make(eth=None, avax=None):
    out = Outbox()
    ctx = WalletContext(address=ME, contacts=[{"name": "Alice", "address": ALICE}])
    eth = eth or FakeChain(tokens={"USDC": 500 * 10**6})
    avax = avax or FakeChain(tokens={"USDC": 20 * 10**6})
    tools = WalletTools(eth, out, ctx, Proposals(), approval_timeout=5, avalanche=avax)
    return tools, out


def text(result):
    return result["content"][0]["text"]


async def confirm_of(out):
    for _ in range(200):
        if out.of_type("confirm"):
            return out.of_type("confirm")[0]
        await asyncio.sleep(0)
    raise AssertionError("no confirm")


async def test_balances_cover_both_networks():
    tools, out = make()
    result = await tools.get_balances({})
    [card] = out.of_type("balances")
    assert [(h["network"], h["symbol"]) for h in card["holdings"]] == [
        ("Ethereum", "ETH"), ("Ethereum", "USDC"), ("Avalanche", "AVAX"), ("Avalanche", "USDC"),
    ]
    assert "Ethereum: ETH 10" in text(result) and "Avalanche: AVAX 10" in text(result)


async def test_balances_survive_one_network_down():
    avax = FakeChain()
    avax.fail = True
    tools, out = make(avax=avax)
    result = await tools.get_balances({})
    assert {h["network"] for h in out.of_type("balances")[0]["holdings"]} == {"Ethereum"}
    assert "Avalanche" in text(result) and "not reachable" in text(result).lower()


async def test_native_token_picks_its_network():
    tools, out = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "AVAX", "amount": "1", "to": "Alice"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["steps"][0]["request"]["chainId"] == 43114
    assert {"label": "Network", "value": "Avalanche (Sandbox)"} in confirm["tx"]["rows"]
    task.cancel()


async def test_balance_decides_when_only_one_network_has_enough():
    tools, out = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "USDC", "amount": "100", "to": "Alice"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["steps"][0]["request"]["chainId"] == 1
    task.cancel()


async def test_ambiguous_token_sends_choice_and_asks_model_to_wait():
    tools, out = make()
    result = await tools.propose_transfer({"token": "USDC", "amount": "10", "to": "Alice"})
    assert result["is_error"] is True and "wait for their answer" in text(result)
    [choice] = out.of_type("choice")
    assert [(o["label"], o["detail"], o["reply"]) for o in choice["options"]] == [
        ("Ethereum", "500 USDC", "Use Ethereum for that."),
        ("Avalanche", "20 USDC", "Use Avalanche for that."),
    ]
    assert not out.of_type("confirm")


async def test_explicit_network_wins_and_is_validated():
    tools, out = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "USDC", "amount": "10", "to": "Alice", "network": "avalanche"}))
    assert (await confirm_of(out))["tx"]["steps"][0]["request"]["chainId"] == 43114
    task.cancel()
    bad = await tools.propose_transfer({"token": "LIT", "amount": "1", "to": "Alice", "network": "avax"})
    assert bad["is_error"] is True and "isn't available on Avalanche" in text(bad)
    unknown = await tools.propose_transfer({"token": "ETH", "amount": "1", "to": "Alice", "network": "solana"})
    assert unknown["is_error"] is True and "Ethereum, Avalanche" in text(unknown)


async def test_avalanche_gas_wording_uses_avax():
    avax = FakeChain(eth=0, tokens={"USDC": 20 * 10**6})
    tools, _ = make(avax=avax)
    result = await tools.propose_transfer({"token": "USDC", "amount": "10", "to": "Alice", "network": "avalanche"})
    assert "little AVAX" in text(result)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory agent pytest tests/test_network_tools.py tests/test_tools.py tests/test_swap_tools.py -q`
Expected: FAIL — `TypeError: WalletTools.__init__() got an unexpected keyword argument 'avalanche'` and missing `network`/`chainId` keys.

- [ ] **Step 3: Implement**

`agent/lazyagent/transfers.py` — `validate` and `display_rows` gain wording params:

```python
def validate(token: Token, amount: int, balance: int, eth_balance: int, gas_cost: int, native: str = "ETH") -> None:
    have = f"{format_units(balance, token.decimals)} {token.symbol}"
    if amount > balance:
        raise TransferError(f"You only have {have}.")
    reserve = gas_cost * FEE_HEADROOM
    if token.address is None:
        if amount + reserve > eth_balance:
            raise TransferError(
                f"That leaves too little for the network fee (keep ~{format_units(reserve, 18)} {native}). Try a slightly smaller amount."
            )
    elif reserve > eth_balance:
        raise TransferError(f"You need a little {native} for the network fee. Get test funds from the Receive screen.")


def display_rows(
    token: Token, amount: int, to: str, name: str | None, price: float, gas_cost: int, eth_price: float, network: str = "Sandbox"
) -> list[dict]:
    human = format_units(amount, token.decimals)
    usd = float(Decimal(amount).scaleb(-token.decimals)) * price
    fee = float(Decimal(gas_cost).scaleb(-18)) * eth_price
    return [
        {"label": "To", "value": f"{name} ({short(to)})" if name else short(to)},
        {"label": "Amount", "value": f"{human} {token.symbol} ({format_usd(usd)})"},
        {"label": "Network fee", "value": f"~{format_usd(fee)}"},
        {"label": "Network", "value": network},
    ]
```

`agent/lazyagent/swaps.py` — `check_swap_funds(..., native: str = "ETH")` uses `{native}` in place of both literal `ETH`s in its message; `swap_rows(..., fee_usd: float, network: str = "Sandbox")` ends with `{"label": "Network", "value": network}`.

`agent/lazyagent/tools.py` — imports: add `import secrets`, `import asyncio` (already), `from .dexalot import Quotes`, `from .networks import ETHEREUM, NETWORKS, Choice, Network, candidates, find_network, pick_network`; drop the module-level `SUPPORTED` constant. Replace the constructor, balance helpers, `get_balances`, `propose_transfer`, `_fresh_balances` (unchanged body), `request_test_funds` text and `unsupported_action`, and add helpers:

```python
class WalletTools:
    def __init__(
        self,
        chain: Chain,
        send: Send,
        ctx: WalletContext,
        proposals: Proposals,
        approval_timeout: float = 300,
        fund: Fund | None = None,
        quoter: Quoter | None = None,
        avalanche: Chain | None = None,
        dexalot: Quotes | None = None,
    ):
        self.fund = fund
        self.quoter = quoter or ChainQuoter(chain)
        self.chain = chain  # Ethereum (Uniswap quoting, approvals)
        self.chains: dict[str, Chain] = {"ethereum": chain, **({"avalanche": avalanche} if avalanche else {})}
        self.dexalot = dexalot
        self.send = send
        self.ctx = ctx
        self.proposals = proposals
        self.approval_timeout = approval_timeout

    @property
    def networks(self) -> list[Network]:
        return [n for n in NETWORKS if n.key in self.chains]

    def supported(self) -> str:
        nets = self.networks
        if len(nets) == 1:
            return ", ".join(t.symbol for t in nets[0].tokens)
        return " · ".join(f"{n.name}: {', '.join(t.symbol for t in n.tokens)}" for n in nets)

    async def _balance_on(self, net: Network, token) -> int:
        chain = self.chains[net.key]
        return await (chain.eth_balance(self.ctx.address) if token.address is None else chain.token_balance(token, self.ctx.address))

    async def _holdings(self, net: Network) -> list[dict]:
        chain = self.chains[net.key]
        holdings = []
        for t in net.tokens:
            raw = await self._balance_on(net, t)
            if raw == 0 and t is not net.native:
                continue
            amount = float(Decimal(raw).scaleb(-t.decimals))
            holdings.append({"network": net.name, "symbol": t.symbol, "amount": amount, "usdPrice": await chain.price_usd(t), "raw": raw, "decimals": t.decimals})
        return holdings

    async def get_balances(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        nets = self.networks
        results = await asyncio.gather(*(self._holdings(n) for n in nets), return_exceptions=True)
        holdings: list[dict] = []
        down: list[str] = []
        for net, r in zip(nets, results):
            if isinstance(r, BaseException):
                down.append(f"{net.name} ({r})")
            else:
                holdings += r
        if not holdings:
            return err(f"The Sandbox chain isn't reachable right now ({'; '.join(down)}).")
        await self.send({"type": "balances", "holdings": [{k: h[k] for k in ("network", "symbol", "amount", "usdPrice")} for h in holdings]})
        parts = []
        for net in nets:
            mine = [h for h in holdings if h["network"] == net.name]
            if mine:
                parts.append(f"{net.name}: " + ", ".join(f"{h['symbol']} {format_units(h['raw'], h['decimals'])} ({format_usd(h['amount'] * h['usdPrice'])})" for h in mine))
        total = sum(h["amount"] * h["usdPrice"] for h in holdings)
        note = f" Not reachable right now: {', '.join(down)}." if down else ""
        return ok(f"Balances shown to the user as a card: {'; '.join(parts)}. Total {format_usd(total)}.{note}")

    async def _resolve(self, args: dict, symbols: list[str], amount_text: str, verb: str) -> Network | dict:
        """Which network a request runs on — or an error result (after sending a choice card when it's ambiguous)."""
        explicit = args.get("network")
        if explicit:
            net = find_network(str(explicit))
            if net is None or net.key not in self.chains:
                return err(f"I can use {', '.join(n.name for n in self.networks)} on Sandbox.")
            missing = [s for s in symbols if find_token(s, net.tokens) is None]
            if missing:
                return err(f"{missing[0]} isn't available on {net.name} Sandbox. There I can {verb} {', '.join(t.symbol for t in net.tokens)}.")
            return net
        cands = candidates(symbols, self.networks)
        if not cands:
            return err(f"I can only {verb} {self.supported()} on Sandbox.")
        if len(cands) == 1:
            return cands[0]
        balances: dict[str, int | None] = {}
        enough: dict[str, bool] = {}
        for net in cands:
            token = find_token(symbols[0], net.tokens)
            try:
                need = parse_amount(amount_text, token.decimals)
            except TransferError as e:
                return err(str(e))
            try:
                balances[net.key] = await self._balance_on(net, token)
            except Exception:
                balances[net.key] = None
            enough[net.key] = balances[net.key] is not None and balances[net.key] >= need
        picked = pick_network(cands, enough)
        if isinstance(picked, Network):
            return picked
        await self._send_choice(picked, symbols[0], balances)
        names = " or ".join(n.name for n in picked.networks)
        return err(
            f"{symbols[0].upper()} is on {names}, so I showed the user buttons to choose. "
            "Ask which network in one short sentence and wait for their answer; then call the tool again with network set."
        )

    async def _send_choice(self, choice: Choice, symbol: str, balances: dict[str, int | None]) -> None:
        options = []
        for net in choice.networks:
            token = find_token(symbol, net.tokens)
            bal = balances.get(net.key)
            detail = "unreachable" if bal is None else f"{format_units(bal, token.decimals)} {token.symbol}"
            options.append({"label": net.name, "detail": detail, "reply": f"Use {net.name} for that."})
        await self.send({"type": "choice", "id": f"c{secrets.token_hex(8)}", "question": f"Which network for {symbol.upper()}?", "options": options})

    @staticmethod
    def _steps_json(steps: list[dict], net: Network) -> list[dict]:
        return [{"label": s["label"], "request": {**s["request"], "chainId": net.chain_id}} for s in steps]

    async def propose_transfer(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        symbol = str(args.get("token", "")).strip()
        net = await self._resolve(args, [symbol], str(args.get("amount", "")), "send")
        if isinstance(net, dict):
            return net
        token = find_token(symbol, net.tokens)
        chain = self.chains[net.key]
        try:
            amount = parse_amount(str(args.get("amount", "")), token.decimals)
            to, name = resolve_recipient(str(args.get("to", "")), self.ctx.contacts)
            native_balance = await chain.eth_balance(self.ctx.address)
            balance = native_balance if token.address is None else await chain.token_balance(token, self.ctx.address)
            gas_cost = gas_units(token) * await chain.gas_price()
            validate(token, amount, balance, native_balance, gas_cost, native=net.native.symbol)
            price = await chain.price_usd(token)
            native_price = await chain.price_usd(net.native)
        except TransferError as e:
            return err(str(e))
        except Exception as e:
            return err(f"The {net.name} Sandbox chain isn't reachable right now ({e}).")

        human = f"{format_units(amount, token.decimals)} {token.symbol}"
        label = name or short(to)
        steps = self._steps_json([{"label": "Send", "request": build_request(token, to, amount)}], net)
        pid, fut = self.proposals.new()
        await self.send(
            {
                "type": "confirm",
                "id": pid,
                "tx": {
                    "title": f"Send {human}",
                    "from": self.ctx.address,
                    "rows": [{"label": "From", "value": short(self.ctx.address)}, *display_rows(token, amount, to, name, price, gas_cost, native_price, network=net.label)],
                    "steps": steps,
                },
            }
        )
        result = await self.proposals.wait(pid, fut, self.approval_timeout)
        success = ""
        if _succeeded(result):
            success = f"Sent {human} to {label}. Confirmed on {net.label}, tx {result.get('hash')}." + await self._fresh_balances()
        return ok(outcome_text(result, steps, "transfer", success))
```

Remove the old `_balance` helper only after Task 8 replaces its uses in `propose_swap`; in this task, keep `_balance` and change `propose_swap` minimally so its tests pass:
- replace `find_token(...)` calls for `tin`/`tout` with `find_token(..., ETHEREUM.tokens)` and the unknown-token error with `err(f"I can only swap {self.supported()} on Sandbox.")`;
- build `steps_json = self._steps_json([s.to_json() for s in steps], ETHEREUM)`;
- pass `network=ETHEREUM.label` to `swap_rows`, and change both `"Confirmed on Sandbox"` strings to `f"Confirmed on {ETHEREUM.label}"`.

`request_test_funds` and `unsupported_action`:

```python
    async def unsupported_action(self, args: dict) -> dict:
        action = str(args.get("action", "That"))
        return ok(f"{action} is coming soon. Right now LazyWallet can check balances, send and swap on Sandbox ({self.supported()}).")
```

In `request_test_funds`, keep the `is_sandbox` check on `self.chain` (the faucet funds every network).

In `build_mcp_server`, replace `SUPPORTED` with `t.supported()` in descriptions, update the faucet description to `"Sandbox faucet: give the active wallet free test funds on every Sandbox network (100 ETH / 100 AVAX plus test tokens). ..."`, and add to `propose_transfer`'s and `propose_swap`'s `properties`:

```python
"network": {"type": "string", "description": "Only if the user named a network or answered a network choice: 'ethereum' or 'avalanche'"},
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory agent pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent
git commit -m "feat(agent): multi-network balances and sends with a network choice card"
```

---

### Task 8: Swaps on Avalanche go through Dexalot

**Files:**
- Modify: `agent/lazyagent/tools.py`
- Test: `agent/tests/test_network_tools.py`, `agent/tests/test_dexalot_swap_fork.py` (new)

**Interfaces:**
- Consumes: Task 6 (`asset_of`, `dexalot_steps`, `dexalot_rows`, `DEXALOT_REVERT_HINT`, `Quotes`), Task 7 (`_resolve`, `_balance_on`, `_steps_json`), `encode_erc20_allowance(owner, spender)`.
- Produces: `propose_swap` resolves the network; Ethereum → Uniswap (`_uniswap_plan`), Avalanche → Dexalot (`_dexalot_plan`). Both plans return `(steps: list[Step], rows: Callable[[float], list[dict]], revert_hint: str)`.

- [ ] **Step 1: Write failing tests**

Append to `agent/tests/test_network_tools.py`:

```python
from lazyagent.dexalot import NATIVE
from lazyagent.transfers import TransferError

MAKER = "0x1FDb2b265d2A5C4302A75cAd682222E4e7bCc313"
AVAX_USDC = "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E"


class FakeQuotes:
    def __init__(self, fail: str | None = None):
        self.calls = []
        self.fail = fail

    async def quote(self, token_in, token_out, amount_in, taker):
        self.calls.append((token_in, token_out, amount_in, taker))
        if self.fail:
            raise TransferError(self.fail)
        order = {"nonceAndMeta": "7", "expiry": "9999999999", "makerAsset": token_out, "takerAsset": token_in, "maker": MAKER,
                 "taker": taker, "makerAmount": "9574000", "takerAmount": str(amount_in)}
        return {"maker": MAKER, "order": order, "signature": "0x" + "11" * 65}


def make_swap(quotes=None, avax=None):
    out = Outbox()
    proposals = Proposals()
    avax = avax or FakeChain(tokens={"USDC": 20 * 10**6})
    tools = WalletTools(FakeChain(), out, WalletContext(address=ME), proposals, approval_timeout=5, avalanche=avax, dexalot=quotes or FakeQuotes())
    return tools, out, proposals, avax


async def test_avalanche_swap_uses_dexalot_and_reports_exact_output():
    quotes = FakeQuotes()
    tools, out, proposals, avax = make_swap(quotes)
    task = asyncio.create_task(tools.propose_swap({"token_in": "AVAX", "token_out": "USDC", "amount": "1"}))
    confirm = await confirm_of(out)
    assert quotes.calls == [(NATIVE, AVAX_USDC, 10**18, ME)]
    assert [s["label"] for s in confirm["tx"]["steps"]] == ["Swap AVAX → USDC"]
    assert confirm["tx"]["steps"][0]["request"]["chainId"] == 43114
    rows = {r["label"]: r["value"] for r in confirm["tx"]["rows"]}
    assert rows["Receive exactly"] == "9.574 USDC" and rows["Network"] == "Avalanche (Sandbox)"
    avax.tokens["USDC"] += 9_574_000
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xs"})
    result = text(await task)
    assert "Swapped 1 AVAX for 9.574 USDC" in result and "Avalanche (Sandbox)" in result


async def test_avalanche_erc20_swap_adds_approval():
    tools, out, _, _ = make_swap()
    task = asyncio.create_task(tools.propose_swap({"token_in": "USDC", "token_out": "AVAX", "amount": "10"}))
    confirm = await confirm_of(out)
    assert [s["label"] for s in confirm["tx"]["steps"]] == ["Allow USDC", "Swap USDC → AVAX"]
    task.cancel()


async def test_avalanche_swap_errors_send_no_card():
    tools, out, _, _ = make_swap(FakeQuotes(fail="Dexalot doesn't offer that pair. Available: AVAX/USDC."))
    result = await tools.propose_swap({"token_in": "AVAX", "token_out": "BTC.b", "amount": "1"})
    assert result["is_error"] is True and "Available: AVAX/USDC" in text(result)
    assert not out.of_type("confirm")
```

`agent/tests/test_dexalot_swap_fork.py`:

```python
import asyncio

from eth_abi import encode
from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3, Web3
from web3.middleware import ExtraDataToPOAMiddleware

from fakes import FakeChain
from lazyagent.chain import RpcChain
from lazyagent.devsigner import execute_steps
from lazyagent.dexalot import SandboxQuotes
from lazyagent.proposals import Proposals
from lazyagent.swaps import display_units
from lazyagent.tokens import AVAX_TOKENS, find_token
from lazyagent.tools import WalletContext, WalletTools

USDC = find_token("USDC", AVAX_TOKENS)


async def run_swap(avax_sandbox, args: dict, usdc: int = 0):
    rpc, sandbox_url = avax_sandbox
    w3 = AsyncWeb3(AsyncHTTPProvider(rpc))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    account = Account.create()
    await w3.provider.make_request("anvil_setBalance", [account.address, hex(10 * 10**18)])
    if usdc:
        key = Web3.keccak(encode(["address", "uint256"], [account.address, 9])).to_0x_hex()
        await w3.provider.make_request("anvil_setStorageAt", [USDC.address, key, "0x" + usdc.to_bytes(32, "big").hex()])
    proposals = Proposals()
    seen = []

    async def send(msg: dict) -> None:
        if msg["type"] == "confirm":
            seen.append(msg)

            async def approve() -> None:
                proposals.resolve(msg["id"], await execute_steps(w3, account.key.to_0x_hex(), msg["tx"]["steps"]))

            asyncio.create_task(approve())

    chain = RpcChain(rpc, poa=True)
    tools = WalletTools(FakeChain(), send, WalletContext(address=account.address), proposals, approval_timeout=120,
                        avalanche=chain, dexalot=SandboxQuotes(sandbox_url))
    result = await tools.propose_swap(args)
    return result["content"][0]["text"], seen, chain, account


async def test_avax_to_usdc_receives_exactly_the_signed_amount(avax_sandbox):
    text, seen, chain, account = await run_swap(avax_sandbox, {"token_in": "AVAX", "token_out": "USDC", "amount": "1"})
    assert "Swapped 1 AVAX for" in text, text
    received = await chain.token_balance(USDC, account.address)
    assert received > 1_000_000  # > $1
    rows = {r["label"]: r["value"] for r in seen[0]["tx"]["rows"]}
    assert rows["Receive exactly"] == f"{display_units(received, 6)} USDC"


async def test_usdc_to_avax_with_approval(avax_sandbox):
    text, seen, chain, account = await run_swap(avax_sandbox, {"token_in": "USDC", "token_out": "AVAX", "amount": "10"}, usdc=50 * 10**6)
    assert "Swapped 10 USDC for about" in text, text
    assert [s["label"] for s in seen[0]["tx"]["steps"]] == ["Allow USDC", "Swap USDC → AVAX"]
    assert await chain.token_balance(USDC, account.address) == 40 * 10**6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory agent pytest tests/test_network_tools.py -q`
Expected: FAIL — Avalanche swap returns "I can only swap …" (swap isn't network-aware yet).

- [ ] **Step 3: Implement**

`agent/lazyagent/tools.py` — add imports `from .dexalot import DEXALOT_REVERT_HINT, Quotes, asset_of, dexalot_rows, dexalot_steps`. Replace `_balance`, `propose_swap` with:

```python
    async def _uniswap_plan(self, tin, tout, amount: int, bps: int):
        now = await self.chain.block_timestamp()
        if (tin.symbol, tout.symbol) in (("ETH", "WETH"), ("WETH", "ETH")):
            weth = tout if tin.address is None else tin
            request = (
                {"to": weth.address, "value": str(amount), "data": WETH_DEPOSIT}
                if tin.address is None
                else {"to": weth.address, "value": "0", "data": encode_weth_withdraw(amount)}
            )
            verb = "Wrap" if tin.address is None else "Unwrap"
            steps = [Step(f"{verb} {tin.symbol} → {tout.symbol}", request, GAS["wrap"])]
            expected = minimum = amount
            label, impact = f"{verb} via WETH contract", 0.0
        else:
            found = await best_route(self.quoter, currency_of(tin), currency_of(tout), amount)
            if found is None:
                raise TransferError(f"I couldn't find a Uniswap v4 route for {tin.symbol} → {tout.symbol} on Sandbox.")
            route, expected = found
            probe_in = max(amount // 1000, 1)
            impact = price_impact(amount, expected, probe_in, await self.quoter.quote(route, probe_in) or 0)
            if impact > MAX_PRICE_IMPACT:
                raise TransferError(f"That trade would move the price by about {impact:.0%}. Try a smaller amount.")
            minimum = min_out(expected, bps)
            steps = await self._approvals(tin, amount, now) if tin.address else []
            swap = {"to": UNIVERSAL_ROUTER, "value": str(amount if tin.address is None else 0), "data": encode_swap(route, amount, minimum, now + DEADLINE_S)}
            steps.append(Step(f"Swap {tin.symbol} → {tout.symbol}", swap, GAS["swap1" if len(route.hops) == 1 else "swap2"]))
            label = route_label(route)

        def rows(fee_usd: float) -> list[dict]:
            return swap_rows(self.ctx.address, tin, tout, amount, expected, minimum, label, impact, fee_usd, network=ETHEREUM.label)

        return steps, rows, f" The price probably moved more than the {bps / 100:g}% slippage — ask again for a fresh quote."

    async def _dexalot_plan(self, net: Network, tin, tout, amount: int):
        if self.dexalot is None:
            raise TransferError("Dexalot swaps aren't set up on this Sandbox.")
        quote = await self.dexalot.quote(asset_of(tin), asset_of(tout), amount, self.ctx.address)
        allowance = 0
        if tin.address is not None:
            raw = await self.chains[net.key].call(tin.address, encode_erc20_allowance(self.ctx.address, quote["maker"]))
            allowance = int.from_bytes(raw[:32], "big")
        received = int(quote["order"]["makerAmount"])

        def rows(fee_usd: float) -> list[dict]:
            return dexalot_rows(self.ctx.address, tin, tout, amount, received, fee_usd, net.label)

        return dexalot_steps(tin, tout, quote, allowance), rows, DEXALOT_REVERT_HINT

    async def propose_swap(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        sym_in, sym_out = str(args.get("token_in", "")).strip(), str(args.get("token_out", "")).strip()
        if sym_in.upper() == sym_out.upper():
            return err("Pick two different tokens to swap.")
        net = await self._resolve(args, [sym_in, sym_out], str(args.get("amount", "")), "swap")
        if isinstance(net, dict):
            return net
        tin, tout = find_token(sym_in, net.tokens), find_token(sym_out, net.tokens)
        chain = self.chains[net.key]
        try:
            amount = parse_amount(str(args.get("amount", "")), tin.decimals)
            bps = parse_slippage(args.get("slippage_percent"))
            native_balance = await chain.eth_balance(self.ctx.address)
            balance = await self._balance_on(net, tin)
            if amount > balance:
                raise TransferError(f"You only have {format_units(balance, tin.decimals)} {tin.symbol}.")
            if net.swap_venue == "dexalot":
                steps, rows, hint = await self._dexalot_plan(net, tin, tout, amount)
            else:
                steps, rows, hint = await self._uniswap_plan(tin, tout, amount, bps)
            reserve = gas_reserve(steps, await chain.gas_price())
            check_swap_funds(tin, amount, balance, native_balance, reserve, native=net.native.symbol)
            fee_usd = float(Decimal(reserve // FEE_HEADROOM).scaleb(-18)) * await chain.price_usd(net.native)
            out_before = await self._balance_on(net, tout)
        except TransferError as e:
            return err(str(e))
        except Exception as e:
            return err(f"The {net.name} Sandbox chain isn't reachable right now ({e}).")

        human_in = f"{format_units(amount, tin.decimals)} {tin.symbol}"
        steps_json = self._steps_json([s.to_json() for s in steps], net)
        pid, fut = self.proposals.new()
        await self.send(
            {
                "type": "confirm",
                "id": pid,
                "tx": {"title": f"Swap {human_in} → {tout.symbol}", "from": self.ctx.address, "rows": rows(fee_usd), "steps": steps_json},
            }
        )
        result = await self.proposals.wait(pid, fut, self.approval_timeout)
        success = ""
        if _succeeded(result):
            try:
                received = max(await self._balance_on(net, tout) - out_before, 0)
            except Exception:
                received = None
            if received is None:
                got = f"{tout.symbol} (I couldn't read the received amount right now — don't swap again; check the balance instead)"
            else:
                got = f"{display_units(received, tout.decimals)} {tout.symbol}"
                got = f"about {got} (after network fees)" if tout.address is None else got
            success = f"Swapped {human_in} for {got}. Confirmed on {net.label}, tx {result.get('hash')}." + await self._fresh_balances()
        return ok(outcome_text(result, steps_json, "swap", success, revert_hint=hint))
```

`_approvals` keeps using `self.chain` (Ethereum only). Delete the old `_balance` method (now unused).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory agent pytest -q`
Expected: PASS, including `test_dexalot_swap_fork.py` (needs network; starts the real sandbox service from `anvil/`).

- [ ] **Step 5: Commit**

```bash
git add agent
git commit -m "feat(agent): swap on Avalanche through Dexalot SimpleSwap"
```

---

### Task 9: Wire Avalanche into the agent server and prompt

**Files:**
- Modify: `agent/lazyagent/session.py`, `agent/lazyagent/server.py`, `agent/lazyagent/prompt.py`
- Test: `agent/tests/test_server.py`

**Interfaces:**
- Consumes: `WalletTools(..., avalanche=, dexalot=)`, `RpcChain(url, poa=True)`, `SandboxQuotes(url)`, `Settings.avax_rpc_url`.
- Produces: `Session(send, chain, client_factory, approval_timeout=300, fund=None, avalanche=None, dexalot=None)`; `create_app(chain, client_factory, allowed_origins, approval_timeout=300, fund=None, avalanche=None, dexalot=None)`.

- [ ] **Step 1: Write the failing test**

Append to `agent/tests/test_server.py` (reuse its existing client-factory helper; if it has none, use the inline `factory` below):

```python
from fakes import FakeChain

from lazyagent.server import create_app
from lazyagent.session import Session


async def test_session_passes_avalanche_to_tools():
    async def factory(tools):
        raise AssertionError("not used")

    avax = FakeChain()
    s = Session(lambda m: None, FakeChain(), factory, avalanche=avax, dexalot=object())
    assert s.tools.chains["avalanche"] is avax and s.tools.dexalot is not None


def test_create_app_accepts_avalanche():
    async def factory(tools):
        raise AssertionError("not used")

    app = create_app(FakeChain(), factory, ("http://localhost:5174",), avalanche=FakeChain())
    assert app.title == "LazyWallet Agent"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory agent pytest tests/test_server.py -q`
Expected: FAIL — `TypeError: Session.__init__() got an unexpected keyword argument 'avalanche'`.

- [ ] **Step 3: Implement**

`session.py` — constructor gains `avalanche: Chain | None = None, dexalot=None` and builds `WalletTools(chain, send, self.ctx, self.proposals, approval_timeout, fund, avalanche=avalanche, dexalot=dexalot)`.

`server.py` — `create_app(..., fund=None, avalanche: Chain | None = None, dexalot=None)` and pass them to `Session(...)`. In `main()`:

```python
    from .dexalot import SandboxQuotes

    app = create_app(
        RpcChain(settings.rpc_url),
        factory,
        settings.allowed_origins,
        fund=fund,
        avalanche=RpcChain(settings.avax_rpc_url, poa=True),
        dexalot=SandboxQuotes(settings.faucet_url),
    )
    print(
        f"LazyWallet agent on ws://127.0.0.1:{settings.port}/ws (model {settings.model}, "
        f"Ethereum {settings.rpc_url}, Avalanche {settings.avax_rpc_url})",
        flush=True,
    )
```

(Put the `SandboxQuotes` import at module top with the others.)

`prompt.py` — replace the `Environment:` line and the faucet/swap/bridging bullets:

```
Environment: Sandbox — local forks of Ethereum mainnet and Avalanche C-Chain with test funds. The wallet has the same address on both; the user never switches networks. Nothing here costs real money.
```

```
- Networks: pass network to propose_transfer / propose_swap only if the user named one ("on Avalanche") or answered a network choice ("Use Avalanche for that." → network "avalanche"). Otherwise leave it out; the tool picks the network (AVAX → Avalanche, ETH → Ethereum, otherwise where the user has enough).
- If a tool says it showed the user buttons to choose a network, ask which network in one short sentence and stop; their next message is the answer.
- "Faucet", "give me test funds", "I need ETH/AVAX to start" and similar → request_test_funds. It funds both Sandbox networks.
- Swaps ("swap 100 USDC to ETH", "trade", "convert", "buy AVAX with 50 USDC" = swap 50 USDC to AVAX) → propose_swap with token_in, token_out and the amount of token_in. Ethereum swaps use Uniswap v4; Avalanche swaps use Dexalot at its live price (sandbox-signed quote, exact output). Pass slippage_percent only if the user said one. The card lists any approval steps; report what was received in one sentence.
- Bridging between networks, schedules, price alerts, dApps or anything else → unsupported_action.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory agent pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent
git commit -m "feat(agent): connect the Avalanche fork and Dexalot quotes; network-aware prompt"
```

---

### Task 10: Wallet signs each step on its own chain

**Files:**
- Create: `apps/wallet/src/chain/networks.ts`, `apps/wallet/src/chain/networks.test.ts`
- Modify: `apps/wallet/src/types.ts`, `apps/wallet/src/lib/wagmi.ts`, `apps/wallet/src/chain/client.ts`, `apps/wallet/src/chain/executeTx.ts`, `apps/wallet/src/chain/executeTx.test.ts`

**Interfaces:**
- Produces: `ethereumFork`, `avalancheFork`, `sandboxChains`, `chainById(id?: number)`, `networkName(id?: number): string` (default id 1); `TxRequest.chainId?: number`; `TxDeps.wait(hash, chainId?)`; `statusPatch` success text `"Confirmed on <Network> (Sandbox)."`; `progressText` single-step `"Submitting to <Network> (Sandbox)…"`.

- [ ] **Step 1: Write failing tests**

`apps/wallet/src/chain/networks.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { chainById, networkName } from './networks'

describe('networks', () => {
  it('names sandbox chains and defaults to Ethereum', () => {
    expect(networkName(43114)).toBe('Avalanche')
    expect(networkName(1)).toBe('Ethereum')
    expect(networkName()).toBe('Ethereum')
    expect(networkName(10)).toBe('Chain 10')
    expect(chainById(43114)?.nativeCurrency.symbol).toBe('AVAX')
  })
})
```

In `apps/wallet/src/chain/executeTx.test.ts`:
- change `'Confirmed on Sandbox.'` to `'Confirmed on Ethereum (Sandbox).'` and `'Submitting to Sandbox…'` to `'Submitting to Ethereum (Sandbox)…'`;
- add:

```ts
  it('waits on the chain of the request and names it', async () => {
    const avax: TxStep[] = [{ label: 'Send', request: { ...req, chainId: 43114 } }]
    const wait = vi.fn(async () => 'success' as const)
    await executeSteps(avax, { send: async () => HASH, wait })
    expect(wait).toHaveBeenCalledWith(HASH, 43114)
    expect(statusPatch({ hashes: [HASH], hash: HASH, status: 'success' }, avax).text).toBe('Confirmed on Avalanche (Sandbox).')
    expect(progressText(0, avax)).toBe('Submitting to Avalanche (Sandbox)…')
  })
```

(place it inside `describe('statusPatch and progressText', …)`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter wallet test`
Expected: FAIL — cannot resolve `./networks`; wording mismatches.

- [ ] **Step 3: Implement**

`apps/wallet/src/chain/networks.ts`:

```ts
import { defineChain } from 'viem'

export const ethereumFork = defineChain({
  id: 1,
  name: 'Ethereum',
  nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
  rpcUrls: { default: { http: [import.meta.env.VITE_SANDBOX_RPC_URL ?? 'http://localhost:8545'] } },
})

export const avalancheFork = defineChain({
  id: 43114,
  name: 'Avalanche',
  nativeCurrency: { name: 'Avalanche', symbol: 'AVAX', decimals: 18 },
  rpcUrls: { default: { http: [import.meta.env.VITE_SANDBOX_AVAX_RPC_URL ?? 'http://localhost:8546'] } },
})

export const sandboxChains = [ethereumFork, avalancheFork] as const

export function chainById(id = 1) {
  return sandboxChains.find((c) => c.id === id)
}

export function networkName(id = 1): string {
  return chainById(id)?.name ?? `Chain ${id}`
}
```

`apps/wallet/src/lib/wagmi.ts`:

```ts
import { createConfig, http } from 'wagmi'
import { avalancheFork, ethereumFork } from '@/chain/networks'

export const wagmiConfig = createConfig({
  chains: [ethereumFork, avalancheFork],
  transports: { [ethereumFork.id]: http(), [avalancheFork.id]: http() },
})
```

`apps/wallet/src/types.ts`: `export type TxRequest = { to: Address; value: string; data: \`0x${string}\`; chainId?: number }`.

`apps/wallet/src/chain/client.ts`:

```ts
import { createPublicClient, createWalletClient, http } from 'viem'
import { mnemonicToAccount } from 'viem/accounts'
import { chainById } from './networks'
import type { TxDeps } from './executeTx'

export function txDepsFor(mnemonic: string): TxDeps {
  const account = mnemonicToAccount(mnemonic)
  const perChain = new Map<number, TxDeps>()

  // One wallet + reader client per Sandbox chain, created on first use.
  function depsFor(chainId = 1): TxDeps {
    const cached = perChain.get(chainId)
    if (cached) return cached
    const chain = chainById(chainId)
    if (!chain) throw new Error(`Unknown network (chain ${chainId}).`)
    const transport = http(chain.rpcUrls.default.http[0])
    const wallet = createWalletClient({ account, chain, transport })
    const reader = createPublicClient({ chain, transport })
    const deps: TxDeps = {
      send: (req) => wallet.sendTransaction({ to: req.to, value: BigInt(req.value), data: req.data }),
      wait: async (hash) => (await reader.waitForTransactionReceipt({ hash })).status,
    }
    perChain.set(chainId, deps)
    return deps
  }

  return {
    send: async (req) => depsFor(req.chainId).send(req),
    wait: (hash, chainId) => depsFor(chainId).wait(hash),
  }
}
```

`apps/wallet/src/chain/executeTx.ts` — import `networkName` from `./networks`; change:

```ts
export type TxDeps = {
  send: (req: TxRequest) => Promise<Hash>
  wait: (hash: Hash, chainId?: number) => Promise<'success' | 'reverted'>
}
```

in `executeTx`: `return { hash, status: await deps.wait(hash, req.chainId) }`; in `statusPatch` success: ``return { state: 'success', text: `Confirmed on ${networkName(steps.at(-1)?.request.chainId)} (Sandbox).`, hash: o.hash }``; in `progressText`: single-step ``return `Submitting to ${networkName(steps[index].request.chainId)} (Sandbox)…` `` (multi-step unchanged).

In `useAgentChat.ts`, the pending status text `'Submitting to Sandbox…'` becomes `progressText(0, steps)` for agent cards (move the `pending` creation after `const steps = m.tx.steps` and use `steps ? progressText(0, steps) : 'Submitting to Sandbox…'`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter wallet test && pnpm --filter wallet build`
Expected: PASS; build type-checks.

- [ ] **Step 5: Commit**

```bash
git add apps/wallet
git commit -m "feat(wallet): sign each step on its own Sandbox chain"
```

---

### Task 11: Wallet choice card and network-aware balances

**Files:**
- Create: `apps/wallet/src/chat/cards/ChoiceCard.tsx`
- Modify: `apps/wallet/src/types.ts`, `apps/wallet/src/agent/protocol.ts`, `apps/wallet/src/agent/chatReducer.ts`, `apps/wallet/src/agent/useAgentChat.ts`, `apps/wallet/src/chat/MessageItem.tsx`, `apps/wallet/src/chat/ChatView.tsx`, `apps/wallet/src/routes/WalletPage.tsx`, `apps/wallet/src/chat/cards/BalanceCard.tsx`
- Test: `apps/wallet/src/agent/chatReducer.test.ts`, `apps/wallet/src/agent/useAgentChat.test.tsx`

**Interfaces:**
- Consumes: server message `{ type: 'choice'; id; question; options: ChoiceOption[] }` (Task 7).
- Produces: `ChoiceOption = { label: string; detail?: string; reply: string }`; message kind `choice` `{ id; role: 'assistant'; kind: 'choice'; question: string; options: ChoiceOption[]; chosen?: string; closed?: boolean }`; `Holding.network?: string`; `useAgentChat().choose(id: string, option: ChoiceOption)`; `MessageActions.onChoose?: (id: string, option: ChoiceOption) => void`.

- [ ] **Step 1: Write failing tests**

Append inside `describe('chatReducer', …)` in `chatReducer.test.ts`:

```ts
  const choiceMsg = server({
    type: 'choice',
    id: 'c1',
    question: 'Which network for USDC?',
    options: [
      { label: 'Ethereum', detail: '500 USDC', reply: 'Use Ethereum for that.' },
      { label: 'Avalanche', detail: '20 USDC', reply: 'Use Avalanche for that.' },
    ],
  })

  it('adds a choice card that stays open after the turn ends', () => {
    const s = run([choiceMsg, server({ type: 'turn_end' })])
    expect(s.messages[0]).toMatchObject({ id: 'c1', kind: 'choice', question: 'Which network for USDC?' })
    expect(s.messages[0]).not.toHaveProperty('closed', true)
  })

  it('closes open choice cards when the user answers in any way', () => {
    const user: Message = { id: 'u1', role: 'user', kind: 'text', text: 'avalanche' }
    const s = run([choiceMsg, { type: 'local', messages: [user] }])
    expect(s.messages[0]).toMatchObject({ kind: 'choice', closed: true })
  })
```

Append inside `describe('useAgentChat', …)` in `useAgentChat.test.tsx` (uses the file's existing `OPTIONS` and `FakeWebSocket`):

```tsx
  it('choose() marks the option and sends its reply as a user message', async () => {
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    const live = FakeWebSocket.instances.at(-1)!
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    const option = { label: 'Avalanche', detail: '20 USDC', reply: 'Use Avalanche for that.' }
    act(() =>
      live.onmessage?.({ data: JSON.stringify({ type: 'choice', id: 'c1', question: 'Which network for USDC?', options: [option] }) }),
    )
    act(() => result.current.choose('c1', option))
    expect(JSON.parse(live.sent.at(-1)!)).toMatchObject({ type: 'user', text: 'Use Avalanche for that.' })
    expect(result.current.messages[0]).toMatchObject({ kind: 'choice', chosen: 'Avalanche', closed: true })
    act(() => result.current.choose('c1', option))
    expect(live.sent).toHaveLength(1) // a closed card can't send twice
  })
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter wallet test`
Expected: FAIL — unknown server message type `choice` / `choose` is not a function.

- [ ] **Step 3: Implement**

`types.ts`:

```ts
export type Holding = { symbol: string; amount: number; usdPrice: number; network?: string }
export type ChoiceOption = { label: string; detail?: string; reply: string }
```

and add to the `Message` union:

```ts
  | { id: string; role: 'assistant'; kind: 'choice'; question: string; options: ChoiceOption[]; chosen?: string; closed?: boolean }
```

`protocol.ts` — import `ChoiceOption` and add to `ServerMsg`:

```ts
  | { type: 'choice'; id: string; question: string; options: ChoiceOption[] }
```

`chatReducer.ts` — add helper and cases:

```ts
function closeChoices(messages: Message[]): Message[] {
  return messages.map((m) => (m.kind === 'choice' && !m.closed ? { ...m, closed: true } : m))
}
```

In `onServer`:

```ts
    case 'choice':
      return {
        ...s,
        streamingId: null,
        messages: [...s.messages, { id: msg.id, role: 'assistant', kind: 'choice', question: msg.question, options: msg.options }],
      }
```

In `chatReducer`, `case 'local'`:

```ts
    case 'local': {
      const answered = e.messages.some((m) => m.role === 'user')
      return { ...s, messages: [...(answered ? closeChoices(s.messages) : s.messages), ...e.messages] }
    }
```

`useAgentChat.ts` — import `ChoiceOption`; add and return `choose`:

```ts
  function choose(id: string, option: ChoiceOption) {
    const m = stateRef.current.messages.find((x) => x.id === id)
    if (!m || m.kind !== 'choice' || m.closed) return
    dispatch({ type: 'update', id, patch: { chosen: option.label } })
    send(option.reply)
  }

  return { messages: state.messages, busy: state.busy, online: state.online, send, approve, reject, choose, deliver }
```

`chat/cards/ChoiceCard.tsx`:

```tsx
import { Button } from '@/components/ui/button'
import type { ChoiceOption } from '@/types'

type Props = { question: string; options: ChoiceOption[]; chosen?: string; closed?: boolean; onChoose: (option: ChoiceOption) => void }

export function ChoiceCard({ question, options, chosen, closed, onChoose }: Props) {
  return (
    <div className="rounded-2xl border bg-card p-4">
      <p className="font-semibold">{question}</p>
      <div className="mt-3 grid gap-2">
        {options.map((o) => (
          <Button
            key={o.label}
            variant={chosen === o.label ? 'default' : 'secondary'}
            disabled={closed}
            onClick={() => onChoose(o)}
            className="h-auto justify-between py-2.5"
          >
            <span>{o.label}</span>
            {o.detail && <span className="font-mono text-xs opacity-70">{o.detail}</span>}
          </Button>
        ))}
      </div>
    </div>
  )
}
```

`MessageItem.tsx` — import `ChoiceCard` and `ChoiceOption`; add `onChoose?: (id: string, option: ChoiceOption) => void` to `MessageActions`; thread it through `AssistantBody` and add:

```tsx
    case 'choice':
      return (
        <ChoiceCard
          question={message.question}
          options={message.options}
          chosen={message.chosen}
          closed={message.closed}
          onChoose={(o) => onChoose?.(message.id, o)}
        />
      )
```

`ChatView.tsx` needs no change (it spreads `actions`). In `routes/WalletPage.tsx`, pass `onChoose={chat.choose}` to `<ChatView … />`.

`BalanceCard.tsx` — key and label per network:

```tsx
        {holdings.map((h) => (
          <li key={`${h.network ?? ''}:${h.symbol}`} className="flex items-center justify-between py-2.5">
            <span>
              <span className="block font-medium">{h.symbol}</span>
              {h.network && <span className="block text-xs text-muted-foreground">{h.network}</span>}
            </span>
            <span className="text-right">
              <span className="block font-mono">{formatAmount(h.amount)}</span>
              <span className="block text-xs text-muted-foreground">{formatUsd(h.amount * h.usdPrice)}</span>
            </span>
          </li>
        ))}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter wallet test && pnpm build && pnpm lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/wallet
git commit -m "feat(wallet): tappable network choice card and per-network balances"
```

---

### Task 12: Docs, spec deviations and end-to-end manual check

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `docs/superpowers/specs/2026-10-15-lazywallet-avalanche-dexalot-design.md`

- [ ] **Step 1: Update `CLAUDE.md`**

- "Current phase" → `Phase 4: Avalanche + Dexalot. Spec: \`docs/superpowers/specs/2026-10-15-lazywallet-avalanche-dexalot-design.md\`.`
- `anvil/` bullet → `Python (uv): Anvil forks of Ethereum mainnet (chain id 1, :8545, from \`ETH_RPC_URL\`) and Avalanche C-Chain (chain id 43114, :8546, from \`AVAX_RPC_URL\`, default public RPC), plus a faucet/sandbox service (:8547) that writes token balances and serves sandbox-signed Dexalot quotes.`
- `pnpm dev:sandbox` comment → `# Anvil forks :8545 (Ethereum) + :8546 (Avalanche) + faucet :8547`
- "Network: Sandbox only (Anvil fork, chain id 1)." → `Networks: Sandbox only — Ethereum fork (1) and Avalanche fork (43114), both always on; every agent step carries \`chainId\`.`
- Add: `- Dexalot recipe (Avalanche swaps) lives in \`anvil/lazysandbox/dexalot.py\` (signer patch, order signing) and \`agent/lazyagent/dexalot.py\` (calldata) — change only with a fork test.`

- [ ] **Step 2: Update `README.md`** status line to Phase 4 (balances, sends and swaps on Ethereum via Uniswap v4 and on Avalanche via Dexalot; bridges still coming soon) and the test-funds example to `100 ETH + 100 AVAX + test tokens`.

- [ ] **Step 3: Record planning decisions in the spec**

In the spec: §6.2 step 1 → "Check balance and gas reserve (AVAX); pair lookup happens in the sandbox service (404 lists available pairs)"; §6.1 `config.py` → `SANDBOX_AVAX_RPC_URL`; §8 "Confirm card: network badge" → "network shown in the card's Network row"; §6.2 "All tools gain optional network" → "`propose_transfer` and `propose_swap` gain optional `network`; balances and faucet always cover both".

- [ ] **Step 4: Full verification**

Run: `pnpm test && pnpm test:py && pnpm build && pnpm lint`
Expected: all PASS.

- [ ] **Step 5: Manual end-to-end check** (run `pnpm dev:sandbox`, `pnpm dev:agent`, `pnpm dev`; open `http://localhost:5174`)

1. Sandbox log shows `Dexalot RFQ: N makers trust sandbox signer 0x…`.
2. "Give me test funds" → summary lists Ethereum and Avalanche.
3. "What's my balance" → one card, rows labelled Ethereum / Avalanche, one total.
4. "Swap 1 AVAX to USDC" → card with Network Avalanche (Sandbox), Receive exactly …; Approve → "Confirmed on Avalanche (Sandbox)."; agent reports the amount.
5. "Swap 10 USDC to AVAX" → Allow USDC + Swap steps; Approve → confirmed.
6. "Send 10 USDC to Bob" (Bob in address book; USDC on both) → choice card; tap Avalanche → card locks with Avalanche highlighted → confirm card on Avalanche.
7. "Swap 0.1 ETH to USDC" → Uniswap v4 card on Ethereum still works.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md README.md docs/superpowers/specs/2026-10-15-lazywallet-avalanche-dexalot-design.md
git commit -m "docs: phase 4 Avalanche + Dexalot"
```
