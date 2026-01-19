from __future__ import annotations

import json
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable

from flask import Flask, jsonify, redirect, render_template, request, url_for

from birds_seed import seed_birds
from db import DB_PATH

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
                bird_id INTEGER,
                bird_text TEXT,
                latitude REAL,
                longitude REAL,
                lat REAL,
                lng REAL,
                location_label TEXT,
                latin_name TEXT,
                description TEXT,
                behavior TEXT,
                notes TEXT,
                spotted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS birds (
                id INTEGER PRIMARY KEY,
                common_name_uk TEXT NOT NULL,
                scientific_name TEXT,
                aliases TEXT,
                wikipedia_title TEXT,
                image_url TEXT
            )
            """
        )
        bird_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(birds)").fetchall()
        }
        birds_optional = {
            "scientific_name": "TEXT",
            "aliases": "TEXT",
            "wikipedia_title": "TEXT",
            "image_url": "TEXT",
        }
        for column, column_type in birds_optional.items():
            if column not in bird_columns:
                connection.execute(f"ALTER TABLE birds ADD COLUMN {column} {column_type}")
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(sightings)").fetchall()
        }
        optional_columns = {
            "bird_id": "INTEGER",
            "bird_text": "TEXT",
            "latitude": "REAL",
            "longitude": "REAL",
            "lat": "REAL",
            "lng": "REAL",
            "location_label": "TEXT",
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


def normalize_text(value: str) -> str:
    value = value.casefold().strip()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def bird_profile_for_name(name: str) -> dict[str, str]:
    normalized = name.casefold()
    for bird_name, profile in BIRD_PROFILES.items():
        if bird_name.casefold() == normalized:
            return profile
    return {}


def match_score(query: str, candidate: str) -> tuple[int, int]:
    if candidate.startswith(query):
        return (0, 0)
    return (1, candidate.find(query))


def fetch_wikipedia_thumbnail(title: str) -> str | None:
    if not title:
        return None
    encoded_title = urllib.parse.quote(title)
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError):
        return None
    thumbnail = payload.get("thumbnail", {})
    return thumbnail.get("source")


def resolve_bird_thumbnail(connection: sqlite3.Connection, row: sqlite3.Row) -> str | None:
    if row["image_url"]:
        return row["image_url"]
    title = row["wikipedia_title"] or row["common_name_uk"] or row["scientific_name"]
    image_url = fetch_wikipedia_thumbnail(title)
    if image_url:
        connection.execute(
            "UPDATE birds SET image_url = ? WHERE id = ?",
            (image_url, row["id"]),
        )
    return image_url


def fetch_sightings() -> Iterable[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                sightings.id,
                sightings.bird_name,
                sightings.location,
                sightings.bird_id,
                sightings.bird_text,
                COALESCE(sightings.lat, sightings.latitude) AS lat,
                COALESCE(sightings.lng, sightings.longitude) AS lng,
                sightings.location_label,
                sightings.latin_name,
                sightings.description,
                sightings.behavior,
                sightings.notes,
                sightings.spotted_at,
                birds.common_name_uk,
                birds.scientific_name,
                birds.wikipedia_title,
                birds.image_url
            FROM sightings
            LEFT JOIN birds ON birds.id = sightings.bird_id
            ORDER BY sightings.spotted_at DESC, sightings.id DESC
            """
        ).fetchall()


@app.route("/api/birds", methods=["GET"])
def search_birds():
    query = normalize_text(request.args.get("q", ""))
    if not query:
        return jsonify([])

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                common_name_uk,
                scientific_name,
                aliases,
                wikipedia_title,
                image_url
            FROM birds
            """
        ).fetchall()

        matches: list[tuple[tuple[int, int], sqlite3.Row]] = []
        for row in rows:
            values = [row["common_name_uk"]]
            if row["aliases"]:
                values.extend(alias.strip() for alias in row["aliases"].split(","))
            normalized_values = [normalize_text(value) for value in values if value]
            scores = [
                match_score(query, value)
                for value in normalized_values
                if query in value
            ]
            if scores:
                matches.append((min(scores), row))

        matches.sort(key=lambda item: item[0])
        response = []
        for _, row in matches[:10]:
            image_url = resolve_bird_thumbnail(connection, row)
            response.append(
                {
                    "id": row["id"],
                    "common_name_uk": row["common_name_uk"],
                    "scientific_name": row["scientific_name"],
                    "image_url": image_url,
                }
            )
    return jsonify(response)


@app.route("/", methods=["GET"])
def index() -> str:
    sightings = fetch_sightings()
    return render_template("index.html", sightings=sightings)


@app.route("/sightings", methods=["POST"])
def create_sighting():
    bird_name = request.form.get("bird_name", "").strip()
    location = request.form.get("location", "").strip()
    location_label = request.form.get("location_label", "").strip()
    lat = request.form.get("lat", "").strip() or None
    lng = request.form.get("lng", "").strip() or None
    notes = request.form.get("notes", "").strip()
    bird_id = request.form.get("bird_id", "").strip() or None
    bird_text = bird_name if not bird_id else None

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
                    bird_id,
                    bird_text,
                    lat,
                    lng,
                    location_label,
                    latin_name,
                    description,
                    behavior,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bird_name,
                    location,
                    int(bird_id) if bird_id else None,
                    bird_text,
                    lat,
                    lng,
                    location_label or None,
                    latin_name,
                    description,
                    behavior,
                    notes or None,
                ),
            )

    return redirect(url_for("index"))


@app.cli.command("seed-birds")
def seed_birds_command() -> None:
    count = seed_birds(DB_PATH)
    print(f"Seeded {count} UK birds into {DB_PATH}.")


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
