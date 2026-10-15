from claude_agent_sdk import AssistantMessage, ResultMessage, StreamEvent, TextBlock, ToolUseBlock

from lazyagent.stream import translate


def delta(text, parent=None):
    return StreamEvent(
        uuid="u", session_id="s", parent_tool_use_id=parent,
        event={"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
    )


def test_text_delta():
    assert translate(delta("Hi")) == [{"type": "text_delta", "text": "Hi"}]


def test_ignores_other_stream_events_and_subagent_text():
    assert translate(StreamEvent(uuid="u", session_id="s", event={"type": "message_start"})) == []
    assert translate(delta("x", parent="tool1")) == []


def test_text_done_after_assistant_text_only():
    assert translate(AssistantMessage(content=[TextBlock(text="Hi")], model="m")) == [{"type": "text_done"}]
    assert translate(AssistantMessage(content=[ToolUseBlock(id="t", name="x", input={})], model="m")) == []


def test_errors():
    assert translate(AssistantMessage(content=[], model="m", error="authentication_failed"))[0]["type"] == "error"
    result = ResultMessage(subtype="error_during_execution", duration_ms=1, duration_api_ms=1, is_error=True, num_turns=1, session_id="s", result="boom")
    assert translate(result) == [{"type": "error", "message": "boom"}]
    ok = ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s")
    assert translate(ok) == []
