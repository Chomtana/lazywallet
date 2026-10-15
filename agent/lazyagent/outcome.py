def outcome_text(result: dict | None, steps: list[dict], what: str, success: str, revert_hint: str = "") -> str:
    """Explain a browser tx_result to the model in one or two sentences."""
    if result is None:
        return f"The user didn't respond to the confirmation within 5 minutes, so the {what} wasn't sent."
    if result.get("outcome") == "rejected":
        return f"The user rejected the {what}. Nothing was sent."
    idx = result.get("failed_step")
    at = f" at step {idx + 1} ({steps[idx]['label']})" if isinstance(idx, int) and 0 <= idx < len(steps) and len(steps) > 1 else ""
    earlier = " The earlier approval steps did go through, which is harmless." if isinstance(idx, int) and idx > 0 else ""
    if result.get("error") and result.get("hash"):
        return (
            f"The {what} was broadcast{at} (tx {result['hash']}) but its confirmation couldn't be read "
            f"({result['error']}). Don't resend — ask the user to check their balance first."
        )
    if result.get("error"):
        return f"The {what} failed before it was sent{at}: {result['error']}.{earlier}"
    if result.get("status") == "reverted":
        return f"The {what} reverted{at}. Tx {result.get('hash')}.{earlier}{revert_hint}"
    return success
