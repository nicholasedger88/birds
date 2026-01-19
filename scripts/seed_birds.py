from __future__ import annotations

from app import app
from birds_seed import seed_birds


if __name__ == "__main__":
    db_path = app.config["DATABASE"]
    print(f"Using database: {db_path}")
    count = seed_birds(db_path)
    print(f"Birds in table after seed: {count}")
