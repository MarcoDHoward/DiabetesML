"""FastAPI backend for prediction market scanner."""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

import json as _json
from database import init_db, get_db, Market, Report, Wallet, WalletPosition, WalletTrade, KalshiSignal, settings
from scheduler import start_scheduler, run_scan, run_whale_scan, run_kalshi_signal_scan
from reports.generator import generate_report

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    start_scheduler()
    yield


app = FastAPI(title="Prediction Market Scanner", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Markets ───────────────────────────────────────────────────────────────────

@app.get("/api/markets")
async def list_markets(
    min_prob: float = 0.0,
    source: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Return active high-probability markets, sorted by probability desc."""
    q = select(Market).where(Market.is_active == True, Market.probability >= min_prob)
    if source:
        q = q.where(Market.source == source)
    q = q.order_by(desc(Market.probability)).limit(limit)
    result = await db.execute(q)
    markets = result.scalars().all()

    return [
        {
            "id": m.id,
            "source": m.source,
            "question": m.question,
            "probability": m.probability,
            "probability_pct": f"{m.probability * 100:.1f}%",
            "volume_24h": m.volume_24h,
            "liquidity": m.liquidity,
            "closes_at": m.closes_at,
            "url": m.url,
            "last_seen": m.last_seen.isoformat(),
        }
        for m in markets
    ]


@app.get("/api/markets/{market_id}")
async def get_market(market_id: str, db: AsyncSession = Depends(get_db)):
    market = await db.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return {
        "id": market.id,
        "source": market.source,
        "question": market.question,
        "probability": market.probability,
        "probability_pct": f"{market.probability * 100:.1f}%",
        "volume_24h": market.volume_24h,
        "liquidity": market.liquidity,
        "closes_at": market.closes_at,
        "url": market.url,
        "last_seen": market.last_seen.isoformat(),
    }


# ─── Reports ───────────────────────────────────────────────────────────────────

@app.get("/api/markets/{market_id}/report")
async def get_or_create_report(
    market_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return a cached report or generate a fresh one via Claude."""
    market = await db.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    # Return cached report if it exists and is recent (< 6 hours old)
    q = (
        select(Report)
        .where(Report.market_id == market_id)
        .order_by(desc(Report.generated_at))
        .limit(1)
    )
    result = await db.execute(q)
    existing = result.scalar_one_or_none()

    if existing:
        from datetime import datetime, timedelta
        age = datetime.utcnow() - existing.generated_at
        if age < timedelta(hours=6):
            return {
                "market_id": market_id,
                "question": existing.question,
                "probability": existing.probability,
                "content": existing.content,
                "generated_at": existing.generated_at.isoformat(),
                "cached": True,
            }

    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured — reports unavailable.",
        )

    content = await generate_report(
        question=market.question,
        probability=market.probability,
        source=market.source,
        volume_24h=market.volume_24h,
        closes_at=market.closes_at or "",
    )

    report = Report(
        market_id=market_id,
        source=market.source,
        question=market.question,
        probability=market.probability,
        content=content,
    )
    db.add(report)
    await db.commit()

    return {
        "market_id": market_id,
        "question": market.question,
        "probability": market.probability,
        "content": content,
        "generated_at": report.generated_at.isoformat(),
        "cached": False,
    }


# ─── Admin ─────────────────────────────────────────────────────────────────────

# ─── Whales ────────────────────────────────────────────────────────────────────

def _fmt_wallet(w: Wallet) -> dict:
    return {
        "address": w.address,
        "username": w.username or w.address[:8] + "…",
        "x_username": w.x_username,
        "profile_image": w.profile_image,
        "pnl_month": w.pnl_month,
        "pnl_all": w.pnl_all,
        "volume": w.volume,
        "rank_month": w.rank_month,
        "last_updated": w.last_updated.isoformat(),
        "polymarket_url": f"https://polymarket.com/profile/{w.address}",
    }


@app.get("/api/whales")
async def list_whales(limit: int = 30, db: AsyncSession = Depends(get_db)):
    """Return top whale wallets sorted by monthly PNL."""
    from sqlalchemy import asc
    q = select(Wallet).order_by(asc(Wallet.rank_month)).limit(limit)
    result = await db.execute(q)
    wallets = result.scalars().all()
    return [_fmt_wallet(w) for w in wallets]


@app.get("/api/whales/{address}")
async def get_whale(address: str, db: AsyncSession = Depends(get_db)):
    """Return a single whale with their open positions and recent trades."""
    wallet = await db.get(Wallet, address)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    pos_q = (
        select(WalletPosition)
        .where(WalletPosition.wallet_address == address)
        .order_by(desc(WalletPosition.current_value))
    )
    trade_q = (
        select(WalletTrade)
        .where(WalletTrade.wallet_address == address)
        .order_by(desc(WalletTrade.timestamp))
        .limit(10)
    )

    pos_result = await db.execute(pos_q)
    trade_result = await db.execute(trade_q)
    positions = pos_result.scalars().all()
    trades = trade_result.scalars().all()

    return {
        **_fmt_wallet(wallet),
        "positions": [
            {
                "condition_id": p.condition_id,
                "title": p.title,
                "outcome": p.outcome,
                "size": p.size,
                "avg_price": p.avg_price,
                "cur_price": p.cur_price,
                "current_value": p.current_value,
                "cash_pnl": p.cash_pnl,
                "percent_pnl": p.percent_pnl,
                "end_date": p.end_date,
                "url": f"https://polymarket.com/event/{p.slug}" if p.slug else "",
            }
            for p in positions
        ],
        "recent_trades": [
            {
                "title": t.title,
                "outcome": t.outcome,
                "side": t.side,
                "size": t.size,
                "price": t.price,
                "usdc_size": t.usdc_size,
                "timestamp": t.timestamp,
                "url": f"https://polymarket.com/event/{t.slug}" if t.slug else "",
            }
            for t in trades
        ],
    }


@app.get("/api/whales/overlap/markets")
async def whale_market_overlap(
    min_prob: float = 0.85,
    db: AsyncSession = Depends(get_db),
):
    """
    Find markets where top whales have open positions AND the market has
    a high probability — the strongest combined signal.
    """
    markets_q = select(Market).where(
        Market.is_active == True,
        Market.probability >= min_prob,
    )
    markets_result = await db.execute(markets_q)
    markets = {m.question.lower()[:60]: m for m in markets_result.scalars().all()}

    positions_q = (
        select(WalletPosition, Wallet)
        .join(Wallet, WalletPosition.wallet_address == Wallet.address)
        .order_by(desc(WalletPosition.current_value))
    )
    pos_result = await db.execute(positions_q)
    rows = pos_result.all()

    overlaps = []
    seen = set()
    for pos, wallet in rows:
        pos_key = pos.title.lower()[:60]
        for mkey, market in markets.items():
            if pos_key in mkey or mkey in pos_key:
                overlap_id = f"{market.id}_{wallet.address}"
                if overlap_id in seen:
                    continue
                seen.add(overlap_id)
                overlaps.append({
                    "market_id": market.id,
                    "question": market.question,
                    "probability": market.probability,
                    "probability_pct": f"{market.probability * 100:.1f}%",
                    "source": market.source,
                    "market_url": market.url,
                    "whale": {
                        "address": wallet.address,
                        "username": wallet.username or wallet.address[:8] + "…",
                        "rank_month": wallet.rank_month,
                        "pnl_month": wallet.pnl_month,
                        "position_outcome": pos.outcome,
                        "position_size": pos.size,
                        "position_value": pos.current_value,
                        "position_pnl_pct": pos.percent_pnl,
                        "whale_url": f"https://polymarket.com/profile/{wallet.address}",
                    },
                })

    overlaps.sort(key=lambda x: x["probability"], reverse=True)
    return overlaps


@app.post("/api/whales/scan")
async def trigger_whale_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_whale_scan)
    return {"status": "whale scan triggered"}


# ─── Kalshi Signals ────────────────────────────────────────────────────────────

SIGNAL_LABELS = {
    "VOLUME_SPIKE": {"label": "Volume Spike", "color": "amber", "icon": "📈"},
    "OI_JUMP": {"label": "OI Jump", "color": "purple", "icon": "🔺"},
    "PRICE_DRIFT_UP": {"label": "Price Drift ↑", "color": "green", "icon": "⬆️"},
    "PRICE_DRIFT_DOWN": {"label": "Price Drift ↓", "color": "red", "icon": "⬇️"},
    "BID_PRESSURE": {"label": "Buy Pressure", "color": "green", "icon": "💚"},
    "ASK_PRESSURE": {"label": "Sell Pressure", "color": "red", "icon": "🔴"},
}


@app.get("/api/kalshi/signals")
async def list_kalshi_signals(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Return current Kalshi smart-money signals, newest first."""
    q = select(KalshiSignal).order_by(desc(KalshiSignal.detected_at)).limit(limit)
    result = await db.execute(q)
    rows = result.scalars().all()

    return [
        {
            "ticker": s.ticker,
            "title": s.title,
            "signals": _json.loads(s.signals),
            "signal_meta": [SIGNAL_LABELS.get(sig, {"label": sig, "color": "slate", "icon": "•"})
                            for sig in _json.loads(s.signals)],
            "details": _json.loads(s.details),
            "mid": s.mid,
            "mid_pct": f"{s.mid * 100:.1f}%",
            "volume_24h": s.volume_24h,
            "open_interest": s.open_interest,
            "close_time": s.close_time,
            "url": s.url,
            "detected_at": s.detected_at.isoformat(),
        }
        for s in rows
    ]


@app.post("/api/kalshi/scan")
async def trigger_kalshi_scan(background_tasks: BackgroundTasks):
    if not settings.kalshi_api_key_id:
        raise HTTPException(status_code=503, detail="Kalshi API key not configured.")
    background_tasks.add_task(run_kalshi_signal_scan)
    return {"status": "Kalshi signal scan triggered"}


@app.post("/api/scan")
async def trigger_scan(background_tasks: BackgroundTasks):
    """Manually trigger a market scan."""
    background_tasks.add_task(run_scan)
    return {"status": "scan triggered"}


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "threshold": settings.probability_threshold,
        "kalshi_configured": bool(settings.kalshi_api_key_id),
        "claude_configured": bool(settings.anthropic_api_key),
    }
