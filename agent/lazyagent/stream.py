from claude_agent_sdk import AssistantMessage, ResultMessage, StreamEvent, TextBlock, ToolUseBlock

THINKING = "Thinking…"
# What the wallet shows while a wallet tool runs. Labels never name a chain.
TOOL_LABELS = {
    "get_balances": "Checking your balances",
    "propose_transfer": "Preparing your transfer",
    "propose_swap": "Finding the best route",
    "list_trending_tokens": "Looking up trending tokens",
    "request_test_funds": "Getting test funds",
    "list_airdrops": "Checking airdrops",
    "propose_deposit": "Preparing the farm",
    "unsupported_action": THINKING,
}


def progress(label: str) -> dict:
    return {"type": "progress", "label": label}


def tool_label(name: str) -> str:
    return TOOL_LABELS.get(name.removeprefix("mcp__wallet__"), "Working…")


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
        out = [{"type": "text_done"}] if any(isinstance(b, TextBlock) for b in msg.content) else []
        if msg.parent_tool_use_id is None:
            out += [progress(tool_label(b.name)) for b in msg.content if isinstance(b, ToolUseBlock)]
        return out
    if isinstance(msg, ResultMessage) and msg.is_error:
        return [{"type": "error", "message": msg.result or "; ".join(msg.errors or []) or "The agent hit an error."}]
    return []
