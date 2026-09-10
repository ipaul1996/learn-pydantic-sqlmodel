from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException

# Dependency Injection — sub-dependencies, yield, and global dependencies
# Builds directly on fastapi6.py.

app = FastAPI(title="Dependency Injection — Advanced")


# Sub-dependencies — a dependency can itself depend on another dependency.
# FastAPI resolves the whole chain: query_extractor runs first, and its result
# is handed to query_or_cookie_extractor, which is the one actually injected
# into the path operation.
def query_extractor(q: str | None = None):
    return q


def query_or_cookie_extractor(
    q: Annotated[str | None, Depends(query_extractor)],
    last_query: Annotated[str | None, Cookie()] = None,
):
    if not q:
        return last_query
    return q


@app.get("/search/")
async def search(
    query_or_default: Annotated[str | None, Depends(query_or_cookie_extractor)],
):
    return {"q_or_cookie": query_or_default}


# Caching — if the SAME dependency is needed by more than one dependant in a single
# request, FastAPI calls it only ONCE and reuses the cached result for the rest of
# that request (use_cache=True is the default). Pass use_cache=False to force a
# fresh call for that specific reference.
call_count = {"n": 0}


def get_value():
    call_count["n"] += 1
    return call_count["n"]


def dep_a(value: Annotated[int, Depends(get_value)]):
    return value


def dep_b_cached(value: Annotated[int, Depends(get_value)]):
    return value


def dep_b_fresh(value: Annotated[int, Depends(get_value, use_cache=False)]):
    return value


@app.get("/cached/")
async def cached_route(
    a: Annotated[int, Depends(dep_a)], b: Annotated[int, Depends(dep_b_cached)]
):
    return {"a": a, "b": b, "same_call": a == b}


@app.get("/uncached/")
async def uncached_route(
    a: Annotated[int, Depends(dep_a)], b: Annotated[int, Depends(dep_b_fresh)]
):
    return {"a": a, "b": b, "same_call": a == b}


# Dependencies with yield — for setup/teardown pairs (open a resource, always
# clean it up afterwards). Only the code BEFORE yield runs before the path
# operation; the code AFTER yield runs once the response has been sent.
# This is exactly the shape get_session() uses in sqlmodel6.py/9.py, just with
# a fake in-memory session here instead of a real SQLModel Session.
class FakeDBSession:
    def __init__(self):
        self.closed = False

    def query(self, sql: str) -> str:
        return f"ran: {sql}"

    def close(self):
        self.closed = True


session_log: list[str] = []


def get_db():
    db = FakeDBSession()
    session_log.append("opened")
    try:
        yield db
    finally:
        db.close()
        session_log.append("closed")


@app.get("/records/")
async def read_records(db: Annotated[FakeDBSession, Depends(get_db)]):
    return {"result": db.query("SELECT * FROM records")}


# yield + exception handling — wrap the yield in try/except to react to exceptions
# raised later in the path operation (e.g. turn a business-logic error into a clean
# HTTPException). If you catch an exception here and don't re-raise it (or raise a
# new one), FastAPI has no idea anything went wrong — always re-raise unless you're
# intentionally replacing it with an HTTPException.
class OwnerError(Exception):
    pass


plumbus_data = {
    "plumbus": {"description": "Freshly pickled plumbus", "owner": "Morty"},
    "portal-gun": {"description": "Gun to create portals", "owner": "Rick"},
}


def get_username():
    try:
        yield "Rick"
    except OwnerError as e:
        raise HTTPException(status_code=400, detail=f"Owner error: {e}")


@app.get("/gadgets/{item_id}")
async def get_gadget(item_id: str, username: Annotated[str, Depends(get_username)]):
    if item_id not in plumbus_data:
        raise HTTPException(status_code=404, detail="Item not found")
    item = plumbus_data[item_id]
    if item["owner"] != username:
        raise OwnerError(username)
    return item


# Global dependencies — pass dependencies=[Depends(...)] to FastAPI() itself to run
# them for EVERY path operation in the app, even ones that don't declare them as a
# parameter (no value gets injected into the function; it's purely enforced).
# Demonstrated on a separate app instance so it doesn't affect the routes above.
async def verify_token(x_token: Annotated[str, Header()]):
    if x_token != "fake-super-secret-token":
        raise HTTPException(status_code=400, detail="X-Token header invalid")


protected_app = FastAPI(
    title="Global Dependencies", dependencies=[Depends(verify_token)]
)


@protected_app.get("/items/")
async def read_protected_items():
    return [{"item": "Portal Gun"}, {"item": "Plumbus"}]


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)
    protected_client = TestClient(protected_app)

    print("GET /search/ — no q, no cookie -> None")
    print(client.get("/search/").json())

    print("\nGET /search/?q=hello — sub-dependency resolves q first")
    print(client.get("/search/", params={"q": "hello"}).json())

    print("\nGET /search/ with a 'last_query' cookie, no q -> falls back to the cookie")
    print(client.get("/search/", cookies={"last_query": "remembered"}).json())

    print("\nGET /cached/ — get_value() is shared by dep_a and dep_b, called ONCE")
    before = call_count["n"]
    r = client.get("/cached/").json()
    print(r, "| calls made:", call_count["n"] - before)

    print("\nGET /uncached/ — dep_b_fresh forces a second call with use_cache=False")
    before = call_count["n"]
    r = client.get("/uncached/").json()
    print(r, "| calls made:", call_count["n"] - before)

    print("\nGET /records/ — yield dependency: open before, close after the response")
    print(client.get("/records/").json())
    print("session_log after the request:", session_log)  # ['opened', 'closed']

    print(
        "\nGET /gadgets/plumbus — Rick asking for Morty's plumbus -> OwnerError -> 400"
    )
    r = client.get("/gadgets/plumbus")
    print(r.status_code, r.json())

    print("\nGET /gadgets/portal-gun — Rick owns this one -> 200")
    print(client.get("/gadgets/portal-gun").json())

    print("\nGET /items/ (protected_app) with no X-Token -> 422 (missing header)")
    r = protected_client.get("/items/")
    print(r.status_code, r.json())

    print("\nGET /items/ (protected_app) with the right X-Token -> 200")
    r = protected_client.get("/items/", headers={"X-Token": "fake-super-secret-token"})
    print(r.status_code, r.json())


# Summary
#
# Sub-dependencies       -> a dependency can Depends() on another dependency; FastAPI
#                           resolves the whole chain automatically
# Caching (use_cache)    -> a dependency shared by multiple dependants in ONE request
#                           runs only once by default; use_cache=False forces a fresh call
# Dependencies with yield -> code before yield = setup, code after yield = teardown,
#                           runs even if the path operation raises (put cleanup in finally)
# yield + try/except      -> catch exceptions from later in the request; ALWAYS re-raise
#                           (or raise a new HTTPException) or FastAPI won't know it failed
# FastAPI(dependencies=[Depends(fn)]) -> run fn for every request in the whole app,
#                           without it being a parameter of each path operation
#
# Continue in fastapi8.py for APIRouter and structuring a multi-file application.
