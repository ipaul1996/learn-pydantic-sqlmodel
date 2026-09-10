from pathlib import Path

from sqlalchemy import and_, func, or_
from sqlmodel import Field, Session, SQLModel, col, create_engine, select


# Queries (select) — Part 2: and/or, sorting, pagination, count, text search
# Uses same database_queries.db as sqlmodel3.py — run sqlmodel3.py first to seed data.

db_file = Path(__file__).parent / "database_queries.db"
engine = create_engine(f"sqlite:///{db_file}", echo=False)


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    age: int
    team: str


def seed_heroes(session: Session) -> None:
    if session.exec(select(Hero)).first():
        return

    heroes = [
        Hero(name="Spiderman", age=16, team="Avengers"),
        Hero(name="Ironman", age=45, team="Avengers"),
        Hero(name="Hulk", age=40, team="Avengers"),
        Hero(name="Black Widow", age=30, team="Avengers"),
        Hero(name="Wolverine", age=35, team="X-Men"),
        Hero(name="Storm", age=32, team="X-Men"),
        Hero(name="Batman", age=38, team="Justice League"),
    ]
    for hero in heroes:
        session.add(hero)
    session.commit()


with Session(engine) as session:
    seed_heroes(session)


# and_ — combine conditions; ALL must be true.
with Session(engine) as session:
    and_result = session.exec(
        select(Hero).where(
            and_(Hero.team == "Avengers", Hero.age >= 35)
        )
    ).all()
    print(f"and_ — {[h.name for h in and_result]}")

    # chaining .where() is also AND (shown in sqlmodel3.py)


# or_ — at least ONE condition must be true.
with Session(engine) as session:
    or_result = session.exec(
        select(Hero).where(
            or_(Hero.name == "Hulk", Hero.name == "Batman")
        )
    ).all()
    print(f"or_ — {[h.name for h in or_result]}")

    or_teams = session.exec(
        select(Hero).where(
            or_(Hero.team == "X-Men", Hero.team == "Justice League")
        )
    ).all()
    print(f"or_ teams — {[h.name for h in or_teams]}")


# order_by — sort results. Pass desc(Hero.age) for descending (from sqlalchemy import desc).
from sqlalchemy import desc

with Session(engine) as session:
    by_age = session.exec(
        select(Hero).order_by(Hero.age)
    ).all()
    print(f"order_by age asc — {[(h.name, h.age) for h in by_age]}")

    by_age_desc = session.exec(
        select(Hero).order_by(desc(Hero.age))
    ).all()
    print(f"order_by age desc — {[(h.name, h.age) for h in by_age_desc]}")

    by_name = session.exec(
        select(Hero).order_by(Hero.name)
    ).all()
    print(f"order_by name — {[h.name for h in by_name]}")


# limit / offset — pagination.
# limit  → max rows to return
# offset → skip first N rows
with Session(engine) as session:
    page_size = 3
    page_number = 1   # 1-based page number

    page1 = session.exec(
        select(Hero)
        .order_by(Hero.id)
        .offset((page_number - 1) * page_size)
        .limit(page_size)
    ).all()
    print(f"page 1 — {[h.name for h in page1]}")

    page_number = 2
    page2 = session.exec(
        select(Hero)
        .order_by(Hero.id)
        .offset((page_number - 1) * page_size)
        .limit(page_size)
    ).all()
    print(f"page 2 — {[h.name for h in page2]}")


# Count queries — how many rows match (without fetching all data).
with Session(engine) as session:
    total = session.exec(select(func.count()).select_from(Hero)).one()
    print(f"count all — {total}")

    avenger_count = session.exec(
        select(func.count())
        .select_from(Hero)
        .where(Hero.team == "Avengers")
    ).one()
    print(f"count Avengers — {avenger_count}")

    # alternative: len(session.exec(select(Hero)).all()) — works but loads all rows (avoid for large tables)


# like / text search — pattern matching (% = any characters).
with Session(engine) as session:
    ends_with_man = session.exec(
        select(Hero).where(col(Hero.name).like("%man"))
    ).all()
    print(f"like '%man' — {[h.name for h in ends_with_man]}")

    starts_with_s = session.exec(
        select(Hero).where(col(Hero.name).like("S%"))
    ).all()
    print(f"like 'S%' — {[h.name for h in starts_with_s]}")

    contains_ack = session.exec(
        select(Hero).where(col(Hero.name).like("%ack%"))
    ).all()
    print(f"like '%ack%' — {[h.name for h in contains_ack]}")

    # case-insensitive (SQLite): use .ilike() instead of .like()
    ilike_result = session.exec(
        select(Hero).where(col(Hero.name).ilike("%iron%"))
    ).all()
    print(f"ilike '%iron%' — {[h.name for h in ilike_result]}")


# Summary — Part 2
# and_(cond1, cond2)              → both must match
# or_(cond1, cond2)               → either can match
# .order_by(Hero.field)           → sort ascending
# .order_by(desc(Hero.field))    → sort descending
# .limit(n).offset(m)            → pagination
# func.count() + select_from()   → count rows
# col(Hero.name).like("%text%")  → text pattern search
