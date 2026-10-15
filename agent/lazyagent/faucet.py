import asyncio
import json
import urllib.error
import urllib.request

TIMEOUT_S = 30


def _post(url: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as res:
            return res.status, json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
    except (urllib.error.URLError, OSError) as e:
        raise ConnectionError(f"Faucet unreachable: {e}") from e


async def request_funds(faucet_url: str, address: str) -> str:
    """Ask the Sandbox faucet (anvil/) to fund `address`; returns its human summary."""
    status, body = await asyncio.to_thread(_post, f"{faucet_url}/fund", {"address": address})
    if status != 200:
        raise RuntimeError(body.get("detail") or f"Faucet error ({status})")
    return body.get("summary", "test funds")
