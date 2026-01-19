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
                latitude REAL,
                longitude REAL,
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
            "latitude": "REAL",
            "longitude": "REAL",
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


def fetch_sightings() -> Iterable[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                id,
                bird_name,
                location,
                latitude,
                longitude,
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
    latitude = request.form.get("latitude", "").strip() or None
    longitude = request.form.get("longitude", "").strip() or None
    latin_name = request.form.get("latin_name", "").strip()
    description = request.form.get("description", "").strip()
    behavior = request.form.get("behavior", "").strip()
    notes = request.form.get("notes", "").strip()

    if not location and latitude and longitude:
        location = f"{latitude}, {longitude}"

    if bird_name and location:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO sightings (
                    bird_name,
                    location,
                    latitude,
                    longitude,
                    latin_name,
                    description,
                    behavior,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bird_name,
                    location,
                    latitude,
                    longitude,
                    latin_name or None,
                    description or None,
                    behavior or None,
                    notes or None,
                ),
            )

    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
