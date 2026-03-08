"""FastAPI backend for prediction market scanner."""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import init_db, get_db, Market, Report, settings
from scheduler import start_scheduler, run_scan
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
