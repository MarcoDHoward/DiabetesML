"""Background scheduler — scans markets every N minutes."""
import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, delete

import json
from database import SessionLocal, Market, Wallet, WalletPosition, WalletTrade, KalshiSnapshot, KalshiSignal, settings
from scanner.polymarket import fetch_high_probability_markets as fetch_poly
from scanner.kalshi import fetch_high_probability_markets as fetch_kalshi
from scanner.deduplicator import deduplicate
from scanner.whale_tracker import fetch_all_whale_data
from scanner.kalshi_signals import fetch_market_snapshots, compute_signals

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


async def run_whale_scan():
    """Refresh top whale wallets, their positions, and recent trades."""
    log.info("Starting whale scan at %s", datetime.utcnow().isoformat())
    try:
        whales = await fetch_all_whale_data(top_n=30, positions_per_whale=15, trades_per_whale=8)
    except Exception as e:
        log.error("Whale scan failed: %s", e)
        return

    async with SessionLocal() as session:
        for whale in whales:
            addr = whale["address"]
            existing = await session.get(Wallet, addr)
            if existing:
                existing.username = whale["username"]
                existing.x_username = whale["x_username"]
                existing.profile_image = whale["profile_image"]
                existing.pnl_month = whale["pnl"]
                existing.pnl_all = whale["pnl_all"]
                existing.volume = whale["volume"]
                existing.rank_month = whale["rank"]
                existing.last_updated = datetime.utcnow()
            else:
                session.add(Wallet(
                    address=addr,
                    username=whale["username"],
                    x_username=whale["x_username"],
                    profile_image=whale["profile_image"],
                    pnl_month=whale["pnl"],
                    pnl_all=whale["pnl_all"],
                    volume=whale["volume"],
                    rank_month=whale["rank"],
                    last_updated=datetime.utcnow(),
                ))

            # Replace positions for this wallet
            await session.execute(
                WalletPosition.__table__.delete().where(
                    WalletPosition.__table__.c.wallet_address == addr
                )
            )
            for pos in whale["positions"]:
                session.add(WalletPosition(
                    wallet_address=addr,
                    condition_id=pos["condition_id"],
                    title=pos["title"],
                    outcome=pos["outcome"],
                    size=pos["size"],
                    avg_price=pos["avg_price"],
                    cur_price=pos["cur_price"],
                    current_value=pos["current_value"],
                    cash_pnl=pos["cash_pnl"],
                    percent_pnl=pos["percent_pnl"],
                    end_date=pos.get("end_date", ""),
                    slug=pos.get("slug", ""),
                    last_updated=datetime.utcnow(),
                ))

            # Upsert trades
            for trade in whale["recent_trades"]:
                existing_trade = await session.get(WalletTrade, trade["tx_hash"])
                if not existing_trade:
                    session.add(WalletTrade(
                        tx_hash=trade["tx_hash"],
                        wallet_address=addr,
                        condition_id=trade["condition_id"],
                        title=trade["title"],
                        outcome=trade["outcome"],
                        side=trade["side"],
                        size=trade["size"],
                        price=trade["price"],
                        usdc_size=trade["usdc_size"],
                        timestamp=trade["timestamp"],
                        slug=trade.get("slug", ""),
                    ))

        await session.commit()

    log.info("Whale scan complete — %d whales updated", len(whales))


async def run_kalshi_signal_scan():
    """Snapshot Kalshi markets, diff vs previous snapshot, store signals."""
    if not settings.kalshi_api_key_id:
        log.debug("Kalshi not configured — skipping signal scan")
        return

    log.info("Starting Kalshi signal scan")
    try:
        current = await fetch_market_snapshots(
            settings.kalshi_api_key_id,
            settings.kalshi_private_key_path,
        )
    except Exception as e:
        log.error("Kalshi snapshot fetch failed: %s", e)
        return

    async with SessionLocal() as session:
        # Load previous snapshots (most recent per ticker)
        from sqlalchemy import text
        prev_rows = await session.execute(
            text("""
                SELECT ticker, title, yes_bid, yes_ask, mid, volume_24h,
                       open_interest, close_time, url, ts
                FROM kalshi_snapshots s1
                WHERE ts = (SELECT MAX(ts) FROM kalshi_snapshots s2 WHERE s2.ticker = s1.ticker)
            """)
        )
        previous = [dict(r._mapping) for r in prev_rows]

        # Compute signals
        signals = compute_signals(current, previous)

        # Store new snapshots
        for snap in current:
            session.add(KalshiSnapshot(**snap))

        # Replace current signals
        await session.execute(KalshiSignal.__table__.delete())
        for sig in signals:
            session.add(KalshiSignal(
                ticker=sig["ticker"],
                title=sig["title"],
                signals=json.dumps(sig["signals"]),
                details=json.dumps(sig["details"]),
                mid=sig["mid"],
                volume_24h=sig["volume_24h"],
                open_interest=sig["open_interest"],
                close_time=sig["close_time"],
                url=sig["url"],
            ))

        # Prune old snapshots (keep last 4 per ticker = ~1 hour at 15m intervals)
        await session.execute(
            text("""
                DELETE FROM kalshi_snapshots
                WHERE id NOT IN (
                    SELECT id FROM kalshi_snapshots s1
                    WHERE id IN (
                        SELECT id FROM kalshi_snapshots s2
                        WHERE s2.ticker = s1.ticker
                        ORDER BY ts DESC LIMIT 4
                    )
                )
            """)
        )

        await session.commit()

    log.info("Kalshi signal scan complete — %d signals detected", len(signals))


def start_scheduler():
    scheduler.add_job(
        run_scan,
        trigger="interval",
        minutes=settings.scan_interval_minutes,
        id="market_scan",
        replace_existing=True,
        next_run_time=datetime.utcnow(),
    )
    scheduler.add_job(
        run_whale_scan,
        trigger="interval",
        minutes=30,
        id="whale_scan",
        replace_existing=True,
        next_run_time=datetime.utcnow(),
    )
    scheduler.add_job(
        run_kalshi_signal_scan,
        trigger="interval",
        minutes=settings.scan_interval_minutes,
        id="kalshi_signals",
        replace_existing=True,
        next_run_time=datetime.utcnow(),
    )
    scheduler.start()
    log.info("Scheduler started (market=%dm, whale=30m, kalshi=%dm)", settings.scan_interval_minutes, settings.scan_interval_minutes)
