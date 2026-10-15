import time
from pathlib import Path

from dotenv import load_dotenv
from web3 import HTTPProvider, Web3

ROOT = Path(__file__).resolve().parents[2]


def load_env() -> None:
    load_dotenv(ROOT / ".env")


AVAX_PUBLIC_RPC = "https://api.avax.network/ext/bc/C/rpc"
AVAX_CHAIN_ID = 43114


def anvil_command(fork_url: str, fork_block: str | None, port: int, chain_id: int = 1) -> list[str]:
    cmd = ["anvil", "--fork-url", fork_url, "--chain-id", str(chain_id), "--port", str(port)]
    if fork_block:
        cmd += ["--fork-block-number", fork_block]
    return cmd


def wait_for_rpc(url: str, timeout: float, chain_id: int = 1) -> None:
    w3 = Web3(HTTPProvider(url))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if w3.eth.chain_id == chain_id:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Anvil at {url} did not become ready within {timeout:.0f}s")
