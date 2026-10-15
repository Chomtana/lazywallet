"""SwapScheduler (contracts/): pinned addresses, calldata, order reads and confirm-card steps.
The model never builds calldata — this module does."""

from dataclasses import dataclass

from eth_abi import decode
from web3 import Web3

from .networks import Network
from .swaps import Step, display_units
from .tokens import Token, find_token
from .transfers import TransferError, format_units, short
from .uniswap import WETH_DEPOSIT, _call, encode_erc20_approve

# = contracts/src/Deployment.sol (CREATE2, identical on both forks)
SCHEDULER = Web3.to_checksum_address("0xE99d9DFBeA09687AdCDdB9a45914d778f330b513")
SWAPPER = Web3.to_checksum_address("0x4244a49afdBE8d73A3b8e430D5bCCBd6116B998B")
FIXED_GAS = 300_000
MIN_INTERVAL_S = 60
MAX_COUNT = 100
MIN_OUT_DISCOUNT_BPS = 500
MAX_LISTED = 200
GAS = {"wrap": 60_000, "approve": 60_000, "schedule": 220_000, "cancel": 60_000}
WRAPPED = {1: "WETH", 43114: "WAVAX"}
ORDER_ABI = "(address,address,address,uint256,uint256,uint64,uint64,uint32,uint32,uint64,bool)"
CALL_ABI = "(address,uint256,bytes)"
NEXT_ID = _call("nextId()", [], [])

Call = tuple[str, int, str]  # target, value, hex calldata


@dataclass(frozen=True)
class Order:
    id: int
    owner: str
    token_in: str
    token_out: str
    amount_in: int
    min_out: int
    start_time: int
    interval: int
    count: int
    executed: int
    next_time: int
    cancelled: bool

    @property
    def active(self) -> bool:
        return not self.cancelled and self.executed < self.count

    def due(self, now: int) -> bool:
        return self.active and self.next_time <= now


def encode_schedule(token_in: str, token_out: str, amount_in: int, min_out: int, start: int, interval: int, count: int) -> str:
    types = ["address", "address", "uint256", "uint256", "uint64", "uint64", "uint32"]
    return _call(f"scheduleSwap({','.join(types)})", types, [token_in, token_out, amount_in, min_out, start, interval, count])


def encode_cancel(order_id: int) -> str:
    return _call("cancel(uint256)", ["uint256"], [order_id])


def encode_execute(order_id: int, calls: list[Call]) -> str:
    values = [(Web3.to_checksum_address(t), v, bytes.fromhex(d.removeprefix("0x"))) for t, v, d in calls]
    return _call(f"executeSwap(uint256,{CALL_ABI}[])", ["uint256", f"{CALL_ABI}[]"], [order_id, values])


def encode_get_order(order_id: int) -> str:
    return _call("getOrder(uint256)", ["uint256"], [order_id])


def encode_gas_balance(owner: str) -> str:
    return _call("gasBalance(address)", ["address"], [owner])


def decode_order(order_id: int, data: bytes) -> Order:
    v = decode([ORDER_ABI], data)[0]
    return Order(order_id, *(Web3.to_checksum_address(a) for a in v[:3]), *v[3:])


def _uint(data: bytes) -> int:
    return int.from_bytes(data[:32], "big")


async def read_orders(chain, owner: str | None = None) -> list[Order]:
    """The newest MAX_LISTED orders, optionally only `owner`'s. No contract on this chain → no orders."""
    n = _uint(await chain.call(SCHEDULER, NEXT_ID))
    orders = [decode_order(i, await chain.call(SCHEDULER, encode_get_order(i))) for i in range(max(0, n - MAX_LISTED), n)]
    return [o for o in orders if owner is None or o.owner.lower() == owner.lower()]


async def gas_balance(chain, owner: str) -> int:
    return _uint(await chain.call(SCHEDULER, encode_gas_balance(owner)))


def gas_top_up(gas_price: int, count: int, balance: int) -> int:
    return max(0, FIXED_GAS * gas_price * count * 2 - balance)


def parse_schedule(interval, count, delay) -> tuple[int, int, int]:
    """(interval seconds, run count, start delay seconds). One run → interval 0."""
    if interval not in (None, "") and count in (None, ""):
        raise TransferError("How many times should it run? Give a count with the interval.")
    try:
        n = int(count) if count not in (None, "") else 1
        every = int(interval) if interval not in (None, "") else 0
        wait = int(delay) if delay not in (None, "") else 0
    except (TypeError, ValueError) as e:
        raise TransferError("The schedule needs whole numbers: seconds between runs and how many runs.") from e
    if not 1 <= n <= MAX_COUNT:
        raise TransferError(f"Pick between 1 and {MAX_COUNT} runs.")
    if n > 1 and every < MIN_INTERVAL_S:
        raise TransferError("Runs need to be at least 1 minute apart.")
    if wait < 0:
        raise TransferError("The start can't be in the past.")
    return (every if n > 1 else 0), n, wait


def wrapped_token(net: Network) -> Token:
    return find_token(WRAPPED[net.chain_id], net.tokens)


def order_token(token: Token, net: Network) -> Token:
    """The ERC-20 an order holds: native ETH/AVAX becomes WETH/WAVAX."""
    return wrapped_token(net) if token.address is None else token


def routing_token(token: Token, net: Network) -> Token:
    """The token venues quote: WETH/WAVAX legs route through native pools/pairs."""
    return net.native if token.symbol == WRAPPED[net.chain_id] else token


def token_at(net: Network, address: str) -> Token | None:
    return next((t for t in net.tokens if t.address and t.address.lower() == address.lower()), None)


def duration_label(seconds: int) -> str:
    for size, unit in ((86400, "d"), (3600, "h"), (60, "min")):
        if seconds >= size:
            return f"{round(seconds / size)} {unit}"
    return f"{seconds}s"


def schedule_label(interval: int, count: int, delay: int) -> str:
    when = "now" if delay <= 0 else f"in {duration_label(delay)}"
    if count == 1:
        return f"once, {when}"
    return f"every {duration_label(interval)} × {count}, starting {when}"


def describe_order(order: Order, net: Network, now: int) -> str:
    tin, tout = token_at(net, order.token_in), token_at(net, order.token_out)
    pay = f"{format_units(order.amount_in, tin.decimals)} {tin.symbol}" if tin else f"{order.amount_in} of {short(order.token_in)}"
    get = tout.symbol if tout else short(order.token_out)
    plan = f"every {duration_label(order.interval)} × {order.count}" if order.count > 1 else "once"
    if order.cancelled:
        status = "cancelled"
    elif not order.active:
        status = "finished"
    elif order.next_time <= now:
        status = "due now"
    else:
        status = f"next run in {duration_label(order.next_time - now)}"
    return f"#{order.id}: {pay} → {get}, {plan}, {order.executed}/{order.count} done, {status}"


def _tx(to: str, data: str, value: int = 0) -> dict:
    return {"to": to, "value": str(value), "data": data}


def schedule_steps(
    tin: Token, tout: Token, net: Network, amount_in: int, min_out: int, start: int, interval: int, count: int, allowance: int, top_up: int, approve_amount: int | None = None
) -> list[Step]:
    pay, get = order_token(tin, net), order_token(tout, net)
    total = amount_in * count
    approve = total if approve_amount is None else approve_amount  # this order plus other active orders on the same token
    steps: list[Step] = []
    if tin.address is None:
        steps.append(Step(f"Wrap {tin.symbol} → {pay.symbol}", _tx(pay.address, WETH_DEPOSIT, total), GAS["wrap"]))
    if allowance < approve:
        if pay.symbol == "USDT" and allowance > 0:
            # USDT reverts when changing one nonzero allowance to another.
            steps.append(Step("Reset USDT allowance", _tx(pay.address, encode_erc20_approve(SCHEDULER, 0)), GAS["approve"]))
        steps.append(Step(f"Allow {pay.symbol}", _tx(pay.address, encode_erc20_approve(SCHEDULER, approve)), GAS["approve"]))
    data = encode_schedule(pay.address, get.address, amount_in, min_out, start, interval, count)
    steps.append(Step("Schedule swap", _tx(SCHEDULER, data, top_up), GAS["schedule"]))
    return steps


def schedule_rows(sender: str, tin: Token, tout: Token, net: Network, amount_in: int, min_out: int, label: str, top_up: int) -> list[dict]:
    get = order_token(tout, net)
    rows = [
        {"label": "From", "value": short(sender)},
        {"label": "Each run", "value": f"{format_units(amount_in, tin.decimals)} {tin.symbol} → {get.symbol}"},
        {"label": "Schedule", "value": label},
        {"label": "Min received per run", "value": f"{display_units(min_out, get.decimals)} {get.symbol}"},
    ]
    if tout.address is None:
        rows.append({"label": "You receive", "value": f"{get.symbol} (wrapped {tout.symbol})"})
    rows += [
        {"label": "Gas deposit", "value": f"{format_units(top_up, 18)} {net.native.symbol}" if top_up else "already covered"},
        {"label": "Executed by", "value": "Anyone — the LazyWallet executor on Sandbox"},
        {"label": "Contract", "value": short(SCHEDULER)},
        {"label": "Network", "value": net.label},
    ]
    return rows
