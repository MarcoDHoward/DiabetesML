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


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with SessionLocal() as session:
        yield session
