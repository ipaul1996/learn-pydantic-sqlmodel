from pathlib import Path
from typing import Optional

from sqlmodel import Field, Relationship, Session, SQLModel, col, create_engine, select

# Relationships (core)
# Connect tables via foreign keys + Relationship().
# Example: one Team → many Heroes (one-to-many), each Hero → one Team (many-to-one).
#
# Avoiding circular import issues:
#   - Put related models in the same file (simplest for learning)
#   - Or use quoted forward refs: team: Optional["Team"] = Relationship(...)
#   - Or split models but import only under if TYPE_CHECKING for type hints

db_file = Path(__file__).parent / "database_relationships.db"
db_file.unlink(
    missing_ok=True
)  # reset for repeatable runs (same pattern as sqlmodel7.py/8.py)
engine = create_engine(f"sqlite:///{db_file}", echo=False)


# Many-to-one side — Hero belongs to one Team.
# team_id is the foreign key column stored in the hero table.
# team is the Python Relationship attribute (not a DB column).


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    team_id: int | None = Field(default=None, foreign_key="team.id")
    team: Optional["Team"] = Relationship(back_populates="heroes")


# One-to-many side — Team has many Heroes.
# heroes is a list Relationship; no extra column on team table.


class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    heroes: list[Hero] = Relationship(
        back_populates="team",
        cascade_delete=True,  # deleting a team also deletes its heroes
    )


# back_populates — links both sides of the relationship.
# Team.heroes ↔ Hero.team must reference each other's attribute name.


SQLModel.metadata.create_all(engine)


# Create parent + child together — add nested heroes when creating a team.
with Session(engine) as session:
    avengers = Team(
        name="Avengers",
        heroes=[
            Hero(name="Spiderman"),
            Hero(name="Ironman"),
        ],
    )
    session.add(avengers)
    session.commit()
    session.refresh(avengers)
    print(
        f"CREATE together — team: {avengers.name}, heroes: {[h.name for h in avengers.heroes]}"
    )


# Optional relationship — hero without a team (team_id=None).
with Session(engine) as session:
    loner = Hero(name="Deadpool")
    session.add(loner)
    session.commit()
    session.refresh(loner)
    print(f"OPTIONAL — hero: {loner.name}, team: {loner.team}")  # team is None


# Link existing hero to existing team via foreign key.
with Session(engine) as session:
    loner = session.exec(select(Hero).where(Hero.name == "Deadpool")).one()
    xmen = Team(name="X-Men", heroes=[])
    session.add(xmen)
    session.commit()
    session.refresh(xmen)

    loner.team_id = xmen.id
    session.add(loner)
    session.commit()
    session.refresh(loner)
    print(f"LINK — {loner.name} joined {loner.team.name}")


# Loading related objects — access Relationship attributes to load linked rows.
with Session(engine) as session:
    hero = session.exec(select(Hero).where(Hero.name == "Spiderman")).one()

    # many-to-one: hero → team
    print(f"LOAD — {hero.name} is in team: {hero.team.name}")

    team = session.exec(select(Team).where(Team.name == "Avengers")).one()

    # one-to-many: team → heroes
    print(f"LOAD — {team.name} members: {[h.name for h in team.heroes]}")


# Read one with relationship data — session.get() + access .heroes / .team
with Session(engine) as session:
    team = session.get(Team, 1)
    if team:
        print(f"GET — team id=1: {team.name}, heroes: {[h.name for h in team.heroes]}")


# Cascade delete — cascade_delete=True on Team.heroes.
# Deleting the parent team removes its child heroes from the DB.
with Session(engine) as session:
    team = session.exec(select(Team).where(Team.name == "Avengers")).one()
    hero_names = [h.name for h in team.heroes]
    print(f"CASCADE — deleting team {team.name} (heroes: {hero_names})")

    session.delete(team)
    session.commit()

    remaining = session.exec(select(Hero).where(col(Hero.name).in_(hero_names))).all()
    print(f"CASCADE — heroes after team delete: {remaining}")  # [] — heroes removed too


# Without cascade_delete, deleting a team would leave heroes with dangling team_id.
# cascade_delete=True maps to SQLAlchemy cascade="all, delete-orphan".


# Foreign key recap
# Hero.team_id  → actual column in hero table (stores the id of the parent team)
# Hero.team     → Relationship shortcut to load the Team object
# Team.heroes   → Relationship list to load all Hero rows with matching team_id


# Summary
#
# One-to-many:  Team.heroes: list[Hero] = Relationship(back_populates="team")
# Many-to-one:  Hero.team_id + Hero.team = Relationship(back_populates="heroes")
# back_populates → must match the name on the other side
# Optional:      team_id: int | None = None  and  team: Optional["Team"]
# Create together: Team(name="...", heroes=[Hero(...), Hero(...)])
# Load:          hero.team  or  team.heroes
# Cascade:       cascade_delete=True on the one-to-many side (parent owns children)
# Circular imports → same file, or quoted "Team"/"Hero", or TYPE_CHECKING imports
