# agent — LazyWallet AI agent

FastAPI WebSocket server (`ws://localhost:8787/ws`) running Claude through the Claude Agent SDK. Uses your **Claude Code login** (no API key). Built-in Claude Code tools are disabled; the agent only has wallet tools: `get_balances`, `resolve_recipient`, `propose_transfer`, `unsupported_action`.

```bash
claude                                            # once: make sure Claude Code is logged in
pnpm dev:agent                                    # start the agent (needs pnpm dev:sandbox)
uv run --directory agent pytest -q                # tests (no Claude calls; fork tests skip without ETH_RPC_URL)
uv run --directory agent python scripts/demo.py   # live check with the real model + seeded test wallet
```

Env (repo-root `.env`, all optional): `AGENT_MODEL` (default `claude-sonnet-5-5`), `SANDBOX_RPC_URL`, `WALLET_ORIGINS`, `AGENT_PORT`. If `ANTHROPIC_API_KEY` is set in your shell, Claude Code uses it instead of your login.
