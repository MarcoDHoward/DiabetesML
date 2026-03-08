"""Kalshi scanner — requires RSA-PSS signed requests."""
import base64
import hashlib
import time
from pathlib import Path
from typing import Any

import httpx

KALSHI_BASE = "https://api.kalshi.com/trade-api/v2"


def _sign_request(key_id: str, private_key_path: str, method: str, path: str) -> dict[str, str]:
    """Generate RSA-PSS signed headers for Kalshi API."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        ts = str(int(time.time() * 1000))
        message = (ts + method.upper() + path).encode()

        key_pem = Path(private_key_path).read_bytes()
        private_key = serialization.load_pem_private_key(key_pem, password=None)

        signature = private_key.sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )

        return {
            "KALSHI-ACCESS-KEY": key_id,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
        }
    except Exception as e:
        raise RuntimeError(f"Kalshi signing failed: {e}") from e


async def fetch_high_probability_markets(
    key_id: str,
    private_key_path: str,
    threshold: float = 0.88,
) -> list[dict[str, Any]]:
    """Fetch open Kalshi markets where YES mid-price >= threshold."""
    if not key_id or not Path(private_key_path).exists():
        raise ValueError("Kalshi API key ID and private key path are required.")

    results = []
    cursor = None
    path = "/trade-api/v2/markets"

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params: dict[str, Any] = {"status": "open", "limit": 200}
            if cursor:
                params["cursor"] = cursor

            headers = _sign_request(key_id, private_key_path, "GET", path)

            resp = await client.get(
                f"{KALSHI_BASE}/markets",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            markets = data.get("markets", [])

            for m in markets:
                try:
                    yes_bid = float(m.get("yes_bid_dollars", 0) or 0)
                    yes_ask = float(m.get("yes_ask_dollars", 1) or 1)
                    mid = (yes_bid + yes_ask) / 2

                    if mid < threshold:
                        continue

                    ticker = m.get("ticker", "")
                    results.append({
                        "id": f"kalshi_{ticker}",
                        "source": "kalshi",
                        "question": m.get("title", ticker),
                        "probability": round(mid, 4),
                        "volume_24h": float(m.get("volume_24h_fp", 0) or 0),
                        "liquidity": float(m.get("open_interest", 0) or 0),
                        "closes_at": m.get("close_time", ""),
                        "url": f"https://kalshi.com/markets/{ticker}",
                    })
                except (ValueError, KeyError, TypeError):
                    continue

            cursor = data.get("cursor")
            if not cursor or len(markets) < 200:
                break

    return results
