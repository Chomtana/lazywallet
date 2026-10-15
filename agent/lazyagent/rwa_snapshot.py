"""Refresh the RWA project-token snapshot (lazyagent/data/rwa_coingecko.json) from CoinGecko's free API.

RWA project token = in CoinGecko's `real-world-assets-rwa` category and NOT in `tokenized-products`
("Tokenized Assets" — the umbrella that contains every tokenized stock/ETF/gold/silver/commodity/
treasury/T-bill/money-market/credit sub-category; verified 2026-10-15). Both categories are ~10 pages
and the free tier 429s even at one request every 15 s, so this runs offline (paced, honouring
Retry-After) instead of on a user's request.
Run: uv run --directory agent python -m lazyagent.rwa_snapshot
"""

import datetime
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from .trending import RWA_SNAPSHOT, RwaCoin, rwa_addresses

CG_API = "https://api.coingecko.com/api/v3"
RWA_CATEGORY = "real-world-assets-rwa"
ASSET_CATEGORIES = ("tokenized-products",)
PER_PAGE = 250


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as res:
        return json.loads(res.read())


class CoinGeckoRwaSource:
    def __init__(
        self,
        base: str = CG_API,
        sleep: Callable[[float], None] = time.sleep,
        pause: float = 15.0,
        retries: int = 6,
        per_page: int = PER_PAGE,
    ):
        self.base = base
        self.sleep = sleep
        self.pause = pause
        self.retries = retries
        self.per_page = per_page

    def _fetch(self, url: str):
        for attempt in range(self.retries):
            try:
                return _get_json(url)
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == self.retries - 1:
                    raise
                self.sleep(float(e.headers.get("retry-after") or 60))
        raise RuntimeError("unreachable")

    def markets(self, category: str) -> list[dict]:
        """Every page of coins/markets for one category; pauses between requests."""
        out: list[dict] = []
        page = 1
        while True:
            batch = self._fetch(f"{self.base}/coins/markets?vs_currency=usd&category={category}&per_page={self.per_page}&page={page}")
            out += batch
            self.sleep(self.pause)
            if len(batch) < self.per_page:
                return out
            page += 1

    def coin_list(self) -> list[dict]:
        return self._fetch(f"{self.base}/coins/list?include_platform=true")

    def coins(self) -> list[RwaCoin]:
        markets = self.markets(RWA_CATEGORY)
        asset_ids = {c["id"] for cat in ASSET_CATEGORIES for c in self.markets(cat)}
        return rwa_addresses(markets, self.coin_list(), asset_ids)


def snapshot_json(coins: list[RwaCoin], generated: str) -> str:
    rows = sorted(coins, key=lambda c: (c.network, -c.volume_24h, -c.market_cap, c.address))
    lines = ",\n".join("    " + json.dumps(asdict(c)) for c in rows)
    head = json.dumps(
        {
            "generated": generated,
            "source": f"CoinGecko coins/markets category={RWA_CATEGORY} minus {', '.join(ASSET_CATEGORIES)} (all pages) + coins/list platforms",
        }
    )[:-1]
    return f'{head}, "coins": [\n{lines}\n]}}\n'


def main(path: Path = RWA_SNAPSHOT) -> None:
    coins = CoinGeckoRwaSource().coins()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot_json(coins, datetime.date.today().isoformat()))
    counts = {n: sum(c.network == n for c in coins) for n in sorted({c.network for c in coins})}
    print(f"Wrote {len(coins)} RWA project-token addresses to {path}: {counts}")


if __name__ == "__main__":
    main()
