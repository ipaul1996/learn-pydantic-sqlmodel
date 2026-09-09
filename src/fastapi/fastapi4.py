from fastapi import FastAPI, status
from pydantic import BaseModel, EmailStr

# Response Model & Status Codes
# Builds on fastapi3.py (request body) and pydanticmodels/model4.py (EmailStr).
#
# The return type annotation on a path operation function (-> Item) tells FastAPI
# what shape to validate, filter and document the RESPONSE as — same mechanism as
# request bodies, just applied to output instead of input.

app = FastAPI(title="Response Model & Status Codes")


class Item(BaseModel):
    name: str
    price: float
    tax: float | None = None
    tags: list[str] = []


# Return type annotation -> Item. FastAPI validates the response against Item,
# serializes it with Pydantic (fast — same Rust core as orjson), and documents it
# in OpenAPI. If your function accidentally returns something that doesn't match
# Item, that's a bug in YOUR code — FastAPI returns a 500 instead of leaking bad data.
@app.post("/items/")
async def create_item(item: Item) -> Item:
    return item


@app.get("/items/")
async def read_items() -> list[Item]:
    return [Item(name="Portal Gun", price=42.0), Item(name="Plumbus", price=32.0)]


# The security-relevant case: never return a password, even if the input model has one.
# Don't do this in production — the input model is echoed straight back, password included.
class UserIn(BaseModel):
    username: str
    password: str
    email: EmailStr
    full_name: str | None = None


# response_model — use when what you return isn't exactly what you want documented.
# Here the function returns the full `user` (with password) but response_model=UserOut
# tells FastAPI to filter the OUTPUT down to only UserOut's fields before sending it.
# response_model takes priority over the "-> " return type annotation when both exist.
class UserOut(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None


@app.post("/users/", response_model=UserOut)
async def create_user(user: UserIn):
    return user  # still has .password, but the client will never see it


# Cleaner alternative — model inheritance. Because UserIn is a subclass of BaseUser,
# it satisfies the "-> BaseUser" return type for tooling (mypy is happy), AND FastAPI's
# data filtering still uses the declared return type (BaseUser) to strip extra fields
# like password from the actual JSON response. Best of both: type checking + filtering.
class BaseUser(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None


class UserInInherited(BaseUser):
    password: str


@app.post("/users/inherited/")
async def create_user_inherited(user: UserInInherited) -> BaseUser:
    return user


# status_code — set the HTTP status returned on success. Use fastapi.status
# constants instead of memorizing numbers; same integer value, editor autocomplete.
@app.post("/items/created/", status_code=status.HTTP_201_CREATED)
async def create_item_201(item: Item):
    return item


# response_model_exclude_unset — only send back fields the caller actually set,
# skipping ones that fell back to their default. Handy for partial/sparse records.
items_db = {
    "foo": {"name": "Foo", "price": 50.2},
    "bar": {"name": "Bar", "price": 62, "tax": 20.2, "tags": ["sale"]},
}


@app.get(
    "/sparse-items/{item_id}", response_model=Item, response_model_exclude_unset=True
)
async def read_sparse_item(item_id: str):
    return items_db[item_id]


# response_model_include / response_model_exclude — quick allow/deny list of field
# names. Prefer separate response models for anything beyond a quick shortcut, since
# the OpenAPI schema still documents the FULL model either way.
@app.get("/items/{item_id}/public", response_model=Item, response_model_exclude={"tax"})
async def read_item_public(item_id: str):
    return items_db[item_id]


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)

    print("POST /items/ — response validated + serialized via response type")
    r = client.post("/items/", json={"name": "Plumbus", "price": 9.99})
    print(r.status_code, r.json())

    print("\nPOST /users/ — password stripped from the response by response_model")
    r = client.post(
        "/users/",
        json={
            "username": "indra",
            "password": "secret123",
            "email": "indra@example.com",
        },
    )
    print(r.status_code, r.json())

    print("\nPOST /users/inherited/ — same filtering via return-type inheritance")
    r = client.post(
        "/users/inherited/",
        json={
            "username": "indra",
            "password": "secret123",
            "email": "indra@example.com",
        },
    )
    print(r.status_code, r.json())

    print("\nPOST /items/created/ — status_code=201")
    r = client.post("/items/created/", json={"name": "Plumbus", "price": 9.99})
    print(r.status_code, r.json())

    print("\nGET /sparse-items/foo — only explicitly-set fields (tax/tags omitted)")
    print(client.get("/sparse-items/foo").json())

    print("\nGET /sparse-items/bar — bar had tax+tags explicitly set, so they show")
    print(client.get("/sparse-items/bar").json())

    print("\nGET /items/bar/public — tax excluded via response_model_exclude")
    print(client.get("/items/bar/public").json())


# Summary
#
# def f() -> Item                     -> declares + validates + documents the response shape
# response_model=X                    -> use when the return type annotation should differ
#                                         from what's actually filtered/documented (priority
#                                         over "-> " if both are present)
# Inheritance (UserIn(BaseUser))       -> best of both: tooling-correct return type AND
#                                         FastAPI still filters down to the base fields
# status_code=status.HTTP_201_CREATED -> set the success status code, use fastapi.status
# response_model_exclude_unset=True    -> only send fields the caller actually set
# response_model_include / _exclude    -> quick field allow/deny list (still fully documented)
#
# Continue in fastapi5.py for HTTPException and custom error handling.
