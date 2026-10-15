import asyncio
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal

from claude_agent_sdk import create_sdk_mcp_server, tool

from .chain import Chain
from .dexalot import DEXALOT_REVERT_HINT, Quotes, asset_of, dexalot_rows, dexalot_steps
from .networks import ETHEREUM, NETWORKS, Choice, Network, candidates, find_network, pick_network
from .outcome import outcome_text
from .proposals import Proposals
from .scheduler import (
    MIN_OUT_DISCOUNT_BPS,
    SCHEDULER,
    decode_order,
    describe_order,
    encode_cancel,
    encode_get_order,
    gas_balance,
    gas_top_up,
    order_token,
    parse_schedule,
    read_orders,
    routing_token,
    schedule_label,
    schedule_rows,
    schedule_steps,
)
from .swaps import (
    DEADLINE_S,
    GAS,
    MAX_PRICE_IMPACT,
    Step,
    approval_steps,
    check_swap_funds,
    display_units,
    gas_reserve,
    min_out,
    parse_slippage,
    price_impact,
    route_label,
    swap_rows,
)
from .tokens import find_token
from .transfers import (
    FEE_HEADROOM,
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
from .uniswap import (
    PERMIT2,
    UNIVERSAL_ROUTER,
    WETH_DEPOSIT,
    ChainQuoter,
    Quoter,
    best_route,
    currency_of,
    decode_permit2_allowance,
    encode_erc20_allowance,
    encode_permit2_allowance,
    encode_swap,
    encode_weth_withdraw,
)

Send = Callable[[dict], Awaitable[None]]
Fund = Callable[[str], Awaitable[str]]
SERVER_NAME = "wallet"
TOOL_NAMES = [
    f"mcp__{SERVER_NAME}__{n}"
    for n in ("get_balances", "resolve_recipient", "propose_transfer", "propose_swap", "propose_scheduled_swap", "list_scheduled_swaps", "cancel_scheduled_swap", "unsupported_action", "request_test_funds")
]


def ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


def _succeeded(result: dict | None) -> bool:
    return bool(result) and result.get("status") == "success" and not result.get("error")


@dataclass
class WalletContext:
    address: str | None = None
    contacts: list[dict] = field(default_factory=list)


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
        if not any(enough.values()) and None not in balances.values():
            have = []
            for n in cands:
                token = find_token(symbols[0], n.tokens)
                have.append(f"{format_units(balances[n.key], token.decimals)} {token.symbol} on {n.name}")
            return err(f"You only have {' and '.join(have)}.")
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

    async def resolve_recipient(self, args: dict) -> dict:
        try:
            address, name = resolve_recipient(str(args.get("name_or_address", "")), self.ctx.contacts)
        except TransferError as e:
            return err(str(e))
        return ok(f"{name or 'Address'} → {address}")

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
            before = await self._snapshot(net, [token])
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
            _, change = await self._show_change(net, [token], before)
            success = f"Sent {human} to {label}. Confirmed on {net.label}, tx {result.get('hash')}.{change}"
        return ok(outcome_text(result, steps, "transfer", success))

    async def _snapshot(self, net: Network, tokens) -> dict[str, int]:
        return {t.symbol: await self._balance_on(net, t) for t in tokens}

    async def _show_change(self, net: Network, tokens, before: dict[str, int]) -> tuple[dict[str, int] | None, str]:
        """After a confirmed tx: a card with only these tokens' new balances and +/- change.
        Returns (balances after, summary for the model), or (None, "") if balances can't be read."""
        try:
            after = await self._snapshot(net, tokens)
            changes, parts = [], []
            for t in {t.symbol: t for t in tokens}.values():
                was, now = before[t.symbol], after[t.symbol]
                delta = now - was
                changes.append(
                    {
                        "network": net.name,
                        "symbol": t.symbol,
                        "before": float(Decimal(was).scaleb(-t.decimals)),
                        "after": float(Decimal(now).scaleb(-t.decimals)),
                        "delta": float(Decimal(delta).scaleb(-t.decimals)),
                        "usdPrice": await self.chains[net.key].price_usd(t),
                    }
                )
                sign = "+" if delta >= 0 else "-"
                parts.append(f"{t.symbol} {sign}{display_units(abs(delta), t.decimals)} (now {display_units(now, t.decimals)})")
        except Exception:
            return None, ""
        await self.send({"type": "balance_change", "changes": changes})
        return after, f" Balance change (shown as a card): {', '.join(parts)}."

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

        return steps, rows, f" The price probably moved more than the {bps / 100:g}% slippage — ask again for a fresh quote.", None

    async def _dexalot_plan(self, net: Network, tin, tout, amount: int):
        if self.dexalot is None:
            raise TransferError("Dexalot swaps aren't set up on this Sandbox.")
        quote = await self.dexalot.quote(asset_of(tin), asset_of(tout), amount, self.ctx.address)
        order = quote["order"]
        if (
            int(order["takerAmount"]) != amount
            or order["takerAsset"].lower() != asset_of(tin).lower()
            or order["makerAsset"].lower() != asset_of(tout).lower()
            or order["taker"].lower() != self.ctx.address.lower()
            or order["maker"].lower() != quote["maker"].lower()
        ):
            raise TransferError("The Sandbox quote didn't match your request — try again.")
        allowance = 0
        if tin.address is not None:
            raw = await self.chains[net.key].call(tin.address, encode_erc20_allowance(self.ctx.address, quote["maker"]))
            allowance = int.from_bytes(raw[:32], "big")
        received = int(quote["order"]["makerAmount"])

        def rows(fee_usd: float) -> list[dict]:
            return dexalot_rows(self.ctx.address, tin, tout, amount, received, fee_usd, net.label)

        return dexalot_steps(tin, tout, quote, allowance), rows, DEXALOT_REVERT_HINT, received

    async def _approvals(self, token, amount: int, now: int) -> list[Step]:
        erc20 = int.from_bytes((await self.chain.call(token.address, encode_erc20_allowance(self.ctx.address, PERMIT2)))[:32], "big")
        p2_amount, p2_exp = decode_permit2_allowance(
            await self.chain.call(PERMIT2, encode_permit2_allowance(self.ctx.address, token.address, UNIVERSAL_ROUTER))
        )
        return approval_steps(token, erc20, p2_amount, p2_exp, amount, now)

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
                steps, rows, hint, exact = await self._dexalot_plan(net, tin, tout, amount)
            else:
                steps, rows, hint, exact = await self._uniswap_plan(tin, tout, amount, bps)
            reserve = gas_reserve(steps, await chain.gas_price())
            check_swap_funds(tin, amount, balance, native_balance, reserve, native=net.native.symbol)
            fee_usd = float(Decimal(reserve // FEE_HEADROOM).scaleb(-18)) * await chain.price_usd(net.native)
            before = await self._snapshot(net, [tin, tout])
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
            after, change = await self._show_change(net, [tin, tout], before)
            if exact is not None:  # a signed RFQ order pays exactly its makerAmount
                received = exact
            else:
                received = max(after[tout.symbol] - before[tout.symbol], 0) if after else None
            if received is None:
                got = f"{tout.symbol} (I couldn't read the received amount right now — don't swap again; check the balance instead)"
            else:
                got = f"{display_units(received, tout.decimals)} {tout.symbol}"
                got = f"about {got} (after network fees)" if tout.address is None and exact is None else got
            success = f"Swapped {human_in} for {got}. Confirmed on {net.label}, tx {result.get('hash')}.{change}"
        return ok(outcome_text(result, steps_json, "swap", success, revert_hint=hint))

    async def _quote_out(self, net: Network, tin, tout, amount: int) -> int:
        """Today's output for one run, from the network's venue (wrapped legs quoted as native)."""
        a, b = routing_token(tin, net), routing_token(tout, net)
        if net.swap_venue == "dexalot":
            if self.dexalot is None:
                raise TransferError("Dexalot swaps aren't set up on this Sandbox.")
            return int((await self.dexalot.quote(asset_of(a), asset_of(b), amount, self.ctx.address))["order"]["makerAmount"])
        found = await best_route(self.quoter, currency_of(a), currency_of(b), amount)
        if found is None:
            raise TransferError(f"I couldn't find a Uniswap v4 route for {tin.symbol} → {tout.symbol} on Sandbox.")
        return found[1]

    async def propose_scheduled_swap(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        sym_in, sym_out = str(args.get("token_in", "")).strip(), str(args.get("token_out", "")).strip()
        if sym_in.upper() == sym_out.upper():
            return err("Pick two different tokens to swap.")
        net = await self._resolve(args, [sym_in, sym_out], str(args.get("amount", "")), "schedule swaps of")
        if isinstance(net, dict):
            return net
        tin, tout = find_token(sym_in, net.tokens), find_token(sym_out, net.tokens)
        pay, get = order_token(tin, net), order_token(tout, net)
        chain = self.chains[net.key]
        try:
            if pay.address == get.address:
                raise TransferError(f"{tin.symbol} and {tout.symbol} are the same token once wrapped — pick two different tokens.")
            amount = parse_amount(str(args.get("amount", "")), tin.decimals)
            interval, count, delay = parse_schedule(args.get("interval_seconds"), args.get("count"), args.get("start_delay_seconds"))
            total = amount * count
            # Remaining runs of the user's other active orders on this token draw on the same allowance and balance.
            committed = sum(
                o.amount_in * (o.count - o.executed)
                for o in await read_orders(chain, self.ctx.address)
                if o.active and o.token_in.lower() == pay.address.lower()
            )
            balance = await self._balance_on(net, tin)
            # Native input is wrapped for this order only; the committed part must already be held as WETH/WAVAX.
            need = total + (committed if tin.address is not None else 0)
            if need > balance:
                reserved = f", plus {format_units(committed, tin.decimals)} reserved for your other scheduled swaps" if committed else ""
                raise TransferError(
                    f"{count} runs of {format_units(amount, tin.decimals)} {tin.symbol} need {format_units(total, tin.decimals)} {tin.symbol}{reserved}, "
                    f"but you have {format_units(balance, tin.decimals)}."
                )
            if tin.address is None and committed and await self._balance_on(net, pay) < committed:
                raise TransferError(f"Your other scheduled swaps still need {format_units(committed, pay.decimals)} {pay.symbol}, which you don't hold.")
            if args.get("min_received"):
                minimum = parse_amount(str(args["min_received"]), get.decimals)
                if minimum == 0:
                    raise TransferError("The minimum to receive has to be more than 0.")
            else:
                minimum = min_out(await self._quote_out(net, tin, tout, amount), MIN_OUT_DISCOUNT_BPS)
            start = await chain.block_timestamp() + delay
            allowance = int.from_bytes((await chain.call(pay.address, encode_erc20_allowance(self.ctx.address, SCHEDULER)))[:32], "big")
            gas_price = await chain.gas_price()
            top_up = gas_top_up(gas_price, count, await gas_balance(chain, self.ctx.address))
            steps = schedule_steps(tin, tout, net, amount, minimum, start, interval, count, allowance, top_up, total + committed)
            needed = gas_reserve(steps, gas_price) + top_up + (total if tin.address is None else 0)
            native_balance = await chain.eth_balance(self.ctx.address)
            if needed > native_balance:
                raise TransferError(
                    f"Not enough {net.native.symbol} for the wrap, gas deposit and fees (need ~{format_units(needed, 18)} {net.native.symbol}). "
                    "Try fewer runs or get test funds."
                )
            label = schedule_label(interval, count, delay)
            rows = schedule_rows(self.ctx.address, tin, tout, net, amount, minimum, label, top_up)
        except TransferError as e:
            return err(str(e))
        except Exception as e:
            return err(f"The {net.name} Sandbox chain isn't reachable right now ({e}).")

        human = f"{format_units(amount, tin.decimals)} {tin.symbol}"
        steps_json = self._steps_json([s.to_json() for s in steps], net)
        pid, fut = self.proposals.new()
        await self.send(
            {"type": "confirm", "id": pid, "tx": {"title": f"Schedule {human} → {get.symbol}", "from": self.ctx.address, "rows": rows, "steps": steps_json}}
        )
        result = await self.proposals.wait(pid, fut, self.approval_timeout)
        success = ""
        if _succeeded(result):
            success = (
                f"Scheduled {human} → {get.symbol}, {label}, on {net.label} (tx {result.get('hash')}). "
                "The executor runs it on-chain — the app doesn't need to stay open. It's listed in Scheduled tasks."
            )
        return ok(outcome_text(result, steps_json, "scheduled swap", success))

    async def list_scheduled_swaps(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        lines, down = [], []
        for net in self.networks:
            chain = self.chains[net.key]
            try:
                orders = await read_orders(chain, self.ctx.address)
                now = await chain.block_timestamp()
            except Exception:
                down.append(net.name)
                continue
            lines += [f"{describe_order(o, net, now)} on {net.name}" for o in orders]
        note = f" Not reachable right now: {', '.join(down)}." if down else ""
        if not lines:
            return ok(f"No scheduled swaps yet.{note}")
        return ok(f"Scheduled swaps: {'; '.join(lines)}.{note}")

    async def cancel_scheduled_swap(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        net = find_network(str(args.get("network", "")))
        if net is None or net.key not in self.chains:
            return err(f"Which network is the scheduled swap on? {', '.join(n.name for n in self.networks)}.")
        try:
            oid = int(args.get("order_id"))
        except (TypeError, ValueError):
            return err("I need the scheduled swap's number, like 3.")
        chain = self.chains[net.key]
        try:
            order = decode_order(oid, await chain.call(SCHEDULER, encode_get_order(oid)))
            now = await chain.block_timestamp()
        except Exception as e:
            return err(f"The {net.name} Sandbox chain isn't reachable right now ({e}).")
        if order.owner.lower() != self.ctx.address.lower():
            return err(f"I can't find a scheduled swap #{oid} of yours on {net.name}.")
        if not order.active:
            return err(f"Scheduled swap #{oid} is already {'cancelled' if order.cancelled else 'finished'}.")
        steps = self._steps_json([{"label": "Cancel scheduled swap", "request": {"to": SCHEDULER, "value": "0", "data": encode_cancel(oid)}}], net)
        rows = [
            {"label": "From", "value": short(self.ctx.address)},
            {"label": "Order", "value": describe_order(order, net, now)},
            {"label": "Network", "value": net.label},
        ]
        pid, fut = self.proposals.new()
        await self.send({"type": "confirm", "id": pid, "tx": {"title": f"Cancel scheduled swap #{oid}", "from": self.ctx.address, "rows": rows, "steps": steps}})
        result = await self.proposals.wait(pid, fut, self.approval_timeout)
        success = f"Cancelled scheduled swap #{oid} on {net.label}, tx {result.get('hash')}." if _succeeded(result) else ""
        return ok(outcome_text(result, steps, "cancellation", success))

    async def request_test_funds(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        if not await self.chain.is_sandbox():
            return err("The faucet only works on Sandbox, and this network isn't Sandbox.")
        if self.fund is None:
            return err("The faucet isn't configured.")
        try:
            summary = await self.fund(self.ctx.address)
        except Exception as e:
            return err(f"The Sandbox faucet isn't reachable ({e}). Start it with `pnpm dev:sandbox`.")
        balances = await self.get_balances({})
        return ok(f"Added {summary} to the wallet. {balances['content'][0]['text']}")

    async def unsupported_action(self, args: dict) -> dict:
        action = str(args.get("action", "That"))
        return ok(f"{action} is coming soon. Right now LazyWallet can check balances, send and swap on Sandbox ({self.supported()}).")


def build_mcp_server(t: WalletTools):
    return create_sdk_mcp_server(
        name=SERVER_NAME,
        version="0.1.0",
        tools=[
            tool("get_balances", "Show the active wallet's balances (native coins and supported tokens on every Sandbox network) with USD values.", {"type": "object", "properties": {}})(t.get_balances),
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
                        "token": {"type": "string", "description": f"One of {t.supported()}"},
                        "amount": {"type": "string", "description": "Decimal amount in whole tokens, e.g. '0.1'"},
                        "to": {"type": "string", "description": "Address-book name or 0x address"},
                        "network": {"type": "string", "description": "Only if the user named a network or answered a network choice: 'ethereum' or 'avalanche'"},
                    },
                    "required": ["token", "amount", "to"],
                },
            )(t.propose_transfer),
            tool(
                "propose_swap",
                "Propose swapping one supported token for another on Uniswap v4 (exact input). Finds the best route, shows one confirmation card with any approval steps, waits for approve/reject, and returns the amount received.",
                {
                    "type": "object",
                    "properties": {
                        "token_in": {"type": "string", "description": f"Token to pay, one of {t.supported()}"},
                        "token_out": {"type": "string", "description": f"Token to receive, one of {t.supported()}"},
                        "amount": {"type": "string", "description": "Decimal amount of token_in, e.g. '100'"},
                        "slippage_percent": {"type": "string", "description": "Only if the user stated one, e.g. '0.5'"},
                        "network": {"type": "string", "description": "Only if the user named a network or answered a network choice: 'ethereum' or 'avalanche'"},
                    },
                    "required": ["token_in", "token_out", "amount"],
                },
            )(t.propose_swap),
            tool(
                "propose_scheduled_swap",
                "Propose an on-chain scheduled swap: one run now/later or recurring (e.g. every minute × 5). Shows one confirmation card "
                "(wrap if paying ETH/AVAX, allowance, schedule + gas deposit), waits for approve/reject. The executor runs it later; the app needn't stay open.",
                {
                    "type": "object",
                    "properties": {
                        "token_in": {"type": "string", "description": f"Token to pay each run, one of {t.supported()}"},
                        "token_out": {"type": "string", "description": f"Token to receive, one of {t.supported()}"},
                        "amount": {"type": "string", "description": "Decimal amount of token_in per run, e.g. '10'"},
                        "interval_seconds": {"type": "integer", "description": "Seconds between runs (≥ 60). Omit for a single run"},
                        "count": {"type": "integer", "description": "Number of runs (1–100). Default 1"},
                        "start_delay_seconds": {"type": "integer", "description": "Seconds from now until the first run. Default 0"},
                        "min_received": {"type": "string", "description": "Only if the user set a limit: minimum token_out per run, decimal"},
                        "network": {"type": "string", "description": "Only if the user named a network or answered a network choice: 'ethereum' or 'avalanche'"},
                    },
                    "required": ["token_in", "token_out", "amount"],
                },
            )(t.propose_scheduled_swap),
            tool("list_scheduled_swaps", "List the user's scheduled swaps on every Sandbox network with progress and next run.", {"type": "object", "properties": {}})(t.list_scheduled_swaps),
            tool(
                "cancel_scheduled_swap",
                "Propose cancelling one of the user's scheduled swaps (confirmation card). Use list_scheduled_swaps first to find its number and network.",
                {
                    "type": "object",
                    "properties": {"order_id": {"type": "integer"}, "network": {"type": "string", "description": "'ethereum' or 'avalanche'"}},
                    "required": ["order_id", "network"],
                },
            )(t.cancel_scheduled_swap),
            tool(
                "request_test_funds",
                "Sandbox faucet: give the active wallet free test funds on every Sandbox network (100 ETH / 100 AVAX plus test tokens). Use when the user asks for test funds, the faucet, or ETH to get started.",
                {"type": "object", "properties": {}},
            )(t.request_test_funds),
            tool(
                "unsupported_action",
                "Use for bridging, price alerts, conditional actions, dApps or anything other than balances, sends, swaps, scheduled swaps and test funds.",
                {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]},
            )(t.unsupported_action),
        ],
    )
