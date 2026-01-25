from __future__ import annotations

from app import app
from birds_seed import seed_birds


if __name__ == "__main__":
    db_path = app.config["DATABASE"]
    print(f"Seeding DB: {db_path}")
    inserted, skipped, total = seed_birds(db_path)
    print(f"Inserted/Skipped: {inserted}/{skipped}")
    print(f"Birds after seed: {total}")
