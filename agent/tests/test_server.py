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
