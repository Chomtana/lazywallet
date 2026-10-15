import time

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, StreamEvent, TextBlock, ToolUseBlock
from fakes import FakeChain
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from lazyagent.server import create_app
from lazyagent.session import Session

ORIGIN = "http://localhost:5174"
ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
THINKING = {"type": "progress", "label": "Thinking…"}
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
        assert ws.receive_json() == THINKING
        confirm = ws.receive_json()
        assert confirm["type"] == "confirm"
        assert confirm["tx"]["steps"][0]["request"]["to"] == ALICE
        ws.send_json({"type": "tx_result", "id": confirm["id"], "outcome": "approved", "hash": "0xabc", "status": "success"})
        assert ws.receive_json()["type"] == "balance_change"  # changed tokens after a confirmed transfer
        delta = ws.receive_json()
        assert delta["type"] == "text_delta"
        assert "Sent 0.1 ETH to Alice" in delta["text"]
        assert ws.receive_json() == {"type": "text_done"}
        assert ws.receive_json() == {"type": "turn_end"}


def test_busy_while_waiting_for_approval():
    with client().websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
        ws.send_json(USER)
        assert ws.receive_json() == THINKING
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
        assert ws.receive_json() == THINKING
        err = ws.receive_json()
        assert err["type"] == "error"
        assert "not logged in" in err["message"]
        assert ws.receive_json() == {"type": "turn_end"}


def test_disconnect_cancels_pending_and_closes_client():
    ScriptedClient.instances.clear()
    with client().websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
        ws.send_json(USER)
        assert ws.receive_json() == THINKING
        assert ws.receive_json()["type"] == "confirm"
    deadline = time.monotonic() + 2
    while not ScriptedClient.instances[0].disconnected and time.monotonic() < deadline:
        time.sleep(0.01)
    assert ScriptedClient.instances[0].disconnected


def test_health():
    assert client().get("/health").json() == {"ok": True}


def test_tx_started_keeps_the_proposal_alive_past_the_approval_timeout():
    app = create_app(FakeChain(), scripted_factory, (ORIGIN,), approval_timeout=0.2)
    with TestClient(app).websocket_connect("/ws", headers={"origin": ORIGIN}) as ws:
        ws.send_json(USER)
        assert ws.receive_json() == THINKING
        confirm = ws.receive_json()
        ws.send_json({"type": "tx_started", "id": confirm["id"]})
        time.sleep(0.4)
        ws.send_json({"type": "tx_result", "id": confirm["id"], "outcome": "approved", "hash": "0xabc", "status": "success"})
        assert ws.receive_json()["type"] == "balance_change"
        assert "Sent 0.1 ETH to Alice" in ws.receive_json()["text"]


async def test_session_passes_avalanche_to_tools():
    async def factory(tools):
        raise AssertionError("not used")

    avax = FakeChain()
    s = Session(lambda m: None, FakeChain(), factory, avalanche=avax, dexalot=object())
    assert s.tools.chains["avalanche"] is avax and s.tools.dexalot is not None


def test_create_app_accepts_avalanche():
    async def factory(tools):
        raise AssertionError("not used")

    app = create_app(FakeChain(), factory, (ORIGIN,), avalanche=FakeChain())
    assert app.title == "LazyWallet Agent"


async def test_session_stores_saved_tokens_and_passes_kyber():
    sent = []

    async def send(m):
        sent.append(m)

    async def factory(tools):
        raise RuntimeError("no claude here")

    coq = {"chainId": 43114, "address": "0x420FcA0121DC28039145009570975747295f2329", "symbol": "COQ", "decimals": 18}
    s = Session(send, FakeChain(), factory, kyber=object(), search=object())
    assert s.tools.kyber is not None and s.tools.search is not None
    await s.handle({**USER, "tokens": [coq]})
    await s._turn
    assert s.ctx.tokens == [coq]
    await s.handle(USER)  # an older wallet build sends no tokens
    await s._turn
    assert s.ctx.tokens == []


async def test_turn_starts_with_thinking_then_a_label_per_tool_call():
    sent = []

    async def send(m):
        sent.append(m)

    class ToolClient:
        async def query(self, text):
            pass

        async def receive_response(self):
            yield AssistantMessage(content=[ToolUseBlock(id="t", name="mcp__wallet__get_balances", input={})], model="test")

    async def factory(tools):
        return ToolClient()

    s = Session(send, FakeChain(), factory)
    await s.handle(USER)
    await s._turn
    assert sent == [
        {"type": "progress", "label": "Thinking…"},
        {"type": "progress", "label": "Checking your balances"},
        {"type": "turn_end"},
    ]
