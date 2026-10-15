import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "claude-sonnet-5-5"


@dataclass(frozen=True)
class Settings:
    rpc_url: str
    model: str
    allowed_origins: tuple[str, ...]
    port: int


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    return Settings(
        rpc_url=os.environ.get("SANDBOX_RPC_URL") or "http://127.0.0.1:8545",
        model=os.environ.get("AGENT_MODEL") or DEFAULT_MODEL,
        allowed_origins=tuple((os.environ.get("WALLET_ORIGINS") or "http://localhost:5174").split(",")),
        port=int(os.environ.get("AGENT_PORT") or 8787),
    )
