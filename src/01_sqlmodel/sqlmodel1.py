from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine, select


# Database URL / connection string
# Tells SQLAlchemy which database to connect to and how.
#
# Common formats:
#   sqlite:///./database.db          → local SQLite file
#   sqlite:///:memory:               → in-memory SQLite (data lost when app stops)
#   postgresql://user:pass@host/db   → PostgreSQL
#   mysql://user:pass@host/db        → MySQL
#
# Format: dialect+driver://username:password@host:port/database

db_file = Path(__file__).parent / "database.db"
sqlite_url = f"sqlite:///{db_file}"
print(f"Database URL: {sqlite_url}")


# create_engine() — creates the database engine (connection pool / DB gateway).
# echo=True prints SQL statements to the console (useful while learning).
engine = create_engine(sqlite_url, echo=True)


# Define a table model — table=True means this maps to a real SQL table.
class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    age: int


# SQLModel.metadata.create_all(engine)
# Reads all SQLModel classes with table=True and creates their tables in the DB.
# Safe to call multiple times — only creates missing tables, does not drop data.
SQLModel.metadata.create_all(engine)


# Session basics — Session(engine) opens a conversation with the database.
# All inserts/updates/deletes go through a session, then commit() saves them.

session = Session(engine)

# session.add()    → stage a new/updated object (not saved yet)
# session.commit() → write staged changes to the database
# session.refresh() → reload object from DB (e.g. get auto-generated id)

hero = Hero(name="Spiderman", age=16)
print(f"Before save — id: {hero.id}")   # None — DB has not assigned id yet

session.add(hero)
session.commit()
session.refresh(hero)

print(f"After save — id: {hero.id}, name: {hero.name}")
session.close()


# session.rollback() — undo uncommitted changes in the current transaction.
with Session(engine) as session:
    hero2 = Hero(name="Ironman", age=45)
    session.add(hero2)
    print(f"Before rollback — staged hero: {hero2.name}")

    session.rollback()   # cancels the pending insert — hero2 is NOT saved to DB
    print("Rollback done — uncommitted changes discarded")

    hero3 = Hero(name="Hulk", age=40)
    session.add(hero3)
    session.commit()
    session.refresh(hero3)
    print(f"After commit — saved hero: {hero3.name}, id: {hero3.id}")


# Context manager pattern — preferred way to use Session.
# with Session(engine) as session:
#     ... do work ...
# Session is automatically closed when the block exits (even on error).

with Session(engine) as session:
    hero4 = Hero(name="Black Widow", age=30)
    session.add(hero4)
    session.commit()
    session.refresh(hero4)
    print(f"Context manager save — {hero4.name}, id: {hero4.id}")
# session is closed here automatically


# Session lifecycle
# 1. Create:  session = Session(engine)   or   with Session(engine) as session
# 2. Work:     session.add() / query / update / session.delete()
# 3. Save:     session.commit()           (or session.rollback() to cancel)
# 4. Refresh:  session.refresh(obj)       (reload from DB after commit)
# 5. Close:    session.close()            (automatic with `with` block)
#
# Rule of thumb: one session per unit of work (e.g. one API request).
# Always commit() after changes, or rollback() on error.

with Session(engine) as session:
    saved_heroes = session.exec(select(Hero)).all()
    print("All heroes in DB:")
    for h in saved_heroes:
        print(f"  id={h.id}, name={h.name}, age={h.age}")
