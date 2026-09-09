from typing import Annotated

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse

# Beyond JSON — Files, Forms, Custom Responses & WebSockets
# Builds on fastapi1-3.py. Not every request/response is a JSON body — file
# uploads, HTML forms, streamed data, and full-duplex WebSocket connections all
# need a different shape. python-multipart must be installed for File()/Form()
# to work (it's what parses "multipart/form-data").

app = FastAPI(title="Files, Forms, Responses & WebSockets")


# bytes vs UploadFile — File(...) with type `bytes` reads the WHOLE file into
# memory as raw bytes. Simple, but risky for large files (all of it sits in RAM).
@app.post("/files/bytes/")
async def create_file(file: Annotated[bytes, File()]):
    return {"file_size": len(file)}


# UploadFile is the better default for anything beyond tiny files: it's backed by
# a "spooled" temp file (stays in memory up to a size limit, then spills to disk),
# exposes metadata (.filename, .content_type), and has an async file-like API:
# await file.read(), await file.write(...), await file.seek(0), await file.close().
@app.post("/files/upload/")
async def create_upload_file(file: UploadFile):
    contents = await file.read()
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(contents),
    }


# Multiple files — declare a list[UploadFile] (or list[bytes]) to accept several
# files sent under the same form field name.
@app.post("/files/upload-multiple/")
async def create_upload_files(files: list[UploadFile]):
    return {"filenames": [f.filename for f in files]}


# File + Form together — you CAN mix File()/Form() params in one endpoint, but you
# CANNOT also add a plain JSON Body() field alongside them: once the request has
# any File/Form field, the whole body is "multipart/form-data", not "application/json".
@app.post("/files/upload-with-token/")
async def create_file_with_token(
    file: Annotated[UploadFile, File()],
    token: Annotated[str, Form()],
):
    contents = await file.read()
    return {"token": token, "filename": file.filename, "size": len(contents)}


# Custom responses — FastAPI returns JSON by default. response_class documents
# the Content-Type in OpenAPI AND lets you return the raw content directly.
@app.get("/page", response_class=HTMLResponse)
async def get_page():
    return "<html><body><h1>Look ma, HTML!</h1></body></html>"


@app.get("/plain", response_class=PlainTextResponse)
async def get_plain():
    return "just plain text, no quotes around it"


# StreamingResponse — takes a generator (sync or async) and streams the body
# chunk by chunk instead of building the whole response in memory first. Good
# for large exports, live logs, or proxying another streaming source.
async def fake_video_streamer():
    for i in range(3):
        yield f"chunk-{i}".encode()


@app.get("/stream")
async def stream_video():
    return StreamingResponse(fake_video_streamer(), media_type="text/plain")


# WebSockets — a persistent, two-way connection (unlike request/response HTTP).
# @app.websocket(...) instead of @app.get/post(...). accept() the connection,
# then receive_text()/send_text() in a loop. WebSocketDisconnect is raised when
# the client closes the connection — catch it to clean up (e.g. remove from a
# list of active connections in a chat app).
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}")
    except WebSocketDisconnect:
        pass  # client closed the connection — nothing else to clean up in this demo


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)

    print("POST /files/bytes/ — whole file read into memory as bytes")
    r = client.post("/files/bytes/", files={"file": ("notes.txt", b"hello world")})
    print(r.json())

    print("\nPOST /files/upload/ — UploadFile exposes filename + content_type")
    r = client.post(
        "/files/upload/",
        files={"file": ("photo.png", b"\x89PNG-fake-bytes", "image/png")},
    )
    print(r.json())

    print("\nPOST /files/upload-multiple/ — several files, one field name")
    r = client.post(
        "/files/upload-multiple/",
        files=[
            ("files", ("a.txt", b"AAA")),
            ("files", ("b.txt", b"BBBB")),
        ],
    )
    print(r.json())

    print("\nPOST /files/upload-with-token/ — File() + Form() in the same request")
    r = client.post(
        "/files/upload-with-token/",
        data={"token": "abc123"},
        files={"file": ("report.csv", b"a,b,c\n1,2,3")},
    )
    print(r.json())

    print("\nGET /page — response_class=HTMLResponse")
    r = client.get("/page")
    print(r.headers["content-type"], "|", r.text)

    print("\nGET /plain — response_class=PlainTextResponse")
    r = client.get("/plain")
    print(r.headers["content-type"], "|", r.text)

    print("\nGET /stream — chunks arrive as a StreamingResponse")
    r = client.get("/stream")
    print(r.text)

    print("\nWebSocket /ws — send two messages over one connection")
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text("hello")
        print(websocket.receive_text())
        websocket.send_text("again")
        print(websocket.receive_text())


# Summary
#
# file: Annotated[bytes, File()]  -> whole file in memory; fine for small files
# file: UploadFile                -> spooled temp file + async read/write/seek/close +
#                                     .filename / .content_type metadata; prefer this
# files: list[UploadFile]         -> multiple files under one form field
# File() + Form() together        -> allowed; NOT alongside a JSON Body() in the same request
# response_class=HTMLResponse/PlainTextResponse/... -> documents + sets the Content-Type
# StreamingResponse(generator)    -> stream a body chunk by chunk instead of building it all first
# @app.websocket("/ws")            -> persistent two-way connection; accept()/receive_text()/send_text()
# WebSocketDisconnect               -> raised when the client disconnects; catch it to clean up
#
# Continue in fastapi12.py for lifespan events (startup/shutdown) and testing patterns.
