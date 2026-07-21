from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, DateTime, Text, Boolean
from datetime import datetime
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    kalshi_api_key_id: str = ""
    kalshi_private_key_path: str = "./kalshi_private_key.pem"
    probability_threshold: float = 0.88
    scan_interval_minutes: int = 15
    database_url: str = "sqlite+aiosqlite:///./markets.db"

    class Config:
        env_file = ".env"


settings = Settings()
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String)  # "polymarket" | "kalshi"
    question: Mapped[str] = mapped_column(Text)
    probability: Mapped[float] = mapped_column(Float)
    volume_24h: Mapped[float] = mapped_column(Float, default=0)
    liquidity: Mapped[float] = mapped_column(Float, default=0)
    closes_at: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str] = mapped_column(String, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    question: Mapped[str] = mapped_column(Text)
    probability: Mapped[float] = mapped_column(Float)
    content: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Wallet(Base):
    __tablename__ = "wallets"

    address: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    x_username: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_image: Mapped[str | None] = mapped_column(String, nullable=True)
    pnl_month: Mapped[float] = mapped_column(Float, default=0)
    pnl_all: Mapped[float] = mapped_column(Float, default=0)
    volume: Mapped[float] = mapped_column(Float, default=0)
    rank_month: Mapped[int] = mapped_column(default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WalletPosition(Base):
    __tablename__ = "wallet_positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String)
    condition_id: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String)
    size: Mapped[float] = mapped_column(Float)
    avg_price: Mapped[float] = mapped_column(Float)
    cur_price: Mapped[float] = mapped_column(Float)
    current_value: Mapped[float] = mapped_column(Float)
    cash_pnl: Mapped[float] = mapped_column(Float, default=0)
    percent_pnl: Mapped[float] = mapped_column(Float, default=0)
    end_date: Mapped[str | None] = mapped_column(String, nullable=True)
    slug: Mapped[str] = mapped_column(String, default="")
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WalletTrade(Base):
    __tablename__ = "wallet_trades"

    tx_hash: Mapped[str] = mapped_column(String, primary_key=True)
    wallet_address: Mapped[str] = mapped_column(String)
    condition_id: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String)
    side: Mapped[str] = mapped_column(String)  # BUY | SELL
    size: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    usdc_size: Mapped[float] = mapped_column(Float, default=0)
    timestamp: Mapped[int] = mapped_column(default=0)
    slug: Mapped[str] = mapped_column(String, default="")


class KalshiSnapshot(Base):
    """Raw market snapshot stored each scan cycle for delta computation."""
    __tablename__ = "kalshi_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(Text)
    yes_bid: Mapped[float] = mapped_column(Float)
    yes_ask: Mapped[float] = mapped_column(Float)
    mid: Mapped[float] = mapped_column(Float)
    volume_24h: Mapped[float] = mapped_column(Float)
    open_interest: Mapped[float] = mapped_column(Float)
    close_time: Mapped[str] = mapped_column(String, default="")
    url: Mapped[str] = mapped_column(String, default="")
    ts: Mapped[int] = mapped_column(default=0)


class KalshiSignal(Base):
    """Detected smart-money signals on Kalshi markets."""
    __tablename__ = "kalshi_signals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(Text)
    signals: Mapped[str] = mapped_column(Text)   # JSON list of signal names
    details: Mapped[str] = mapped_column(Text)   # JSON details dict
    mid: Mapped[float] = mapped_column(Float)
    volume_24h: Mapped[float] = mapped_column(Float)
    open_interest: Mapped[float] = mapped_column(Float)
    close_time: Mapped[str] = mapped_column(String, default="")
    url: Mapped[str] = mapped_column(String, default="")
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with SessionLocal() as session:
        yield session
