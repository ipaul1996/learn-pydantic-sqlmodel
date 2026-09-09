from typing import Annotated

from fastapi import Body, FastAPI
from pydantic import BaseModel

# Request Body
# Builds on fastapi1-2.py (path/query params) and the whole pydanticmodels/ folder
# (BaseModel, Field, validators, nested models — all of that still applies here,
# FastAPI just wires a Pydantic model to the HTTP request body for you).
#
# A request body is what the client SENDS (POST/PUT/PATCH/DELETE).
# A response body is what your API SENDS BACK — almost every request has one.
# GET requests are not supposed to carry a body (the spec leaves it undefined),
# so FastAPI/Swagger won't document a body for GET path operations.

app = FastAPI(title="Request Body")


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None


# Declare a body param the same way as a path/query param: name + type hint.
# FastAPI will: read the body as JSON -> validate it against Item -> give you a
# real Item instance (with autocomplete) -> reject bad data with a 422.
@app.post("/items/")
async def create_item(item: Item):
    item_dict = item.model_dump()
    if item.tax is not None:
        item_dict["price_with_tax"] = item.price + item.tax
    return item_dict


# Body + path + query, all at once — FastAPI figures out where each param comes from:
#   - name matches a {placeholder} in the path      -> path parameter
#   - singular type (int, str, bool, float, etc.)   -> query parameter
#   - type is a Pydantic model                       -> request body
@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item, q: str | None = None):
    result: dict = {"item_id": item_id, **item.model_dump()}
    if q:
        result["q"] = q
    return result


class User(BaseModel):
    username: str
    full_name: str | None = None


# Multiple body models — FastAPI notices there are two Pydantic-model parameters
# and wraps each one under its parameter name as a key in the expected JSON body:
#   {"item": {...Item fields...}, "user": {...User fields...}}
@app.put("/items/{item_id}/full")
async def update_item_full(item_id: int, item: Item, user: User):
    return {"item_id": item_id, "item": item, "user": user}


# Singular values in body — a plain int/str would normally be read as a query
# param. Wrap it in Body() to force FastAPI to read it from the JSON body instead,
# as another top-level key alongside "item" and "user".
@app.put("/items/{item_id}/full-with-importance")
async def update_item_with_importance(
    item_id: int,
    item: Item,
    user: User,
    importance: Annotated[int, Body(gt=0)],
):
    return {"item_id": item_id, "item": item, "user": user, "importance": importance}


# Embed a single body param — normally a single Item body param expects the JSON
# to BE the Item directly: {"name": ..., "price": ...}. Body(embed=True) makes
# FastAPI expect it wrapped under its parameter name instead: {"item": {...}}.
# Useful for keeping request shapes consistent once you might add more fields later.
@app.put("/items/{item_id}/embedded")
async def update_item_embedded(item_id: int, item: Annotated[Item, Body(embed=True)]):
    return {"item_id": item_id, "item": item}


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)

    print("POST /items/ — body validated + parsed into Item")
    r = client.post("/items/", json={"name": "Plumbus", "price": 9.99, "tax": 1.0})
    print(r.status_code, r.json())

    print("\nPOST /items/ — missing required 'price' -> 422")
    r = client.post("/items/", json={"name": "Plumbus"})
    print(r.status_code, r.json()["detail"][0]["loc"])

    print("\nPUT /items/5?q=sale — path + query + body together")
    r = client.put(
        "/items/5", params={"q": "sale"}, json={"name": "Widget", "price": 3.5}
    )
    print(r.status_code, r.json())

    print("\nPUT /items/5/full — two body models nest under their param names")
    r = client.put(
        "/items/5/full",
        json={
            "item": {"name": "Widget", "price": 3.5},
            "user": {"username": "indra"},
        },
    )
    print(r.status_code, r.json())

    print("\nPUT .../full-with-importance — Body() adds a singular value to the body")
    r = client.put(
        "/items/5/full-with-importance",
        json={
            "item": {"name": "Widget", "price": 3.5},
            "user": {"username": "indra"},
            "importance": 5,
        },
    )
    print(r.status_code, r.json())

    print("\nPUT .../embedded — body must be wrapped under 'item'")
    r = client.put(
        "/items/5/embedded",
        json={"item": {"name": "Widget", "price": 3.5}},
    )
    print(r.status_code, r.json())


# Summary
#
# item: Item                          -> request body, parsed + validated against the model
# GET requests                        -> don't declare a body (undefined by the HTTP spec)
# Path/query/body detection           -> by name (path), singular type (query), model (body)
# item: Item, user: User               -> multiple body models, each nested under its param name
# importance: Annotated[int, Body()]   -> force a singular value to be read from the body
# Body(embed=True)                    -> wrap even a single body model under its param name
#
# All the deep validation (Field, custom validators, nested models, EmailStr, etc.)
# still comes from Pydantic — see pydanticmodels/model1-6.py for that. This file is
# only about how FastAPI decides WHERE to read data from and HOW to shape the body.
#
# Continue in fastapi4.py for response_model, status codes, and hiding fields on output.
