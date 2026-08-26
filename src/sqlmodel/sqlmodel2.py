from datetime import datetime
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine, select


# CRUD — Create, Read, Update, Delete
# Daily database operations through a Session.
# Builds on sqlmodel1.py (engine, session, add, commit, refresh).

db_file = Path(__file__).parent / "database_crud.db"
engine = create_engine(f"sqlite:///{db_file}", echo=False)


# Auto fields — DB/app generates values automatically.
# id           → auto-increment primary key (None before insert, int after commit+refresh)
# created_at   → default_factory sets timestamp when object is created in Python

class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    age: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


SQLModel.metadata.create_all(engine)


# Create — instantiate model → add → commit → refresh
with Session(engine) as session:
    hero = Hero(name="Spiderman", age=16)
    print(f"CREATE — before save: id={hero.id}, created_at={hero.created_at}")

    session.add(hero)
    session.commit()
    session.refresh(hero)

    print(f"CREATE — after save:  id={hero.id}, name={hero.name}, created_at={hero.created_at}")
    hero_id = hero.id   # save id for later examples


# Read one — session.get(Model, id) fetches a single row by primary key.
with Session(engine) as session:
    found = session.get(Hero, hero_id)
    print(f"READ ONE — {found}")

    missing = session.get(Hero, 99999)
    print(f"READ ONE — not found: {missing}")   # None — no row with that id


# Read many — select(Model) returns all rows (use .where() for filters — see next file).
with Session(engine) as session:
    session.add(Hero(name="Ironman", age=45))
    session.add(Hero(name="Hulk", age=40))
    session.commit()

    heroes = session.exec(select(Hero)).all()
    print("READ MANY — all heroes:")
    for h in heroes:
        print(f"  id={h.id}, name={h.name}, age={h.age}")


# Update — fetch → mutate fields → add → commit
with Session(engine) as session:
    hero = session.get(Hero, hero_id)

    if hero is None:
        print("UPDATE — hero not found")
    else:
        hero.age = 17
        hero.name = "Spiderman (Updated)"
        session.add(hero)      # stage the change (add marks dirty instance for commit)
        session.commit()
        session.refresh(hero)
        print(f"UPDATE — {hero.name}, age={hero.age}")


# Delete — session.delete(obj) → commit
with Session(engine) as session:
    hero = session.get(Hero, hero_id)

    if hero is None:
        print("DELETE — hero not found")
    else:
        session.delete(hero)
        session.commit()
        print(f"DELETE — removed hero id={hero_id}")

    # verify deletion
    gone = session.get(Hero, hero_id)
    print(f"DELETE — verify gone: {gone}")   # None


# Handling None when record not found
# session.get() returns None if the row does not exist — always check before use.

def get_hero_or_none(session: Session, hero_id: int) -> Hero | None:
    return session.get(Hero, hero_id)


with Session(engine) as session:
    hero = get_hero_or_none(session, 99999)

    if hero is None:
        print("NOT FOUND — no hero with that id")
    else:
        print(f"FOUND — {hero.name}")

    # common pattern in APIs:
    # if hero is None: raise HTTPException(status_code=404, detail="Hero not found")


# CRUD summary
#
# CREATE:  obj = Hero(...) → session.add(obj) → session.commit() → session.refresh(obj)
# READ:    session.get(Hero, id)              → one row (or None)
#          session.exec(select(Hero)).all()   → many rows
# UPDATE:  hero = session.get(...) → hero.field = new → session.add(hero) → session.commit()
# DELETE:  session.delete(hero) → session.commit()
#
# Auto fields:
#   id         → assigned by DB after commit+refresh
#   created_at → set by default_factory when Python object is created

with Session(engine) as session:
    remaining = session.exec(select(Hero)).all()
    print("Remaining heroes after delete:")
    for h in remaining:
        print(f"  id={h.id}, name={h.name}, age={h.age}, created_at={h.created_at}")
