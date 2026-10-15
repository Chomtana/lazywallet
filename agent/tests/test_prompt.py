from lazyagent.prompt import SYSTEM_PROMPT


def test_prompt_never_volunteers_the_environment():
    lower = SYSTEM_PROMPT.lower()
    assert "sandbox" not in lower and "nothing here costs real money" not in lower and "is a demo" not in lower


def test_prompt_answers_honestly_when_asked():
    assert "fork of Ethereum and Avalanche mainnet with real contracts and live prices, and no real funds move" in SYSTEM_PROMPT
    assert "Never claim it's live mainnet" in SYSTEM_PROMPT
