from lazyagent.outcome import outcome_text

ONE = [{"label": "Send", "request": {}}]
THREE = [{"label": "Allow USDC", "request": {}}, {"label": "Allow Uniswap router", "request": {}}, {"label": "Swap USDC → ETH", "request": {}}]


def test_timeout_and_reject():
    assert "didn't respond" in outcome_text(None, ONE, "transfer", "ok")
    assert outcome_text({"outcome": "rejected"}, ONE, "swap", "ok") == "The user rejected the swap. Nothing was sent."


def test_success_passthrough():
    assert outcome_text({"outcome": "approved", "status": "success", "hash": "0x1"}, ONE, "transfer", "Sent!") == "Sent!"


def test_single_step_failures_keep_phase2_wording():
    assert "failed before it was sent: nope" in outcome_text({"outcome": "approved", "error": "nope"}, ONE, "transfer", "ok")
    text = outcome_text({"outcome": "approved", "error": "timeout", "hash": "0xfeed"}, ONE, "transfer", "ok")
    assert "0xfeed" in text and "Don't resend" in text
    assert "reverted" in outcome_text({"outcome": "approved", "status": "reverted", "hash": "0x2"}, ONE, "transfer", "ok")


def test_multi_step_revert_names_step_and_hints():
    result = {"outcome": "approved", "status": "reverted", "hash": "0x3", "failed_step": 2}
    text = outcome_text(result, THREE, "swap", "ok", revert_hint=" The price probably moved more than the 1% slippage.")
    assert "step 3 (Swap USDC → ETH)" in text
    assert "approval steps did go through" in text
    assert "1% slippage" in text


def test_first_step_failure_has_no_harmless_note():
    text = outcome_text({"outcome": "approved", "error": "denied", "failed_step": 0}, THREE, "swap", "ok")
    assert "step 1 (Allow USDC)" in text
    assert "did go through" not in text
