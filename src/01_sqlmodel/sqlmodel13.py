import sqlite3
import subprocess
import sys
from pathlib import Path

# Schema Migrations with Alembic
# SQLModel's own docs don't have a full migrations tutorial yet — their Advanced
# User Guide literally lists "How to run migrations" as future work. Alembic
# (alembic.sqlalchemy.org) is the standard, officially documented migration tool
# for SQLAlchemy/SQLModel, and real production apps need it:
#
# SQLModel.metadata.create_all() — used everywhere else in this folder — only
# CREATES tables that don't exist yet. It never alters a table that's already
# there, so it can't handle "add a column", "rename a column", "change a type",
# etc. on a database that already has real data in it.
#
# This file drives the REAL `alembic` CLI (installed in this repo's venv)
# against a real, disposable project in migrations_demo/ (alembic.ini,
# alembic/env.py, alembic/versions/) — the output below is genuine Alembic
# output, not a simulation, so re-running this file re-proves it still works.

demo_dir = Path(__file__).resolve().parent / "migrations_demo"
models_file = demo_dir / "models.py"
versions_dir = demo_dir / "alembic" / "versions"
demo_db = demo_dir / "demo.db"
alembic_bin = Path(sys.executable).parent / "alembic"  # same venv's `alembic` CLI

MODEL_V1 = """from sqlmodel import Field, SQLModel


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
"""

MODEL_V2 = """from sqlmodel import Field, SQLModel


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    secret_name: str | None = None
"""


def run_alembic(*args: str) -> str:
    result = subprocess.run(
        [str(alembic_bin), *args], cwd=demo_dir, capture_output=True, text=True
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        raise RuntimeError(f"alembic {' '.join(args)} failed:\n{output}")
    return output


def hero_columns() -> list[str]:
    if not demo_db.exists():
        return []
    conn = sqlite3.connect(demo_db)
    try:
        return [row[1] for row in conn.execute("PRAGMA table_info(hero)")]
    finally:
        conn.close()


# Reset — delete any previously generated migrations + database so this file
# produces the exact same result every time (same idea as db_file.unlink() at
# the top of sqlmodel7.py/sqlmodel8.py).
versions_dir.mkdir(parents=True, exist_ok=True)
demo_db.unlink(missing_ok=True)
for old_migration in versions_dir.glob("*.py"):
    old_migration.unlink()
models_file.write_text(MODEL_V1)


# Step 1 — first migration. `alembic revision --autogenerate` diffs
# SQLModel.metadata (imported from models.py — see migrations_demo/alembic/env.py:
# `target_metadata = SQLModel.metadata`) against the current (empty) database,
# and writes a migration script that creates whatever is missing.
#
# Revision filenames start with a random hex id (not a timestamp), so alphabetical
# sort does NOT reflect creation order — diff the directory listing before/after
# instead of assuming sorted(...)[-1] is "the newest one" (a real bug caught by
# actually running this and checking the printed filenames against `history`).
before = set(versions_dir.glob("*.py"))
run_alembic("revision", "--autogenerate", "-m", "create hero table")
first_migration = (set(versions_dir.glob("*.py")) - before).pop()
print(f"STEP 1 — generated migration: {first_migration.name}")

# GOTCHA (found by actually running this — not documented anywhere official):
# autogenerate renders string columns as sqlmodel.sql.sqltypes.AutoString(),
# but never adds `import sqlmodel` to the generated file, so running it as-is
# raises NameError: name 'sqlmodel' is not defined. Fixed ONCE, permanently, by
# adding `import sqlmodel` directly to alembic/script.py.mako — the template
# used to generate EVERY future migration — instead of patching each file by hand.
run_alembic("upgrade", "head")
print(f"STEP 1 — after upgrade, hero columns: {hero_columns()}")


# Step 2 — change the model (add a column) and autogenerate detects the diff
# against the now-existing table, generating an ALTER-style migration instead
# of a CREATE — something create_all() is simply not able to do.
models_file.write_text(MODEL_V2)
before = set(versions_dir.glob("*.py"))
run_alembic("revision", "--autogenerate", "-m", "add secret_name column")
second_migration = (set(versions_dir.glob("*.py")) - before).pop()
print(f"\nSTEP 2 — generated migration: {second_migration.name}")

run_alembic("upgrade", "head")
print(f"STEP 2 — after upgrade, hero columns: {hero_columns()}")


# Step 3 — downgrade (rollback) exactly one revision, confirm the column is
# really gone, then upgrade back to head. Real, reversible, versioned schema
# changes — the core value Alembic adds over SQLModel.metadata.create_all().
run_alembic("downgrade", "-1")
print(f"\nSTEP 3 — after downgrade -1, hero columns: {hero_columns()}")

run_alembic("upgrade", "head")
print(f"STEP 3 — after upgrade head again, hero columns: {hero_columns()}")

print(f"\nHISTORY —\n{run_alembic('history')}")


# Summary
#
# alembic init alembic                     -> scaffold alembic.ini + env.py + versions/ (done once)
# env.py: target_metadata = SQLModel.metadata -> wires autogenerate to your models
# alembic revision --autogenerate -m "..." -> diff models vs database, write a migration script
# alembic upgrade head                     -> apply all migrations up to the latest ("head")
# alembic downgrade -1                     -> undo exactly one migration (each script
#                                              defines both upgrade() and downgrade())
# alembic history                          -> show the ordered chain of revisions
#
# SQLModel.metadata.create_all() -> only creates missing tables, quick for scripts/tests
# Alembic                        -> versioned, reversible changes to a real, already-populated database
#
# GOTCHA (verified by running this, not from any doc): autogenerate emits
# sqlmodel.sql.sqltypes.AutoString() but never imports sqlmodel — add
# `import sqlmodel` to alembic/script.py.mako once, so every future generated
# migration includes it automatically.
