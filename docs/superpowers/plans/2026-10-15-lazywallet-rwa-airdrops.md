# LazyWallet — RWA Airdrops (list + farm) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "What RWA airdrops can I farm?" shows a visual **airdrops card** (curated points programs, RWA first, live TVL) and the agent says one short sentence. Two executable farms, one per chain: "Farm Theo with 50 USDC" shows one Approve card that swaps USDC → thUSD and stakes it into Theo's sthUSD vault on Ethereum; "Farm Avant with 50 USDC" does USDC → avUSD → savUSD on Avalanche. "Buy 50 USDC of reUSD (0x…)" goes through the existing `propose_swap`.

**Architecture:** One new agent module, `agent/lazyagent/airdrops.py`, with a checked-in curated list `agent/lazyagent/data/airdrops.json`:
- Pure: `parse_program`/`load_curated`/`find_program`, `enrich`, `rank`, `filter_programs`, `parse_args`, `to_json`, `card`, `deposit_plan`, `farm_rows`, the ERC-4626 encoders.
- I/O: `DefiLlamaHttp` (`/protocol/{slug}`) and `GeckoPoolsHttp` (`/networks/{eth|avax}/tokens/{addr}/pools`) behind protocols, and an `Airdrops` class with a 10 min per-lookup cache that never caches errors.
- Tool layer: `AIRDROPS_TOOL`, `DEPOSIT_TOOL`, `airdrops_reply`.

`tools.py` registers both tools and owns `propose_deposit` (it needs `WalletTools`' balances, approvals, proposals and balance-change card). Each `deposit` block names its swap venue: `uniswap_v4_pinned_then_kyber` (Theo: the pinned Uniswap v4 pool, else KyberSwap) or `kyber` (Avant). KyberSwap runs through a new `kyber_swap()` (the body of `kyber_plan`, split out so the deposit can read the verified minimum). One code path serves both farms. The browser gets `tx.addTokens` (saved after success) and, once `feat-token-cards` has merged, an `AirdropCard` for the new `{"type": "airdrops"}` message.

**Tech Stack:** Python 3.12+ (uv, claude-agent-sdk, web3/eth_abi, pytest-asyncio `asyncio_mode = "auto"`), DefiLlama and GeckoTerminal public APIs (no key, stdlib `urllib` via `kyber.http_json`), Anvil fork tests; React 19 + TS + Vitest + Testing Library, shadcn `Badge`/`Button`.

**Spec:** `docs/superpowers/specs/2026-10-15-lazywallet-rwa-airdrops-design.md` (incl. `551432d`: v4 first, then KyberSwap). Research: `docs/research/2026-10-15-rwa-airdrops.md`.

## Global Constraints

- **Branch.** Work in a worktree on `feat-rwa-airdrops` from `main` (≥ `89a926c`, which has KyberSwap/custom tokens and trending). Do not touch the `lazywallet-cards` (feat-token-cards) or `lazywallet-scheduler` worktrees.
- **Avant demo assumption (user decision, 2026-10-15):** Avant Season 1 is treated as **running** for the hackathon demo. Its entry is `status: "live"`, `action_kind: "deposit"`, category `other`, `season_ends: null`, and carries `demo_assumption: "Season 1 treated as running for the hackathon demo; it actually ended 2026-05-15 and the AVANT claim is pending"`. The model must never state real season or claim dates for an entry with `demo_assumption`; the Points notice still applies.
- **Deposit venues:** `uniswap_v4_pinned_then_kyber` (needs `route` and network `ethereum`) and `kyber`. A deposit runs on its own network; the model never picks it.
- **Decisions accepted by the user** (spec "decisions for the user"): stake only the swap's **guaranteed minimum**; new `tx.addTokens`; Tori and Avant are category `other`; unverified/pending programs are listed with labels; **no** withdraw/unstake.
- **Visual, not text.** `list_airdrops` sends `{"type": "airdrops", "title": "RWA airdrops" | "Airdrops", "items": [...]}` to the browser and tells the model to answer in **one short sentence**.
- **Never name a chain in titles or suggestions.** Card titles are exactly `RWA airdrops` (category `rwa`) or `Airdrops` (anything else) — also when a network filter is used. Chip messages are `Farm Theo with 50 USDC`, `Farm Avant with 50 USDC` and `Buy 50 USDC of reUSD (0x5086bf358635B81D8C47C66d1C8b9E567Db70c72)`. The new example chip is `What RWA airdrops can I farm?`. The points notice is `Only count on real mainnet. This Sandbox is a demo and earns nothing.` (no chain name).
- **Pinned addresses (checksummed, verified on-chain 2026-10-15):** thUSD `0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3` (6 dec), sthUSD `0xA808Bc9775cb41c52C7842f8b50427fE7A770326` (6 dec), reUSD Ethereum `0x5086bf358635B81D8C47C66d1C8b9E567Db70c72`, reUSD Avalanche `0x180aF87b47Bf272B2df59dccf2D76a6eaFa625Bf`, trUSD `0xd0580192E98eA6CEB9c7b6191Ed2E27560911697` avUSD `0x24dE8771bC5DdB3362Db529Fc3358F2df3A0E346`, savUSD `0x06d47F3fb376649c3A9Dafe069B3D6E35572219E` (ERC-4626, `asset()` = avUSD, `maxDeposit` unlimited, no `paused()`, 1-day withdraw cooldown) (all 18 dec except thUSD/sthUSD). Theo pool: Uniswap v4 USDC/thUSD, fee `100`, tickSpacing `1`, no hooks (pool id `0xb30bf32e…594b5a0d`).
- **DefiLlama slugs (checked 2026-10-15):** `theo-network-thusd`, `re`, `tori-finance`, `avant-protocol`, `suzaku`, `aave-v4`. TVL = sum of `currentChainTvls["Ethereum"|"Avalanche"]` for the program's networks (never the `-borrowed` keys).
- **Buyable** = deepest GeckoTerminal pool `reserve_in_usd ≥ $10,000` (`custom_tokens.MIN_RESERVE_USD`). Unknown (lookup failed) = `null`.
- **Rank:** category `rwa` → `other`; status `live` → `unverified` → `claim_pending`; executable → any buyable farm token → `token == "none"`; TVL descending. Cap **8**.
- **Cache:** 10 min per lookup (`TTL_S = 600`); errors are never cached and never fatal — the curated data is returned with nulls.
- **Deposit:** `DEFAULT_SLIPPAGE_BPS` (1%); `minimum = min_out(quote, 100)`; stake exactly `minimum`; `GAS["deposit"] = 120_000`; `MAX_PRICE_IMPACT` (15%) applies. Kyber fallback uses slippage `"1"` (never the Sandbox 50% default).
- **Error texts, verbatim:** `category must be one of: rwa, other, all.` · `network must be one of: ethereum, avalanche.` · `I don't know that program. Call list_airdrops for the ids.` · `I can list {name} but can't farm it from here yet.` · `{Theo|Avant}'s vault isn't accepting deposits right now.` · `{Avant} farming isn't set up on this Sandbox.`
- **The model never builds calldata.** It passes a farm id/name and a decimal USDC amount only.
- **Tests never hit the network** (fakes and fixtures). The fork test is opt-in (`fork_rpc`, skips without `ETH_RPC_URL`) and runs on the conftest test port, never 8545–8547.
- **Done** = `pnpm test:py`, `pnpm --filter wallet test`, `pnpm build && pnpm lint` pass.

## Review Focus

1. **DefiLlama/GeckoTerminal down or rate-limited (429)** — the card still appears with the curated list, TVL "unknown", Buy shown for unknown liquidity; nothing is cached. Pinned by `test_cache_is_10_minutes_and_errors_are_not_cached` and `test_list_enriches_ranks_and_caps` (Task 3).
2. **The user taps Farm while the agent is busy or offline** — the chips must be disabled, not queue a message. Pinned by `buttons are disabled while the agent is busy or offline` (Task 7).
3. **A network filter ("airdrops on Avalanche")** — the title still has no chain name and Buy never offers the Ethereum token on an Avalanche-only answer (Avalanche reUSD is unbuyable → no Buy). Pinned in `test_card_titles_never_name_a_chain_and_buttons_follow_the_data` (Task 2).
4. **Allowances already granted from an earlier farm** — the card must skip "Allow USDC", "Allow Uniswap router" and "Allow thUSD". Pinned by `test_farm_by_short_name_skips_allowances_that_already_cover_it` (Task 4).
5. **The user says "Farm Theo" instead of the id** — `find_program` accepts the short name; an unknown name gets a clear error, never a guess. Pinned by `test_find_program_by_id_or_farm_name` (Task 1) and the `"nope"` case in `test_deposit_refusals_send_no_card` (Task 4).

---

## File Structure

| File | Responsibility |
|---|---|
| `agent/lazyagent/data/airdrops.json` (new) | Curated programs (6 entries), hand-refreshed |
| `agent/lazyagent/airdrops.py` (new) | Parsing/validation, enrichment, ranking, card, sources + cache, tool tuples, `airdrops_reply`, ERC-4626 encoders, `deposit_plan`, `farm_rows` |
| `agent/lazyagent/kyber.py` | Split `kyber_swap()` (returns `KyberSwap`) out of `kyber_plan` — no behaviour change |
| `agent/lazyagent/swaps.py` | `GAS["deposit"] = 120_000` |
| `agent/lazyagent/tools.py` | Register `list_airdrops`, `propose_deposit`; `WalletTools.list_airdrops`, `_farm_swap`, `propose_deposit` |
| `agent/lazyagent/prompt.py` | Routing bullets |
| `agent/tests/fakes.py` | `FakeLlama`, `FakeGeckoPools` |
| `agent/tests/test_airdrops.py` (new) | Pure + cache tests |
| `agent/tests/test_airdrop_tools.py` (new) | Tool tests with fakes |
| `agent/tests/test_deposit_fork.py` (new) | Opt-in farms on forks: Theo (Ethereum) and Avant (Avalanche, real KyberSwap API) |
| `apps/wallet/src/types.ts`, `chain/executeTx.ts`, `agent/useAgentChat.ts` | `tx.addTokens` → saved after success (`tokensToSave`) |
| `apps/wallet/src/agent/protocol.ts`, `agent/chatReducer.ts`, `types.ts` | `airdrops` server message → `kind: 'airdrops'` chat message (Task 6, so the reducer never sees an unknown type) |
| `apps/wallet/src/chat/cards/airdrops.ts` (new) | Pure helpers: `AMOUNTS_USDC`, `statusLabel`, `tvlLabel`, `farmReply`, `buyReply` |
| `apps/wallet/src/chat/cards/AirdropCard.tsx` (new) | The card |
| `apps/wallet/src/chat/MessageItem.tsx`, `routes/WalletPage.tsx`, `lib/format.ts`, `mock/fixtures.ts` | Wire the card; `onSend`; `formatCompactUsd`; example chip |
| `CLAUDE.md`, the spec | Docs + planning decisions |

**Task order:** 1 → 2 → 3 → 4 → 5 (agent), 6 (wallet `addTokens` + `airdrops` message — must merge with or before Task 3 reaches users), 7 (**only after `feat-token-cards` is merged into `main`**), 8 (docs + verification).

---

### Task 1: Curated data and loader

**Files:**
- Create: `agent/lazyagent/data/airdrops.json`
- Create: `agent/lazyagent/airdrops.py`
- Test: `agent/tests/test_airdrops.py`

**Interfaces:**
- Consumes: `custom_tokens.GECKO_API`, `GECKO_NETWORK`, `MIN_RESERVE_USD`; `kyber.http_json`; `swaps.GAS`, `Step`, `display_units`; `transfers.TransferError`, `format_units`, `format_usd`, `short`, `token_address_rows`; `uniswap.encode_erc20_allowance`; `tokens.Token`; `chain.Chain` (imported now, used by later tasks).
- Produces: `DATA: Path`, `CHAIN_NAMES = {"ethereum": "Ethereum", "avalanche": "Avalanche"}`, `CATEGORIES`, `STATUSES`, `ACTION_KINDS`, `TTL_S`, `MAX_RESULTS`, `POINTS_NOTICE`, `AirdropError`, dataclasses `FarmToken(network, symbol, address, decimals)`, `V4_THEN_KYBER = "uniswap_v4_pinned_then_kyber"`, `KYBER = "kyber"`, `Deposit(name, network, venue, vault: FarmToken, asset: FarmToken, pay, fee: int | None = None, tick_spacing: int | None = None)`, `Program(..., demo_assumption: str | None = None)`; `parse_program(d: dict) -> Program`, `load_curated(path=DATA) -> list[Program]`, `PROGRAMS: list[Program]`, `find_program(text: str, programs=PROGRAMS) -> Program | None`.

- [ ] **Step 1: Write the failing test** — create `agent/tests/test_airdrops.py`:

```python
import json

import pytest
from web3 import Web3

from lazyagent.airdrops import (
    DATA,
    PROGRAMS,
    find_program,
    load_curated,
    parse_program,
)

THUSD = "0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3"
REUSD_ETH = "0x5086bf358635B81D8C47C66d1C8b9E567Db70c72"
REUSD_AVAX = "0x180aF87b47Bf272B2df59dccf2D76a6eaFa625Bf"
AVUSD = "0x24dE8771bC5DdB3362Db529Fc3358F2df3A0E346"


def program(id_: str):
    return next(p for p in PROGRAMS if p.id == id_)


def raw(id_: str) -> dict:
    return next(d for d in json.loads(DATA.read_text()) if d["id"] == id_)


def test_the_real_curated_file_is_valid():
    programs = load_curated()
    assert [p.id for p in programs] == ["theo-thusd", "re", "tori", "avant", "suzaku-s2", "aave-v4-avax"]
    for p in programs:
        for t in p.farm_tokens:
            assert Web3.is_checksum_address(t.address)
        if p.deposit:
            assert p.deposit.asset in p.farm_tokens and p.deposit.network in p.networks
    assert [p.id for p in programs if p.deposit] == ["theo-thusd", "avant"]
    theo = program("theo-thusd").deposit
    assert (theo.name, theo.network, theo.venue, theo.vault.address, theo.asset.address, theo.pay, theo.fee, theo.tick_spacing) == (
        "Theo", "ethereum", "uniswap_v4_pinned_then_kyber", "0xA808Bc9775cb41c52C7842f8b50427fE7A770326", THUSD, "USDC", 100, 1,
    )
    avant = program("avant")
    assert (avant.deposit.name, avant.deposit.network, avant.deposit.venue, avant.deposit.fee) == ("Avant", "avalanche", "kyber", None)
    assert (avant.deposit.asset.address, avant.deposit.asset.decimals) == (AVUSD, 18)
    assert (avant.deposit.vault.symbol, avant.deposit.vault.address) == ("savUSD", "0x06d47F3fb376649c3A9Dafe069B3D6E35572219E")
    # Season 1 is assumed running for the demo; the real state stays on record and no real date is shown.
    assert (avant.status, avant.category, avant.season_ends) == ("live", "other", None)
    assert "ended 2026-05-15" in avant.demo_assumption
    assert all(p.demo_assumption is None for p in programs if p.id != "avant")


@pytest.mark.parametrize(
    "patch",
    [
        {"category": "airdrop"},
        {"status": "ended"},
        {"networks": ["base"]},
        {"token": "soon"},
        {"farm_tokens": [{"network": "ethereum", "symbol": "thUSD", "address": THUSD.lower(), "decimals": 6}]},
    ],
)
def test_malformed_entries_fail_loudly(patch):
    with pytest.raises((ValueError, KeyError)):
        parse_program({**raw("theo-thusd"), **patch})


def test_deposit_asset_must_be_a_farm_token():
    bad = raw("theo-thusd")
    bad["deposit"] = {**bad["deposit"], "asset": REUSD_ETH}
    with pytest.raises(ValueError, match="farm tokens"):
        parse_program(bad)


def test_deposit_venue_must_be_known_and_v4_only_on_ethereum():
    unknown = raw("avant")
    unknown["deposit"] = {**unknown["deposit"], "venue": "dexalot"}
    with pytest.raises(ValueError, match="unknown deposit venue"):
        parse_program(unknown)
    v4_on_avalanche = raw("avant")
    v4_on_avalanche["deposit"] = {**v4_on_avalanche["deposit"], "venue": "uniswap_v4_pinned_then_kyber", "route": {"fee": 100, "tick_spacing": 1}}
    with pytest.raises(ValueError, match="needs network ethereum"):
        parse_program(v4_on_avalanche)


def test_find_program_by_id_or_farm_name():
    assert find_program("theo-thusd").id == "theo-thusd"
    assert find_program(" THEO ").id == "theo-thusd"
    assert find_program("Avant").id == "avant"
    assert find_program("re").id == "re"
    assert find_program("nope") is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --directory agent pytest -q tests/test_airdrops.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'lazyagent.airdrops'`.

- [ ] **Step 3: Create the curated file** `agent/lazyagent/data/airdrops.json`:

```json
[
  {
    "id": "theo-thusd",
    "name": "Theo thUSD Points",
    "category": "rwa",
    "networks": ["ethereum"],
    "status": "live",
    "reward": "Theo points — no token announced",
    "token": "none",
    "season_ends": null,
    "action": "Stake thUSD (a T-bill-backed dollar) into sthUSD",
    "action_kind": "deposit",
    "kyc": "mint_only",
    "farm_tokens": [{"network": "ethereum", "symbol": "thUSD", "address": "0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3", "decimals": 6}],
    "defillama_slug": "theo-network-thusd",
    "deposit": {
      "name": "Theo",
      "network": "ethereum",
      "venue": "uniswap_v4_pinned_then_kyber",
      "vault": {"symbol": "sthUSD", "address": "0xA808Bc9775cb41c52C7842f8b50427fE7A770326", "decimals": 6},
      "asset": "0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3",
      "pay": "USDC",
      "route": {"fee": 100, "tick_spacing": 1}
    },
    "source_url": "https://theo.xyz/articles/thusd-points-program",
    "verified_at": "2026-10-15"
  },
  {
    "id": "re",
    "name": "Re Points Season 2",
    "category": "rwa",
    "networks": ["ethereum", "avalanche"],
    "status": "live",
    "reward": "Re points — paid in RE",
    "token": "live: RE",
    "season_ends": "~2026-12",
    "action": "Hold reUSD (a reinsurance-backed yield dollar)",
    "action_kind": "hold",
    "kyc": "mint_only",
    "farm_tokens": [
      {"network": "ethereum", "symbol": "reUSD", "address": "0x5086bf358635B81D8C47C66d1C8b9E567Db70c72", "decimals": 18},
      {"network": "avalanche", "symbol": "reUSD", "address": "0x180aF87b47Bf272B2df59dccf2D76a6eaFa625Bf", "decimals": 18}
    ],
    "defillama_slug": "re",
    "deposit": null,
    "source_url": "https://docs.re.xyz/re-points/about-re-points",
    "verified_at": "2026-10-15"
  },
  {
    "id": "tori",
    "name": "Tori Cores Season 1",
    "category": "other",
    "networks": ["ethereum"],
    "status": "live",
    "reward": "Tori Cores — no token announced",
    "token": "none",
    "season_ends": null,
    "action": "Hold trUSD (or stake it to strUSD)",
    "action_kind": "hold",
    "kyc": "mint_only",
    "farm_tokens": [{"network": "ethereum", "symbol": "trUSD", "address": "0xd0580192E98eA6CEB9c7b6191Ed2E27560911697", "decimals": 18}],
    "defillama_slug": "tori-finance",
    "deposit": null,
    "source_url": "https://docs.tori.finance/resources/cores",
    "verified_at": "2026-10-15"
  },
  {
    "id": "avant",
    "name": "Avant Season 1 points",
    "category": "other",
    "networks": ["avalanche"],
    "status": "live",
    "reward": "Avant points — AVANT token not launched yet",
    "token": "pending: AVANT",
    "season_ends": null,
    "action": "Stake avUSD into savUSD",
    "action_kind": "deposit",
    "kyc": "mint_only",
    "farm_tokens": [{"network": "avalanche", "symbol": "avUSD", "address": "0x24dE8771bC5DdB3362Db529Fc3358F2df3A0E346", "decimals": 18}],
    "defillama_slug": "avant-protocol",
    "deposit": {
      "name": "Avant",
      "network": "avalanche",
      "venue": "kyber",
      "vault": {"symbol": "savUSD", "address": "0x06d47F3fb376649c3A9Dafe069B3D6E35572219E", "decimals": 18},
      "asset": "0x24dE8771bC5DdB3362Db529Fc3358F2df3A0E346",
      "pay": "USDC"
    },
    "demo_assumption": "Season 1 treated as running for the hackathon demo; it actually ended 2026-05-15 and the AVANT claim is pending",
    "source_url": "https://docs.avantprotocol.com/rewards-program/avant-season-1-airdrop",
    "verified_at": "2026-10-15"
  },
  {
    "id": "suzaku-s2",
    "name": "Suzaku Points Season 2",
    "category": "other",
    "networks": ["avalanche"],
    "status": "unverified",
    "reward": "Suzaku points — paid in SUZ",
    "token": "live: SUZ",
    "season_ends": null,
    "action": "Deposit into Suzaku restaking vaults",
    "action_kind": "deposit",
    "kyc": "none",
    "farm_tokens": [],
    "defillama_slug": "suzaku",
    "deposit": null,
    "source_url": "https://docs.suzaku.network",
    "verified_at": "2026-10-15"
  },
  {
    "id": "aave-v4-avax",
    "name": "Aave V4 WAVAX incentives",
    "category": "other",
    "networks": ["avalanche"],
    "status": "live",
    "reward": "Weekly WAVAX incentives (paid directly, not points)",
    "token": "n/a",
    "season_ends": null,
    "action": "Supply USDt or USDC on Aave V4",
    "action_kind": "deposit",
    "kyc": "none",
    "farm_tokens": [],
    "defillama_slug": "aave-v4",
    "deposit": null,
    "source_url": "https://api.merkl.xyz/v4/opportunities?chainId=43114&status=LIVE",
    "verified_at": "2026-10-15"
  }
]
```

- [ ] **Step 4: Create `agent/lazyagent/airdrops.py`** (the full import block is added now; later tasks append below it):

```python
"""Airdrops / points programs: a curated list (data/airdrops.json) enriched live with DefiLlama TVL and
GeckoTerminal liquidity, plus the calldata for executable farms (ERC-4626 deposit).
Research: docs/research/2026-10-15-rwa-airdrops.md. Points only count on real mainnet; the Sandbox is a demo."""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from eth_abi import encode
from web3 import Web3

from .chain import Chain
from .custom_tokens import GECKO_API, GECKO_NETWORK, MIN_RESERVE_USD
from .kyber import http_json
from .swaps import GAS, Step, display_units
from .tokens import Token
from .transfers import TransferError, format_units, format_usd, short, token_address_rows
from .uniswap import encode_erc20_allowance

DATA = Path(__file__).parent / "data" / "airdrops.json"
LLAMA_API = "https://api.llama.fi"
CHAIN_NAMES = {"ethereum": "Ethereum", "avalanche": "Avalanche"}  # DefiLlama's chain keys, and card labels
CATEGORIES = ("rwa", "other")
STATUSES = ("live", "unverified", "claim_pending")
ACTION_KINDS = ("hold", "deposit", "claim")
V4_THEN_KYBER, KYBER = "uniswap_v4_pinned_then_kyber", "kyber"  # deposit venues for the pay → asset swap
TTL_S = 600
MAX_RESULTS = 8
POINTS_NOTICE = "Only count on real mainnet. This Sandbox is a demo and earns nothing."


class AirdropError(Exception):
    """A message for the model (bad arguments)."""


@dataclass(frozen=True)
class FarmToken:
    network: str
    symbol: str
    address: str
    decimals: int


@dataclass(frozen=True)
class Deposit:
    name: str  # short program name for buttons and card titles, e.g. "Theo"
    network: str
    venue: str  # V4_THEN_KYBER (pinned Uniswap v4 pool, else KyberSwap) | KYBER
    vault: FarmToken  # the ERC-4626 share token
    asset: FarmToken  # what the vault takes — one of the program's farm tokens
    pay: str  # symbol of the built-in token the user pays with
    fee: int | None = None  # pinned v4 pool (V4_THEN_KYBER only)
    tick_spacing: int | None = None


@dataclass(frozen=True)
class Program:
    id: str
    name: str
    category: str
    networks: tuple[str, ...]
    status: str
    reward: str
    token: str  # "none" | "n/a" | "live: X" | "pending: X"
    season_ends: str | None
    action: str
    action_kind: str
    kyc: str
    farm_tokens: tuple[FarmToken, ...]
    defillama_slug: str | None
    deposit: Deposit | None
    source_url: str
    verified_at: str
    demo_assumption: str | None = None  # set when the demo deliberately differs from reality (the model must not state real dates)


def _checksummed(address: str) -> str:
    if not Web3.is_checksum_address(address):
        raise ValueError(f"not a checksummed address: {address}")
    return address


def _farm_token(d: dict) -> FarmToken:
    if d["network"] not in CHAIN_NAMES:
        raise ValueError(f"unknown network {d['network']}")
    return FarmToken(d["network"], str(d["symbol"]), _checksummed(d["address"]), int(d["decimals"]))


def parse_program(d: dict) -> Program:
    """One curated entry → Program. Raises ValueError/KeyError on anything malformed."""
    networks = tuple(d["networks"])
    if not networks or any(n not in CHAIN_NAMES for n in networks):
        raise ValueError(f"{d.get('id')}: bad networks {networks}")
    if d["category"] not in CATEGORIES or d["status"] not in STATUSES or d["action_kind"] not in ACTION_KINDS:
        raise ValueError(f"{d.get('id')}: bad category, status or action_kind")
    token = str(d["token"])
    if token not in ("none", "n/a") and not token.startswith(("live: ", "pending: ")):
        raise ValueError(f"{d.get('id')}: bad token {token}")
    farm_tokens = tuple(_farm_token(t) for t in d["farm_tokens"])
    deposit = None
    if d.get("deposit"):
        dep = d["deposit"]
        vault = _farm_token({**dep["vault"], "network": dep["network"]})
        asset = next((t for t in farm_tokens if t.address == dep["asset"] and t.network == dep["network"]), None)
        if asset is None:
            raise ValueError(f"{d['id']}: deposit asset is not one of its farm tokens")
        venue = dep["venue"]
        if venue == V4_THEN_KYBER:
            if dep["network"] != "ethereum":  # Uniswap v4 swaps run on Ethereum only
                raise ValueError(f"{d['id']}: a pinned v4 route needs network ethereum")
            fee, spacing = int(dep["route"]["fee"]), int(dep["route"]["tick_spacing"])
        elif venue == KYBER:
            fee = spacing = None
        else:
            raise ValueError(f"{d['id']}: unknown deposit venue {venue}")
        deposit = Deposit(str(dep["name"]), dep["network"], venue, vault, asset, str(dep["pay"]), fee, spacing)
    return Program(
        str(d["id"]), str(d["name"]), d["category"], networks, d["status"], str(d["reward"]), token, d.get("season_ends"),
        str(d["action"]), d["action_kind"], str(d["kyc"]), farm_tokens, d.get("defillama_slug"), deposit,
        str(d["source_url"]), str(d["verified_at"]), d.get("demo_assumption"),
    )


def load_curated(path: Path = DATA) -> list[Program]:
    programs = [parse_program(d) for d in json.loads(path.read_text())]
    ids = [p.id for p in programs]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate airdrop ids")
    return programs


PROGRAMS = load_curated()


def find_program(text: str, programs: list[Program] = PROGRAMS) -> Program | None:
    """By id ("theo-thusd") or by its farm's short name ("Theo"), case-insensitive."""
    q = text.strip().lower()
    return next((p for p in programs if p.id == q or (p.deposit and p.deposit.name.lower() == q)), None)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --directory agent pytest -q tests/test_airdrops.py`
Expected: PASS (9 tests).

- [ ] **Step 6: Commit**

```bash
git add agent/lazyagent/airdrops.py agent/lazyagent/data/airdrops.json agent/tests/test_airdrops.py
git commit -m "feat(agent): curated airdrop programs and loader"
```

---

### Task 2: Enrichment, ranking, model JSON and the card payload (pure)

**Files:**
- Modify: `agent/lazyagent/airdrops.py` (append)
- Test: `agent/tests/test_airdrops.py`

**Interfaces:**
- Consumes: Task 1's `Program`, `PROGRAMS`, `CHAIN_NAMES`, `CATEGORIES`, `STATUSES`, `MIN_RESERVE_USD`, `POINTS_NOTICE`, `AirdropError`.
- Produces: `LiveToken(network, symbol, address, liquidity_usd: float | None, buyable: bool | None)`; `Airdrop(program, tvl_usd: float | None, token_launched: bool, farm_tokens: tuple[LiveToken, ...])` with property `executable`; `deepest_pool_usd(body) -> float`; `enrich(program, llama: dict | None, pools: dict[str, dict | None]) -> Airdrop` (pools keyed by **lower-case** address); `rank(list[Airdrop]) -> list[Airdrop]`; `filter_programs(programs, category, network) -> list[Program]`; `parse_args(args) -> (category, network | None)`; `to_json(list[Airdrop]) -> str` (entries include `demo_assumption`); `card(airdrops, category, network=None) -> dict` — the browser message `{"type": "airdrops", "title", "items": [{id, name, category, networks: [display names], status, action, tvlUsd, farm: str | None, buy: {symbol, address} | None}]}`.

- [ ] **Step 1: Write the failing tests.** Replace the `from lazyagent.airdrops import (...)` block at the top of `agent/tests/test_airdrops.py` with:

```python
from lazyagent.airdrops import (
    DATA,
    PROGRAMS,
    AirdropError,
    card,
    enrich,
    filter_programs,
    find_program,
    load_curated,
    parse_args,
    parse_program,
    rank,
    to_json,
)
```

and append to the end of the file:

```python
# --- enrichment, ranking, card ---


def pools(*reserves) -> dict:
    return {"data": [{"attributes": {"reserve_in_usd": str(r)}} for r in reserves]}


def llama(tvls: dict, symbol="-", gecko_id=None) -> dict:
    return {"currentChainTvls": tvls, "symbol": symbol, "gecko_id": gecko_id}


def test_enrich_sums_tvl_over_the_programs_networks_only():
    a = enrich(program("re"), llama({"Ethereum": 400e6, "Avalanche": 5e3, "Base": 4e6, "Ethereum-borrowed": 1e9}), {})
    assert a.tvl_usd == 400e6 + 5e3
    assert enrich(program("re"), llama({"Base": 4e6}), {}).tvl_usd is None


def test_token_launched_flips_only_for_programs_without_a_token():
    assert enrich(program("theo-thusd"), llama({}, gecko_id="theo"), {}).token_launched is True
    assert enrich(program("theo-thusd"), llama({}, symbol="THEO"), {}).token_launched is True
    assert enrich(program("theo-thusd"), llama({}), {}).token_launched is False
    assert enrich(program("re"), llama({}, symbol="RE", gecko_id="re"), {}).token_launched is False  # already "live: RE"


def test_buyable_at_the_10k_rule_and_unknown_when_lookup_failed():
    a = enrich(program("re"), None, {REUSD_ETH.lower(): pools(25e6, 2e6), REUSD_AVAX.lower(): pools(6151.3, 93)})
    assert [(t.network, t.liquidity_usd, t.buyable) for t in a.farm_tokens] == [("ethereum", 25e6, True), ("avalanche", 6151.3, False)]
    assert enrich(program("re"), None, {REUSD_ETH.lower(): pools(10_000)}).farm_tokens[0].buyable is True
    assert enrich(program("re"), None, {REUSD_ETH.lower(): pools()}).farm_tokens[0].buyable is False
    unknown = enrich(program("re"), None, {REUSD_ETH.lower(): None})
    assert (unknown.tvl_usd, unknown.farm_tokens[0].liquidity_usd, unknown.farm_tokens[0].buyable) == (None, None, None)


def test_rank_rwa_first_then_status_then_executable_then_tvl():
    items = [enrich(p, llama({"Ethereum": 1e9, "Avalanche": 1e9}), {}) for p in PROGRAMS]
    assert [a.program.id for a in rank(items)] == ["theo-thusd", "re", "avant", "tori", "aave-v4-avax", "suzaku-s2"]
    # Without enrichment the curated order still holds: RWA → other, live → unverified → claim_pending.
    plain = [a.program.id for a in rank([enrich(p, None, {}) for p in PROGRAMS])]
    assert plain[:3] == ["theo-thusd", "re", "avant"] and plain[-1] == "suzaku-s2"


def test_rank_puts_buyable_and_tokenless_ahead_at_equal_status():
    tori = enrich(program("tori"), llama({"Ethereum": 1}), {"0xd0580192e98ea6ceb9c7b6191ed2e27560911697": pools(2.6e6)})
    aave = enrich(program("aave-v4-avax"), llama({"Avalanche": 1e9}), {})
    assert [a.program.id for a in rank([aave, tori])] == ["tori", "aave-v4-avax"]


def test_filter_and_args():
    assert [p.id for p in filter_programs(PROGRAMS, "rwa", None)] == ["theo-thusd", "re"]
    assert [p.id for p in filter_programs(PROGRAMS, "all", "avalanche")] == ["re", "avant", "suzaku-s2", "aave-v4-avax"]
    assert [p.id for p in filter_programs(PROGRAMS, "other", "avalanche")] == ["avant", "suzaku-s2", "aave-v4-avax"]
    assert [p.id for p in filter_programs(PROGRAMS, "rwa", "avalanche")] == ["re"]
    assert parse_args({}) == ("all", None)
    assert parse_args({"category": "RWA", "network": "Avalanche"}) == ("rwa", "avalanche")
    with pytest.raises(AirdropError, match="category must be one of: rwa, other, all."):
        parse_args({"category": "meme"})
    with pytest.raises(AirdropError, match="network must be one of: ethereum, avalanche."):
        parse_args({"network": "base"})


def test_to_json_entry_shape():
    a = enrich(program("re"), llama({"Ethereum": 1.5e6}), {REUSD_ETH.lower(): pools(25e6)})
    [entry] = json.loads(to_json([a]))["airdrops"]
    assert list(entry) == [
        "id", "name", "category", "networks", "status", "reward", "token", "token_launched", "season_ends", "action",
        "action_kind", "executable", "kyc", "farm_tokens", "tvl_usd", "source_url", "verified_at", "demo_assumption",
    ]
    assert entry["farm_tokens"][0] == {"network": "ethereum", "symbol": "reUSD", "address": REUSD_ETH, "liquidity_usd": 25e6, "buyable": True}
    assert entry["farm_tokens"][1]["buyable"] is None
    assert json.loads(to_json([a]))["points"] == "Only count on real mainnet. This Sandbox is a demo and earns nothing."


def test_card_titles_never_name_a_chain_and_buttons_follow_the_data():
    theo = enrich(program("theo-thusd"), llama({"Ethereum": 132e6}), {THUSD.lower(): pools(3.5e6)})
    re_ = enrich(program("re"), None, {REUSD_ETH.lower(): pools(25e6), REUSD_AVAX.lower(): pools(6e3)})
    avant = enrich(program("avant"), None, {})
    msg = card([theo, re_, avant], "rwa")
    assert msg["type"] == "airdrops" and msg["title"] == "RWA airdrops"
    assert card([], "all")["title"] == card([], "other")["title"] == "Airdrops"
    t, r, a = msg["items"]
    assert t == {
        "id": "theo-thusd", "name": "Theo thUSD Points", "category": "rwa", "networks": ["Ethereum"], "status": "live",
        "action": "Stake thUSD (a T-bill-backed dollar) into sthUSD", "tvlUsd": 132e6, "farm": "Theo", "buy": None,
    }
    assert (r["farm"], r["buy"]) == (None, {"symbol": "reUSD", "address": REUSD_ETH})
    assert (a["farm"], a["buy"], a["status"], a["networks"]) == ("Avant", None, "live", ["Avalanche"])
    # Asked for one network: only that network's farm token, and never one known to be unbuyable.
    assert card([re_], "all", "avalanche")["items"][0]["buy"] is None
    assert card([enrich(program("re"), None, {})], "all")["items"][0]["buy"] == {"symbol": "reUSD", "address": REUSD_ETH}  # unknown → offer
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --directory agent pytest -q tests/test_airdrops.py`
Expected: FAIL — `ImportError: cannot import name 'AirdropError' from 'lazyagent.airdrops'`.

- [ ] **Step 3: Append the pure enrichment code** to `agent/lazyagent/airdrops.py`:

```python
# --- live enrichment: pure ---


@dataclass(frozen=True)
class LiveToken:
    network: str
    symbol: str
    address: str
    liquidity_usd: float | None  # deepest pool; None = unknown (lookup failed)
    buyable: bool | None  # deepest pool ≥ $10k; None = unknown


@dataclass(frozen=True)
class Airdrop:
    program: Program
    tvl_usd: float | None
    token_launched: bool
    farm_tokens: tuple[LiveToken, ...]

    @property
    def executable(self) -> bool:
        return self.program.deposit is not None


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def deepest_pool_usd(body: dict) -> float:
    """GeckoTerminal /tokens/{address}/pools → the largest reserve_in_usd (0 when there are no pools)."""
    return max((_num((p.get("attributes") or {}).get("reserve_in_usd")) for p in body.get("data") or []), default=0.0)


def enrich(program: Program, llama: dict | None, pools: dict[str, dict | None]) -> Airdrop:
    """`llama` = DefiLlama /protocol/{slug} (None if unavailable); `pools` = farm token address (lower-case) →
    GeckoTerminal pools JSON (None if unavailable)."""
    tvl, launched = None, False
    if llama is not None:
        chains = llama.get("currentChainTvls") or {}
        found = [_num(chains[CHAIN_NAMES[n]]) for n in program.networks if CHAIN_NAMES[n] in chains]
        tvl = sum(found) if found else None
        symbol = str(llama.get("symbol") or "-").strip()
        launched = program.token == "none" and (bool(llama.get("gecko_id")) or symbol not in ("-", ""))
    live = []
    for t in program.farm_tokens:
        body = pools.get(t.address.lower())
        liquidity = None if body is None else deepest_pool_usd(body)
        live.append(LiveToken(t.network, t.symbol, t.address, liquidity, None if liquidity is None else liquidity >= MIN_RESERVE_USD))
    return Airdrop(program, tvl, launched, tuple(live))


def rank(airdrops: list[Airdrop]) -> list[Airdrop]:
    """RWA first; then live → unverified → claim_pending; then executable → buyable → no token yet; then TVL."""

    def key(a: Airdrop):
        p = a.program
        return (
            CATEGORIES.index(p.category),
            STATUSES.index(p.status),
            not a.executable,
            not any(t.buyable for t in a.farm_tokens),
            p.token != "none",
            -(a.tvl_usd or 0.0),
        )

    return sorted(airdrops, key=key)


def filter_programs(programs: list[Program], category: str, network: str | None) -> list[Program]:
    return [p for p in programs if category in ("all", p.category) and (network is None or network in p.networks)]


def parse_args(args: dict) -> tuple[str, str | None]:
    category = str(args.get("category") or "all").strip().lower()
    network = str(args["network"]).strip().lower() if args.get("network") else None
    if category not in (*CATEGORIES, "all"):
        raise AirdropError("category must be one of: rwa, other, all.")
    if network is not None and network not in CHAIN_NAMES:
        raise AirdropError("network must be one of: ethereum, avalanche.")
    return category, network


def to_json(airdrops: list[Airdrop]) -> str:
    entries = []
    for a in airdrops:
        p = a.program
        entries.append(
            {
                "id": p.id, "name": p.name, "category": p.category, "networks": list(p.networks), "status": p.status,
                "reward": p.reward, "token": p.token, "token_launched": a.token_launched, "season_ends": p.season_ends,
                "action": p.action, "action_kind": p.action_kind, "executable": a.executable, "kyc": p.kyc,
                "farm_tokens": [
                    {"network": t.network, "symbol": t.symbol, "address": t.address, "liquidity_usd": t.liquidity_usd, "buyable": t.buyable}
                    for t in a.farm_tokens
                ],
                "tvl_usd": a.tvl_usd, "source_url": p.source_url, "verified_at": p.verified_at,
                "demo_assumption": p.demo_assumption,
            }
        )
    return json.dumps({"source": "curated list + DefiLlama/GeckoTerminal (live mainnet)", "points": POINTS_NOTICE, "airdrops": entries})


def card(airdrops: list[Airdrop], category: str, network: str | None = None) -> dict:
    """The browser's airdrops card. Titles never name a chain. Buy = the first farm token (on `network`, if one
    was asked for) that isn't known to be unbuyable; executable programs get Farm instead."""
    items = []
    for a in airdrops:
        p = a.program
        tokens = [t for t in a.farm_tokens if t.buyable is not False and network in (None, t.network)]
        buy = None if a.executable or not tokens else tokens[0]
        items.append(
            {
                "id": p.id, "name": p.name, "category": p.category, "networks": [CHAIN_NAMES[n] for n in p.networks],
                "status": p.status, "action": p.action, "tvlUsd": a.tvl_usd,
                "farm": p.deposit.name if p.deposit else None,
                "buy": {"symbol": buy.symbol, "address": buy.address} if buy else None,
            }
        )
    return {"type": "airdrops", "title": "RWA airdrops" if category == "rwa" else "Airdrops", "items": items}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --directory agent pytest -q tests/test_airdrops.py`
Expected: PASS (17 tests).

- [ ] **Step 5: Commit**

```bash
git add agent/lazyagent/airdrops.py agent/tests/test_airdrops.py
git commit -m "feat(agent): airdrop enrichment, ranking and card payload"
```

---

### Task 3: Live sources, 10 min cache and the `list_airdrops` tool

**Files:**
- Modify: `agent/lazyagent/airdrops.py` (append)
- Modify: `agent/lazyagent/tools.py`, `agent/lazyagent/prompt.py`
- Modify: `agent/tests/fakes.py` (append), `agent/tests/test_tools.py`
- Test: `agent/tests/test_airdrops.py`, `agent/tests/test_airdrop_tools.py` (new)

**Interfaces:**
- Consumes: Task 2's `enrich`, `rank`, `filter_programs`, `parse_args`, `to_json`, `card`; `kyber.http_json(url, payload, headers) -> (status, body)`.
- Produces: protocols `DefiLlamaSource.protocol(slug) -> dict`, `GeckoSource.pools(network, address) -> dict`; `DefiLlamaHttp`, `GeckoPoolsHttp`; `Airdrops(llama, gecko, programs=PROGRAMS, ttl=TTL_S, clock=time.monotonic)` with `async list(category="all", network=None) -> list[Airdrop]`; `AIRDROPS`; `AIRDROPS_TOOL` (name, description, schema); `async airdrops_reply(airdrops, args, send) -> str` (sends the card; raises `AirdropError`); `WalletTools.airdrops` class attribute and `WalletTools.list_airdrops(args) -> dict`. Test fakes `FakeLlama(bodies)`, `FakeGeckoPools(bodies)`.

- [ ] **Step 1: Add the fakes** — append to `agent/tests/fakes.py`:

```python
class FakeLlama:
    """DefiLlama /protocol/{slug} stand-in: slug → body; a missing slug raises like an HTTP error."""

    def __init__(self, bodies: dict | None = None):
        self.bodies = bodies or {}
        self.calls: list[str] = []
        self.fail = False

    async def protocol(self, slug):
        self.calls.append(slug)
        if self.fail or slug not in self.bodies:
            raise ConnectionError("HTTP Error 429: Too Many Requests")
        return self.bodies[slug]


class FakeGeckoPools:
    """GeckoTerminal /tokens/{address}/pools stand-in: lower-case address → body; missing raises."""

    def __init__(self, bodies: dict | None = None):
        self.bodies = bodies or {}
        self.calls: list[tuple[str, str]] = []

    async def pools(self, network, address):
        self.calls.append((network, address))
        if address.lower() not in self.bodies:
            raise ConnectionError("HTTP Error 429: Too Many Requests")
        return self.bodies[address.lower()]
```

- [ ] **Step 2: Write the failing tests.** In `agent/tests/test_airdrops.py`, replace the import block with the final one:

```python
import json

import pytest
from fakes import FakeGeckoPools, FakeLlama
from web3 import Web3

from lazyagent.airdrops import (
    DATA,
    MAX_RESULTS,
    PROGRAMS,
    AirdropError,
    Airdrops,
    card,
    enrich,
    filter_programs,
    find_program,
    load_curated,
    parse_args,
    parse_program,
    rank,
    to_json,
)
```

and append:

```python
# --- live sources and cache ---


async def test_list_enriches_ranks_and_caps():
    source = Airdrops(FakeLlama({"theo-network-thusd": llama({"Ethereum": 132e6})}), FakeGeckoPools({THUSD.lower(): pools(3.5e6)}))
    items = await source.list()
    assert len(items) == len(PROGRAMS) <= MAX_RESULTS
    assert items[0].program.id == "theo-thusd" and items[0].tvl_usd == 132e6 and items[0].farm_tokens[0].buyable is True
    assert all(a.tvl_usd is None for a in items[1:])  # every other lookup failed → curated data with nulls


async def test_cache_is_10_minutes_and_errors_are_not_cached():
    now = [0.0]
    llama_src = FakeLlama({"theo-network-thusd": llama({"Ethereum": 1})})
    gecko = FakeGeckoPools({})
    source = Airdrops(llama_src, gecko, clock=lambda: now[0])
    await source.list("rwa")
    await source.list("rwa")
    assert llama_src.calls.count("theo-network-thusd") == 1
    assert llama_src.calls.count("re") == 2  # failed both times, never cached
    assert gecko.calls.count(("ethereum", THUSD)) == 2
    now[0] = 601
    await source.list("rwa")
    assert llama_src.calls.count("theo-network-thusd") == 2
```

Create `agent/tests/test_airdrop_tools.py`:

```python
import json

from fakes import FakeChain, FakeGeckoPools, FakeLlama, Outbox

from lazyagent.airdrops import AIRDROPS_TOOL, Airdrops
from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


def text(result):
    return result["content"][0]["text"]


# --- list_airdrops ---


def list_tools(airdrops: Airdrops, address: str | None = ME):
    out = Outbox()
    tools = WalletTools(FakeChain(), out, WalletContext(address=address), Proposals())
    tools.airdrops = airdrops
    return tools, out


async def test_list_airdrops_sends_a_card_and_asks_for_one_sentence():
    tools, out = list_tools(Airdrops(FakeLlama({"theo-network-thusd": {"currentChainTvls": {"Ethereum": 132e6}}}), FakeGeckoPools()))
    result = await tools.list_airdrops({"category": "rwa"})
    assert not result.get("is_error")
    [msg] = out.of_type("airdrops")
    assert msg["title"] == "RWA airdrops"
    assert [i["id"] for i in msg["items"]] == ["theo-thusd", "re"]
    assert "ONE short sentence" in text(result)
    data = json.loads(text(result).split("Data: ", 1)[1])
    assert data["airdrops"][0]["executable"] is True and data["airdrops"][0]["tvl_usd"] == 132e6


async def test_list_airdrops_works_without_a_wallet_and_rejects_bad_args():
    tools, out = list_tools(Airdrops(FakeLlama(), FakeGeckoPools()), address=None)
    assert not (await tools.list_airdrops({})).get("is_error")
    assert out.of_type("airdrops")[0]["title"] == "Airdrops"
    bad = await tools.list_airdrops({"category": "nft"})
    assert bad["is_error"] is True and text(bad) == "category must be one of: rwa, other, all."
    assert len(out.of_type("airdrops")) == 1


def test_list_tool_schema():
    assert AIRDROPS_TOOL[0] == "list_airdrops" and AIRDROPS_TOOL[2]["properties"]["category"]["enum"] == ["rwa", "other", "all"]
```

In `agent/tests/test_tools.py`, `test_mcp_server_and_names`, add `"mcp__wallet__list_airdrops",` after `"mcp__wallet__list_trending_tokens",`.

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run --directory agent pytest -q tests/test_airdrops.py tests/test_airdrop_tools.py tests/test_tools.py`
Expected: FAIL — `ImportError: cannot import name 'Airdrops'` / `'AIRDROPS_TOOL'`, and the `TOOL_NAMES` assertion.

- [ ] **Step 4: Append sources, cache and the tool layer** to `agent/lazyagent/airdrops.py`:

```python
# --- live enrichment: I/O ---


class DefiLlamaSource(Protocol):
    async def protocol(self, slug: str) -> dict: ...


class GeckoSource(Protocol):
    async def pools(self, network: str, address: str) -> dict: ...


async def _get(url: str) -> dict:
    status, body = await asyncio.to_thread(http_json, url, None, {"accept": "application/json"})
    if status != 200:
        raise ConnectionError(f"{url} answered {status}")
    return body


class DefiLlamaHttp:
    async def protocol(self, slug: str) -> dict:
        return await _get(f"{LLAMA_API}/protocol/{slug}")


class GeckoPoolsHttp:
    async def pools(self, network: str, address: str) -> dict:
        return await _get(f"{GECKO_API}/networks/{GECKO_NETWORK[network]}/tokens/{address}/pools")


class Airdrops:
    """The curated programs, enriched live. Each lookup is cached for 10 min; a failed one reads as unknown
    (None) and isn't cached."""

    def __init__(
        self,
        llama: DefiLlamaSource,
        gecko: GeckoSource,
        programs: list[Program] = PROGRAMS,
        ttl: float = TTL_S,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.llama, self.gecko, self.programs, self.ttl, self.clock = llama, gecko, programs, ttl, clock
        self._cache: dict[tuple, tuple[float, dict]] = {}

    async def _cached(self, key: tuple, fetch: Callable[[], Awaitable[dict]]) -> dict | None:
        hit = self._cache.get(key)
        if hit is not None and self.clock() - hit[0] < self.ttl:
            return hit[1]
        try:
            body = await fetch()
        except Exception:
            return None
        self._cache[key] = (self.clock(), body)
        return body

    async def _enrich(self, p: Program) -> Airdrop:
        llama = await self._cached(("llama", p.defillama_slug), lambda: self.llama.protocol(p.defillama_slug)) if p.defillama_slug else None
        pools = {}
        for t in p.farm_tokens:
            pools[t.address.lower()] = await self._cached(("pools", t.network, t.address.lower()), lambda t=t: self.gecko.pools(t.network, t.address))
        return enrich(p, llama, pools)

    async def list(self, category: str = "all", network: str | None = None) -> list[Airdrop]:
        programs = filter_programs(self.programs, category, network)
        return rank(list(await asyncio.gather(*(self._enrich(p) for p in programs))))[:MAX_RESULTS]


AIRDROPS = Airdrops(DefiLlamaHttp(), GeckoPoolsHttp())


# --- agent tools ---

AIRDROPS_TOOL = (
    "list_airdrops",
    "Airdrops and points programs the user can farm (read-only): a curated list with live TVL and farm-token "
    "liquidity. RWA programs first. Each: id, name, category, networks, status (live | unverified = may have ended | "
    "claim_pending = claim not open yet), reward, token, action, executable (propose_deposit can farm it), farm_tokens "
    "(contract address, buyable). Also shows the user a card, so reply in one short sentence.",
    {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": [*CATEGORIES, "all"], "description": "'rwa' only if the user said RWA / real-world assets; default 'all'"},
            "network": {"type": "string", "enum": list(CHAIN_NAMES), "description": "Only if the user named a network"},
        },
    },
)



async def airdrops_reply(airdrops: Airdrops, args: dict, send: Callable[[dict], Awaitable[None]]) -> str:
    """Sends the card and returns the tool's text. Raises AirdropError for bad arguments."""
    category, network = parse_args(args)
    items = await airdrops.list(category, network)
    if not items:
        return "No airdrops match that right now. Say so in one short sentence."
    await send(card(items, category, network))
    return (
        "The user now sees these as a card. Reply in ONE short sentence: name the top one or two and which one "
        "LazyWallet can farm or buy; say points only count on real mainnet. Don't read the list out. Data: " + to_json(items)
    )
```

- [ ] **Step 5: Register the tool in `agent/lazyagent/tools.py`.**

Add this import above `from .chain import Chain`:

```python
from .airdrops import AIRDROPS, AIRDROPS_TOOL, AirdropError, Airdrops, airdrops_reply
```

In `TOOL_NAMES`, append `"list_airdrops"` after `"list_trending_tokens"`.

Insert directly above `async def unsupported_action(self, args: dict) -> dict:`:

```python
    airdrops: Airdrops = AIRDROPS  # shared 10 min cache; tests assign their own

    async def list_airdrops(self, args: dict) -> dict:
        try:
            return ok(await airdrops_reply(self.airdrops, args, self.send))
        except AirdropError as e:
            return err(str(e))

```

In `build_mcp_server`, after `tool(*TRENDING_TOOL)(t.list_trending_tokens),` add:

```python
            tool(*AIRDROPS_TOOL)(t.list_airdrops),
```

- [ ] **Step 6: Prompt.** In `agent/lazyagent/prompt.py`, insert these two lines directly above the line that starts `- Bridging between networks`:

```text
- Airdrops, points, farming, "what can I farm", "RWA airdrops" → list_airdrops. Pass category "rwa" only if the user said RWA or real-world assets, and network only if they named one. The app shows the list as a card with Farm and Buy buttons, so reply in ONE short sentence: the top pick and what LazyWallet can do for it (farm the executable one, or buy a buyable farm token). Say "may have ended" for unverified and "the claim isn't open yet" for claim_pending. Never promise a token or an airdrop, and don't name a chain unless the user did.
- Whenever you talk about farming or points, say points only count on real mainnet; this Sandbox is a demo.
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run --directory agent pytest -q tests/test_airdrops.py tests/test_airdrop_tools.py tests/test_tools.py`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add agent/lazyagent/airdrops.py agent/lazyagent/tools.py agent/lazyagent/prompt.py agent/tests/fakes.py agent/tests/test_airdrops.py agent/tests/test_airdrop_tools.py agent/tests/test_tools.py
git commit -m "feat(agent): list_airdrops tool with live TVL/liquidity and a browser card"
```

---

### Task 4: `propose_deposit` — Theo (v4 first, KyberSwap fallback) and Avant (KyberSwap)

**Files:**
- Modify: `agent/lazyagent/kyber.py` (split `kyber_swap` out of `kyber_plan`)
- Modify: `agent/lazyagent/swaps.py` (`GAS["deposit"]`)
- Modify: `agent/lazyagent/airdrops.py` (append)
- Modify: `agent/lazyagent/tools.py`, `agent/lazyagent/prompt.py`, `agent/tests/test_tools.py`
- Test: `agent/tests/test_airdrop_tools.py`

**Interfaces:**
- Consumes: Task 1's `find_program`, `Deposit`; `WalletTools._balance_on`, `_approvals`, `_snapshot`, `_show_change`, `_steps_json`, `quoter`, `kyber`; `swaps.approval_steps` (via `_approvals`), `erc20_approval`, `gas_reserve`, `check_swap_funds`, `min_out`, `price_impact`; `uniswap.Route`, `Hop`, `encode_swap`, `currency_of`, `UNIVERSAL_ROUTER`.
- Produces: `kyber.KyberSwap(steps, verified: Verified, label, impact, bps)` and `async kyber_swap(client, chain, net, tin, tout, amount, user, slippage) -> KyberSwap` (`kyber_plan` keeps its signature); `GAS["deposit"] = 120_000`; `airdrops.encode_erc4626_deposit(assets, receiver)`, `encode_preview_deposit(assets)`, `encode_max_deposit(receiver)`, `ENCODED_ASSET`, `DepositPlan(allowance, shares, step: Step)`, `async deposit_plan(chain, dep, user, assets) -> DepositPlan` (raises `TransferError`), `farm_rows(...) -> list[dict]`, `DEPOSIT_TOOL`; `WalletTools._farm_swap(net, dep: Deposit, usdc, asset, amount) -> (steps, expected, minimum, venue label, impact | None)` (switches on `dep.venue`) and `WalletTools.propose_deposit(args) -> dict`. Confirm `tx` carries `addTokens: [CustomToken]` (thUSD + sthUSD, or avUSD + savUSD).

- [ ] **Step 1: Write the failing tests.** In `agent/tests/test_airdrop_tools.py`, replace everything above `# --- list_airdrops ---` with:

```python
import asyncio
import json

from eth_abi import decode, encode
from fakes import FakeChain, FakeGeckoPools, FakeKyber, FakeLlama, FakeQuoter, Outbox

from lazyagent.airdrops import AIRDROPS_TOOL, DEPOSIT_TOOL, Airdrops
from lazyagent.kyber import ROUTER
from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.uniswap import PERMIT2, UNIVERSAL_ROUTER, Hop

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


def text(result):
    return result["content"][0]["text"]
```

and append to the end of the file:

```python
# --- propose_deposit ---

USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
THUSD = "0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3"
STHUSD = "0xA808Bc9775cb41c52C7842f8b50427fE7A770326"
QUOTE_100 = 100_037_000  # 100 USDC → 100.037 thUSD (fork, 2026-10-15)
MINIMUM_100 = QUOTE_100 * 99 // 100  # 1% slippage
SHARES = 97_200_000
STEPS = ["Allow USDC", "Allow Uniswap router", "Swap USDC → thUSD", "Allow thUSD", "Stake thUSD → sthUSD"]


def theo_pool(route, amount_in):
    """Only the pinned USDC/thUSD 0.01% pool; 1 USDC = 1.00037 thUSD."""
    if route.hops != (Hop(100, 1),) or route.currencies != (USDC, THUSD):
        return None
    return amount_in * 100_037 // 100_000


def vault_chain(**tokens) -> FakeChain:
    chain = FakeChain(tokens={"USDC": 500 * 10**6, **tokens})
    chain.call_responses["0x38d52e0f"] = encode(["address"], [THUSD])  # asset()
    chain.call_responses["0x402d267d"] = encode(["uint256"], [2**256 - 1])  # maxDeposit(user)
    chain.call_responses["0xef8b30f7"] = encode(["uint256"], [SHARES])  # previewDeposit(assets)
    return chain


def make(chain=None, quote=theo_pool, kyber=None):
    out = Outbox()
    proposals = Proposals()
    chain = chain or vault_chain()
    tools = WalletTools(chain, out, WalletContext(address=ME), proposals, approval_timeout=5, quoter=FakeQuoter(quote), kyber=kyber)
    return tools, out, proposals, chain


def rows_of(confirm):
    return {r["label"]: r["value"] for r in confirm["tx"]["rows"]}


async def confirm_of(out):
    for _ in range(200):
        if out.of_type("confirm"):
            return out.of_type("confirm")[0]
        await asyncio.sleep(0)
    raise AssertionError("no confirm")


def test_deposit_tool_schema():
    assert DEPOSIT_TOOL[0] == "propose_deposit" and DEPOSIT_TOOL[2]["required"] == ["farm", "amount"]


async def test_farm_theo_builds_every_step_and_stakes_the_minimum():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(tools.propose_deposit({"farm": "theo-thusd", "amount": "100"}))
    confirm = await confirm_of(out)
    tx = confirm["tx"]
    assert tx["title"] == "Farm Theo points: 100 USDC → sthUSD"
    assert [s["label"] for s in tx["steps"]] == STEPS
    assert [s["request"]["to"] for s in tx["steps"]] == [USDC, PERMIT2, UNIVERSAL_ROUTER, THUSD, STHUSD]
    assert all(s["request"]["chainId"] == 1 for s in tx["steps"])
    stake = tx["steps"][-1]["request"]["data"]
    assert stake.startswith("0x6e553f65")
    assert decode(["uint256", "address"], bytes.fromhex(stake[10:])) == (MINIMUM_100, ME.lower())
    allow = tx["steps"][3]["request"]["data"]
    assert decode(["address", "uint256"], bytes.fromhex(allow[10:])) == (STHUSD.lower(), MINIMUM_100)
    rows = rows_of(confirm)
    assert rows["Swap"] == "USDC → thUSD · Uniswap v4 0.01%"
    assert rows["Expected"] == "≈ 100.037 thUSD"
    assert rows["Stake"] == "99.0366 thUSD → ≈ 97.2 sthUSD"
    assert rows["Left in wallet"] == "≈ 1.00037 thUSD"
    assert rows["Program"] == "Theo thUSD Points — Theo points — no token announced"
    assert rows["Points"] == "Only count on real mainnet. This Sandbox is a demo and earns nothing."
    assert rows["thUSD address"] == THUSD and rows["sthUSD address"] == STHUSD
    assert rows["Network"] == "Ethereum (Sandbox)"
    assert tx["addTokens"] == [
        {"chainId": 1, "address": THUSD, "symbol": "thUSD", "decimals": 6},
        {"chainId": 1, "address": STHUSD, "symbol": "sthUSD", "decimals": 6},
    ]
    chain.tokens.update(USDC=400 * 10**6, thUSD=QUOTE_100 - MINIMUM_100, sthUSD=SHARES)
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xd"})
    result = text(await task)
    assert "Staked 99.0366 thUSD into sthUSD, got 97.2 sthUSD; 1.00037 thUSD left. Confirmed on Ethereum (Sandbox), tx 0xd." in result
    assert "Points only count on real mainnet" in result
    [change] = out.of_type("balance_change")
    assert [c["symbol"] for c in change["changes"]] == ["USDC", "thUSD", "sthUSD"]


async def test_farm_by_short_name_skips_allowances_that_already_cover_it():
    chain = vault_chain()
    chain.call_responses["0xdd62ed3e"] = encode(["uint256"], [10**30])  # USDC→Permit2 and thUSD→vault
    chain.call_responses["0x927da105"] = encode(["uint160", "uint48", "uint48"], [10**30, chain.now + 3600, 0])
    tools, out, _, _ = make(chain=chain)
    task = asyncio.create_task(tools.propose_deposit({"farm": "Theo", "amount": "100"}))
    assert [s["label"] for s in (await confirm_of(out))["tx"]["steps"]] == ["Swap USDC → thUSD", "Stake thUSD → sthUSD"]
    task.cancel()


async def test_without_a_v4_quote_kyber_buys_the_thusd_with_its_checks():
    chain = vault_chain()
    chain.sim_out = QUOTE_100
    chain.access_keys, chain.allowance_slot = ["0x09"], "0x09"
    kyber = FakeKyber(out=QUOTE_100)
    tools, out, _, _ = make(chain=chain, quote=lambda route, amount: None, kyber=kyber)
    task = asyncio.create_task(tools.propose_deposit({"farm": "theo-thusd", "amount": "100"}))
    confirm = await confirm_of(out)
    assert [s["label"] for s in confirm["tx"]["steps"]] == ["Allow USDC", "Swap USDC → thUSD", "Allow thUSD", "Stake thUSD → sthUSD"]
    assert confirm["tx"]["steps"][1]["request"]["to"] == ROUTER
    assert kyber.routes == [("ethereum", USDC, THUSD, 100 * 10**6)]
    assert kyber.builds == [("ethereum", ME, 100)]  # 1% — not the Sandbox's 50% default
    assert rows_of(confirm)["Swap"] == "USDC → thUSD · KyberSwap via LFJ"
    stake = confirm["tx"]["steps"][-1]["request"]["data"]
    assert decode(["uint256", "address"], bytes.fromhex(stake[10:]))[0] == MINIMUM_100
    task.cancel()


async def test_deposit_refusals_send_no_card():
    wrong_asset = vault_chain()
    wrong_asset.call_responses["0x38d52e0f"] = encode(["address"], [USDC])
    full = vault_chain()
    full.call_responses["0x402d267d"] = encode(["uint256"], [10**6])
    broke = vault_chain()
    broke.eth = 0

    def huge_impact(route, amount_in):
        q = theo_pool(route, amount_in)
        return q // 2 if q and amount_in >= 10**8 else q

    cases = [
        ({"farm": "nope", "amount": "10"}, {}, "Call list_airdrops"),
        ({"farm": "re", "amount": "10"}, {}, "can list Re Points Season 2 but can't farm it from here yet"),
        ({"farm": "theo-thusd", "amount": "0"}, {}, "more than 0"),
        ({"farm": "theo-thusd", "amount": "1000"}, {}, "You only have 500 USDC."),
        ({"farm": "theo-thusd", "amount": "100"}, {"chain": wrong_asset}, "Theo's vault isn't accepting deposits right now."),
        ({"farm": "theo-thusd", "amount": "100"}, {"chain": full}, "Theo's vault isn't accepting deposits right now."),
        ({"farm": "theo-thusd", "amount": "100"}, {"quote": huge_impact}, "move the price"),
        ({"farm": "theo-thusd", "amount": "100"}, {"quote": lambda r, a: None}, "couldn't get a quote"),
        ({"farm": "theo-thusd", "amount": "100"}, {"quote": lambda r, a: None, "kyber": FakeKyber(no_route=True)}, "no route"),
        ({"farm": "theo-thusd", "amount": "100"}, {"chain": broke}, "network fees"),
    ]
    for args, kwargs, fragment in cases:
        tools, out, _, _ = make(**kwargs)
        result = await tools.propose_deposit(args)
        assert result.get("is_error") is True, args
        assert fragment in text(result), (args, text(result))
        assert not out.of_type("confirm")


async def test_deposit_needs_a_wallet():
    tools, _, _, _ = make()
    tools.ctx.address = None
    assert text(await tools.propose_deposit({"farm": "theo-thusd", "amount": "1"})) == "No wallet is active in the app."


async def test_reverted_stake_names_the_step():
    tools, out, proposals, _ = make()
    task = asyncio.create_task(tools.propose_deposit({"farm": "theo-thusd", "amount": "100"}))
    confirm = await confirm_of(out)
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "reverted", "hash": "0xr", "failed_step": 4})
    result = text(await task)
    assert "The deposit reverted at step 5 (Stake thUSD → sthUSD)" in result
    assert "1% slippage" in result
    assert not out.of_type("balance_change")


# --- Avant: KyberSwap only, on Avalanche ---

AVAX_USDC = "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E"
AVUSD = "0x24dE8771bC5DdB3362Db529Fc3358F2df3A0E346"
SAVUSD = "0x06d47F3fb376649c3A9Dafe069B3D6E35572219E"
AVUSD_100 = 100_005 * 10**15  # 100 USDC → 100.005 avUSD (KyberSwap via Pharaoh, 2026-10-15)
AVUSD_MIN = AVUSD_100 * 99 // 100


def avant_chain() -> FakeChain:
    chain = FakeChain(tokens={"USDC": 500 * 10**6})
    chain.call_responses["0x38d52e0f"] = encode(["address"], [AVUSD])  # asset()
    chain.call_responses["0x402d267d"] = encode(["uint256"], [2**256 - 1])  # maxDeposit(user)
    chain.call_responses["0xef8b30f7"] = encode(["uint256"], [82 * 10**18])  # previewDeposit(assets)
    chain.sim_out = AVUSD_100
    chain.access_keys, chain.allowance_slot = ["0x0a"], "0x0a"
    return chain


def no_v4(route, amount_in):
    raise AssertionError("Avant must not quote Uniswap v4")


async def test_farm_avant_swaps_on_kyberswap_and_stakes_on_its_own_network():
    avax, kyber, out, proposals = avant_chain(), FakeKyber(out=AVUSD_100), Outbox(), Proposals()
    tools = WalletTools(FakeChain(), out, WalletContext(address=ME), proposals, approval_timeout=5, quoter=FakeQuoter(no_v4), avalanche=avax, kyber=kyber)
    task = asyncio.create_task(tools.propose_deposit({"farm": "Avant", "amount": "100"}))
    confirm = await confirm_of(out)
    tx = confirm["tx"]
    assert tx["title"] == "Farm Avant points: 100 USDC → savUSD"
    assert [s["label"] for s in tx["steps"]] == ["Allow USDC", "Swap USDC → avUSD", "Allow avUSD", "Stake avUSD → savUSD"]
    assert [s["request"]["to"] for s in tx["steps"]] == [AVAX_USDC, ROUTER, AVUSD, SAVUSD]
    assert all(s["request"]["chainId"] == 43114 for s in tx["steps"])
    assert kyber.routes == [("avalanche", AVAX_USDC, AVUSD, 100 * 10**6)] and kyber.builds == [("avalanche", ME, 100)]
    stake = tx["steps"][-1]["request"]["data"]
    assert decode(["uint256", "address"], bytes.fromhex(stake[10:])) == (AVUSD_MIN, ME.lower())
    rows = rows_of(confirm)
    assert rows["Swap"] == "USDC → avUSD · KyberSwap via LFJ"
    assert rows["Points"] == "Only count on real mainnet. This Sandbox is a demo and earns nothing."
    assert rows["Network"] == "Avalanche (Sandbox)"
    assert tx["addTokens"] == [
        {"chainId": 43114, "address": AVUSD, "symbol": "avUSD", "decimals": 18},
        {"chainId": 43114, "address": SAVUSD, "symbol": "savUSD", "decimals": 18},
    ]
    avax.tokens.update(USDC=400 * 10**6, avUSD=AVUSD_100 - AVUSD_MIN, savUSD=82 * 10**18)
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xa"})
    assert "Staked 99.0049 avUSD into savUSD, got 82 savUSD; 1.00005 avUSD left. Confirmed on Avalanche (Sandbox), tx 0xa." in text(await task)


async def test_avant_needs_the_avalanche_sandbox():
    tools = WalletTools(FakeChain(tokens={"USDC": 500 * 10**6}), Outbox(), WalletContext(address=ME), Proposals(), kyber=FakeKyber())
    assert text(await tools.propose_deposit({"farm": "avant", "amount": "10"})) == "Avant farming isn't set up on this Sandbox."
```

In `agent/tests/test_tools.py`, add `"mcp__wallet__propose_deposit",` after `"mcp__wallet__list_airdrops",`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --directory agent pytest -q tests/test_airdrop_tools.py tests/test_tools.py`
Expected: FAIL — `ImportError: cannot import name 'DEPOSIT_TOOL'`.

- [ ] **Step 3: Split `kyber_swap` out of `kyber_plan`** in `agent/lazyagent/kyber.py`. Replace the whole `async def kyber_plan(...)` function (from its `async def` line down to its final `return ...` line) with:

```python
@dataclass(frozen=True)
class KyberSwap:
    steps: list[Step]
    verified: Verified
    label: str
    impact: float | None
    bps: int


async def kyber_swap(client: Kyber, chain: Chain, net: Network, tin: Token, tout: Token, amount: int, user: str, slippage: str | None) -> KyberSwap:
    """Route, build, verify and simulate a KyberSwap swap."""
    bps = kyber_slippage(slippage)
    req = SwapRequest(kyber_asset(tin), kyber_asset(tout), amount, user, bps)
    route = await client.route(net.key, req.token_in, req.token_out, amount)
    summary = route["routeSummary"]
    v = verify(await client.build(net.key, summary, user, bps), req, _int(summary.get("amountOut")))
    allowance, override = 0, None
    if tin.address is not None:
        allowance = int.from_bytes((await chain.call(tin.address, encode_erc20_allowance(user, ROUTER)))[:32], "big")
        if allowance < amount:
            override = await allowance_override(chain, tin.address, user, amount)
    await simulate(chain, user, v, override)
    steps = kyber_steps(tin, tout, amount, allowance, v, max(_int(summary.get("gas")), SWAP_GAS_FLOOR))
    return KyberSwap(steps, v, kyber_label(summary), usd_impact(summary), bps)


async def kyber_plan(
    client: Kyber, chain: Chain, net: Network, tin: Token, tout: Token, amount: int, user: str, slippage: str | None
) -> tuple[list[Step], Callable[[float], list[dict]], str, None]:
    """kyber_swap as propose_swap's plan: (steps, rows(fee_usd), revert hint, None)."""
    k = await kyber_swap(client, chain, net, tin, tout, amount, user, slippage)

    def rows(fee_usd: float) -> list[dict]:
        base = swap_rows(user, tin, tout, amount, k.verified.expected, k.verified.minimum, k.label, k.impact, fee_usd, network=net.label)
        return base + token_address_rows(tin, tout)

    return k.steps, rows, f" The price probably moved more than the {k.bps / 100:g}% slippage — ask again for a fresh quote.", None
```

Run: `uv run --directory agent pytest -q tests/test_kyber.py tests/test_kyber_tools.py`
Expected: PASS (unchanged behaviour).

- [ ] **Step 4: Gas budget.** In `agent/lazyagent/swaps.py`, change the `GAS` line to:

```python
GAS = {"approve": 60_000, "permit2": 60_000, "wrap": 60_000, "swap1": 170_000, "swap2": 220_000, "deposit": 120_000}
```

(the fork measured 88k for `sthUSD.deposit`).

- [ ] **Step 5: Append the deposit helpers** to `agent/lazyagent/airdrops.py`:

```python
# --- deposit calldata ---


def _call(signature: str, types: list[str], values: list) -> str:
    return "0x" + (Web3.keccak(text=signature)[:4] + encode(types, values)).hex()


def encode_erc4626_deposit(assets: int, receiver: str) -> str:
    return _call("deposit(uint256,address)", ["uint256", "address"], [assets, receiver])


def encode_preview_deposit(assets: int) -> str:
    return _call("previewDeposit(uint256)", ["uint256"], [assets])


def encode_max_deposit(receiver: str) -> str:
    return _call("maxDeposit(address)", ["address"], [receiver])


ENCODED_ASSET = _call("asset()", [], [])


def _word(raw: bytes) -> int:
    return int.from_bytes(raw[:32], "big")


@dataclass(frozen=True)
class DepositPlan:
    allowance: int  # the user's current allowance of the asset to the vault
    shares: int  # previewDeposit(assets)
    step: Step


async def deposit_plan(chain: Chain, dep: Deposit, user: str, assets: int) -> DepositPlan:
    """Checks the vault on-chain (guards against a stale JSON or an upgraded proxy) and builds the deposit step."""
    vault = dep.vault.address
    closed = TransferError(f"{dep.name}'s vault isn't accepting deposits right now.")
    try:
        asset = Web3.to_checksum_address((await chain.call(vault, ENCODED_ASSET))[12:32])
        room = _word(await chain.call(vault, encode_max_deposit(user)))
    except Exception as e:
        raise closed from e
    if asset != dep.asset.address or room < assets:
        raise closed
    shares = _word(await chain.call(vault, encode_preview_deposit(assets)))
    allowance = _word(await chain.call(dep.asset.address, encode_erc20_allowance(user, vault)))
    request = {"to": vault, "value": "0", "data": encode_erc4626_deposit(assets, user)}
    return DepositPlan(allowance, shares, Step(f"Stake {dep.asset.symbol} → {dep.vault.symbol}", request, GAS["deposit"]))


def farm_rows(
    sender: str, program: Program, pay: Token, asset: Token, vault: Token, amount: int, expected: int, minimum: int,
    shares: int, venue: str, fee_usd: float, network: str,
) -> list[dict]:
    return [
        {"label": "From", "value": short(sender)},
        {"label": "You pay", "value": f"{format_units(amount, pay.decimals)} {pay.symbol}"},
        {"label": "Swap", "value": f"{pay.symbol} → {asset.symbol} · {venue}"},
        {"label": "Expected", "value": f"≈ {display_units(expected, asset.decimals)} {asset.symbol}"},
        {"label": "Stake", "value": f"{display_units(minimum, asset.decimals)} {asset.symbol} → ≈ {display_units(shares, vault.decimals)} {vault.symbol}"},
        {"label": "Left in wallet", "value": f"≈ {display_units(expected - minimum, asset.decimals)} {asset.symbol}"},
        {"label": "Program", "value": f"{program.name} — {program.reward}"},
        {"label": "Points", "value": POINTS_NOTICE},
        *token_address_rows(asset, vault),
        {"label": "Network fee", "value": f"~{format_usd(fee_usd)}"},
        {"label": "Network", "value": network},
    ]


DEPOSIT_TOOL = (
    "propose_deposit",
    "Farm an executable airdrop program (executable true in list_airdrops: Theo, Avant): swaps USDC to the "
    "program's token and stakes it, on the program's own network, in one confirmation card. Waits for approve/reject "
    "and returns what was staked.",
    {
        "type": "object",
        "properties": {
            "farm": {"type": "string", "description": "The program id from list_airdrops (e.g. 'theo-thusd') or its short name ('Theo', 'Avant')"},
            "amount": {"type": "string", "description": "Decimal USDC amount, e.g. '100'"},
        },
        "required": ["farm", "amount"],
    },
)
```

- [ ] **Step 6: `propose_deposit` in `agent/lazyagent/tools.py`.**

Replace the Task 3 import line `from .airdrops import AIRDROPS, AIRDROPS_TOOL, AirdropError, Airdrops, airdrops_reply` with:

```python
from .airdrops import (
    AIRDROPS,
    AIRDROPS_TOOL,
    DEPOSIT_TOOL,
    V4_THEN_KYBER,
    AirdropError,
    Airdrops,
    Deposit,
    airdrops_reply,
    deposit_plan,
    farm_rows,
    find_program,
)
```

Change `from .kyber import Kyber, kyber_plan` to `from .kyber import Kyber, kyber_plan, kyber_swap`. In the `from .swaps import (...)` block add `DEFAULT_SLIPPAGE_BPS,` (after `DEADLINE_S,`) and `erc20_approval,` (after `display_units,`). Change `from .tokens import find_token` to `from .tokens import Token, find_token`. In the `from .uniswap import (...)` block add `Hop,` (after `ChainQuoter,`) and `Route,` (after `Quoter,`).

In `TOOL_NAMES`, append `"propose_deposit"` after `"list_airdrops"`.

Insert directly below the `list_airdrops` method (above `async def unsupported_action`):

```python
    async def _farm_swap(self, net: Network, dep: Deposit, usdc, asset, amount: int):
        """USDC → the farm's token on the deposit's venue: the pinned Uniswap v4 pool first (V4_THEN_KYBER), else
        KyberSwap with all of kyber.py's checks. Returns (steps, expected, minimum, venue label, price impact or None)."""
        if dep.venue == V4_THEN_KYBER:
            route = Route((currency_of(usdc), asset.address), (Hop(dep.fee, dep.tick_spacing),))
            expected = await self.quoter.quote(route, amount)
            if expected:
                probe_in = max(amount // 1000, 1)
                impact = price_impact(amount, expected, probe_in, await self.quoter.quote(route, probe_in) or 0)
                minimum = min_out(expected, DEFAULT_SLIPPAGE_BPS)
                now = await self.chain.block_timestamp()
                steps = await self._approvals(usdc, amount, now)
                swap = {"to": UNIVERSAL_ROUTER, "value": "0", "data": encode_swap(route, amount, minimum, now + DEADLINE_S)}
                steps.append(Step(f"Swap {usdc.symbol} → {asset.symbol}", swap, GAS["swap1"]))
                return steps, expected, minimum, f"Uniswap v4 {dep.fee / 10_000:g}%", impact
        if self.kyber is None:
            raise TransferError(f"I couldn't get a quote for {usdc.symbol} → {asset.symbol} on Sandbox right now.")
        k = await kyber_swap(self.kyber, self.chains[net.key], net, usdc, asset, amount, self.ctx.address, f"{DEFAULT_SLIPPAGE_BPS / 100:g}")
        return k.steps, k.verified.expected, k.verified.minimum, k.label, k.impact

    async def propose_deposit(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        program = find_program(str(args.get("farm", "")))
        if program is None:
            return err("I don't know that program. Call list_airdrops for the ids.")
        if program.deposit is None:
            return err(f"I can list {program.name} but can't farm it from here yet.")
        dep = program.deposit
        net = next((n for n in self.networks if n.key == dep.network), None)
        if net is None:
            return err(f"{dep.name} farming isn't set up on this Sandbox.")
        chain = self.chains[net.key]
        usdc = find_token(dep.pay, net.tokens)
        asset, vault = (Token(t.symbol, t.address, t.decimals, custom=True) for t in (dep.asset, dep.vault))
        try:
            amount = parse_amount(str(args.get("amount", "")), usdc.decimals)
            balance = await self._balance_on(net, usdc)
            if amount > balance:
                raise TransferError(f"You only have {format_units(balance, usdc.decimals)} {usdc.symbol}.")
            swap_steps, expected, minimum, venue, impact = await self._farm_swap(net, dep, usdc, asset, amount)
            if impact is not None and impact > MAX_PRICE_IMPACT:
                raise TransferError(f"That trade would move the price by about {impact:.0%}. Try a smaller amount.")
            plan = await deposit_plan(chain, dep, self.ctx.address, minimum)
            steps = swap_steps + erc20_approval(asset, plan.allowance, minimum, vault.address) + [plan.step]
            native_balance = await chain.eth_balance(self.ctx.address)
            reserve = gas_reserve(steps, await chain.gas_price())
            check_swap_funds(usdc, amount, balance, native_balance, reserve, native=net.native.symbol)
            fee_usd = float(Decimal(reserve // FEE_HEADROOM).scaleb(-18)) * await chain.price_usd(net.native)
            before = await self._snapshot(net, [usdc, asset, vault])
        except TransferError as e:
            return err(str(e))
        except Exception as e:
            return err(f"The {net.name} Sandbox chain isn't reachable right now ({e}).")

        human_in = f"{format_units(amount, usdc.decimals)} {usdc.symbol}"
        steps_json = self._steps_json([s.to_json() for s in steps], net)
        rows = farm_rows(self.ctx.address, program, usdc, asset, vault, amount, expected, minimum, plan.shares, venue, fee_usd, net.label)
        tx = {
            "title": f"Farm {dep.name} points: {human_in} → {vault.symbol}",
            "from": self.ctx.address,
            "rows": rows,
            "steps": steps_json,
            "addTokens": [{"chainId": net.chain_id, "address": t.address, "symbol": t.symbol, "decimals": t.decimals} for t in (asset, vault)],
        }
        pid, fut = self.proposals.new()
        await self.send({"type": "confirm", "id": pid, "tx": tx})
        result = await self.proposals.wait(pid, fut, self.approval_timeout)
        success = ""
        if _succeeded(result):
            after, change = await self._show_change(net, [usdc, asset, vault], before)
            staked = f"Staked {display_units(minimum, asset.decimals)} {asset.symbol} into {vault.symbol}"
            if after:
                got = display_units(max(after[vault.symbol] - before[vault.symbol], 0), vault.decimals)
                left = display_units(max(after[asset.symbol] - before[asset.symbol], 0), asset.decimals)
                staked += f", got {got} {vault.symbol}; {left} {asset.symbol} left"
            success = f"{staked}. Confirmed on {net.label}, tx {result.get('hash')}.{change} Points only count on real mainnet; this Sandbox is a demo."
        hint = f" The price probably moved more than the {DEFAULT_SLIPPAGE_BPS / 100:g}% slippage — ask again for a fresh quote."
        return ok(outcome_text(result, steps_json, "deposit", success, revert_hint=hint))
```

In `build_mcp_server`, after `tool(*AIRDROPS_TOOL)(t.list_airdrops),` add:

```python
            tool(*DEPOSIT_TOOL)(t.propose_deposit),
```

- [ ] **Step 7: Prompt.** In `agent/lazyagent/prompt.py`, insert this line directly after the `list_airdrops` bullet (before the "Whenever you talk about farming" bullet):

```text
- "Farm Theo with 50 USDC", "Farm Avant with 50 USDC", "stake into Theo" → propose_deposit with the farm id (or its name) and the USDC amount; it runs on the program's own network, so don't pass one. "Buy 50 USDC of reUSD (0x…)" → propose_swap with token_in USDC, token_out that contract address and amount 50. For hold-type programs (Re, Tori) offer to buy the farm token only if its buyable isn't false, using the contract address from list_airdrops.
```

insert this line directly after the "Whenever you talk about farming" bullet:

```text
- If a program has demo_assumption, treat it as running as listed and never state its real season or claim dates.
```

and replace the bridging line with:

```text
- Bridging between networks, schedules, price alerts, other dApps, staking anywhere else, withdrawals or unstaking, or anything else → unsupported_action.
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run --directory agent pytest -q tests/test_airdrop_tools.py tests/test_tools.py tests/test_kyber.py tests/test_kyber_tools.py tests/test_swap_tools.py`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add agent/lazyagent/kyber.py agent/lazyagent/swaps.py agent/lazyagent/airdrops.py agent/lazyagent/tools.py agent/lazyagent/prompt.py agent/tests/test_airdrop_tools.py agent/tests/test_tools.py
git commit -m "feat(agent): propose_deposit farms Theo (Ethereum) and Avant (Avalanche) in one card each"
```

---

### Task 5: Opt-in fork tests — Theo on Ethereum, Avant on Avalanche

**Files:**
- Test: `agent/tests/test_deposit_fork.py` (new)

**Interfaces:**
- Consumes: `fork_rpc` / `avax_fork_rpc` fixtures (conftest; Anvil on the conftest test ports, never 8545–8547), `test_swap_fork.funded_account(rpc, usdc=...)`, USDC funded by storage write (slot 9 on both chains), `devsigner.execute_steps`, the real `RpcChain`, `WalletTools` (default `ChainQuoter`) and `KyberClient` (live API; the Avant test skips if KyberSwap has no USDC → avUSD route).
- Produces: nothing new — verifies Tasks 1–4 against mainnet state.

- [ ] **Step 1: Write the test** — create `agent/tests/test_deposit_fork.py`:

```python
"""Opt-in: the two executable farms end to end on forks, one per chain — Theo on Ethereum (pinned Uniswap v4 pool)
and Avant on Avalanche (real KyberSwap API, simulated on the fork before the card)."""

import asyncio

import pytest
from eth_abi import encode
from eth_account import Account
from test_swap_fork import USDC, funded_account
from web3 import AsyncHTTPProvider, AsyncWeb3, Web3
from web3.middleware import ExtraDataToPOAMiddleware

from fakes import FakeChain
from lazyagent.chain import RpcChain
from lazyagent.devsigner import execute_steps
from lazyagent.kyber import KyberClient
from lazyagent.networks import AVALANCHE
from lazyagent.proposals import Proposals
from lazyagent.tokens import Token, find_token
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.transfers import TransferError

THUSD = Token("thUSD", "0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3", 6, custom=True)
STHUSD = Token("sthUSD", "0xA808Bc9775cb41c52C7842f8b50427fE7A770326", 6, custom=True)
AVAX_USDC = find_token("USDC", AVALANCHE.tokens)
AVUSD = Token("avUSD", "0x24dE8771bC5DdB3362Db529Fc3358F2df3A0E346", 18, custom=True)
SAVUSD = Token("savUSD", "0x06d47F3fb376649c3A9Dafe069B3D6E35572219E", 18, custom=True)
USDC_BALANCE_SLOT = 9  # Circle FiatToken on both chains


def approving(w3, account, proposals: Proposals, seen: list[dict]):
    async def send(msg: dict) -> None:
        if msg["type"] == "confirm":
            seen.append(msg)

            async def approve() -> None:
                proposals.resolve(msg["id"], await execute_steps(w3, account.key.to_0x_hex(), msg["tx"]["steps"]))

            asyncio.create_task(approve())

    return send


async def test_farm_theo_on_a_fork(fork_rpc):
    w3, account = await funded_account(fork_rpc, usdc=500 * 10**6)
    proposals, seen = Proposals(), []
    chain = RpcChain(fork_rpc)
    tools = WalletTools(chain, approving(w3, account, proposals, seen), WalletContext(address=account.address), proposals, approval_timeout=120)
    result = await tools.propose_deposit({"farm": "theo-thusd", "amount": "100"})
    text = result["content"][0]["text"]
    assert "Staked" in text and "into sthUSD" in text, text
    assert [s["label"] for s in seen[0]["tx"]["steps"]] == [
        "Allow USDC", "Allow Uniswap router", "Swap USDC → thUSD", "Allow thUSD", "Stake thUSD → sthUSD",
    ]
    rows = {r["label"]: r["value"] for r in seen[0]["tx"]["rows"]}
    assert rows["Swap"] == "USDC → thUSD · Uniswap v4 0.01%"
    assert await chain.token_balance(USDC, account.address) == 400 * 10**6
    assert await chain.token_balance(STHUSD, account.address) > 0
    assert await chain.token_balance(THUSD, account.address) <= 100 * 10**6 * 15 // 1000  # ≤ 1.5% of the quote left


async def test_farm_avant_on_a_fork(avax_fork_rpc):
    kyber = KyberClient()
    try:
        await kyber.route("avalanche", AVAX_USDC.address, AVUSD.address, 100 * 10**6)
    except TransferError as e:
        pytest.skip(f"KyberSwap has no USDC → avUSD route right now: {e}")
    w3 = AsyncWeb3(AsyncHTTPProvider(avax_fork_rpc))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    account = Account.create()  # Kyber rejects Anvil's well-known dev accounts
    await w3.provider.make_request("anvil_setBalance", [account.address, hex(10 * 10**18)])
    key = Web3.keccak(encode(["address", "uint256"], [account.address, USDC_BALANCE_SLOT])).to_0x_hex()
    await w3.provider.make_request("anvil_setStorageAt", [AVAX_USDC.address, key, "0x" + (500 * 10**6).to_bytes(32, "big").hex()])
    proposals, seen = Proposals(), []
    avax = RpcChain(avax_fork_rpc, poa=True)
    tools = WalletTools(FakeChain(), approving(w3, account, proposals, seen), WalletContext(address=account.address), proposals,
                        approval_timeout=120, avalanche=avax, kyber=kyber)
    result = await tools.propose_deposit({"farm": "avant", "amount": "100"})
    text = result["content"][0]["text"]
    assert "Staked" in text and "into savUSD" in text and "Avalanche (Sandbox)" in text, text
    assert [s["label"] for s in seen[0]["tx"]["steps"]] == ["Allow USDC", "Swap USDC → avUSD", "Allow avUSD", "Stake avUSD → savUSD"]
    assert await avax.token_balance(AVAX_USDC, account.address) == 400 * 10**6
    assert await avax.token_balance(SAVUSD, account.address) > 0
    assert await avax.token_balance(AVUSD, account.address) <= 100 * 10**18 * 15 // 1000  # ≤ 1.5% of ~100 avUSD left
```

- [ ] **Step 2: Run it**

Run: `uv run --directory agent pytest -q tests/test_deposit_fork.py`
Expected: 2 PASS in ~40 s (Theo skips without `ETH_RPC_URL`; Avant uses `AVAX_RPC_URL` or the public Avalanche RPC). If Theo fails at the swap, the pinned pool moved — re-check the pool key with `lazyagent.uniswap.pool_id` before touching `airdrops.json`. If Avant fails at the stake, check `savUSD.asset()` and `maxDeposit` on the fork.

- [ ] **Step 3: Commit**

```bash
git add agent/tests/test_deposit_fork.py
git commit -m "test(agent): Theo and Avant farms end to end on forks"
```

---

### Task 6: Wallet — `tx.addTokens` and the `airdrops` chat message

The reducer must know the new server message **before** the agent can send it: an unknown `type` makes `onServer` return `undefined`, which would wipe the chat state. The card that renders it comes in Task 7; until then `MessageItem` renders nothing for `kind: 'airdrops'`.

**Files:**
- Modify: `apps/wallet/src/types.ts`, `apps/wallet/src/chain/executeTx.ts`, `apps/wallet/src/agent/useAgentChat.ts`, `apps/wallet/src/agent/protocol.ts`, `apps/wallet/src/agent/chatReducer.ts`
- Test: `apps/wallet/src/chain/executeTx.test.ts`, `apps/wallet/src/agent/useAgentChat.test.tsx`, `apps/wallet/src/agent/chatReducer.test.ts`

**Interfaces:**
- Consumes: the agent's confirm `tx.addTokens` (Task 4) and `{"type": "airdrops", "title", "items"}` (Task 3); `lib/tokens.saveToken(wallet, token)`.
- Produces: `TxDraft.addTokens?: CustomToken[]`; `tokensToSave(o: StepsOutcome, tx: TxDraft): CustomToken[]` (replaces `tokenToSave`; `addToken` first, then `addTokens`, deduplicated by chainId + lower-case address; `[]` unless every step succeeded); `AirdropItem` type; `Message` kind `'airdrops'` (`{ title, items }`); `ServerMsg` `{ type: 'airdrops'; title; items }`.

- [ ] **Step 1: Write the failing tests.** In `apps/wallet/src/chain/executeTx.test.ts`, change the import to `import { executeSteps, executeTx, progressText, statusPatch, tokensToSave, type TxDeps } from './executeTx'` and replace the whole `describe('tokenToSave', ...)` block with:

```ts
describe('tokensToSave', () => {
  const COQ: CustomToken = { chainId: 43114, address: '0x420FcA0121DC28039145009570975747295f2329', symbol: 'COQ', decimals: 18 }
  const THUSD: CustomToken = { chainId: 1, address: '0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3', symbol: 'thUSD', decimals: 6 }
  const STHUSD: CustomToken = { chainId: 1, address: '0xA808Bc9775cb41c52C7842f8b50427fE7A770326', symbol: 'sthUSD', decimals: 6 }
  const tx: TxDraft = { title: 'Swap 1 AVAX → COQ', rows: [], steps: ONE, addToken: COQ }
  const farm: TxDraft = { title: 'Farm Theo points: 100 USDC → sthUSD', rows: [], steps: THREE, addTokens: [THUSD, STHUSD] }
  const ok: TxDeps = { send: async () => HASH, wait: async () => 'success' }

  it('returns the tokens only when every step succeeded', async () => {
    expect(tokensToSave(await executeSteps(ONE, ok), tx)).toEqual([COQ])
    expect(tokensToSave(await executeSteps(THREE, ok), farm)).toEqual([THUSD, STHUSD])
    const reverted: TxDeps = { send: async () => HASH, wait: async () => 'reverted' }
    expect(tokensToSave(await executeSteps(ONE, reverted), tx)).toEqual([])
    expect(tokensToSave(await executeSteps(THREE, reverted), farm)).toEqual([])
    const unsent: TxDeps = {
      send: async () => {
        throw new Error('rejected')
      },
      wait: async () => 'success',
    }
    expect(tokensToSave(await executeSteps(ONE, unsent), tx)).toEqual([])
  })

  it('merges addToken and addTokens without duplicates', () => {
    const both: TxDraft = { ...farm, addToken: { ...THUSD, address: THUSD.address.toLowerCase() as CustomToken['address'] } }
    expect(tokensToSave({ hashes: [HASH], hash: HASH, status: 'success' }, both).map((t) => t.symbol)).toEqual(['thUSD', 'sthUSD'])
  })

  it('returns nothing for cards without tokens', () => {
    expect(tokensToSave({ hashes: [HASH], hash: HASH, status: 'success' }, { ...tx, addToken: undefined })).toEqual([])
  })
})
```

Append inside the `describe('useAgentChat', ...)` block of `apps/wallet/src/agent/useAgentChat.test.tsx` (after the last `it(...)`):

```tsx
  it('saves every token a farm card lists once all its steps succeed', async () => {
    localStorage.clear()
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    const live = FakeWebSocket.instances.at(-1)!
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    const me = OPTIONS.address
    const THUSD = { chainId: 1, address: '0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3', symbol: 'thUSD', decimals: 6 }
    const STHUSD = { chainId: 1, address: '0xA808Bc9775cb41c52C7842f8b50427fE7A770326', symbol: 'sthUSD', decimals: 6 }
    const step = (label: string) => ({ label, request: { to: me, value: '0', data: '0x', chainId: 1 } })
    const tx = { title: 'Farm Theo points: 100 USDC → sthUSD', from: me, rows: [], steps: [step('Swap USDC → thUSD'), step('Stake thUSD → sthUSD')], addTokens: [THUSD, STHUSD] }
    act(() => live.onmessage?.({ data: JSON.stringify({ type: 'confirm', id: 'pfarm', tx }) }))
    await act(() => result.current.approve('pfarm'))
    expect(savedTokens(me)).toEqual([THUSD, STHUSD])
  })
```

In `apps/wallet/src/agent/chatReducer.test.ts`, add above `it('adds balance and confirm cards', ...)`:

```ts
  it('adds an airdrops card and ends the streaming bubble', () => {
    const item = {
      id: 'theo-thusd', name: 'Theo thUSD Points', category: 'rwa' as const, networks: ['Ethereum'], status: 'live' as const,
      action: 'Stake thUSD into sthUSD', tvlUsd: 132e6, farm: 'Theo', buy: null,
    }
    const s = run([server({ type: 'text_delta', text: 'Here' }), server({ type: 'airdrops', title: 'RWA airdrops', items: [item] })])
    expect(s.messages[1]).toMatchObject({ role: 'assistant', kind: 'airdrops', title: 'RWA airdrops', items: [item] })
    expect(s.streamingId).toBeNull()
    expect(new Set(s.messages.map((m) => m.id)).size).toBe(2)
  })
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pnpm --filter wallet exec vitest run src/chain/executeTx.test.ts src/agent/useAgentChat.test.tsx src/agent/chatReducer.test.ts`
Expected: FAIL — `tokensToSave is not a function`, sthUSD not saved, and the reducer returns `undefined` for `airdrops` (type errors in the editor too).

- [ ] **Step 3: Implement.** In `apps/wallet/src/types.ts`, add under `addToken?` in `TxDraft`:

```ts
  addTokens?: CustomToken[] // tokens a multi-step card (e.g. a farm deposit) leaves in the wallet; saved like addToken
```

In `apps/wallet/src/chain/executeTx.ts`, replace `tokenToSave` with:

```ts
/** The tokens a card asked to remember (addToken, then addTokens; no duplicates) — only once every step succeeded. */
export function tokensToSave(o: StepsOutcome, tx: TxDraft): CustomToken[] {
  if (o.status !== 'success' || o.error) return []
  const key = (t: CustomToken) => `${t.chainId}:${t.address.toLowerCase()}`
  const all = [...(tx.addToken ? [tx.addToken] : []), ...(tx.addTokens ?? [])]
  return all.filter((t, i) => all.findIndex((u) => key(u) === key(t)) === i)
}
```

In `apps/wallet/src/agent/useAgentChat.ts`, import `tokensToSave` instead of `tokenToSave`, and replace

```ts
    const bought = tokenToSave(outcome, m.tx)
    if (bought && m.tx.from) saveToken(m.tx.from, bought)
```

with

```ts
    const from = m.tx.from
    if (from) for (const t of tokensToSave(outcome, m.tx)) saveToken(from, t)
```

In `apps/wallet/src/types.ts`, add above `export type ChoiceOption`:

```ts
// One row of the airdrops card (agent list_airdrops). farm = short name for "Farm <farm> with N USDC"; buy = a farm token to buy.
export type AirdropItem = {
  id: string
  name: string
  category: 'rwa' | 'other'
  networks: string[]
  status: 'live' | 'unverified' | 'claim_pending'
  action: string
  tvlUsd: number | null
  farm: string | null
  buy: { symbol: string; address: Address } | null
}
```

and add to the `Message` union (after the `choice` member):

```ts
  | { id: string; role: 'assistant'; kind: 'airdrops'; title: string; items: AirdropItem[] }
```

In `apps/wallet/src/agent/protocol.ts`, import `AirdropItem` from `@/types` and add to `ServerMsg` after the `choice` member:

```ts
  | { type: 'airdrops'; title: string; items: AirdropItem[] }
```

In `apps/wallet/src/agent/chatReducer.ts` (`onServer`), add before `case 'error':`:

```ts
    case 'airdrops':
      return {
        ...s,
        seq: s.seq + 1,
        streamingId: null,
        messages: [...s.messages, { id: nextId, role: 'assistant', kind: 'airdrops', title: msg.title, items: msg.items }],
      }
```

- [ ] **Step 4: Run the tests, build and lint**

Run: `pnpm --filter wallet test && pnpm build && pnpm lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/wallet/src/types.ts apps/wallet/src/chain/executeTx.ts apps/wallet/src/chain/executeTx.test.ts apps/wallet/src/agent/useAgentChat.ts apps/wallet/src/agent/useAgentChat.test.tsx apps/wallet/src/agent/protocol.ts apps/wallet/src/agent/chatReducer.ts apps/wallet/src/agent/chatReducer.test.ts
git commit -m "feat(wallet): tx.addTokens and the airdrops chat message"
```

---

### Task 7: Wallet — `AirdropCard` (after `feat-token-cards` merges)

**Precondition:** `feat-token-cards` (TokenListCard for trending) is merged into `main` and this branch is rebased onto it. Until then the `airdrops` message is stored (Task 6) but renders nothing, and the model's one sentence still reads fine — do not ship without this task.

**Check on `main` first (assumed names from `feat-token-cards`; adapt, don't duplicate):**
- `formatCompactUsd(n: number): string` in `src/lib/format.ts` — if it exists (any compact USD formatter, e.g. `$132.2M`), **skip Step 3a** and import that one in `airdrops.ts`.
- `MessageActions.onSend?: (text: string) => void` in `src/chat/MessageItem.tsx`, wired as `onSend={chat.send}` in `WalletPage.tsx` — if it exists under this or another name, **skip Steps 3d (the `onSend` part) and 3e** and use it.
- A shared amount-chip row (e.g. `AmountChips`) or a `[10, 50, 100]` constant used by `TokenListCard` — if present, use it instead of `AMOUNTS_USDC` and the inline chip `Button`s below, keeping the same messages.
- Match `TokenListCard`'s outer container, row and header classes if they differ from `rounded-2xl border bg-card p-4` / `divide-y` (the BalanceCard style used below).

**Files:**
- Create: `apps/wallet/src/chat/cards/airdrops.ts`, `apps/wallet/src/chat/cards/AirdropCard.tsx`
- Modify: `apps/wallet/src/chat/MessageItem.tsx`, `apps/wallet/src/routes/WalletPage.tsx`, `apps/wallet/src/lib/format.ts`, `apps/wallet/src/mock/fixtures.ts`
- Test: `apps/wallet/src/chat/cards/airdrops.test.ts`, `apps/wallet/src/chat/cards/AirdropCard.test.tsx`, `apps/wallet/src/lib/format.test.ts`

**Interfaces:**
- Consumes: Task 6's `AirdropItem` and `kind: 'airdrops'` message; `useAgentChat().send`.
- Produces: helpers `AMOUNTS_USDC = [10, 50, 100]`, `statusLabel(status)`, `tvlLabel(tvlUsd)`, `farmReply(farm, usdc)`, `buyReply(buy, usdc)`; `<AirdropCard title items enabled onSend />`; `MessageActions.onSend`.

- [ ] **Step 1: Write the failing tests.**

`apps/wallet/src/chat/cards/airdrops.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { AMOUNTS_USDC, buyReply, farmReply, statusLabel, tvlLabel } from './airdrops'

describe('airdrop card helpers', () => {
  it('labels statuses in plain words', () => {
    expect(statusLabel('live')).toBe('live')
    expect(statusLabel('unverified')).toBe('may have ended')
    expect(statusLabel('claim_pending')).toBe('claim not open yet')
  })

  it('shows TVL compactly, or unknown', () => {
    expect(tvlLabel(132_161_995.8)).toBe('TVL $132.2M')
    expect(tvlLabel(1_037_041)).toBe('TVL $1M')
    expect(tvlLabel(null)).toBe('TVL unknown')
  })

  it('builds the chat messages the chips send', () => {
    expect(AMOUNTS_USDC).toEqual([10, 50, 100])
    expect(farmReply('Theo', 50)).toBe('Farm Theo with 50 USDC')
    expect(farmReply('Avant', 10)).toBe('Farm Avant with 10 USDC')
    expect(buyReply({ symbol: 'reUSD', address: '0x5086bf358635B81D8C47C66d1C8b9E567Db70c72' }, 10)).toBe(
      'Buy 10 USDC of reUSD (0x5086bf358635B81D8C47C66d1C8b9E567Db70c72)',
    )
  })
})
```

`apps/wallet/src/chat/cards/AirdropCard.test.tsx`:

```tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AirdropItem } from '@/types'
import { AirdropCard } from './AirdropCard'

const THEO: AirdropItem = {
  id: 'theo-thusd', name: 'Theo thUSD Points', category: 'rwa', networks: ['Ethereum'], status: 'live',
  action: 'Stake thUSD into sthUSD', tvlUsd: 132e6, farm: 'Theo', buy: null,
}
const RE: AirdropItem = {
  id: 're', name: 'Re Points Season 2', category: 'rwa', networks: ['Ethereum', 'Avalanche'], status: 'live',
  action: 'Hold reUSD', tvlUsd: null, farm: null, buy: { symbol: 'reUSD', address: '0x5086bf358635B81D8C47C66d1C8b9E567Db70c72' },
}
const AVANT: AirdropItem = {
  id: 'avant', name: 'Avant Season 1 points', category: 'other', networks: ['Avalanche'], status: 'live',
  action: 'Stake avUSD into savUSD', tvlUsd: 126e6, farm: 'Avant', buy: null,
}
const SUZAKU: AirdropItem = {
  id: 'suzaku-s2', name: 'Suzaku Points Season 2', category: 'other', networks: ['Avalanche'], status: 'unverified',
  action: 'Deposit into Suzaku restaking vaults', tvlUsd: 1e6, farm: null, buy: null,
}

describe('AirdropCard', () => {
  afterEach(cleanup)

  it('Farm reveals amount chips and sends the farm message, one farm per chain', () => {
    const onSend = vi.fn()
    render(<AirdropCard title="Airdrops" items={[THEO, RE, AVANT, SUZAKU]} enabled onSend={onSend} />)
    expect(screen.getByText('Airdrops')).toBeTruthy()
    expect(screen.getByText('may have ended')).toBeTruthy()
    expect(screen.queryByText('$50')).toBeNull()
    const [theoFarm, avantFarm] = screen.getAllByText('Farm')
    fireEvent.click(theoFarm)
    fireEvent.click(screen.getByText('$50'))
    expect(onSend).toHaveBeenLastCalledWith('Farm Theo with 50 USDC')
    expect(screen.queryByText('$50')).toBeNull()
    fireEvent.click(avantFarm)
    fireEvent.click(screen.getByText('$100'))
    expect(onSend).toHaveBeenLastCalledWith('Farm Avant with 100 USDC')
  })

  it('Buy sends the token with its contract address; rows without either get no button', () => {
    const onSend = vi.fn()
    render(<AirdropCard title="Airdrops" items={[RE, SUZAKU]} enabled onSend={onSend} />)
    expect(screen.getAllByRole('button')).toHaveLength(1)
    fireEvent.click(screen.getByText('Buy reUSD'))
    fireEvent.click(screen.getByText('$10'))
    expect(onSend).toHaveBeenCalledWith('Buy 10 USDC of reUSD (0x5086bf358635B81D8C47C66d1C8b9E567Db70c72)')
  })

  it('buttons are disabled while the agent is busy or offline', () => {
    render(<AirdropCard title="Airdrops" items={[THEO]} enabled={false} onSend={vi.fn()} />)
    expect((screen.getByText('Farm') as HTMLButtonElement).disabled).toBe(true)
  })
})
```

In `apps/wallet/src/lib/format.test.ts` (skip if `formatCompactUsd` already exists), import `formatCompactUsd` and add after the `'formats USD'` test:

```ts
  it('formats large USD compactly', () => {
    expect(formatCompactUsd(132_161_995.8)).toBe('$132.2M')
    expect(formatCompactUsd(1_037_041)).toBe('$1M')
    expect(formatCompactUsd(950)).toBe('$950')
  })
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pnpm --filter wallet test`
Expected: FAIL — cannot resolve `./airdrops` / `./AirdropCard`, `formatCompactUsd` not exported.

- [ ] **Step 3: Implement.**

a. `apps/wallet/src/lib/format.ts` (skip if a compact formatter exists) — add above `formatAmount`:

```ts
const compactUsd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', minimumFractionDigits: 0, maximumFractionDigits: 1 })

export function formatCompactUsd(n: number): string {
  return compactUsd.format(n)
}
```

b. `apps/wallet/src/chat/cards/airdrops.ts`:

```ts
import { formatCompactUsd } from '@/lib/format'
import type { AirdropItem } from '@/types'

export const AMOUNTS_USDC = [10, 50, 100] as const

const STATUS: Record<AirdropItem['status'], string> = { live: 'live', unverified: 'may have ended', claim_pending: 'claim not open yet' }

export function statusLabel(status: AirdropItem['status']): string {
  return STATUS[status] ?? status
}

export function tvlLabel(tvlUsd: number | null): string {
  return tvlUsd === null ? 'TVL unknown' : `TVL ${formatCompactUsd(tvlUsd)}`
}

/** What a Farm chip sends — the agent maps it to propose_deposit. */
export function farmReply(farm: string, usdc: number): string {
  return `Farm ${farm} with ${usdc} USDC`
}

/** What a Buy chip sends — the full address so the agent swaps the exact token. */
export function buyReply(buy: NonNullable<AirdropItem['buy']>, usdc: number): string {
  return `Buy ${usdc} USDC of ${buy.symbol} (${buy.address})`
}
```

c. `apps/wallet/src/chat/cards/AirdropCard.tsx`:

```tsx
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { AirdropItem } from '@/types'
import { AMOUNTS_USDC, buyReply, farmReply, statusLabel, tvlLabel } from './airdrops'

type Props = { title: string; items: AirdropItem[]; enabled: boolean; onSend: (text: string) => void }

export function AirdropCard({ title, items, enabled, onSend }: Props) {
  // Which row's amount chips are open: `${id}:farm` or `${id}:buy`.
  const [open, setOpen] = useState<string | null>(null)
  return (
    <div className="rounded-2xl border bg-card p-4">
      <p className="text-sm text-muted-foreground">{title}</p>
      <ul className="mt-2 divide-y">
        {items.map((a) => {
          const action = a.farm ? 'farm' : a.buy ? 'buy' : null
          const key = `${a.id}:${action}`
          return (
            <li key={a.id} className="py-3">
              <div className="flex items-start justify-between gap-3">
                <span className="min-w-0">
                  <span className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium">{a.name}</span>
                    <Badge variant={a.category === 'rwa' ? 'default' : 'secondary'}>{a.category === 'rwa' ? 'RWA' : 'other'}</Badge>
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {a.networks.join(' · ')} · <span className={cn(a.status === 'live' ? 'text-primary' : 'text-muted-foreground')}>{statusLabel(a.status)}</span>
                  </span>
                  <span className="mt-1 block text-sm">{a.action}</span>
                </span>
                <span className="shrink-0 text-right">
                  <span className="block font-mono text-xs text-muted-foreground">{tvlLabel(a.tvlUsd)}</span>
                  {action && (
                    <Button size="sm" variant="secondary" className="mt-1.5" disabled={!enabled} onClick={() => setOpen(open === key ? null : key)}>
                      {action === 'farm' ? 'Farm' : `Buy ${a.buy?.symbol}`}
                    </Button>
                  )}
                </span>
              </div>
              {action && open === key && (
                <div className="mt-2 flex justify-end gap-2">
                  {AMOUNTS_USDC.map((usdc) => (
                    <Button
                      key={usdc}
                      size="sm"
                      variant="outline"
                      className="font-mono"
                      disabled={!enabled}
                      onClick={() => {
                        setOpen(null)
                        onSend(a.farm ? farmReply(a.farm, usdc) : buyReply(a.buy!, usdc))
                      }}
                    >
                      ${usdc}
                    </Button>
                  ))}
                </div>
              )}
            </li>
          )
        })}
      </ul>
      <p className="mt-2 text-xs text-muted-foreground">Points only count on real mainnet. This Sandbox is a demo.</p>
    </div>
  )
}
```

d. `apps/wallet/src/chat/MessageItem.tsx` — `import { AirdropCard } from './cards/AirdropCard'`; add `onSend?: (text: string) => void` to `MessageActions` (skip if present); destructure `onSend` in `AssistantBody`; add the case after `'choice'`:

```tsx
    case 'airdrops':
      return <AirdropCard title={message.title} items={message.items} enabled={choicesEnabled} onSend={(t) => onSend?.(t)} />
```

e. `apps/wallet/src/routes/WalletPage.tsx` — on `<ChatView ...>`, add `onSend={chat.send}` after `onChoose={chat.choose}` (skip if present).

f. `apps/wallet/src/mock/fixtures.ts` — in `EXAMPLES`, add `'What RWA airdrops can I farm?',` after `'Swap 100 USDC to ETH',`.

- [ ] **Step 4: Run the tests, build and lint**

Run: `pnpm --filter wallet test && pnpm build && pnpm lint`
Expected: PASS (lint: only the existing shadcn `only-export-components` warnings in `components/ui`).

- [ ] **Step 5: Commit**

```bash
git add apps/wallet/src/chat apps/wallet/src/routes/WalletPage.tsx apps/wallet/src/lib apps/wallet/src/mock/fixtures.ts
git commit -m "feat(wallet): airdrops card with Farm and Buy amount chips"
```

---

### Task 8: Docs, planning decisions, full verification, manual check

**Files:**
- Modify: `CLAUDE.md`, `docs/superpowers/specs/2026-10-15-lazywallet-rwa-airdrops-design.md`

- [ ] **Step 1: `CLAUDE.md`.** After the KyberSwap bullet under "Wallet app conventions", add:

```markdown
- Airdrops (`list_airdrops`, `propose_deposit`) live in `agent/lazyagent/airdrops.py`; the programs are curated by hand in `agent/lazyagent/data/airdrops.json` (each with `source_url`, `verified_at`) and enriched live (DefiLlama TVL, GeckoTerminal liquidity, 10 min cache). `list_airdrops` sends an `airdrops` card; titles never name a chain. Only entries with a `deposit` block are farmable, one per chain: Theo (USDC → thUSD on the pinned v4 pool, KyberSwap fallback, then `sthUSD.deposit`) and Avant (USDC → avUSD on KyberSwap, then `savUSD.deposit`), each staking the swap's minimum. Avant Season 1 is a demo assumption (`demo_assumption` in the JSON) — never state its real dates. Change a deposit block only with `tests/test_deposit_fork.py`. Points only count on real mainnet — the Sandbox is a demo.
```

- [ ] **Step 2: Record planning decisions in the spec.** Set `Status:` to `Implemented on feat-rwa-airdrops`, then append:

```markdown
## 11. Decisions made while planning

- Visual card: `list_airdrops` sends `{"type": "airdrops", "title": "RWA airdrops" | "Airdrops", "items": [...]}` and the model answers in one sentence. Items: `id, name, category, networks (display names), status, action, tvlUsd, farm (short name) | null, buy {symbol, address} | null`. Buy = the first farm token (on the requested network, if any) whose `buyable` isn't `false`; executable entries get Farm instead. Chips send `Farm Theo with 50 USDC` / `Buy 50 USDC of reUSD (0x…)`.
- Titles and suggestions never name a chain: the Points row reads "Only count on real mainnet. This Sandbox is a demo and earns nothing." (§2 said "real Ethereum mainnet"); the Aave entry is named "Aave V4 WAVAX incentives".
- `Deposit` gets a `venue` (`uniswap_v4_pinned_then_kyber` | `kyber`) so Theo and Avant share one code path, and a `name` ("Theo", "Avant") so `propose_deposit` accepts the id or the short name; the JSON `deposit.asset` is resolved to its farm token (symbol + decimals).
- `filter` is named `filter_programs` (no shadowing of the builtin) and filters before enrichment, so a filtered request makes fewer HTTP calls. `action_kind` adds `claim` (Avant).
- `kyber_swap()` is split out of `kyber_plan` (same checks) so the deposit can stake KyberSwap's verified minimum; the fallback uses 1% slippage, not the Sandbox 50% default.
- Card rows: the vault address row is `sthUSD address` (from `token_address_rows`, same as custom-token swaps).
- `addTokens` handling: `tokenToSave` became `tokensToSave` (array; `addToken` first, deduplicated).
- Avant (user decision, after the plan was written): Season 1 is treated as running for the hackathon demo — `status: "live"`, `action_kind: "deposit"`, category `other`, `season_ends: null`, plus `demo_assumption` recording the real state (ended 2026-05-15, AVANT claim pending). It is the Avalanche farm: USDC → avUSD on KyberSwap, then `savUSD.deposit` of the swap's minimum (savUSD verified on a fork: `asset()` = avUSD, `maxDeposit` unlimited, no pause switch). The prompt forbids stating real dates for entries with `demo_assumption`.
- DefiLlama slugs: Re is `re`; Avant uses the parent `avant-protocol` (Avalanche TVL only); Aave uses `aave-v4` (Avalanche TVL only).
```

- [ ] **Step 3: Full verification**

Run: `pnpm test:py && pnpm --filter wallet test && pnpm build && pnpm lint`
Expected: all PASS (the fork tests run when `ETH_RPC_URL` is set).

- [ ] **Step 4: Manual check.** Start `pnpm dev:sandbox`, `pnpm dev:agent` and `pnpm dev`; open `http://localhost:5174`, get test funds.

1. Tap the example "What RWA airdrops can I farm?" → a card titled **RWA airdrops** with Theo (Farm) and Re (Buy reUSD), TVLs, status "live"; the agent says one sentence that mentions points only count on real mainnet.
2. "Any airdrops?" → card titled **Airdrops**: Theo (Farm), Re (Buy reUSD), Avant (Farm), Tori (Buy trUSD), Aave V4 WAVAX incentives, Suzaku ("may have ended"). The agent never mentions Avant's real season dates.
3. "Any airdrops on Avalanche?" → title still **Airdrops** (no chain); Re has no Buy button (Avalanche reUSD isn't buyable).
4. On the Theo row tap Farm → $50 → the message "Farm Theo with 50 USDC" is sent → one confirm card titled "Farm Theo points: 50 USDC → sthUSD" with 5 steps, the Points row and both token addresses → Approve → the reply reports sthUSD received and thUSD left; "What's my balance" shows thUSD and sthUSD (sthUSD may be "price unknown" — spec §10.1).
5. On the Avant row tap Farm → $10 → "Farm Avant with 10 USDC" → a card titled "Farm Avant points: 10 USDC → savUSD" with 4 steps, Network "Avalanche (Sandbox)" and a Swap row "USDC → avUSD · KyberSwap via …" → Approve → the reply reports savUSD received and avUSD left.
6. On Re tap Buy reUSD → $10 → "Buy 10 USDC of reUSD (0x5086…)" → a KyberSwap swap card on Ethereum.
7. While the agent is answering, the Farm/Buy buttons are disabled.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-10-15-lazywallet-rwa-airdrops-design.md
git commit -m "docs: RWA airdrops list, Theo and Avant farms"
```

---

## Merge note

`feat-token-cards` is in flight. If it lands first, rebase and do Task 7 against it (see its "check on `main` first" list). If this branch lands first, Tasks 1–6 and 8 can merge without Task 7 only with the user's OK; otherwise hold the merge until Task 7 is done. Expected additive conflicts (keep both sides): `tools.py` (`TOOL_NAMES`, imports, registration), `prompt.py` bullets, `test_tools.py`, the end of `fakes.py`, `types.ts` (`Message` union), `protocol.ts` (`ServerMsg`), `chatReducer.ts` (cases), `MessageItem.tsx` (cases, `MessageActions`), `WalletPage.tsx`, `lib/format.ts`, `CLAUDE.md`.
