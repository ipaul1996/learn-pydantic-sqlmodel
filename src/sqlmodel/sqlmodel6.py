from pathlib import Path
from typing import Annotated, Generator

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, create_engine, select


# FastAPI + SQLModel
# Connect HTTP endpoints to database operations.
# Builds on sqlmodel1–5 (engine, session, CRUD, select, relationships).
#
# Run the API server:
#   uvicorn sqlmodel6:app --reload --app-dir src/sqlmodel
#
# Or run this file to demo all endpoints with TestClient:
#   python src/sqlmodel/sqlmodel6.py
#
# Config/env + sync vs async session: sqlmodel9.py


db_file = Path(__file__).parent / "database_fastapi.db"
engine = create_engine(f"sqlite:///{db_file}", echo=False)


# Request body vs DB model separation
# Use separate models for API input/output vs the DB table.
#
# Hero          → table=True  (DB table — may have extra/internal fields)
# HeroCreate    → table=False (POST body — no id, client cannot set id)
# HeroUpdate    → table=False (PATCH body — all fields optional)
# HeroPublic    → table=False (response — hide internal fields like secret_name)

class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    age: int
    secret_name: str | None = None   # stored in DB, hidden from API responses


class HeroCreate(SQLModel):
    name: str
    age: int
    secret_name: str | None = None


class HeroUpdate(SQLModel):
    name: str | None = None
    age: int | None = None
    secret_name: str | None = None


class HeroPublic(SQLModel):
    id: int
    name: str
    age: int


SQLModel.metadata.create_all(engine)


# Dependency injection for Session
# FastAPI calls get_session() per request, yields a Session, closes it after response.
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI(title="Hero API")


# Create endpoint → DB insert
# HeroCreate = request body, HeroPublic = response_model (hides secret_name)
@app.post("/heroes/", response_model=HeroPublic)
def create_hero(hero_in: HeroCreate, session: SessionDep) -> Hero:
    hero = Hero.model_validate(hero_in)
    session.add(hero)
    session.commit()
    session.refresh(hero)
    return hero


# Read many → select + return
# Query params + filtering — optional ?min_age=30&name=Spider
@app.get("/heroes/", response_model=list[HeroPublic])
def list_heroes(
    session: SessionDep,
    min_age: int | None = Query(default=None, ge=0),
    name: str | None = Query(default=None),
) -> list[Hero]:
    statement = select(Hero)

    if min_age is not None:
        statement = statement.where(Hero.age >= min_age)
    if name is not None:
        statement = statement.where(Hero.name.contains(name))

    return session.exec(statement).all()


# Read one — path param + DB lookup + 404 when not found
@app.get("/heroes/{hero_id}", response_model=HeroPublic)
def get_hero(hero_id: int, session: SessionDep) -> Hero:
    hero = session.get(Hero, hero_id)

    if hero is None:
        raise HTTPException(status_code=404, detail="Hero not found")

    return hero


# Update endpoint — fetch → apply partial update → commit
@app.patch("/heroes/{hero_id}", response_model=HeroPublic)
def update_hero(
    hero_id: int,
    hero_in: HeroUpdate,
    session: SessionDep,
) -> Hero:
    hero = session.get(Hero, hero_id)

    if hero is None:
        raise HTTPException(status_code=404, detail="Hero not found")

    update_data = hero_in.model_dump(exclude_unset=True)
    hero.sqlmodel_update(update_data)

    session.add(hero)
    session.commit()
    session.refresh(hero)
    return hero


# Delete endpoint — session.delete → commit + 404 when not found
@app.delete("/heroes/{hero_id}")
def delete_hero(hero_id: int, session: SessionDep) -> dict[str, str]:
    hero = session.get(Hero, hero_id)

    if hero is None:
        raise HTTPException(status_code=404, detail="Hero not found")

    session.delete(hero)
    session.commit()
    return {"detail": f"Hero {hero_id} deleted"}


# Demo — run all endpoints locally without starting uvicorn
if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)

    print("POST /heroes/ — create")
    r = client.post("/heroes/", json={"name": "Spiderman", "age": 16, "secret_name": "Peter Parker"})
    print(r.status_code, r.json())
    hero_id = r.json()["id"]

    print("\nGET /heroes/ — list all")
    print(client.get("/heroes/").json())

    print("\nGET /heroes/?min_age=10&name=Spider — query param filtering")
    print(client.get("/heroes/", params={"min_age": 10, "name": "Spider"}).json())

    print(f"\nGET /heroes/{hero_id} — read one")
    print(client.get(f"/heroes/{hero_id}").json())

    print(f"\nPATCH /heroes/{hero_id} — update")
    print(client.patch(f"/heroes/{hero_id}", json={"age": 17}).json())

    print("\nGET /heroes/999 — 404 not found")
    print(client.get("/heroes/999").status_code, client.get("/heroes/999").json())

    print(f"\nDELETE /heroes/{hero_id} — delete")
    print(client.delete(f"/heroes/{hero_id}").json())

    print(f"\nGET /heroes/{hero_id} — 404 after delete")
    print(client.get(f"/heroes/{hero_id}").status_code, client.get(f"/heroes/{hero_id}").json())


# Summary
#
# response_model=HeroPublic     → controls JSON output shape (hides secret_name)
# SessionDep = Depends(get_session) → inject DB session per request
# HeroCreate / HeroUpdate       → request body models (not DB tables)
# Hero (table=True)             → DB model used internally
# session.get(Hero, id)         → path param lookup
# HTTPException(404)            → when record not found
# select(Hero).where(...)       → query param filtering
# POST → add/commit/refresh     → create
# PATCH → sqlmodel_update       → partial update
# DELETE → session.delete       → remove
