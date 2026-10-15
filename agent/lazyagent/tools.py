from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal

from claude_agent_sdk import create_sdk_mcp_server, tool

from .chain import Chain
from .outcome import outcome_text
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
Fund = Callable[[str], Awaitable[str]]
SERVER_NAME = "wallet"
TOOL_NAMES = [
    f"mcp__{SERVER_NAME}__{n}"
    for n in ("get_balances", "resolve_recipient", "propose_transfer", "unsupported_action", "request_test_funds")
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
    def __init__(
        self,
        chain: Chain,
        send: Send,
        ctx: WalletContext,
        proposals: Proposals,
        approval_timeout: float = 300,
        fund: Fund | None = None,
    ):
        self.fund = fund
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
        steps = [{"label": "Send", "request": build_request(token, to, amount)}]
        pid, fut = self.proposals.new()
        await self.send(
            {
                "type": "confirm",
                "id": pid,
                "tx": {
                    "title": f"Send {human}",
                    "from": self.ctx.address,
                    "rows": [{"label": "From", "value": short(self.ctx.address)}, *display_rows(token, amount, to, name, price, gas_cost, eth_price)],
                    "steps": steps,
                },
            }
        )
        result = await self.proposals.wait(pid, fut, self.approval_timeout)
        return ok(outcome_text(result, steps, "transfer", f"Sent {human} to {label}. Confirmed on Sandbox, tx {result and result.get('hash')}."))

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
                "request_test_funds",
                "Sandbox faucet: give the active wallet free test funds (100 ETH plus test tokens). Use when the user asks for test funds, the faucet, or ETH to get started.",
                {"type": "object", "properties": {}},
            )(t.request_test_funds),
            tool(
                "unsupported_action",
                "Use for swaps, bridging, scheduling, price alerts, dApps or anything other than balances and sends.",
                {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]},
            )(t.unsupported_action),
        ],
    )
