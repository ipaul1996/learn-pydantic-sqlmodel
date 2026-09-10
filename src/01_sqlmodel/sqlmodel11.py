from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from sqlmodel import Field, Session, SQLModel, create_engine, select

# Decimal Numbers & UUID Primary Keys
# Two focused "Advanced" SQLModel topics for real production schemas.
# Builds on sqlmodel8.py (Field() options).

db_file = Path(__file__).parent / "database_advanced_types.db"
db_file.unlink(missing_ok=True)
engine = create_engine(f"sqlite:///{db_file}", echo=False)


# Decimal — money/currency needs EXACT precision, floats do not give that.
# float uses binary fractions internally, so 1.1 + 2.2 != 3.3 exactly:
print("FLOAT ROUNDING ERROR —", 1.1 + 2.2)  # 3.3000000000000003, not 3.3

# Decimal(max_digits=..., decimal_places=...) on Field() fixes this: Pydantic
# validates the precision, and SQLAlchemy maps it to a DECIMAL/NUMERIC column.
# max_digits   → total digits allowed (both sides of the decimal point combined)
# decimal_places → how many of those digits are after the decimal point


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    money: Decimal = Field(default=0, max_digits=5, decimal_places=3)


SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    # plain floats are accepted — Pydantic coerces them to Decimal on the way in
    h1 = Hero(name="Deadpond", money=1.1)
    h2 = Hero(name="Rusty-Man", money=2.2)
    session.add(h1)
    session.add(h2)
    session.commit()
    session.refresh(h1)
    session.refresh(h2)
    print(
        f"DECIMAL — stored types: {type(h1.money).__name__}, values: {h1.money}, {h2.money}"
    )

# Verified on SQLite specifically (the docs warn SQLite has no native DECIMAL
# column type and falls back to NUMERIC) — SQLAlchemy's Decimal adapter still
# round-trips the value correctly, even after a fresh query in a NEW session:
with Session(engine) as session:
    fresh1 = session.exec(select(Hero).where(Hero.name == "Deadpond")).one()
    fresh2 = session.exec(select(Hero).where(Hero.name == "Rusty-Man")).one()
    print(
        f"DECIMAL — sum after round-trip through SQLite: {fresh1.money + fresh2.money}"
    )  # 3.300, not 3.3000000000000003

# Values that break max_digits/decimal_places raise a normal ValidationError,
# same as any other Field() constraint (see model2.py):
# Hero(name="Too Precise", money=1.2345)     # 4 decimal places > decimal_places=3
# Hero(name="Too Many Digits", money=123.45)  # 5 digits total but only 2 left for
#                                              # the integer part (5 - 3 = 2)


# UUID primary keys — an alternative to auto-increment int ids.
# uuid.UUID field + default_factory=uuid.uuid4 generates the id in Python,
# BEFORE the row is even sent to the database (unlike an auto-increment id,
# which is None until after commit+refresh).
class Order(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    item: str


SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    order = Order(item="Web Shooters")
    print(
        f"\nUUID — id already set before save: {order.id} ({type(order.id).__name__})"
    )

    session.add(order)
    session.commit()
    session.refresh(order)
    print(f"UUID — same id after save: {order.id}")
    order_id = order.id

# SQLite has no native UUID column type either — it stores the value as a
# string under the hood — but SQLAlchemy's Uuid type converts transparently,
# so lookups work with a real uuid.UUID object, not a string:
with Session(engine) as session:
    found = session.get(Order, order_id)
    print(
        f"UUID — session.get() with a uuid.UUID object: {found.item if found else None}"
    )

    found2 = session.exec(select(Order).where(Order.id == order_id)).one()
    print(f"UUID — select().where(id == uuid_obj): {found2.item}")


# Why choose UUID over auto-increment int:
#   - can be generated client-side, before the row is ever saved (no round trip needed)
#   - safe to expose in public URLs — sequential ints leak "how many rows exist"
#   - works well for merging data from multiple databases (near-zero collision risk)
# Trade-offs:
#   - 16 bytes vs ~4 bytes for an int — more storage, slightly slower joins on some DBs
#   - not sortable by creation order the way an auto-increment id naturally is


# Summary
#
# Decimal + Field(max_digits=, decimal_places=) -> exact precision for money/currency,
#                                                    avoids float rounding errors
# SQLite has no native DECIMAL/UUID column type -> SQLAlchemy still round-trips both
#                                                    correctly (verified, not just assumed)
# UUID field + Field(default_factory=uuid4, primary_key=True) -> id generated in
#                                                    Python before the row is saved
# session.get(Model, uuid_obj) / select().where(Model.id == uuid_obj) -> work directly
#                                                    with real uuid.UUID objects
#
# Continue in sqlmodel12.py for testing FastAPI + SQLModel apps (in-memory DB,
# dependency overrides, pytest-style fixtures).
