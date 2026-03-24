import os
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return int(v)


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "data/uploads")).resolve()
DB_PATH = Path(os.environ.get("DB_PATH", "data/uploads.db")).resolve()

# Default: 3 days (bashupload-style)
TTL_SECONDS = _env_int("TTL_SECONDS", 3 * 24 * 60 * 60)
MAX_DOWNLOADS = _env_int("MAX_DOWNLOADS", 1)
# 0 = no limit
MAX_UPLOAD_BYTES = _env_int("MAX_UPLOAD_BYTES", 0)
