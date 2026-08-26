from pathlib import Path

from sqlmodel import Field, Session, SQLModel, col, create_engine, select


# Queries (select) — Part 1: basics
# How to read data with select() + session.exec().
# Uses database_queries.db — shared with sqlmodel4.py.

db_file = Path(__file__).parent / "database_queries.db"
engine = create_engine(f"sqlite:///{db_file}", echo=False)


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    age: int
    team: str


SQLModel.metadata.create_all(engine)


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


# select(Model) — builds a query for a table. Does NOT hit the DB until session.exec().
statement = select(Hero)
print(f"select(Hero) → {statement}")


# session.exec(select(...)) — runs the query, returns a Result object.
with Session(engine) as session:
    result = session.exec(select(Hero))


# .all() — fetch all matching rows as a list.
with Session(engine) as session:
    all_heroes = session.exec(select(Hero)).all()
    print(f".all() — {len(all_heroes)} heroes total")


# .first() — first row or None (does not error if empty).
with Session(engine) as session:
    first = session.exec(select(Hero)).first()
    print(f".first() — {first.name if first else None}")


# .one() — exactly one row required; raises error if 0 or more than 1.
with Session(engine) as session:
    one = session.exec(select(Hero).where(Hero.name == "Hulk")).one()
    print(f".one() — {one.name}")

    # session.exec(select(Hero)).one()              # Error — multiple rows
    # session.exec(select(Hero).where(Hero.name == "Nobody")).one()  # Error — zero rows


# .one_or_none() — one row or None; raises error only if more than one match.
with Session(engine) as session:
    found = session.exec(select(Hero).where(Hero.name == "Ironman")).one_or_none()
    missing = session.exec(select(Hero).where(Hero.name == "Nobody")).one_or_none()
    print(f".one_or_none() — found: {found.name}, missing: {missing}")


# where() filters — narrow results. Chain multiple where() for AND logic.
with Session(engine) as session:
    avengers = session.exec(
        select(Hero).where(Hero.team == "Avengers")
    ).all()
    print(f"where team — {[h.name for h in avengers]}")


# Comparison operators — ==, !=, >, <, >=, <=
with Session(engine) as session:
    adults = session.exec(select(Hero).where(Hero.age >= 35)).all()
    print(f"age >= 35 — {[h.name for h in adults]}")

    not_avengers = session.exec(select(Hero).where(Hero.team != "Avengers")).all()
    print(f"team != Avengers — {[h.name for h in not_avengers]}")

    young = session.exec(select(Hero).where(Hero.age < 20)).all()
    print(f"age < 20 — {[h.name for h in young]}")


# in_ — match any value in a list. Use col() for the column.
with Session(engine) as session:
    selected_teams = session.exec(
        select(Hero).where(col(Hero.team).in_(["Avengers", "X-Men"]))
    ).all()
    print(f"in_ teams — {[h.name for h in selected_teams]}")


# Filtering by multiple fields — chain .where() (implicit AND).
with Session(engine) as session:
    filtered = session.exec(
        select(Hero)
        .where(Hero.team == "Avengers")
        .where(Hero.age >= 30)
    ).all()
    print(f"multi-field — {[h.name for h in filtered]}")

    # same as above using single where with multiple conditions:
    filtered2 = session.exec(
        select(Hero).where(Hero.team == "Avengers", Hero.age >= 30)
    ).all()
    print(f"multi-field (comma) — {[h.name for h in filtered2]}")


# Summary — Part 1
# select(Hero)                          → build query
# session.exec(...).all()               → list of all rows
# session.exec(...).first()             → first row or None
# session.exec(...).one()               → exactly one row (or error)
# session.exec(...).one_or_none()       → one row, None, or error if many
# .where(Hero.field == value)           → filter rows
# col(Hero.field).in_([...])            → match list of values

print("\n→ Continue with sqlmodel4.py for and_/or_, order_by, pagination, count, like")
