import asyncio
import os
import re
import secrets
import shutil
from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from starlette.background import BackgroundTask

from app import db
from app.config import (
    BASE_URL,
    MAX_DOWNLOADS,
    MAX_UPLOAD_BYTES,
    TTL_SECONDS,
    UPLOAD_DIR,
)

app = FastAPI(title="bashupload alternative", version="0.1.0")

_TOKEN_RE = re.compile(r"^[a-f0-9]{16}$")


def _secure_filename(name: str) -> str:
    base = Path(unquote(name)).name
    base = base.replace("\x00", "").strip()
    if not base or base in (".", ".."):
        return "upload.bin"
    base = os.path.basename(base)
    if len(base) > 255:
        root, ext = os.path.splitext(base)
        base = root[: 255 - len(ext)] + ext
    return base


def _new_token() -> str:
    return secrets.token_hex(8)


async def _stream_request_to_path(request: Request, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    cl = request.headers.get("content-length")
    if cl is not None and MAX_UPLOAD_BYTES > 0:
        try:
            if int(cl) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Payload too large")
        except ValueError:
            pass

    loop = asyncio.get_event_loop()
    try:
        with open(dest, "wb") as f:
            async for chunk in request.stream():
                written += len(chunk)
                if MAX_UPLOAD_BYTES > 0 and written > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Payload too large")
                await loop.run_in_executor(None, f.write, chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise


@app.on_event("startup")
def _startup():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


def _upload_response(token: str, filename: str) -> PlainTextResponse:
    url = f"{BASE_URL}/{token}/{filename}"
    text = f"{url}\n\ncurl -O {url}\n"
    return PlainTextResponse(text)


@app.api_route("/{filename:path}", methods=["PUT"])
async def upload_put(filename: str, request: Request):
    name = _secure_filename(filename)
    token = _new_token()
    dest = UPLOAD_DIR / token / name
    await _stream_request_to_path(request, dest)
    db.insert_upload(token, name, dest, TTL_SECONDS, MAX_DOWNLOADS)
    return _upload_response(token, name)


@app.api_route("/{filename:path}", methods=["POST"])
async def upload_post(filename: str, request: Request):
    ct = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in ct:
        raise HTTPException(status_code=400, detail="Use POST / for multipart uploads")
    name = _secure_filename(filename)
    token = _new_token()
    dest = UPLOAD_DIR / token / name
    await _stream_request_to_path(request, dest)
    db.insert_upload(token, name, dest, TTL_SECONDS, MAX_DOWNLOADS)
    return _upload_response(token, name)


@app.post("/")
async def upload_multipart(request: Request):
    ct = request.headers.get("content-type", "").lower()
    if "multipart/form-data" not in ct:
        raise HTTPException(
            status_code=400,
            detail="Send multipart/form-data or PUT/POST with a filename in the path",
        )
    form = await request.form()
    files: list[tuple[str, UploadFile]] = []
    for _, val in form.multi_items():
        if isinstance(val, UploadFile) and val.filename:
            files.append((_secure_filename(val.filename), val))
    if not files:
        raise HTTPException(status_code=400, detail="No file fields in multipart body")

    token = _new_token()
    dest_dir = UPLOAD_DIR / token
    dest_dir.mkdir(parents=True, exist_ok=True)
    urls: list[str] = []
    loop = asyncio.get_event_loop()
    for fname, uf in files:
        path = dest_dir / fname
        with open(path, "wb") as out:
            while True:
                chunk = await uf.read(1024 * 1024)
                if not chunk:
                    break
                await loop.run_in_executor(None, out.write, chunk)
        if MAX_UPLOAD_BYTES > 0 and path.stat().st_size > MAX_UPLOAD_BYTES:
            shutil.rmtree(dest_dir, ignore_errors=True)
            raise HTTPException(status_code=413, detail="Payload too large")
        db.insert_upload(token, fname, path, TTL_SECONDS, MAX_DOWNLOADS)
        urls.append(f"{BASE_URL}/{token}/{fname}")

    body = "\n".join(urls) + "\n\nwget " + " ".join(urls) + "\n"
    return PlainTextResponse(body)


@app.get("/{token}/{filename:path}")
async def download(token: str, filename: str):
    if not _TOKEN_RE.match(token):
        raise HTTPException(status_code=404, detail="Not found")
    name = _secure_filename(filename)
    path = db.try_claim_download(token, name)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    def cleanup():
        try:
            if path.is_file():
                path.unlink()
            parent = path.parent
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
            db.delete_upload(token, name)
        except OSError:
            pass

    if MAX_DOWNLOADS <= 1:
        return FileResponse(
            path,
            filename=name,
            background=BackgroundTask(cleanup),
        )
    return FileResponse(path, filename=name)
