from typing import Annotated

from fastapi import FastAPI, Path, Query

# Query parameters & validation
# Builds on fastapi1.py (path parameters).
#
# Any function parameter that is NOT part of the path is treated as a query
# parameter — the key=value pairs after "?" in a URL, e.g. /items/?skip=0&limit=10.
# FastAPI tells path params and query params apart by name: if the name matches
# a {placeholder} in the path, it's a path param; otherwise it's a query param.

app = FastAPI(title="Query Params & Validation")

fake_items_db = [{"item_name": "Foo"}, {"item_name": "Bar"}, {"item_name": "Baz"}]


# Defaults — a query param with a default value is optional.
# skip=0, limit=10 below are the defaults used when the client omits them.
@app.get("/items/")
async def read_items(skip: int = 0, limit: int = 10):
    return fake_items_db[skip : skip + limit]


# Optional (nullable) — default of None makes it optional AND nullable.
# Required — no default at all makes a query param mandatory (422 if missing).
# bool type conversion — "1"/"true"/"yes"/"on" (any case) all become True.
@app.get("/items/{item_id}")
async def read_item(item_id: str, q: str | None = None, short: bool = False):
    item: dict = {"item_id": item_id}
    if q:
        item["q"] = q
    if not short:
        item["description"] = "This is an amazing item that has a long description"
    return item


@app.get("/users/{user_id}/items/{item_id}")
async def read_user_item(user_id: int, item_id: str, needy: str):
    # "needy" has no default -> required query param
    return {"item_id": item_id, "owner_id": user_id, "needy": needy}


# Query() — add validation + metadata to a query param.
# Recommended style: put Query() inside Annotated, keep the real default outside.
#
#   q: Annotated[str | None, Query(max_length=50)] = None   <- do this
#   q: str | None = Query(default=None, max_length=50)      <- older style, still works
#
# Why Annotated is preferred: the function's actual default stays a plain Python
# default (None), so the function still behaves correctly if called directly
# from other code (e.g. in tests), without needing FastAPI to "unwrap" Query().
@app.get("/search/")
async def search_items(
    q: Annotated[
        str | None,
        Query(
            min_length=3,
            max_length=50,
            pattern="^[a-zA-Z ]+$",  # only letters and spaces
            title="Search query",
            description="What to search for in item names",
            alias="search-term",  # client sends ?search-term=... instead of ?q=...
        ),
    ] = None,
):
    results: dict = {"items": fake_items_db}
    if q:
        results["q"] = q
    return results


# Required query param declared through Query() — simply omit the default.
@app.get("/required-search/")
async def required_search(q: Annotated[str, Query(min_length=3)]):
    return {"q": q}


# List / multiple values — the same query key repeated: ?tag=a&tag=b&tag=c
@app.get("/tags/")
async def read_tags(tag: Annotated[list[str] | None, Query()] = None):
    return {"tags": tag}


# Path() — same validation ideas as Query(), but for path parameters.
# A path parameter is always required (it's part of the URL), so there's no
# "default" concept for it — Path() is purely for numeric/string constraints + metadata.
# gt/ge/lt/le work the same as Pydantic's Field() constraints (model2.py).
@app.get("/products/{product_id}")
async def read_product(
    product_id: Annotated[int, Path(title="The ID of the product", ge=1, le=1000)],
    q: str | None = None,
):
    result: dict = {"product_id": product_id}
    if q:
        result["q"] = q
    return result


# Other parameter sources — Header() and Cookie() work exactly like Query()/Path(),
# just reading from HTTP headers / cookies instead. Same Annotated[...] pattern:
#   x_token: Annotated[str, Header()]
#   session: Annotated[str | None, Cookie()] = None
# (used later in fastapi7.py and fastapi8.py for auth-style headers)


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)

    print("GET /items/ — defaults skip=0, limit=10")
    print(client.get("/items/").json())

    print("\nGET /items/?skip=1 — limit still defaults to 10")
    print(client.get("/items/", params={"skip": 1}).json())

    print("\nGET /items/foo?short=1 — bool query param")
    print(client.get("/items/foo", params={"short": 1}).json())

    print("\nGET /users/1/items/foo — missing required 'needy' -> 422")
    r = client.get("/users/1/items/foo")
    print(r.status_code, r.json())

    print("\nGET /users/1/items/foo?needy=yes")
    print(client.get("/users/1/items/foo", params={"needy": "yes"}).json())

    print("\nGET /search/?search-term=hello world — alias + pattern validation")
    print(client.get("/search/", params={"search-term": "hello world"}).json())

    print("\nGET /search/?search-term=ab — too short (min_length=3) -> 422")
    r = client.get("/search/", params={"search-term": "ab"})
    print(r.status_code, r.json()["detail"][0]["msg"])

    print("\nGET /tags/?tag=python&tag=fastapi — repeated query key -> list")
    print(client.get("/tags/", params=[("tag", "python"), ("tag", "fastapi")]).json())

    print("\nGET /products/0 — violates ge=1 -> 422")
    r = client.get("/products/0")
    print(r.status_code, r.json()["detail"][0]["msg"])

    print("\nGET /products/5 — valid")
    print(client.get("/products/5").json())


# Summary
#
# Query param   -> any function param not in the path; optional if it has a default
# q: str | None = None       -> optional + nullable
# q: str                     -> required (no default)
# Annotated[T, Query(...)]   -> preferred way to add validation/metadata (0.95+)
#   min_length, max_length, pattern  -> string constraints
#   title, description, alias, deprecated -> metadata for docs
# Annotated[list[str], Query()]     -> repeated query key becomes a list
# Annotated[T, Path(...)]           -> same idea for path params: gt, ge, lt, le
# Header()/Cookie()                 -> same Annotated[...] pattern, different source
#
# Continue in fastapi3.py for request bodies (Pydantic models as the request payload).
