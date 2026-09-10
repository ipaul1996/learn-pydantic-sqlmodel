from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Handling Errors
# Builds on fastapi1-4.py. When something goes wrong on the CLIENT's side
# (bad input, missing resource, no permission), you respond with a 4xx status
# code instead of crashing — HTTPException is how you do that in FastAPI.

app = FastAPI(title="Handling Errors")

items = {"foo": "The Foo Wrestlers"}


# HTTPException is a normal Python exception — you raise it, you don't return it.
# Raising it immediately stops the rest of the function and sends the error
# straight to the client, which is exactly what you want for "this doesn't exist"
# or "you're not allowed" checks, even deep inside a helper function.
@app.get("/items/{item_id}")
async def read_item(item_id: str):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item": items[item_id]}


# Custom headers on an error — occasionally needed for auth flows (e.g. WWW-Authenticate).
@app.get("/items-header/{item_id}")
async def read_item_header(item_id: str):
    if item_id not in items:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
            headers={"X-Error": "There goes my error"},
        )
    return {"item": items[item_id]}


# Custom exception + custom handler — for errors that aren't a simple HTTPException,
# define your own exception class and register a handler with @app.exception_handler().
# FastAPI/Starlette catches it anywhere it's raised and runs your handler instead
# of the default 500.
class UnicornException(Exception):
    def __init__(self, name: str):
        self.name = name


@app.exception_handler(UnicornException)
async def unicorn_exception_handler(request: Request, exc: UnicornException):
    return JSONResponse(
        status_code=418,
        content={"message": f"Oops! {exc.name} did something. There goes a rainbow..."},
    )


@app.get("/unicorns/{name}")
async def read_unicorn(name: str):
    if name == "yolo":
        raise UnicornException(name=name)
    return {"unicorn_name": name}


# Overriding the default validation error handler — FastAPI raises its own
# RequestValidationError when incoming data fails Pydantic validation, with a
# default handler that returns the {"detail": [...]} shape you've seen in
# fastapi1-3.py. You can override it, e.g. to return plain text instead.
#
# Note: register the handler for Starlette's HTTPException (StarletteHTTPException),
# not FastAPI's. FastAPI's HTTPException is a subclass of Starlette's — the only
# difference is FastAPI's accepts any JSON-able `detail`, not just a string. Any
# HTTPException you raise (FastAPI's or a plain Starlette one from internal code)
# will be caught by a handler registered for the Starlette base class.
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Gotcha: exc.headers (e.g. a custom X-Error, or WWW-Authenticate for auth flows
    # in fastapi10.py) is NOT applied automatically once you override the handler —
    # forward it yourself, or you'll silently lose headers callers may depend on.
    return PlainTextResponse(
        str(exc.detail), status_code=exc.status_code, headers=exc.headers
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # exc.body holds the raw invalid payload the client sent — useful for logging/debugging.
    # jsonable_encoder converts non-JSON-native values (dates, etc.) before returning them.
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
    )


@app.post("/validate/{item_id}")
async def validate_item(item_id: int):
    return {"item_id": item_id}


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)

    print("GET /items/foo — exists")
    print(client.get("/items/foo").json())

    print("\nGET /items/bar — HTTPException(404), now rendered as plain text")
    r = client.get("/items/bar")
    print(r.status_code, r.text)  # overridden handler -> plain text, not JSON

    print("\nGET /items-header/bar — custom header on the error response")
    r = client.get("/items-header/bar")
    print(r.status_code, dict(r.headers).get("x-error"))

    print("\nGET /unicorns/yolo — custom exception -> custom handler -> 418")
    r = client.get("/unicorns/yolo")
    print(r.status_code, r.json())

    print("\nGET /unicorns/rick — no exception raised")
    print(client.get("/unicorns/rick").json())

    print("\nPOST /validate/not-an-int — overridden RequestValidationError handler")
    r = client.post("/validate/not-an-int")
    print(r.status_code, r.json())


# Summary
#
# raise HTTPException(status_code=404, detail="...")   -> stop execution, send a 4xx error
# headers={...} on HTTPException                       -> add custom response headers
# Custom Exception + @app.exception_handler(MyError)   -> handle app-specific errors globally
# @app.exception_handler(StarletteHTTPException)        -> override the default HTTPException handler
# @app.exception_handler(RequestValidationError)         -> override the default 422 validation handler
# exc.errors() / exc.body                                -> structured errors + raw invalid payload
# jsonable_encoder(...)                                  -> make arbitrary Python data JSON-safe
#
# Continue in fastapi6.py for Dependency Injection — FastAPI's `Depends()` system.
