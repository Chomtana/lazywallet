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
