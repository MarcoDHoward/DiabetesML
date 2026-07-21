"""
Kalshi smart money signal detector.

Since Kalshi is a regulated exchange with private trader identities,
we detect unusual activity patterns from public market data:
- Order book imbalance (heavy buy vs sell pressure)
- Volume spikes (vs rolling average)
- Open interest jumps
- Price drift (movement without a clear news catalyst)
"""
import httpx
import time
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)
KALSHI_BASE = "https://api.kalshi.com/trade-api/v2"


def _sign(key_id: str, private_key_path: str, method: str, path: str) -> dict[str, str]:
    """RSA-PSS signed headers for Kalshi API."""
    import base64
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


async def _get(client: httpx.AsyncClient, key_id: str, pk_path: str, path: str, params: dict) -> Any:
    headers = _sign(key_id, pk_path, "GET", path)
    resp = await client.get(f"{KALSHI_BASE}{path}", params=params, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def fetch_market_snapshots(
    key_id: str,
    private_key_path: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Fetch current open markets with price, volume, and open interest.
    Returns raw snapshots for anomaly detection.
    """
    path = "/markets"
    async with httpx.AsyncClient(timeout=30) as client:
        data = await _get(client, key_id, private_key_path, path, {"status": "open", "limit": limit})

    snapshots = []
    for m in data.get("markets", []):
        try:
            yes_bid = float(m.get("yes_bid_dollars", 0) or 0)
            yes_ask = float(m.get("yes_ask_dollars", 1) or 1)
            snapshots.append({
                "ticker": m.get("ticker", ""),
                "title": m.get("title", ""),
                "yes_bid": yes_bid,
                "yes_ask": yes_ask,
                "mid": (yes_bid + yes_ask) / 2,
                "volume_24h": float(m.get("volume_24h_fp", 0) or 0),
                "open_interest": float(m.get("open_interest", 0) or 0),
                "close_time": m.get("close_time", ""),
                "url": f"https://kalshi.com/markets/{m.get('ticker', '')}",
                "ts": int(time.time()),
            })
        except (ValueError, TypeError):
            continue
    return snapshots


def compute_signals(
    current: list[dict],
    previous: list[dict],
    volume_spike_multiplier: float = 2.5,
    oi_jump_pct: float = 0.20,
    price_drift_threshold: float = 0.05,
    imbalance_ratio: float = 3.0,
) -> list[dict[str, Any]]:
    """
    Compare current snapshot vs previous snapshot to detect signals.

    Signals detected:
    - VOLUME_SPIKE: 24h volume > N× previous
    - OI_JUMP: open interest grew > X%
    - PRICE_DRIFT: mid price moved > Y points
    - BID_PRESSURE: bid > ask*imbalance_ratio (more buyers than sellers)
    - ASK_PRESSURE: ask < bid/imbalance_ratio (more sellers than buyers)
    """
    prev_map = {m["ticker"]: m for m in previous}
    signals = []

    for cur in current:
        ticker = cur["ticker"]
        prev = prev_map.get(ticker)
        found: list[str] = []
        details: dict[str, Any] = {}

        # Order book imbalance (from current snapshot alone)
        bid = cur["yes_bid"]
        ask = cur["yes_ask"]
        spread = ask - bid
        if spread > 0:
            # bid pressure = lots of buyers pushing bid up close to ask
            if bid > 0 and ask > 0:
                # Imbalance: bid is unusually close to ask from above (deep bids)
                # We use bid/ask ratio — if bid is 90% of ask, strong buy pressure
                ratio = bid / ask if ask > 0 else 0
                if ratio >= 0.95 and bid >= 0.70:
                    found.append("BID_PRESSURE")
                    details["bid_ask_ratio"] = round(ratio, 3)
                elif ratio <= 0.50 and ask <= 0.40:
                    found.append("ASK_PRESSURE")
                    details["bid_ask_ratio"] = round(ratio, 3)

        if prev:
            # Volume spike
            prev_vol = prev["volume_24h"]
            cur_vol = cur["volume_24h"]
            if prev_vol > 0 and cur_vol >= prev_vol * volume_spike_multiplier:
                found.append("VOLUME_SPIKE")
                details["volume_multiplier"] = round(cur_vol / prev_vol, 1)
                details["volume_24h"] = cur_vol

            # Open interest jump
            prev_oi = prev["open_interest"]
            cur_oi = cur["open_interest"]
            if prev_oi > 0 and cur_oi > prev_oi * (1 + oi_jump_pct):
                found.append("OI_JUMP")
                details["oi_change_pct"] = round((cur_oi - prev_oi) / prev_oi * 100, 1)
                details["open_interest"] = cur_oi

            # Price drift
            prev_mid = prev["mid"]
            cur_mid = cur["mid"]
            drift = cur_mid - prev_mid
            if abs(drift) >= price_drift_threshold:
                direction = "UP" if drift > 0 else "DOWN"
                found.append(f"PRICE_DRIFT_{direction}")
                details["price_drift"] = round(drift, 4)
                details["prev_mid"] = round(prev_mid, 4)
                details["cur_mid"] = round(cur_mid, 4)

        if found:
            signals.append({
                "ticker": ticker,
                "title": cur["title"],
                "signals": found,
                "details": details,
                "mid": cur["mid"],
                "volume_24h": cur["volume_24h"],
                "open_interest": cur["open_interest"],
                "close_time": cur["close_time"],
                "url": cur["url"],
                "ts": cur["ts"],
            })

    # Sort by number of signals (more signals = stronger case)
    signals.sort(key=lambda s: len(s["signals"]), reverse=True)
    return signals
