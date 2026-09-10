from pathlib import Path
from typing import AsyncGenerator, Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlmodel.ext.asyncio.session import AsyncSession


# Config / env with pydantic-settings
# Production apps store config in environment variables (and .env locally).
# pydantic-settings loads them into a typed Settings object — same validation as Pydantic.
#
# Typical layout in a repo:
#   .env              → local secrets (NOT committed to git)
#   .env.example      → template showing required keys (committed)
#   app/settings.py   → Settings class
#   app/database.py   → engine + get_session using settings.database_url
#
# See .env.example in this folder for sample keys.


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",   # load .env if present
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Hero API"
    debug: bool = False
    database_url: str = "sqlite:///./database_settings.db"


settings = Settings()
print(f"SETTINGS — app_name={settings.app_name}, debug={settings.debug}")
print(f"SETTINGS — database_url={settings.database_url}")


# Override via environment variable (production pattern):
#   export DATABASE_URL="postgresql://user:pass@localhost/mydb"
# pydantic-settings maps DATABASE_URL env var → settings.database_url automatically.


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    age: int


# Sync session injection (most common with SQLModel today)
# create_engine once at startup → get_session() yields Session per request.
#
# FastAPI usage (see sqlmodel6.py):
#   SessionDep = Annotated[Session, Depends(get_session)]
#   def route(session: SessionDep): ...

sync_db_path = Path(__file__).parent / "database_settings.db"
sync_engine = create_engine(f"sqlite:///{sync_db_path}", echo=False)
SQLModel.metadata.create_all(sync_engine)


def get_session() -> Generator[Session, None, None]:
    with Session(sync_engine) as session:
        yield session


print("\nSYNC SESSION — one Session per request via Depends(get_session)")
with Session(sync_engine) as session:
    if not session.exec(select(Hero)).first():
        session.add(Hero(name="Spiderman", age=16))
        session.commit()

for session in get_session():
    hero = session.exec(select(Hero)).first()
    print(f"SYNC SESSION — loaded {hero.name if hero else None}")


# Async session injection (modern FastAPI / SQLAlchemy 2 style)
# Use when routes are `async def` and DB driver supports async (asyncpg, aiosqlite, etc.).
#
# Differences from sync:
#   create_async_engine(...)     instead of create_engine(...)
#   AsyncSession                 instead of Session
#   async def get_async_session  instead of def get_session
#   await session.exec(...)      instead of session.exec(...)
#   await session.commit()       instead of session.commit()
#
# FastAPI usage:
#   AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]
#   async def route(session: AsyncSessionDep): ...

async_db_path = Path(__file__).parent / "database_settings_async.db"
async_database_url = f"sqlite+aiosqlite:///{async_db_path}"

async_engine = create_async_engine(async_database_url, echo=False)
async_session_maker = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_async_db() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def demo_async_session() -> None:
    await init_async_db()

    async for session in get_async_session():
        if not (await session.exec(select(Hero))).first():
            session.add(Hero(name="Ironman", age=45))
            await session.commit()

    async for session in get_async_session():
        hero = (await session.exec(select(Hero))).first()
        print(f"ASYNC SESSION — loaded {hero.name if hero else None}")


print("\nASYNC SESSION — async engine + AsyncSession + await session.exec()")
import asyncio

asyncio.run(demo_async_session())


# Sync vs async — which to use?
#
# Sync (Session + def get_session):
#   - simpler, matches most SQLModel tutorials
#   - fine for many production APIs (FastAPI runs sync routes in a thread pool)
#   - used in sqlmodel1–8 and sqlmodel6.py
#
# Async (AsyncSession + async def get_async_session):
#   - better when app is fully async (many concurrent I/O-bound requests)
#   - requires async DB driver (postgresql+asyncpg, sqlite+aiosqlite, etc.)
#   - all DB calls in that route must use await
#
# Rule: match what the production repo already uses — don't mix sync Session in async def.


# Summary
#
# pydantic-settings  → Settings class reads env vars + .env file
# settings.database_url → single place for DB connection string
# get_session()        → sync DI dependency (Generator[Session])
# get_async_session()  → async DI dependency (AsyncGenerator[AsyncSession])
# Check the repo's app/core/config.py and app/db/session.py for real patterns
