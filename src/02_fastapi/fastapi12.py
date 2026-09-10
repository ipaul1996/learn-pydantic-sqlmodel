from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI

# Lifespan Events & Testing
# Builds on fastapi6-7.py (Depends) and mirrors the get_session() pattern already
# used in sqlmodel6.py/9.py, but focuses on FastAPI's own lifecycle + test tools.

ml_models: dict[str, Callable[[float], float]] = {}
startup_log: list[str] = []


def fake_load_model() -> Callable[[float], float]:
    # Pretend this is an expensive load (reading a big file, a DB connection pool,
    # a machine learning model, etc). Doing it here means it happens ONCE, before
    # the app starts accepting requests — not on every request.
    return lambda x: x * 42


# Lifespan — an async context manager: code BEFORE `yield` runs once at startup,
# code AFTER `yield` runs once at shutdown. This is the modern replacement for the
# older @app.on_event("startup") / @app.on_event("shutdown") decorators (still seen
# in older codebases, but deprecated — lifespan can share state/variables between
# the startup and shutdown halves far more naturally).
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    startup_log.append("startup")
    ml_models["answer_to_everything"] = fake_load_model()
    yield
    ml_models.clear()
    startup_log.append("shutdown")


app = FastAPI(title="Lifespan & Testing", lifespan=lifespan)


@app.get("/predict")
async def predict(x: float):
    return {"result": ml_models["answer_to_everything"](x)}


# Settings-as-a-dependency — a common production pattern: instead of one global
# `settings` object (as in sqlmodel9.py), inject settings through Depends(). This
# makes it trivial to swap in different settings during tests via dependency_overrides,
# with zero changes to the endpoint itself.
class Settings:
    def __init__(
        self, app_name: str = "Awesome API", admin_email: str = "admin@example.com"
    ):
        self.app_name = app_name
        self.admin_email = admin_email


def get_settings() -> Settings:
    return Settings()


@app.get("/info")
async def info(settings: Annotated[Settings, Depends(get_settings)]):
    return {"app_name": settings.app_name, "admin_email": settings.admin_email}


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    # Using TestClient as a context manager ("with") is what actually triggers the
    # lifespan startup/shutdown events — without "with", they never run, and
    # ml_models would stay empty.
    print("Using TestClient WITHOUT 'with' — lifespan never runs")
    plain_client = TestClient(app)
    print("startup_log:", startup_log)  # still empty

    print("\nUsing TestClient AS A CONTEXT MANAGER — lifespan runs")
    with TestClient(app) as client:
        print("startup_log right after entering the 'with' block:", startup_log)

        print("\nGET /predict?x=2 — uses the model loaded during startup")
        print(client.get("/predict", params={"x": 2}).json())

        print("\nGET /info — default settings")
        print(client.get("/info").json())

        # dependency_overrides — swap ANY Depends() target for a stand-in, scoped to
        # this app object. This is THE way to inject test doubles: fake settings,
        # an in-memory DB session instead of a real one, a fake "current user", etc.
        def get_settings_override() -> Settings:
            return Settings(admin_email="testing_admin@example.com")

        app.dependency_overrides[get_settings] = get_settings_override

        print("\nGET /info — after overriding the settings dependency for tests")
        print(client.get("/info").json())

        app.dependency_overrides.clear()  # always clean up after a test

        print("\nGET /info — back to the real dependency after clearing overrides")
        print(client.get("/info").json())

    print("\nAfter the 'with' block exits — shutdown ran, model cleared")
    print("startup_log:", startup_log)
    print("ml_models:", ml_models)


# Summary
#
# @asynccontextmanager + lifespan(app) with one yield -> code before yield = startup,
#                                       code after yield = shutdown
# FastAPI(lifespan=lifespan)           -> wire it into the app
# @app.on_event("startup"/"shutdown")   -> older, deprecated alternative; avoid in new code
# with TestClient(app) as client:        -> REQUIRED to actually trigger lifespan in tests
# def test_xxx(): ... assert ...        -> pytest convention; TestClient calls are plain
#                                          sync calls, no await needed even for async endpoints
# app.dependency_overrides[dep] = fn    -> swap a real dependency for a test double
# app.dependency_overrides.clear()       -> always reset overrides after each test
#
# Continue in fastapi13.py for production essentials: running the server, workers,
# health checks, and where everything in this folder fits together.
