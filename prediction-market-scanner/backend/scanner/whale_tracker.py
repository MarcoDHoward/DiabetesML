"""
Polymarket whale tracker — fetches top traders from the leaderboard,
their open positions, and recent trades. All endpoints are public.
"""
import time
import httpx
from typing import Any

DATA_BASE = "https://data-api.polymarket.com"


async def fetch_leaderboard(limit: int = 50, time_period: str = "MONTH") -> list[dict[str, Any]]:
    """Return top traders by PNL for the given time period."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{DATA_BASE}/leaderboard",
            params={
                "limit": limit,
                "offset": 0,
                "timePeriod": time_period,
                "orderBy": "PNL",
                "category": "OVERALL",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    wallets = []
    for i, entry in enumerate(data):
        address = entry.get("proxyWallet", "")
        if not address:
            continue
        wallets.append({
            "address": address,
            "username": entry.get("userName") or entry.get("pseudonym") or "",
            "x_username": entry.get("xUsername", ""),
            "profile_image": entry.get("profileImage", ""),
            "pnl": float(entry.get("pnl", 0) or 0),
            "volume": float(entry.get("vol", 0) or 0),
            "rank": i + 1,
        })
    return wallets


async def fetch_positions(address: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return open positions for a wallet, sorted by current value descending."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{DATA_BASE}/positions",
            params={
                "user": address,
                "sizeThreshold": 1.0,
                "limit": limit,
                "sortBy": "CURRENT",
                "sortDirection": "DESC",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    positions = []
    for p in data:
        try:
            positions.append({
                "condition_id": p.get("conditionId", ""),
                "title": p.get("title", ""),
                "outcome": p.get("outcome", "Yes"),
                "size": float(p.get("size", 0) or 0),
                "avg_price": float(p.get("avgPrice", 0) or 0),
                "cur_price": float(p.get("curPrice", 0) or 0),
                "current_value": float(p.get("currentValue", 0) or 0),
                "cash_pnl": float(p.get("cashPnl", 0) or 0),
                "percent_pnl": float(p.get("percentPnl", 0) or 0),
                "end_date": p.get("endDate", ""),
                "slug": p.get("slug", ""),
            })
        except (ValueError, TypeError):
            continue
    return positions


async def fetch_recent_trades(address: str, limit: int = 10) -> list[dict[str, Any]]:
    """Return the most recent trades for a wallet."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{DATA_BASE}/trades",
            params={
                "user": address,
                "limit": limit,
                "takerOnly": "true",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    trades = []
    for t in data:
        try:
            trades.append({
                "tx_hash": t.get("transactionHash", "") or f"{address}_{t.get('timestamp',0)}",
                "condition_id": t.get("conditionId", ""),
                "title": t.get("title", ""),
                "outcome": t.get("outcome", "Yes"),
                "side": t.get("side", "BUY"),
                "size": float(t.get("size", 0) or 0),
                "price": float(t.get("price", 0) or 0),
                "usdc_size": float(t.get("usdcSize", 0) or 0),
                "timestamp": int(t.get("timestamp", 0) or 0),
                "slug": t.get("slug", ""),
            })
        except (ValueError, TypeError):
            continue
    return trades


async def fetch_all_whale_data(
    top_n: int = 30,
    positions_per_whale: int = 15,
    trades_per_whale: int = 8,
) -> list[dict[str, Any]]:
    """
    Fetch leaderboard + positions + recent trades for the top N wallets.
    Returns enriched whale records.
    """
    whales = await fetch_leaderboard(limit=top_n)

    # Also fetch all-time PNL for context
    try:
        all_time = await fetch_leaderboard(limit=top_n, time_period="ALL")
        all_time_map = {w["address"]: w["pnl"] for w in all_time}
    except Exception:
        all_time_map = {}

    enriched = []
    for whale in whales:
        addr = whale["address"]
        try:
            positions = await fetch_positions(addr, limit=positions_per_whale)
        except Exception:
            positions = []

        try:
            trades = await fetch_recent_trades(addr, limit=trades_per_whale)
        except Exception:
            trades = []

        enriched.append({
            **whale,
            "pnl_all": all_time_map.get(addr, 0),
            "positions": positions,
            "recent_trades": trades,
        })

    return enriched
