from typing import Annotated

from fastapi import Depends, FastAPI

# Dependency Injection — the basics
# Builds on fastapi1-2.py (query params).
#
# "Dependency Injection" means: your path operation function declares what it
# NEEDS, and FastAPI takes care of building that thing and handing it over.
# It's how FastAPI shares logic across endpoints without copy-pasting code —
# things like "parse these 3 common query params", "give me a DB session"
# (already used as get_session() in sqlmodel6.py/9.py), or "check this user is
# logged in" (fastapi10.py). This file covers the plain building blocks;
# fastapi7.py covers sub-dependencies, yield-based setup/teardown, and globals.

app = FastAPI(title="Dependency Injection — Basics")

fake_items_db = [{"item_name": "Foo"}, {"item_name": "Bar"}, {"item_name": "Baz"}]


# A dependency ("dependable") is just a callable — usually a plain function —
# that can take the same kind of parameters a path operation function can.
async def common_parameters(q: str | None = None, skip: int = 0, limit: int = 100):
    return {"q": q, "skip": skip, "limit": limit}


# Depends(common_parameters) tells FastAPI: before running this path operation,
# call common_parameters() (resolving ITS OWN query params first), and inject
# whatever it returns as the `commons` parameter here.
@app.get("/items/")
async def read_items(commons: Annotated[dict, Depends(common_parameters)]):
    return {
        "items": fake_items_db[commons["skip"] : commons["skip"] + commons["limit"]],
        **commons,
    }


# The whole point: reuse. Any other endpoint can depend on the exact same function
# and get the exact same query-param parsing logic, with zero duplication.
@app.get("/users/")
async def read_users(commons: Annotated[dict, Depends(common_parameters)]):
    return commons


# Type alias for a Depends(...) annotation — write it once, reuse the alias.
# Purely standard Python (a type alias), nothing FastAPI-specific about the syntax,
# but it keeps signatures clean once a dependency is used in many places.
CommonsDep = Annotated[dict, Depends(common_parameters)]


@app.get("/products/")
async def read_products(commons: CommonsDep):
    return commons


# Classes as dependencies — a class is callable too (calling MyClass(...) runs
# __init__ and returns an instance), so FastAPI can use a class exactly like a
# function dependency. This upgrades the plain dict above into a real object with
# autocomplete/type-checking for commons.q, commons.skip, commons.limit.
class CommonQueryParams:
    def __init__(self, q: str | None = None, skip: int = 0, limit: int = 100):
        self.q = q
        self.skip = skip
        self.limit = limit


@app.get("/catalog/")
async def read_catalog(
    commons: Annotated[CommonQueryParams, Depends(CommonQueryParams)],
):
    response: dict = {}
    if commons.q:
        response["q"] = commons.q
    response["items"] = fake_items_db[commons.skip : commons.skip + commons.limit]
    return response


# Shortcut — when the dependency IS the same class as the type annotation, you can
# write Depends() with no argument instead of repeating the class name twice.
# commons: Annotated[CommonQueryParams, Depends(CommonQueryParams)]   <- explicit
# commons: Annotated[CommonQueryParams, Depends()]                    <- shortcut, same effect
@app.get("/catalog/shortcut")
async def read_catalog_shortcut(commons: Annotated[CommonQueryParams, Depends()]):
    return {"q": commons.q, "skip": commons.skip, "limit": commons.limit}


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)

    print("GET /items/?q=foo&limit=2 — dependency parses shared query params")
    print(client.get("/items/", params={"q": "foo", "limit": 2}).json())

    print("\nGET /users/?skip=1 — same dependency, reused on a different endpoint")
    print(client.get("/users/", params={"skip": 1}).json())

    print("\nGET /products/ — same dependency again, via the CommonsDep alias")
    print(client.get("/products/").json())

    print("\nGET /catalog/?q=widget — class-based dependency (real object, not a dict)")
    print(client.get("/catalog/", params={"q": "widget"}).json())

    print("\nGET /catalog/shortcut?limit=1 — Depends() shortcut, same class")
    print(client.get("/catalog/shortcut", params={"limit": 1}).json())


# Summary
#
# Depends(some_function)              -> inject the return value of some_function
# Annotated[T, Depends(fn)]            -> preferred style (matches Query/Path/Body)
# CommonsDep = Annotated[...]          -> name a dependency once, reuse the alias everywhere
# Classes as dependencies              -> FastAPI calls the class like a function (its __init__
#                                         params become the dependency's params); you get a
#                                         real typed object back instead of a dict
# Annotated[MyClass, Depends()]        -> shortcut when the annotation IS the dependency class
# Reuse across endpoints                -> the entire point: shared logic, written once
#
# Continue in fastapi7.py for sub-dependencies, yield (setup/teardown), and global dependencies.
