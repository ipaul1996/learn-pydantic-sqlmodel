import time
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Middleware, CORS, and Background Tasks
# Builds on fastapi1-8.py. These three are almost always present in a real
# production API, so they're grouped together here.

app = FastAPI(title="Middleware, CORS & Background Tasks")


# Middleware — code that runs around EVERY request, before the path operation
# and after the response is generated. @app.middleware("http") wraps a function
# that receives the request and a `call_next` callable (which runs the rest of
# the app and returns the response).
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Multiple middleware stack like layers: the LAST one added/declared is the
# OUTERMOST, so it runs first on the way in and last on the way out.
#   add_middleware(A); add_middleware(B)
#   request:  B -> A -> route
#   response: route -> A -> B


@app.get("/slow")
async def slow_endpoint():
    return {"message": "done"}


# CORSMiddleware — needed whenever a browser-based frontend on one origin
# (protocol+domain+port) calls an API on a different origin. Without it, the
# browser blocks the response from reaching the frontend's JavaScript.
# Defaults are restrictive on purpose — you opt in to what you actually need.
origins = [
    "http://localhost:3000",
    "https://myfrontend.example.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # ["*"] allows any origin, but disables credentials support
    allow_credentials=True,  # allow cookies / Authorization headers cross-origin
    allow_methods=["*"],  # or a specific list like ["GET", "POST"]
    allow_headers=["*"],
)


@app.get("/public-data")
async def public_data():
    return {"message": "visible to any allowed origin"}


# Background Tasks — run code AFTER the response has already been sent to the
# client. Good for: sending a notification email, writing an audit log, light
# post-processing — anything the client doesn't need to wait for.
notification_log: list[str] = []


def write_notification(email: str, message: str = ""):
    notification_log.append(f"notification for {email}: {message}")


@app.post("/send-notification/{email}")
async def send_notification(email: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(write_notification, email, message="welcome aboard!")
    return {"message": "Notification will be sent in the background"}


# BackgroundTasks also works through Depends() — FastAPI reuses the SAME
# BackgroundTasks instance across the path operation and any dependency that
# asks for one, merging every .add_task() call into a single list that runs
# once, after the response.
def log_query(background_tasks: BackgroundTasks, q: str | None = None):
    if q:
        background_tasks.add_task(notification_log.append, f"searched for: {q}")
    return q


@app.post("/send-notification-2/{email}")
async def send_notification_2(
    email: str,
    background_tasks: BackgroundTasks,
    q: Annotated[str | None, Depends(log_query)] = None,
):
    background_tasks.add_task(write_notification, email, message="second message")
    return {"message": "queued"}


# Caveat — BackgroundTasks runs in the SAME process as your API. Fine for small,
# quick jobs. For heavy/slow work (video processing, big reports) or work that
# must survive a server restart, use a real task queue instead (e.g. Celery with
# Redis/RabbitMQ) so it can run in its own worker process.


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)

    print("GET /slow — middleware adds an X-Process-Time header to every response")
    r = client.get("/slow")
    print(r.json(), "| X-Process-Time:", r.headers.get("x-process-time"))

    print("\nGET /public-data with an allowed Origin — CORS headers present")
    r = client.get("/public-data", headers={"Origin": "http://localhost:3000"})
    print(r.status_code, dict(r.headers).get("access-control-allow-origin"))

    print("\nGET /public-data with a DISALLOWED Origin — header is simply absent")
    r = client.get("/public-data", headers={"Origin": "http://evil.example.com"})
    print(
        r.status_code, "access-control-allow-origin" in {k.lower() for k in r.headers}
    )

    print(
        "\nPOST /send-notification/indra@example.com — background task runs after the response"
    )
    r = client.post("/send-notification/indra@example.com")
    print(r.json())
    print("notification_log after the call returns:", notification_log)

    print(
        "\nPOST /send-notification-2/...?q=widgets — dependency + route both add tasks"
    )
    r = client.post("/send-notification-2/rick@example.com", params={"q": "widgets"})
    print(r.json())
    print("notification_log now:", notification_log)


# Summary
#
# @app.middleware("http")          -> code that wraps every request/response
# call_next(request)               -> runs the rest of the app, returns the Response
# Multiple middlewares              -> last added = outermost = runs first on the way in
# CORSMiddleware                    -> required for browser frontends on a different origin
#   allow_origins / allow_methods / allow_headers / allow_credentials / max_age
# BackgroundTasks + .add_task(fn, *args, **kwargs) -> runs fn AFTER the response is sent
# BackgroundTasks via Depends()     -> shared/merged with the one used in the path operation
# Heavy or must-survive-restart work -> use a real task queue (Celery, etc.), not BackgroundTasks
#
# Continue in fastapi10.py for authentication: OAuth2, password hashing, and JWT tokens.
