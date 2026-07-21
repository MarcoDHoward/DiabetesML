"""Polymarket scanner — no auth required for read endpoints."""
import json
import httpx
from typing import Any

GAMMA_BASE = "https://gamma-api.polymarket.com"


async def fetch_high_probability_markets(threshold: float = 0.88) -> list[dict[str, Any]]:
    """Fetch active Polymarket markets where YES probability >= threshold."""
    results = []
    offset = 0
    limit = 100

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            resp = await client.get(
                f"{GAMMA_BASE}/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": limit,
                    "offset": offset,
                    "order": "volume24hr",
                    "ascending": "false",
                },
            )
            resp.raise_for_status()
            markets = resp.json()

            if not markets:
                break

            for m in markets:
                try:
                    prices_raw = m.get("outcomePrices", "[]")
                    prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                    if not prices:
                        continue

                    yes_prob = float(prices[0])
                    if yes_prob < threshold:
                        continue

                    results.append({
                        "id": f"poly_{m.get('conditionId', m.get('id', ''))}",
                        "source": "polymarket",
                        "question": m.get("question", ""),
                        "probability": yes_prob,
                        "volume_24h": float(m.get("volume24hr", 0) or 0),
                        "liquidity": float(m.get("liquidityNum", 0) or 0),
                        "closes_at": m.get("endDate", ""),
                        "url": f"https://polymarket.com/event/{m.get('slug', '')}",
                    })
                except (ValueError, KeyError, TypeError):
                    continue

            if len(markets) < limit:
                break
            offset += limit

            # Stop after 500 markets to respect rate limits
            if offset >= 500:
                break

    return results
