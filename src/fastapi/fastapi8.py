from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException

# APIRouter & Structuring Bigger Applications
# Builds on fastapi6-7.py (Depends). Real projects split routes across files —
# this file emulates that with clearly-labeled sections; in an actual project
# each section below would be its own file:
#
#   app/
#   ├── main.py           <- creates FastAPI(), includes the routers
#   ├── dependencies.py   <- shared dependencies (get_token_header, below)
#   └── routers/
#       ├── users.py      <- router = APIRouter(); @router.get(...)
#       └── items.py      <- router = APIRouter(prefix=..., tags=..., dependencies=...)
#
# Then main.py does: from .routers import items, users; app.include_router(items.router)
# (relative imports: one dot "." = same package, ".." = parent package, etc.)


# --- app/dependencies.py -----------------------------------------------------
async def get_token_header(x_token: Annotated[str, Header()]):
    if x_token != "fake-super-secret-token":
        raise HTTPException(status_code=400, detail="X-Token header invalid")


# --- app/routers/users.py ----------------------------------------------------
# APIRouter is a "mini FastAPI" — same @router.get/post/... decorators, same
# support for dependencies, tags, responses. Nothing here is prefixed or tagged
# at the router level, so each path operation states its own tags.
users_router = APIRouter()


@users_router.get("/users/", tags=["users"])
async def read_users():
    return [{"username": "Rick"}, {"username": "Morty"}]


@users_router.get("/users/me", tags=["users"])
async def read_user_me():
    return {"username": "fakecurrentuser"}


# --- app/routers/items.py -----------------------------------------------------
# prefix/tags/dependencies/responses declared once on the router apply to EVERY
# path operation registered on it — no need to repeat them per-endpoint.
# Rule: the prefix must NOT end in "/", and each route path must start with "/".
fake_items_db = {"plumbus": {"name": "Plumbus"}, "gun": {"name": "Portal Gun"}}

items_router = APIRouter(
    prefix="/items",
    tags=["items"],
    dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Not found"}},
)


@items_router.get("/")
async def read_items():
    return fake_items_db


@items_router.get("/{item_id}")
async def read_item(item_id: str):
    if item_id not in fake_items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return fake_items_db[item_id]


# Path operation configuration — summary/description/deprecated are per-endpoint
# metadata shown in the docs. description defaults to the function's docstring
# if you don't pass one explicitly. tags=["custom"] here MERGES with the router's
# own tags=["items"], so this operation shows up under both in the docs.
@items_router.put(
    "/{item_id}",
    tags=["custom"],
    summary="Update an existing item",
    response_description="The updated item",
    responses={403: {"description": "Operation forbidden"}},
)
async def update_item(item_id: str):
    """Rename **plumbus** — every other item is forbidden in this demo."""
    if item_id != "plumbus":
        raise HTTPException(status_code=403, detail="You can only update: plumbus")
    return {"item_id": item_id, "name": "The great Plumbus"}


@items_router.get("/{item_id}/legacy-name", deprecated=True)
async def read_item_legacy_name(item_id: str):
    return {"item_id": item_id, "note": "use /items/{item_id} instead"}


# --- app/main.py ---------------------------------------------------------------
# The main FastAPI() app just ties the routers together with include_router().
# You can ALSO add prefix/tags/dependencies/responses here at inclusion time,
# without modifying the router itself — handy for a shared router with different
# rules per project (e.g. "admin" router reused across services with different auth).
app = FastAPI(title="Bigger Applications")

app.include_router(users_router)
app.include_router(items_router)


admin_router = APIRouter()


@admin_router.post("/")
async def update_admin():
    return {"message": "Admin getting schwifty"}


app.include_router(
    admin_router,
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_token_header)],
    responses={418: {"description": "I'm a teapot"}},
)


@app.get("/")
async def root():
    return {"message": "Hello Bigger Applications!"}


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)

    print("GET / — path declared directly on the app")
    print(client.get("/").json())

    print("\nGET /users/ — from users_router (no prefix)")
    print(client.get("/users/").json())

    print("\nGET /items/ — no X-Token header -> router-level dependency rejects it")
    r = client.get("/items/")
    print(r.status_code, r.json())

    print("\nGET /items/ — with the right X-Token header")
    print(client.get("/items/", headers={"X-Token": "fake-super-secret-token"}).json())

    print("\nGET /items/plumbus — path param inside the prefixed router")
    print(
        client.get(
            "/items/plumbus", headers={"X-Token": "fake-super-secret-token"}
        ).json()
    )

    print(
        "\nPUT /items/plumbus — tags=['custom'] merges with the router's tags=['items']"
    )
    r = client.put("/items/plumbus", headers={"X-Token": "fake-super-secret-token"})
    print(r.status_code, r.json())

    print(
        "\nPOST /admin/ — prefix/tags/deps added at include_router() time, not on the router itself"
    )
    print(client.post("/admin/", headers={"X-Token": "fake-super-secret-token"}).json())

    print("\nGET /openapi.json — tags recorded per operation")
    schema = client.get("/openapi.json").json()
    print(schema["paths"]["/items/{item_id}"]["put"]["tags"])  # ['items', 'custom']
    print(schema["paths"]["/items/{item_id}/legacy-name"]["get"]["deprecated"])  # True


# Summary
#
# APIRouter()                          -> a "mini FastAPI"; same decorators, same features
# APIRouter(prefix=, tags=, dependencies=, responses=) -> apply to every route on that router
# app.include_router(router)           -> wire a router into the main app
# app.include_router(router, prefix=, tags=, dependencies=) -> add/override at inclusion time,
#                                          without touching the router's own file
# tags on a single route + router tags -> they MERGE, not replace
# summary / description / response_description / deprecated -> per-route docs metadata
# Docstring                             -> used as `description` if none is passed explicitly
#
# Continue in fastapi9.py for middleware, CORS, and background tasks.
