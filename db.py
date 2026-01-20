from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = Path(
    os.environ.get(
        "BIRDS_DB_PATH",
        BASE_DIR / "birds.db",
    )
).resolve()