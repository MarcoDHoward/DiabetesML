"""Background scheduler — scans markets every N minutes."""
import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, delete

from database import SessionLocal, Market, settings
from scanner.polymarket import fetch_high_probability_markets as fetch_poly
from scanner.kalshi import fetch_high_probability_markets as fetch_kalshi
from scanner.deduplicator import deduplicate

log = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def run_scan():
    """Fetch markets from both platforms and upsert into DB."""
    log.info("Starting market scan at %s", datetime.utcnow().isoformat())
    markets: list[dict] = []

    # Polymarket (no auth)
    try:
        poly = await fetch_poly(threshold=settings.probability_threshold)
        markets.extend(poly)
        log.info("Polymarket: %d high-probability markets", len(poly))
    except Exception as e:
        log.error("Polymarket fetch failed: %s", e)

    # Kalshi (auth required)
    if settings.kalshi_api_key_id:
        try:
            kal = await fetch_kalshi(
                key_id=settings.kalshi_api_key_id,
                private_key_path=settings.kalshi_private_key_path,
                threshold=settings.probability_threshold,
            )
            markets.extend(kal)
            log.info("Kalshi: %d high-probability markets", len(kal))
        except Exception as e:
            log.error("Kalshi fetch failed: %s", e)

    if not markets:
        log.warning("No markets fetched this cycle")
        return

    deduped = deduplicate(markets)

    async with SessionLocal() as session:
        # Mark all existing as inactive
        await session.execute(
            Market.__table__.update().values(is_active=False)
        )

        for m in deduped:
            existing = await session.get(Market, m["id"])
            if existing:
                existing.probability = m["probability"]
                existing.volume_24h = m["volume_24h"]
                existing.liquidity = m["liquidity"]
                existing.is_active = True
                existing.last_seen = datetime.utcnow()
            else:
                session.add(
                    Market(
                        id=m["id"],
                        source=m["source"],
                        question=m["question"],
                        probability=m["probability"],
                        volume_24h=m["volume_24h"],
                        liquidity=m["liquidity"],
                        closes_at=m.get("closes_at", ""),
                        url=m.get("url", ""),
                        is_active=True,
                        last_seen=datetime.utcnow(),
                    )
                )

        await session.commit()

    log.info("Scan complete — %d markets stored", len(deduped))


def start_scheduler():
    scheduler.add_job(
        run_scan,
        trigger="interval",
        minutes=settings.scan_interval_minutes,
        id="market_scan",
        replace_existing=True,
        next_run_time=datetime.utcnow(),  # Run immediately on startup
    )
    scheduler.start()
    log.info("Scheduler started (interval=%dm)", settings.scan_interval_minutes)
