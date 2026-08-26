from pathlib import Path
from typing import Optional

from sqlmodel import Field, Relationship, Session, SQLModel, col, create_engine, select


# Many-to-many + Joins
# Many-to-many: heroes ↔ tags via a link/junction table.
# Joins: query across two tables in one select (hero + team in one query).
#
# Builds on sqlmodel5.py (one-to-many) and sqlmodel3–4.py (select).

db_file = Path(__file__).parent / "database_advanced.db"
db_file.unlink(missing_ok=True)
engine = create_engine(f"sqlite:///{db_file}", echo=False)


# Many-to-many — needs a link table (association table) with FKs to both sides.

class HeroTagLink(SQLModel, table=True):
    hero_id: int | None = Field(default=None, foreign_key="hero.id", primary_key=True)
    tag_id: int | None = Field(default=None, foreign_key="tag.id", primary_key=True)


class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    heroes: list["Hero"] = Relationship(back_populates="team")


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    heroes: list["Hero"] = Relationship(
        back_populates="tags",
        link_model=HeroTagLink,
    )


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    team_id: int | None = Field(default=None, foreign_key="team.id")
    team: Optional[Team] = Relationship(back_populates="heroes")
    tags: list[Tag] = Relationship(
        back_populates="heroes",
        link_model=HeroTagLink,
    )


SQLModel.metadata.create_all(engine)


with Session(engine) as session:
    avengers = Team(name="Avengers")
    xmen = Team(name="X-Men")
    strong = Tag(name="strong")
    flying = Tag(name="flying")
    session.add(avengers)
    session.add(xmen)
    session.add(strong)
    session.add(flying)
    session.commit()
    session.refresh(avengers)
    session.refresh(strong)
    session.refresh(flying)

    spiderman = Hero(name="Spiderman", team_id=avengers.id, tags=[strong])
    ironman = Hero(name="Ironman", team_id=avengers.id, tags=[strong, flying])
    session.add(spiderman)
    session.add(ironman)
    session.commit()
    session.refresh(spiderman)
    session.refresh(ironman)

    print("MANY-TO-MANY — Spiderman tags:", [t.name for t in spiderman.tags])
    print("MANY-TO-MANY — 'strong' tag heroes:", [h.name for h in strong.heroes])


# Add tag to existing hero — append to relationship list and commit.

with Session(engine) as session:
    hero = session.exec(select(Hero).where(Hero.name == "Spiderman")).one()
    flying = session.exec(select(Tag).where(Tag.name == "flying")).one()
    hero.tags.append(flying)
    session.add(hero)
    session.commit()
    session.refresh(hero)
    print("MANY-TO-MANY — after add tag:", [t.name for t in hero.tags])


# Joins — fetch columns from two tables in one query.
# select(Hero, Team).join(Team) → returns tuples (Hero, Team).

with Session(engine) as session:
    results = session.exec(
        select(Hero, Team)
        .join(Team)
        .where(Team.name == "Avengers")
    ).all()

    print("JOIN — heroes in Avengers:")
    for hero, team in results:
        print(f"  {hero.name} → team={team.name}")


# Join + filter on both tables

with Session(engine) as session:
    results = session.exec(
        select(Hero, Team)
        .join(Team)
        .where(Team.name == "Avengers")
        .where(Hero.name.contains("man"))
    ).all()

    print("JOIN + filter — names containing 'man':")
    for hero, team in results:
        print(f"  {hero.name} ({team.name})")


# Join heroes with tags through link table (many-to-many join)

with Session(engine) as session:
    results = session.exec(
        select(Hero, Tag)
        .join(HeroTagLink, HeroTagLink.hero_id == Hero.id)
        .join(Tag, HeroTagLink.tag_id == Tag.id)
        .where(Tag.name == "flying")
    ).all()

    print("JOIN m2m — heroes with 'flying' tag:")
    for hero, tag in results:
        print(f"  {hero.name} has tag {tag.name}")


# Alternative: load via Relationship (simpler for small data; join better for large/filtered queries)
with Session(engine) as session:
    heroes = session.exec(select(Hero)).all()
    print("RELATIONSHIP load — tags per hero:")
    for hero in heroes:
        print(f"  {hero.name}: {[t.name for t in hero.tags]}")


# Summary
#
# Many-to-many:
#   link_model=HeroTagLink on both Relationship() sides
#   link table has composite PK (hero_id, tag_id) + FKs to both tables
#
# Joins:
#   select(A, B).join(B).where(...)  → SQL JOIN, returns (A, B) tuples
#   use joins for filtered lists across tables
#   use Relationship for convenient object navigation (watch N+1 in APIs)
