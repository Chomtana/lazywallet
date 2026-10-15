from lazyagent.config import ROOT, load_settings


def test_defaults(monkeypatch):
    monkeypatch.setattr("lazyagent.config.load_dotenv", lambda *a, **k: None)
    for key in ("SANDBOX_RPC_URL", "AGENT_MODEL", "WALLET_ORIGINS", "AGENT_PORT", "FAUCET_URL"):
        monkeypatch.delenv(key, raising=False)
    s = load_settings()
    assert s.rpc_url == "http://127.0.0.1:8545"
    assert s.model == "claude-sonnet-5-5"
    assert s.allowed_origins == ("http://localhost:5174",)
    assert s.port == 8787
    assert s.faucet_url == "http://127.0.0.1:8547"


def test_empty_model_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("AGENT_MODEL", "")
    assert load_settings().model == "claude-sonnet-5-5"


def test_root_is_repo_root():
    assert (ROOT / "pnpm-workspace.yaml").exists()
