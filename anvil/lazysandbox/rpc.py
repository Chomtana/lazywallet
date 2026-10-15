import time
from pathlib import Path

from dotenv import load_dotenv
from web3 import HTTPProvider, Web3

ROOT = Path(__file__).resolve().parents[2]


def load_env() -> None:
    load_dotenv(ROOT / ".env")


def anvil_command(fork_url: str, fork_block: str | None, port: int) -> list[str]:
    cmd = ["anvil", "--fork-url", fork_url, "--chain-id", "1", "--port", str(port)]
    if fork_block:
        cmd += ["--fork-block-number", fork_block]
    return cmd


def wait_for_rpc(url: str, timeout: float) -> None:
    w3 = Web3(HTTPProvider(url))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if w3.eth.chain_id == 1:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Anvil at {url} did not become ready within {timeout:.0f}s")
