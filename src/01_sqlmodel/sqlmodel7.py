from pathlib import Path
from typing import Generator

from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, create_engine, select


# Session & transaction patterns
# How to use Session safely in real apps (scripts, FastAPI, background jobs).
# Builds on sqlmodel1.py (session basics) and sqlmodel6.py (FastAPI DI).

db_file = Path(__file__).parent / "database_transactions.db"
db_file.unlink(missing_ok=True)   # reset for repeatable demo runs
engine = create_engine(f"sqlite:///{db_file}", echo=False)


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    age: int


SQLModel.metadata.create_all(engine)


# One session per request (unit of work)
# Rule: open one Session for each request/job, do all DB work inside it, then close.
# In FastAPI this is done with Depends(get_session) — one session per HTTP request.

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def handle_one_request() -> None:
    for session in get_session():
        hero = Hero(name="Spiderman", age=16)
        session.add(hero)
        session.commit()
        print(f"ONE SESSION PER REQUEST — saved {hero.name}")


handle_one_request()


# Commit vs flush
# flush()  → sends pending SQL to DB inside the current transaction (not permanent yet)
# commit() → makes the transaction permanent
#
# Use flush() when you need DB-generated values (like id) BEFORE commit,
# or when you need FK checks within the same transaction.

with Session(engine) as session:
    hero = Hero(name="Ironman", age=45)
    session.add(hero)

    print(f"Before flush — id: {hero.id}")       # None
    session.flush()                               # INSERT runs, still inside transaction
    print(f"After flush  — id: {hero.id}")       # may have id now (DB assigned)

    session.rollback()                            # flush is undone — Ironman NOT saved
    print("After rollback — flush undone, Ironman not persisted")

with Session(engine) as session:
    hero = Hero(name="Ironman", age=45)
    session.add(hero)
    session.commit()                              # permanent save
    print(f"After commit — Ironman saved, id={hero.id}")


# When to refresh()
# Call session.refresh(obj) after commit when you need the latest DB state:
#   - auto-generated id (if not available after flush/commit)
#   - server-side defaults / triggers updated columns
#   - after concurrent updates (rare in simple apps)
#
# Skip refresh() if you already have all fields and nothing DB-generated is needed.

with Session(engine) as session:
    hero = Hero(name="Hulk", age=40)
    session.add(hero)
    session.commit()
    session.refresh(hero)
    print(f"REFRESH — id from DB: {hero.id}")


# Error handling + rollback
# On failure: rollback() clears the uncommitted transaction, then re-raise or handle.

def create_hero_safe(session: Session, name: str, age: int) -> Hero | None:
    try:
        hero = Hero(name=name, age=age)
        session.add(hero)
        session.commit()
        session.refresh(hero)
        return hero
    except IntegrityError:
        session.rollback()
        print(f"ROLLBACK — duplicate name rejected: {name}")
        return None
    except Exception:
        session.rollback()
        raise


with Session(engine) as session:
    ok = create_hero_safe(session, "Black Widow", age=30)
    print(f"Created: {ok.name if ok else None}")

    dup = create_hero_safe(session, "Black Widow", age=31)
    print(f"Duplicate attempt: {dup}")


# Avoiding detached instance issues
# When a Session closes, objects loaded/created in it become "detached".
# Problems after session closes:
#   - lazy-loaded relationships may fail
#   - some attribute access may break if it triggers a DB load
#
# Fixes:
#   1. Read needed data while session is still open
#   2. Return plain dict / response model (HeroPublic) from API, not raw ORM object
#   3. Use a new session if you need to work with the object again

hero_id: int | None = None

with Session(engine) as session:
    hero = session.exec(select(Hero).where(Hero.name == "Spiderman")).one()
    hero_id = hero.id
    name = hero.name
# session closed — hero is detached here

print(f"DETACHED — saved id={hero_id}, name={name} before session closed")

with Session(engine) as session:
    hero = session.get(Hero, hero_id)
    print(f"RE-ATTACH — load again in new session: {hero.name if hero else None}")


# Idempotent create patterns
# "Create if not exists" — safe to call multiple times with same input.
#
# Pattern 1: check first, then insert

def get_or_create_hero(session: Session, name: str, age: int) -> tuple[Hero, bool]:
    existing = session.exec(select(Hero).where(Hero.name == name)).first()
    if existing:
        return existing, False

    hero = Hero(name=name, age=age)
    session.add(hero)
    session.commit()
    session.refresh(hero)
    return hero, True


with Session(engine) as session:
    hero, created = get_or_create_hero(session, "Wolverine", age=35)
    print(f"IDEMPOTENT 1st call — created={created}, {hero.name}")

    hero, created = get_or_create_hero(session, "Wolverine", age=35)
    print(f"IDEMPOTENT 2nd call — created={created}, {hero.name} (same row, no duplicate)")


# Pattern 2: try insert, catch IntegrityError on unique constraint (name is unique)

def create_if_absent(session: Session, name: str, age: int) -> Hero:
    try:
        hero = Hero(name=name, age=age)
        session.add(hero)
        session.commit()
        session.refresh(hero)
        return hero
    except IntegrityError:
        session.rollback()
        return session.exec(select(Hero).where(Hero.name == name)).one()


with Session(engine) as session:
    hero = create_if_absent(session, "Storm", age=32)
    print(f"IDEMPOTENT insert-or-fetch — {hero.name}, id={hero.id}")

    hero2 = create_if_absent(session, "Storm", age=32)
    print(f"IDEMPOTENT retry — same hero id={hero2.id}")


# Summary
#
# One session per request     → with Session(engine) / FastAPI Depends(get_session)
# flush()                     → SQL runs, transaction not finalized yet
# commit()                    → save permanently
# refresh()                   → reload obj from DB after commit (ids, DB defaults)
# rollback()                  → undo on error; always rollback before retrying
# Detached instances          → don't use ORM objects after session closes; re-query or return DTO
# Idempotent create           → get-or-create, or insert + catch IntegrityError

with Session(engine) as session:
    heroes = session.exec(select(Hero)).all()
    print("\nAll heroes:")
    for h in heroes:
        print(f"  id={h.id}, name={h.name}, age={h.age}")
