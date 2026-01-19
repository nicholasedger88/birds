from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from flask import Flask, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "birds.db"

app = Flask(__name__)


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sightings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bird_name TEXT NOT NULL,
                location TEXT NOT NULL,
                latin_name TEXT,
                description TEXT,
                behavior TEXT,
                notes TEXT,
                spotted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(sightings)").fetchall()
        }
        optional_columns = {
            "latin_name": "TEXT",
            "description": "TEXT",
            "behavior": "TEXT",
        }
        for column, column_type in optional_columns.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE sightings ADD COLUMN {column} {column_type}"
                )


init_db()

BIRD_PROFILES = {
    "Northern Cardinal": {
        "latin_name": "Cardinalis cardinalis",
        "description": "A vivid red songbird with a crest and stout bill.",
        "behavior": "Often seen at feeders, singing from high perches.",
    },
    "American Robin": {
        "latin_name": "Turdus migratorius",
        "description": "A gray-brown thrush with a warm orange breast.",
        "behavior": "Runs across lawns searching for worms and insects.",
    },
    "Blue Jay": {
        "latin_name": "Cyanocitta cristata",
        "description": "A blue-and-white corvid with a bold crest.",
        "behavior": "Noisy flocks, mimics calls, caches acorns.",
    },
    "Barn Swallow": {
        "latin_name": "Hirundo rustica",
        "description": "Streamlined swallow with a forked tail and blue back.",
        "behavior": "Skims over water catching insects in flight.",
    },
    "Great Egret": {
        "latin_name": "Ardea alba",
        "description": "Tall white heron with elegant plume-like feathers.",
        "behavior": "Stalks shallow water, spearing fish with patience.",
    },
}


def bird_profile_for_name(name: str) -> dict[str, str]:
    normalized = name.casefold()
    for bird_name, profile in BIRD_PROFILES.items():
        if bird_name.casefold() == normalized:
            return profile
    return {}


def fetch_sightings() -> Iterable[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                id,
                bird_name,
                location,
                latin_name,
                description,
                behavior,
                notes,
                spotted_at
            FROM sightings
            ORDER BY spotted_at DESC, id DESC
            """
        ).fetchall()


@app.route("/", methods=["GET"])
def index() -> str:
    sightings = fetch_sightings()
    return render_template("index.html", sightings=sightings)


@app.route("/sightings", methods=["POST"])
def create_sighting():
    bird_name = request.form.get("bird_name", "").strip()
    location = request.form.get("location", "").strip()
    notes = request.form.get("notes", "").strip()

    profile = bird_profile_for_name(bird_name)
    latin_name = profile.get("latin_name")
    description = profile.get("description")
    behavior = profile.get("behavior")

    if bird_name and location:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO sightings (
                    bird_name,
                    location,
                    latin_name,
                    description,
                    behavior,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    bird_name,
                    location,
                    latin_name,
                    description,
                    behavior,
                    notes or None,
                ),
            )

    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
