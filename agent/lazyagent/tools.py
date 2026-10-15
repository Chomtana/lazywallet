import asyncio
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from decimal import Decimal

from claude_agent_sdk import create_sdk_mcp_server, tool

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
    farm_summary,
    find_program,
)
from .chain import Chain
from .custom_tokens import ADDRESS, MIN_RESERVE_USD, Search, discover, merge
from .dexalot import DEXALOT_REVERT_HINT, Quotes, asset_of, dexalot_rows, dexalot_steps
from .kyber import Kyber, kyber_plan, kyber_swap
from .networks import ETHEREUM, NETWORKS, Choice, Network, candidates, find_network, pick_network
from .outcome import outcome_text
from .proposals import Proposals
from .swaps import (
    DEADLINE_S,
    DEFAULT_SLIPPAGE_BPS,
    GAS,
    MAX_PRICE_IMPACT,
    Step,
    SwapPlan,
    approval_steps,
    check_swap_funds,
    display_units,
    erc20_approval,
    gas_reserve,
    min_out,
    parse_slippage,
    price_impact,
    route_label,
    swap_rows,
    swap_summary,
)
from .tokens import Token, find_token
from .transfers import (
    FEE_HEADROOM,
    NoRoute,
    TransferError,
    build_request,
    display_rows,
    format_units,
    format_usd,
    gas_units,
    parse_amount,
    resolve_recipient,
    short,
    token_address_rows,
    validate,
)
from .trending import TRENDING, TRENDING_TOOL, TrendingError, TrendingTokens, trending_reply
from .uniswap import (
    PERMIT2,
    UNIVERSAL_ROUTER,
    WETH_DEPOSIT,
    ChainQuoter,
    Hop,
    Quoter,
    Route,
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
    for n in ("get_balances", "resolve_recipient", "propose_transfer", "propose_swap", "unsupported_action", "request_test_funds", "list_trending_tokens", "list_airdrops", "propose_deposit")
]


def ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


def _usd(holding: dict) -> str:
    return "price unknown" if holding["usdPrice"] is None else format_usd(holding["amount"] * holding["usdPrice"])


def _succeeded(result: dict | None) -> bool:
    return bool(result) and result.get("status") == "success" and not result.get("error")


@dataclass
class WalletContext:
    address: str | None = None
    contacts: list[dict] = field(default_factory=list)
    tokens: list[dict] = field(default_factory=list)  # the wallet's saved custom tokens (lw.tokens)


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
        kyber: Kyber | None = None,
        search: Search | None = None,
    ):
        self.fund = fund
        self.kyber = kyber
        self.search = search
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
        return [merge(n, self.ctx.tokens) for n in NETWORKS if n.key in self.chains]

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
            holdings.append(
                {"network": net.name, "symbol": t.symbol, "amount": amount, "usdPrice": await chain.price_usd(t), "logo": t.logo, "raw": raw, "decimals": t.decimals}
            )
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
            return err(f"The network isn't reachable right now ({'; '.join(down)}).")
        await self.send({"type": "balances", "holdings": [{k: h[k] for k in ("network", "symbol", "amount", "usdPrice", "logo")} for h in holdings]})
        parts = []
        for net in nets:
            mine = [h for h in holdings if h["network"] == net.name]
            if mine:
                parts.append(f"{net.name}: " + ", ".join(f"{h['symbol']} {format_units(h['raw'], h['decimals'])} ({_usd(h)})" for h in mine))
        total = sum(h["amount"] * h["usdPrice"] for h in holdings if h["usdPrice"] is not None)
        note = f" Not reachable right now: {', '.join(down)}." if down else ""
        return ok(f"Balances shown to the user as a card: {'; '.join(parts)}. Total {format_usd(total)}.{note}")

    async def _resolve(self, args: dict, symbols: list[str], amount_text: str, verb: str) -> Network | dict:
        """Which network a request runs on — or an error result (after sending a choice card when it's ambiguous)."""
        nets = self.networks
        explicit = args.get("network")
        if explicit:
            named = find_network(str(explicit))
            nets = [n for n in nets if named is not None and n.key == named.key]
            if not nets:
                return err(f"I can use {', '.join(n.name for n in self.networks)}.")
        try:
            nets = await self._discover(symbols, nets)
        except TransferError as e:  # a token posing as a built-in
            return err(str(e))
        if explicit:
            net = nets[0]
            missing = [s for s in symbols if find_token(s, net.tokens) is None]
            if missing:
                if ADDRESS.match(missing[0].strip()):
                    return err(f"That address isn't a token on {net.name}.")
                return err(
                    f"{missing[0]} isn't available on {net.name}, and I couldn't find it with at least "
                    f"${MIN_RESERVE_USD:,} of liquidity. Ask the user for its contract address."
                )
            return net
        cands = candidates(symbols, nets)
        if not cands:
            unknown = next((s for s in symbols if not any(find_token(s, n.tokens) for n in nets)), None)
            if unknown and ADDRESS.match(unknown.strip()):
                # Only the networks that have the request's other tokens were checked.
                where = [n for n in nets if all(find_token(s, n.tokens) for s in symbols if s != unknown)] or nets
                return err(f"That address isn't a token on {' or '.join(n.name for n in where)}.")
            if unknown:
                return err(
                    f"I couldn't find {unknown} with at least ${MIN_RESERVE_USD:,} of liquidity. "
                    f"I can only {verb} {self.supported()} or a token by its contract address — ask the user for it."
                )
            return err(f"I can only {verb} {self.supported()}.")
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

    async def _discover(self, symbols: list[str], nets: list[Network]) -> list[Network]:
        """Adds tokens the user named that aren't built in or saved (a 0x address, else a symbol search) to each
        network where they're found. Skips a network that lacks a token the user named that exists elsewhere."""
        known = {s for s in symbols if any(find_token(s, n.tokens) for n in nets)}
        out = []
        for net in nets:
            missing = [s for s in symbols if find_token(s, net.tokens) is None]
            if missing and not known.intersection(missing):
                found = [await discover(s, net, self.chains[net.key], self.search) for s in missing]
                if all(found):
                    net = replace(net, tokens=net.tokens + tuple(found))
            out.append(net)
        return out

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
            return err(f"{net.name} isn't reachable right now ({e}).")

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
                    "rows": [
                        {"label": "From", "value": short(self.ctx.address)},
                        *display_rows(token, amount, to, name, price, gas_cost, native_price, network=net.label),
                        *token_address_rows(token),
                    ],
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

    async def _price(self, net: Network, token) -> float | None:
        """USD price for a card; None (shown as no USD value) rather than failing the card."""
        try:
            return await self.chains[net.key].price_usd(token)
        except Exception:
            return None

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
                        "logo": t.logo,
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
            label, via, impact = f"{verb} via WETH contract", "WETH contract", 0.0
        else:
            found = await best_route(self.quoter, currency_of(tin), currency_of(tout), amount)
            if found is None:
                raise NoRoute(f"I couldn't find a Uniswap v4 route for {tin.symbol} → {tout.symbol}.")
            route, expected = found
            probe_in = max(amount // 1000, 1)
            impact = price_impact(amount, expected, probe_in, await self.quoter.quote(route, probe_in) or 0)
            if impact > MAX_PRICE_IMPACT:
                raise TransferError(f"That trade would move the price by about {impact:.0%}. Try a smaller amount.")
            minimum = min_out(expected, bps)
            steps = await self._approvals(tin, amount, now) if tin.address else []
            swap = {"to": UNIVERSAL_ROUTER, "value": str(amount if tin.address is None else 0), "data": encode_swap(route, amount, minimum, now + DEADLINE_S)}
            steps.append(Step(f"Swap {tin.symbol} → {tout.symbol}", swap, GAS["swap1" if len(route.hops) == 1 else "swap2"]))
            label, via = route_label(route), "Uniswap v4"
        hint = f" The price probably moved more than the {bps / 100:g}% slippage — ask again for a fresh quote."
        return SwapPlan(steps, swap_rows(self.ctx.address, label, impact), hint, expected, via, impact)

    async def _dexalot_plan(self, net: Network, tin, tout, amount: int):
        if self.dexalot is None:
            raise TransferError("Dexalot swaps aren't set up here.")
        quote = await self.dexalot.quote(asset_of(tin), asset_of(tout), amount, self.ctx.address)
        order = quote["order"]
        if (
            int(order["takerAmount"]) != amount
            or order["takerAsset"].lower() != asset_of(tin).lower()
            or order["makerAsset"].lower() != asset_of(tout).lower()
            or order["taker"].lower() != self.ctx.address.lower()
            or order["maker"].lower() != quote["maker"].lower()
        ):
            raise TransferError("The Dexalot quote didn't match your request — try again.")
        allowance = 0
        if tin.address is not None:
            raw = await self.chains[net.key].call(tin.address, encode_erc20_allowance(self.ctx.address, quote["maker"]))
            allowance = int.from_bytes(raw[:32], "big")
        received = int(quote["order"]["makerAmount"])
        rows = dexalot_rows(self.ctx.address, tin, tout, amount, received)
        return SwapPlan(dexalot_steps(tin, tout, quote, allowance), rows, DEXALOT_REVERT_HINT, received, "Dexalot", None, exact=True)

    async def _swap_plan(self, net: Network, tin, tout, amount: int, bps: int, slippage: str | None) -> SwapPlan:
        """The network's venue for built-in pairs it can quote; KyberSwap for custom tokens and everything else."""
        if not (tin.custom or tout.custom):
            try:
                if net.swap_venue == "dexalot":
                    return await self._dexalot_plan(net, tin, tout, amount)
                return await self._uniswap_plan(tin, tout, amount, bps)
            except NoRoute:
                if self.kyber is None:
                    raise
        if self.kyber is None:
            raise TransferError("Swaps for tokens outside the built-in list aren't set up here.")
        return await kyber_plan(self.kyber, self.chains[net.key], net, tin, tout, amount, self.ctx.address, slippage)

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
            plan = await self._swap_plan(net, tin, tout, amount, bps, args.get("slippage_percent"))
            steps = plan.steps
            reserve = gas_reserve(steps, await chain.gas_price())
            check_swap_funds(tin, amount, balance, native_balance, reserve, native=net.native.symbol)
            fee_usd = float(Decimal(reserve // FEE_HEADROOM).scaleb(-18)) * await chain.price_usd(net.native)
            prices = (await self._price(net, tin), await self._price(net, tout))
            before = await self._snapshot(net, [tin, tout])
        except TransferError as e:
            return err(str(e))
        except Exception as e:
            return err(f"{net.name} isn't reachable right now ({e}).")

        human_in = f"{format_units(amount, tin.decimals)} {tin.symbol}"
        steps_json = self._steps_json([s.to_json() for s in steps], net)
        summary = swap_summary(
            net.name, tin, tout, amount, plan.expected, via=plan.via, fee_usd=fee_usd, impact=plan.impact, prices=prices, exact=plan.exact
        )
        tx = {"title": "Swap", "from": self.ctx.address, "summary": summary, "rows": plan.rows, "steps": steps_json}
        if tout.custom:  # the wallet remembers it after the swap succeeds
            tx["addToken"] = {"chainId": net.chain_id, "address": tout.address, "symbol": tout.symbol, "decimals": tout.decimals}
        pid, fut = self.proposals.new()
        await self.send({"type": "confirm", "id": pid, "tx": tx})
        result = await self.proposals.wait(pid, fut, self.approval_timeout)
        success = ""
        if _succeeded(result):
            after, change = await self._show_change(net, [tin, tout], before)
            if plan.exact:  # a signed RFQ order pays exactly its makerAmount
                received = plan.expected
            else:
                received = max(after[tout.symbol] - before[tout.symbol], 0) if after else None
            if received is None:
                got = f"{tout.symbol} (I couldn't read the received amount right now — don't swap again; check the balance instead)"
            else:
                got = f"{display_units(received, tout.decimals)} {tout.symbol}"
                got = f"about {got} (after network fees)" if tout.address is None and not plan.exact else got
            success = f"Swapped {human_in} for {got}. Confirmed on {net.label}, tx {result.get('hash')}.{change}"
        return ok(outcome_text(result, steps_json, "swap", success, revert_hint=plan.hint))

    async def request_test_funds(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        if not await self.chain.is_sandbox():
            return err("Adding funds isn't available on this network.")
        if self.fund is None:
            return err("The faucet isn't configured.")
        try:
            summary = await self.fund(self.ctx.address)
        except Exception as e:
            return err(f"The funds service isn't reachable ({e}). Start it with `pnpm dev:sandbox`.")
        balances = await self.get_balances({})
        return ok(f"Added {summary} to the wallet. {balances['content'][0]['text']}")

    trending: TrendingTokens = TRENDING  # shared 60 s cache; tests assign their own

    async def list_trending_tokens(self, args: dict) -> dict:
        try:
            card, reply = await trending_reply(self.trending, args)
        except TrendingError as e:
            return err(str(e))
        if card:
            await self.send(card)
        return ok(reply)

    airdrops: Airdrops = AIRDROPS  # shared 10 min cache; tests assign their own

    async def list_airdrops(self, args: dict) -> dict:
        try:
            return ok(await airdrops_reply(self.airdrops, args, self.send))
        except AirdropError as e:
            return err(str(e))

    async def _farm_swap(self, net: Network, dep: Deposit, usdc: Token, asset: Token, amount: int):
        """USDC → the farm's token on the deposit's venue: the pinned Uniswap v4 pool first (V4_THEN_KYBER), else
        KyberSwap with all of kyber.py's checks. Returns (steps, expected, minimum, via, route detail, price impact or None)."""
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
                return steps, expected, minimum, "Uniswap v4", f"Uniswap v4 {dep.fee / 10_000:g}%", impact
        if self.kyber is None:
            raise TransferError(f"I couldn't get a quote for {usdc.symbol} → {asset.symbol} right now.")
        k = await kyber_swap(self.kyber, self.chains[net.key], net, usdc, asset, amount, self.ctx.address, f"{DEFAULT_SLIPPAGE_BPS / 100:g}")
        return k.steps, k.verified.expected, k.verified.minimum, k.label, k.label, k.impact

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
            return err(f"{dep.name} farming isn't set up here.")
        chain = self.chains[net.key]
        usdc = find_token(dep.pay, net.tokens)
        asset, vault = (Token(t.symbol, t.address, t.decimals, custom=True) for t in (dep.asset, dep.vault))
        try:
            amount = parse_amount(str(args.get("amount", "")), usdc.decimals)
            balance = await self._balance_on(net, usdc)
            if amount > balance:
                raise TransferError(f"You only have {format_units(balance, usdc.decimals)} {usdc.symbol}.")
            swap_steps, expected, minimum, via, route, impact = await self._farm_swap(net, dep, usdc, asset, amount)
            if impact is not None and impact > MAX_PRICE_IMPACT:
                raise TransferError(f"That trade would move the price by about {impact:.0%}. Try a smaller amount.")
            plan = await deposit_plan(chain, dep, self.ctx.address, minimum)
            steps = swap_steps + erc20_approval(asset, plan.allowance, minimum, vault.address) + [plan.step]
            native_balance = await chain.eth_balance(self.ctx.address)
            reserve = gas_reserve(steps, await chain.gas_price())
            check_swap_funds(usdc, amount, balance, native_balance, reserve, native=net.native.symbol)
            fee_usd = float(Decimal(reserve // FEE_HEADROOM).scaleb(-18)) * await chain.price_usd(net.native)
            prices = (await self._price(net, usdc), await self._price(net, asset))
            before = await self._snapshot(net, [usdc, asset, vault])
        except TransferError as e:
            return err(str(e))
        except Exception as e:
            return err(f"{net.name} isn't reachable right now ({e}).")

        human_in = f"{format_units(amount, usdc.decimals)} {usdc.symbol}"
        steps_json = self._steps_json([s.to_json() for s in steps], net)
        rows = farm_rows(self.ctx.address, program, usdc, asset, vault, expected, minimum, plan.shares, route, impact)
        summary = farm_summary(
            dep, net.name, usdc, asset, vault, amount, expected, minimum, plan.shares, via=via, fee_usd=fee_usd, impact=impact, prices=prices
        )
        tx = {
            "title": f"Farm {dep.name}",
            "from": self.ctx.address,
            "summary": summary,
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
            success = f"{staked}. Confirmed on {net.label}, tx {result.get('hash')}.{change}"
        swap_at = next(i for i, s in enumerate(steps_json) if s["label"].startswith("Swap "))
        failed = (result or {}).get("failed_step")
        unsent = (result or {}).get("error")
        if isinstance(failed, int) and swap_at < failed < len(steps_json) and not (unsent and result.get("hash")):
            # The swap landed but the approve/stake after it didn't: the token is unstaked; a retry would swap again.
            label = steps_json[failed]["label"]
            what = f"failed before it was sent at step {failed + 1} ({label}): {unsent}" if unsent else f"reverted at step {failed + 1} ({label}) (tx {result.get('hash')})"
            _, change = await self._show_change(net, [usdc, asset, vault], before)
            return ok(
                f"The deposit {what}. The swap went through, so your {asset.symbol} is in your wallet but wasn't staked. "
                f"Don't swap again; ask the user whether to try staking later.{change}"
            )
        hint = f" The price probably moved more than the {DEFAULT_SLIPPAGE_BPS / 100:g}% slippage — ask again for a fresh quote."
        return ok(outcome_text(result, steps_json, "deposit", success, revert_hint=hint))

    async def unsupported_action(self, args: dict) -> dict:
        action = str(args.get("action", "That"))
        return ok(f"{action} is coming soon. Right now LazyWallet can check balances, send and swap ({self.supported()}).")


def build_mcp_server(t: WalletTools):
    return create_sdk_mcp_server(
        name=SERVER_NAME,
        version="0.1.0",
        tools=[
            tool("get_balances", "Show the active wallet's balances (native coins and supported tokens on every network) with USD values.", {"type": "object", "properties": {}})(t.get_balances),
            tool(
                "resolve_recipient",
                "Look up an address-book name or validate a 0x address.",
                {"type": "object", "properties": {"name_or_address": {"type": "string"}}, "required": ["name_or_address"]},
            )(t.resolve_recipient),
            tool(
                "propose_transfer",
                "Propose sending a native coin or any token. Shows a confirmation card and waits for the user to approve or reject; returns the outcome.",
                {
                    "type": "object",
                    "properties": {
                        "token": {"type": "string", "description": f"Symbol (built in: {t.supported()}; or a token the user bought) or the token's 0x contract address"},
                        "amount": {"type": "string", "description": "Decimal amount in whole tokens, e.g. '0.1'"},
                        "to": {"type": "string", "description": "Address-book name or 0x address"},
                        "network": {"type": "string", "description": "Only if the user named a network or answered a network choice: 'ethereum' or 'avalanche'"},
                    },
                    "required": ["token", "amount", "to"],
                },
            )(t.propose_transfer),
            tool(
                "propose_swap",
                "Propose swapping one token for another (exact input): Uniswap v4 on Ethereum, Dexalot on Avalanche, KyberSwap for any other token or pair. Shows one confirmation card with any approval steps, waits for approve/reject, and returns the amount received.",
                {
                    "type": "object",
                    "properties": {
                        "token_in": {"type": "string", "description": f"Token to pay: symbol (built in: {t.supported()}) or 0x contract address"},
                        "token_out": {"type": "string", "description": "Token to receive: symbol or 0x contract address (any token, e.g. a memecoin)"},
                        "amount": {"type": "string", "description": "Decimal amount of token_in, e.g. '100'"},
                        "slippage_percent": {"type": "string", "description": "Only if the user stated one, e.g. '0.5'"},
                        "network": {"type": "string", "description": "Only if the user named a network or answered a network choice: 'ethereum' or 'avalanche'"},
                    },
                    "required": ["token_in", "token_out", "amount"],
                },
            )(t.propose_swap),
            tool(
                "request_test_funds",
                "Add funds to the active wallet on every network (100 ETH / 100 AVAX plus tokens). Use when the user asks to add or get funds, the faucet, or ETH to get started.",
                {"type": "object", "properties": {}},
            )(t.request_test_funds),
            tool(*TRENDING_TOOL)(t.list_trending_tokens),
            tool(*AIRDROPS_TOOL)(t.list_airdrops),
            tool(*DEPOSIT_TOOL)(t.propose_deposit),
            tool(
                "unsupported_action",
                "Use for bridging, scheduling, price alerts, other dApps, withdrawals/unstaking or anything other than balances, sends, swaps, adding funds, trending tokens and airdrops/farming.",
                {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]},
            )(t.unsupported_action),
        ],
    )
