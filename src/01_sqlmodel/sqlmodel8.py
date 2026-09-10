from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, Text, func
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select


# Field() for SQL columns
# SQLModel Field() does double duty: Pydantic validation + SQLAlchemy column definition.
# Builds on model2.py (Pydantic Field) — here focused on DB-specific options.

db_file = Path(__file__).parent / "database_fields.db"
db_file.unlink(missing_ok=True)
engine = create_engine(f"sqlite:///{db_file}", echo=False)


# primary_key=True — unique identifier for each row. Usually on id.
# id: int | None = Field(default=None, primary_key=True)
#   → None before insert; DB auto-generates integer id after commit+refresh.

class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    # index=True — faster lookups/filters on this column (creates DB index).
    name: str = Field(index=True)

    # unique=True — no two rows can share this value (creates unique constraint).
    email: str = Field(unique=True, index=True)

    # foreign_key="table.column" — links to parent table primary key column.
    team_id: int | None = Field(default=None, foreign_key="team.id")
    team: Optional[Team] = Relationship()

    # default — fixed default value when field not provided.
    role: str = Field(default="hero")

    # default_factory — compute a fresh default per row (UUID, timestamp, list, dict).
    public_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # nullable via Optional — column allows NULL in DB.
    nickname: str | None = Field(default=None)       # optional, can be NULL
    bio: str | None = None                           # same: Optional + default None

    # sa_column — escape hatch for full SQLAlchemy Column control.
    # Use when Field() options are not enough (custom types, server_default, etc.).
    # When sa_column is set, do NOT also pass primary_key/foreign_key/index on Field().
    notes: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime, onupdate=func.now(), nullable=True),
    )


SQLModel.metadata.create_all(engine)


with Session(engine) as session:
    team = Team(name="Avengers")
    session.add(team)
    session.commit()
    session.refresh(team)

    hero = Hero(
        name="Spiderman",
        email="spider@avengers.com",
        team_id=team.id,
        # role defaults to "hero"
        # public_id and created_at set by default_factory
        # nickname and bio left as None (nullable)
    )
    session.add(hero)
    session.commit()
    session.refresh(hero)

    print(f"PRIMARY KEY — id={hero.id}")
    print(f"FOREIGN KEY — team_id={hero.team_id}, team={hero.team.name}")
    print(f"DEFAULT — role={hero.role}")
    print(f"DEFAULT_FACTORY — public_id={hero.public_id[:8]}..., created_at={hero.created_at}")
    print(f"NULLABLE — nickname={hero.nickname}, bio={hero.bio}")


# unique=True — second row with same email fails at commit time.
with Session(engine) as session:
    try:
        dupe = Hero(name="Fake Spider", email="spider@avengers.com")
        session.add(dupe)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"UNIQUE — duplicate email rejected: {type(e).__name__}")


# index=True — no runtime error; helps query speed on name/email filters.
with Session(engine) as session:
    found = session.exec(
        select(Hero).where(Hero.name == "Spiderman")
    ).first()
    print(f"INDEX — lookup by name: {found.email if found else None}")


# Nullable vs required recap
#
# name: str                    → required, NOT NULL
# nickname: str | None = None  → optional, NULL allowed
# role: str = Field(default="hero") → NOT NULL, default applied if omitted

with Session(engine) as session:
    minimal = Hero(name="Ironman", email="iron@avengers.com")
    session.add(minimal)
    session.commit()
    session.refresh(minimal)
    print(f"NULLABLE minimal hero — nickname={minimal.nickname}, role={minimal.role}")


# sa_column — lower-level SQLAlchemy when you need:
#   - specific SQL types (Text, Numeric, JSONB in Postgres)
#   - server_default / onupdate at DB level
#   - complex column args not exposed on Field()

with Session(engine) as session:
    hero = session.exec(select(Hero).where(Hero.name == "Spiderman")).one()
    hero.notes = "Friendly neighborhood hero."
    session.add(hero)
    session.commit()
    session.refresh(hero)
    print(f"SA_COLUMN notes (Text) — {hero.notes}")


# Summary
#
# primary_key=True     → row identifier (usually id, auto-increment)
# foreign_key="t.col"  → link to another table's column
# index=True           → faster searches (DB index)
# unique=True          → no duplicate values allowed
# default=...          → fixed default for new rows
# default_factory=...  → callable default (uuid, datetime, list)
# Optional[T] + None   → nullable column
# sa_column=Column(...) → full SQLAlchemy control when Field() is not enough

with Session(engine) as session:
    heroes = session.exec(select(Hero)).all()
    print("\nAll heroes:")
    for h in heroes:
        print(f"  id={h.id}, name={h.name}, email={h.email}, role={h.role}")
