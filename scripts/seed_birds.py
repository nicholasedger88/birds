from __future__ import annotations

from birds_seed import seed_birds
from db import DB_PATH


if __name__ == "__main__":
    count = seed_birds(DB_PATH)
    print(f"Seeded {count} UK birds into {DB_PATH}.")
