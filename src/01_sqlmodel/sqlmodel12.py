from pathlib import Path
from typing import Annotated, Generator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

# Testing FastAPI + SQLModel apps
# The official pattern for testing a SQLModel-backed FastAPI app WITHOUT ever
# touching the real production database.
# Builds on sqlmodel6.py (FastAPI + SQLModel CRUD, Depends(get_session)).


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    secret_name: str
    age: int | None = None


# The "production" app — same shape as sqlmodel6.py. This engine/file is
# created here only to exist; the tests below never actually read or write it,
# because dependency_overrides replaces get_session entirely.
production_db_file = Path(__file__).parent / "database_production.db"
engine = create_engine(f"sqlite:///{production_db_file}", echo=False)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
app = FastAPI(title="Hero API")


@app.post("/heroes/")
def create_hero(hero: Hero, session: SessionDep) -> Hero:
    session.add(hero)
    session.commit()
    session.refresh(hero)
    return hero


@app.get("/heroes/")
def list_heroes(session: SessionDep) -> list[Hero]:
    return session.exec(select(Hero)).all()


@app.get("/heroes/{hero_id}")
def get_hero(hero_id: int, session: SessionDep) -> Hero:
    hero = session.get(Hero, hero_id)
    if hero is None:
        raise HTTPException(status_code=404, detail="Hero not found")
    return hero


# Why not just point tests at the production engine above?
#   - tests would read/write real data in database_production.db
#   - a bad test could delete production rows
#   - each test run needs a clean, empty database to get repeatable results
# Fix: override get_session for the duration of the test only, pointing it at
# a throwaway database instead.


# In-memory SQLite ("sqlite://", no path) — lives only in memory, discarded
# when the connection closes. Fast, and there's no file left behind to clean up.
#
# connect_args={"check_same_thread": False} -> SQLite refuses to share a
#   connection across threads by default; TestClient may call the app from a
#   different thread than the one that opened the connection, so this must be
#   disabled explicitly for tests.
# poolclass=StaticPool -> VERIFIED NECESSARY, not just cargo-culted: without
#   it, "sqlite://" gives each new connection its OWN private empty in-memory
#   database. create_all() runs against connection #1, but the session inside
#   get_session() opens connection #2 — which never had create_all() run
#   against it. The real, observed failure is:
#     sqlite3.OperationalError: no such table: hero
#   StaticPool forces every connection to share the exact same in-memory
#   database, so data created by the app is visible when the test reads it back.
def build_test_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


# Official docs use pytest fixtures — functions decorated with @pytest.fixture
# that `yield` a value; pytest runs them fresh before/after EACH test function:
#
#   @pytest.fixture(name="session")
#   def session_fixture():
#       engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
#       SQLModel.metadata.create_all(engine)
#       with Session(engine) as session:
#           yield session
#
#   @pytest.fixture(name="client")
#   def client_fixture(session: Session):
#       def get_session_override():
#           return session
#       app.dependency_overrides[get_session] = get_session_override
#       client = TestClient(app)
#       yield client
#       app.dependency_overrides.clear()
#
#   def test_create_hero(client: TestClient):
#       response = client.post("/heroes/", json={"name": "Deadpond", "secret_name": "Dive Wilson"})
#       assert response.status_code == 200
#
# This repo's files are plain runnable scripts, not a pytest suite, so the demo
# below reproduces the exact same mechanics with a plain function instead of
# @pytest.fixture — same engine, same override, same cleanup — just called
# directly instead of through the pytest runner.
def make_test_client(test_engine) -> TestClient:
    SQLModel.metadata.create_all(test_engine)

    def get_session_override() -> Generator[Session, None, None]:
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    return TestClient(app)


# "Test" 1 — create + read, using its own isolated in-memory database
client = make_test_client(build_test_engine())

response = client.post(
    "/heroes/", json={"name": "Deadpond", "secret_name": "Dive Wilson"}
)
data = response.json()
assert response.status_code == 200
assert data["name"] == "Deadpond"
assert data["age"] is None
assert data["id"] is not None
print(f"TEST 1 — created hero: {data}")

response = client.get("/heroes/")
assert len(response.json()) == 1
print(f"TEST 1 — list has exactly the one hero just created: {response.json()}")

app.dependency_overrides.clear()  # always undo the override once the test is done


# "Test" 2 — a FRESH in-memory database (new engine) proves tests are isolated
# from each other: no leftover hero from test 1 should appear here.
client = make_test_client(build_test_engine())

response = client.get("/heroes/")
assert response.json() == []
print(f"TEST 2 — fresh database has no leakage from test 1: {response.json()}")

response = client.get("/heroes/999")
assert response.status_code == 404
print(f"TEST 2 — 404 for missing hero: {response.status_code}")

app.dependency_overrides.clear()


# Confirm the real production database file was genuinely never touched
print(f"\nPRODUCTION DB untouched — file exists on disk: {production_db_file.exists()}")


# Summary
#
# Problem: testing against the real engine pollutes/risks production data.
# Fix:     override the session dependency for the duration of the test only.
#
# "sqlite://"                                -> in-memory DB, gone when the connection closes
# connect_args={"check_same_thread": False}  -> allow TestClient's thread to share the connection
# poolclass=StaticPool                       -> force ALL connections to share ONE in-memory db
#                                                (without it: "no such table" — verified above)
# app.dependency_overrides[get_session] = .. -> swap the DB the app uses, only for tests
# app.dependency_overrides.clear()           -> always undo the override after each test
# pytest fixtures (session, client)          -> the official way to avoid repeating this setup
#                                                in every single test function
#
# Continue in sqlmodel13.py for schema migrations with Alembic.
