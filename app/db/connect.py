import os
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

# Относительный путь от корня запуска приложения (где лежит nataiv.db)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./nataiv.db")

engine = create_async_engine(DATABASE_URL, echo=False)

async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def init_db():


    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)