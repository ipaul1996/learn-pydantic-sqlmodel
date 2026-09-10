# Docs Link: https://fastapi.tiangolo.com/learn/

# ====================================================================================

from enum import Enum

from fastapi import FastAPI

# FastAPI — fundamentals
# FastAPI is a web framework for building APIs. It sits on top of two libraries:
#   Starlette  -> handles the actual web parts (routing, requests, responses, async)
#   Pydantic   -> handles data validation (already covered in pydanticmodels/model1-6.py)
# FastAPI's job is to glue your Python type hints to both of these, so one type
# hint gives you validation + serialization + auto-generated docs, all at once.
#
# Run the API server (matches the convention used in sqlmodel6.py):
#   uvicorn fastapi1:app --reload --app-dir src/fastapi
#
# Or just run this file directly to see a demo of every endpoint below:
#   python src/fastapi/fastapi1.py


app = FastAPI(title="FastAPI Basics")


# Path operation — a function tied to a URL "path" + an HTTP "operation" (method).
# @app.get("/") registers: when a GET request hits "/", call the function below.
# "async def" is optional here — FastAPI supports both "async def" and plain "def".
# Use plain "def" if the function does blocking I/O with no async library available;
# FastAPI will run it in a threadpool so it doesn't block the event loop.
@app.get("/")
async def root():
    return {"message": "Hello World"}


# Path parameters — declared with {curly_braces} in the path string.
# Adding a type hint (item_id: int) gives you three things for free:
#   1. Data conversion  -> the string from the URL is converted to int
#   2. Data validation  -> "/items/foo" fails with a clear 422 error, not a crash
#   3. Editor support   -> autocomplete knows item_id is an int inside the function
@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}


# Order matters — FastAPI matches path operations top to bottom, first match wins.
# A fixed path like "/users/me" MUST be declared before the dynamic "/users/{user_id}",
# otherwise "/users/me" would match the dynamic route with user_id="me".
@app.get("/users/me")
async def read_current_user():
    return {"user_id": "the current user"}


@app.get("/users/{user_id}")
async def read_user(user_id: str):
    return {"user_id": user_id}


# Predefined values — use a Python Enum (inheriting from str + Enum) to restrict a
# path parameter to a fixed set of choices. The interactive docs render this as a
# dropdown, and FastAPI rejects any value that isn't one of the members.
class ModelName(str, Enum):
    alexnet = "alexnet"
    resnet = "resnet"
    lenet = "lenet"


@app.get("/models/{model_name}")
async def get_model(model_name: ModelName):
    if model_name is ModelName.alexnet:
        return {"model_name": model_name, "message": "Deep Learning FTW!"}
    if model_name.value == "lenet":
        return {"model_name": model_name, "message": "LeCNN all the images"}
    return {"model_name": model_name, "message": "Have some residuals"}


# Returning data — you can return dict, list, str, int, bool, or a Pydantic model.
# FastAPI (via Pydantic) converts it to JSON automatically. No manual json.dumps().


# Automatic docs — FastAPI reads your path operations + type hints and builds a
# full OpenAPI schema for you, with zero extra code. Visit these once the server
# is running with uvicorn:
#   /docs        -> interactive Swagger UI (try requests right from the browser)
#   /redoc       -> alternative ReDoc documentation
#   /openapi.json -> the raw OpenAPI schema (what powers both docs UIs above)


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)

    print("GET / — root")
    print(client.get("/").json())

    print("\nGET /items/3 — path param converted to int")
    print(client.get("/items/3").json())
    print(type(client.get("/items/3").json()["item_id"]))  # <class 'int'>, not str

    print("\nGET /items/foo — validation error (422)")
    r = client.get("/items/foo")
    print(r.status_code, r.json())

    print("\nGET /users/me — fixed path wins over /users/{user_id}")
    print(client.get("/users/me").json())

    print("\nGET /users/johndoe — falls through to the dynamic route")
    print(client.get("/users/johndoe").json())

    print("\nGET /models/alexnet — Enum path param")
    print(client.get("/models/alexnet").json())

    print("\nGET /models/not-a-real-model — Enum rejects unknown values")
    r = client.get("/models/not-a-real-model")
    print(r.status_code, r.json())

    print("\nGET /openapi.json — auto-generated schema (truncated)")
    schema = client.get("/openapi.json").json()
    print(f"openapi={schema['openapi']}, title={schema['info']['title']}")
    print("paths:", list(schema["paths"].keys()))


# Summary
#
# FastAPI()                      -> create the app instance, the main entrypoint
# @app.get/post/put/delete(path)  -> path operation decorators (one per HTTP method)
# def vs async def               -> both work; async def for async I/O, def runs in a threadpool
# {param} + type hint             -> path parameter: conversion + validation + editor support
# Order matters                  -> fixed paths before dynamic paths with the same prefix
# class X(str, Enum)              -> restrict a path param to a fixed set of choices
# Return dict/list/model          -> FastAPI serializes it to JSON automatically
# /docs, /redoc, /openapi.json    -> free, auto-generated interactive documentation
#
# Continue in fastapi2.py for query parameters and validation with Query()/Path().
