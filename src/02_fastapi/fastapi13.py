from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Query

# Production Essentials
# Wraps up the fastapi1-12.py learning path with the things that show up in
# almost every real deployment but don't fit neatly into "one FastAPI feature".

app = FastAPI(title="Production Essentials")


# Settings — already covered in depth in sqlmodel9.py (pydantic-settings, .env
# files, sync vs async DB sessions) and as a Depends()-based pattern in
# fastapi12.py. Same idea everywhere: never hardcode secrets/URLs, read them
# from environment variables via a Pydantic Settings class.


# Health check — load balancers, Kubernetes, and uptime monitors all expect a
# cheap, no-auth endpoint that proves the process is alive and can reach its
# dependencies (DB, cache, etc). Keep it FAST — no heavy queries.
@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Pagination — a reusable dependency instead of repeating "page/page_size" query
# params (with the same validation) on every list endpoint. Builds on the
# limit/offset pattern already used directly on queries in sqlmodel4.py; here
# it's wrapped as a shared, DB-agnostic dependency.
class PageParams:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="1-based page number")] = 1,
        page_size: Annotated[
            int, Query(ge=1, le=100, description="items per page")
        ] = 20,
    ):
        self.page = page
        self.page_size = page_size
        self.limit = page_size
        self.offset = (page - 1) * page_size


fake_catalog = [{"id": i, "name": f"item-{i}"} for i in range(1, 51)]


@app.get("/catalog")
async def list_catalog(pagination: Annotated[PageParams, Depends()]):
    page_items = fake_catalog[pagination.offset : pagination.offset + pagination.limit]
    return {
        "page": pagination.page,
        "page_size": pagination.page_size,
        "total": len(fake_catalog),
        "items": page_items,
    }


# API versioning — the same APIRouter can be included more than once with a
# different prefix, so old and new URLs both work while clients migrate.
v1_router = APIRouter()


@v1_router.get("/status")
async def status_endpoint():
    return {"version": "reported per-prefix, not per-router"}


app.include_router(v1_router, prefix="/api/v1", tags=["v1"])
app.include_router(v1_router, prefix="/api/latest", tags=["latest"])


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)

    print("GET /health — cheap liveness check for load balancers / Kubernetes")
    print(client.get("/health").json())

    print("\nGET /catalog?page=2&page_size=5 — shared pagination dependency")
    print(client.get("/catalog", params={"page": 2, "page_size": 5}).json())

    print("\nGET /catalog?page_size=1000 — page_size capped by le=100 -> 422")
    r = client.get("/catalog", params={"page_size": 1000})
    print(r.status_code, r.json()["detail"][0]["msg"])

    print("\nGET /api/v1/status and /api/latest/status — same router, two prefixes")
    print(client.get("/api/v1/status").json())
    print(client.get("/api/latest/status").json())


# Deployment concepts — no code here, just what to know before shipping:
#
# Running the process
#   - This repo's convention: uvicorn fastapi13:app --reload --app-dir src/fastapi
#   - `--reload` is for local development ONLY — never in production (it's slower
#     and watches the filesystem for changes)
#   - FastAPI also ships its own CLI: `fastapi dev main.py` (development) and
#     `fastapi run main.py` (production), both wrapping Uvicorn underneath
#
# HTTPS
#   - Your app code does not do TLS termination. A reverse proxy in front of it
#     does (Nginx, Traefik, Caddy, or your cloud provider's load balancer)
#
# Replication (workers)
#   - One Python process handles many concurrent requests, but only one CPU core
#   - Run multiple worker processes to use multiple cores, e.g. `uvicorn ... --workers 4`
#   - Each worker is a separate process with its OWN memory — a value cached in
#     one worker (like ml_models in fastapi12.py) is NOT shared with the others
#
# Restarts
#   - A crashed process should come back on its own — handled by an external
#     supervisor (Docker/Kubernetes restart policies, systemd, supervisord, etc.),
#     not by code inside your app
#
# CORS, auth, background tasks, middleware
#   - Already covered in fastapi9.py and fastapi10.py — all of it still applies
#     unchanged in production; nothing about "prod" changes their code shape
#
# Where to go from here
#   - pydanticmodels/model1-6.py -> data validation fundamentals
#   - sqlmodel/sqlmodel1-10.py   -> the database layer (engine, sessions, CRUD,
#     relationships, transactions) — sqlmodel6.py already wires SQLModel INTO
#     FastAPI endpoints exactly the way fastapi3-4.py describe request/response
#     models, and sqlmodel9.py covers settings + sync vs async sessions in depth
#   - fastapi1-13.py (this folder) -> the HTTP/web layer sitting on top of both
