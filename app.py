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
app.config["DATABASE"] = str(DB_PATH)
print(f"Using database: {app.config['DATABASE']}")


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(app.config["DATABASE"])
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
                image_url TEXT,
                UNIQUE(common_name_uk, scientific_name)
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS birds_unique_name
            ON birds (common_name_uk, scientific_name)
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


def normalized_sql(column: str) -> str:
    return (
        "lower(replace(replace(replace(replace(replace("
        f"coalesce({column}, ''), '.', ' '), ',', ' '), '-', ' '), '''', ''), '’', ' '))"
    )


def search_birds_query(connection: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    normalized_query = normalize_text(query)
    if not normalized_query:
        return []
    prefix = f"{normalized_query}%"
    substring = f"%{normalized_query}%"
    common_expr = normalized_sql("common_name_uk")
    aliases_expr = normalized_sql("aliases")
    return connection.execute(
        f"""
        SELECT
            id,
            common_name_uk,
            scientific_name,
            aliases,
            wikipedia_title,
            image_url
        FROM birds
        WHERE
            {common_expr} LIKE :prefix
            OR {common_expr} LIKE :substring
            OR {aliases_expr} LIKE :substring
        ORDER BY
            CASE
                WHEN {common_expr} LIKE :prefix THEN 1
                WHEN {common_expr} LIKE :substring THEN 2
                ELSE 3
            END,
            common_name_uk
        LIMIT 10
        """,
        {"prefix": prefix, "substring": substring},
    ).fetchall()


def fetch_wikipedia_thumbnail(title: str) -> str | None:
    if not title:
        return None
    encoded_title = urllib.parse.quote(title)
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "BirdLog/1.0 (+https://github.com/nicholasedger88/birds)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError):
        return None
    thumbnail = payload.get("thumbnail", {})
    image_url = thumbnail.get("source")
    if image_url and image_url.startswith("http://"):
        image_url = image_url.replace("http://", "https://", 1)
    return image_url


def get_bird_thumbnail(connection: sqlite3.Connection, row: sqlite3.Row) -> str | None:
    if row["image_url"]:
        return row["image_url"] or None
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
    with get_connection() as connection:
        rows = search_birds_query(connection, request.args.get("q", ""))
        response = []
        for index, row in enumerate(rows):
            image_url = row["image_url"]
            if image_url is None and index < 5:
                image_url = get_bird_thumbnail(connection, row)
            response.append(
                {
                    "id": row["id"],
                    "common_name_uk": row["common_name_uk"],
                    "scientific_name": row["scientific_name"],
                    "image_url": image_url,
                }
            )
    return jsonify(response)


@app.route("/api/sightings", methods=["GET"])
def sightings_api():
    from_date = request.args.get("from", "").strip()
    to_date = request.args.get("to", "").strip()
    only_geocoded = request.args.get("only_geocoded", "").strip() == "1"
    bird_id = request.args.get("bird_id", "").strip()

    filters = []
    params: dict[str, str] = {}

    if from_date:
        filters.append("sightings.spotted_at >= :from_date")
        params["from_date"] = f"{from_date} 00:00:00"
    if to_date:
        filters.append("sightings.spotted_at < datetime(:to_date, '+1 day')")
        params["to_date"] = f"{to_date} 00:00:00"
    if only_geocoded:
        filters.append(
            "COALESCE(sightings.lat, sightings.latitude) IS NOT NULL "
            "AND COALESCE(sightings.lng, sightings.longitude) IS NOT NULL"
        )
    if bird_id:
        filters.append("sightings.bird_id = :bird_id")
        params["bird_id"] = bird_id

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT
                sightings.id,
                sightings.spotted_at,
                sightings.description,
                sightings.behavior,
                sightings.notes,
                COALESCE(sightings.lat, sightings.latitude) AS lat,
                COALESCE(sightings.lng, sightings.longitude) AS lng,
                birds.common_name_uk,
                birds.scientific_name,
                birds.wikipedia_title,
                birds.image_url
            FROM sightings
            LEFT JOIN birds ON birds.id = sightings.bird_id
            {where_clause}
            ORDER BY sightings.spotted_at DESC, sightings.id DESC
            """,
            params,
        ).fetchall()

        response = []
        for row in rows:
            image_url = row["image_url"]
            if image_url is None and row["common_name_uk"]:
                image_url = get_bird_thumbnail(connection, row)
            wiki_title = row["wikipedia_title"] or row["common_name_uk"] or row[
                "scientific_name"
            ]
            wiki_url = (
                f"https://en.wikipedia.org/wiki/{urllib.parse.quote(wiki_title)}"
                if wiki_title
                else None
            )
            google_maps_url = None
            if row["lat"] is not None and row["lng"] is not None:
                google_maps_url = (
                    f"https://www.google.com/maps?q={row['lat']},{row['lng']}"
                )
            response.append(
                {
                    "id": row["id"],
                    "created_at": row["spotted_at"],
                    "common_name_uk": row["common_name_uk"],
                    "scientific_name": row["scientific_name"],
                    "image_url": image_url,
                    "wiki_url": wiki_url,
                    "description": row["description"],
                    "behavior": row["behavior"],
                    "notes": row["notes"],
                    "lat": row["lat"],
                    "lng": row["lng"],
                    "google_maps_url": google_maps_url,
                }
            )
    return jsonify(response)


@app.route("/api/debug/db-info", methods=["GET"])
def debug_db_info():
    with get_connection() as connection:
        tables = [
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
        ]
        birds_count = connection.execute("SELECT COUNT(*) FROM birds").fetchone()[0]
    return jsonify(
        {
            "database_path": str(app.config["DATABASE"]),
            "tables": tables,
            "birds_count": birds_count,
        }
    )


@app.route("/api/debug/db", methods=["GET"])
def debug_db():
    with get_connection() as connection:
        birds_count = connection.execute("SELECT COUNT(*) FROM birds").fetchone()[0]
    return jsonify(
        {
            "db_path": str(app.config["DATABASE"]),
            "birds_count": birds_count,
        }
    )


@app.route("/api/debug/birds-sample", methods=["GET"])
def debug_birds_sample():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT common_name_uk, wikipedia_title, image_url
            FROM birds
            ORDER BY common_name_uk
            LIMIT 5
            """
        ).fetchall()
    return jsonify(
        [
            {
                "common_name_uk": row["common_name_uk"],
                "wikipedia_title": row["wikipedia_title"],
                "image_url": row["image_url"],
            }
            for row in rows
        ]
    )


@app.route("/api/debug/wiki", methods=["GET"])
def debug_wiki():
    title = request.args.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    encoded_title = urllib.parse.quote(title)
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
    request_obj = urllib.request.Request(
        url,
        headers={"User-Agent": "BirdLog/1.0 (+https://github.com/nicholasedger88/birds)"},
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=5) as response:
            payload = json.load(response)
            status = response.status
    except urllib.error.HTTPError as exc:
        return jsonify({"status": exc.code, "error": str(exc)}), exc.code
    except urllib.error.URLError as exc:
        return jsonify({"status": 500, "error": str(exc)}), 500
    thumbnail = payload.get("thumbnail", {})
    image_url = thumbnail.get("source")
    if image_url and image_url.startswith("http://"):
        image_url = image_url.replace("http://", "https://", 1)
    return jsonify({"status": status, "image_url": image_url, "title": title})


@app.route("/api/debug/search-test", methods=["GET"])
def debug_search_test():
    with get_connection() as connection:
        return jsonify(
            {
                "rob": [
                    {
                        "id": row["id"],
                        "common_name_uk": row["common_name_uk"],
                        "scientific_name": row["scientific_name"],
                    }
                    for row in search_birds_query(connection, "rob")
                ],
                "blackbird": [
                    {
                        "id": row["id"],
                        "common_name_uk": row["common_name_uk"],
                        "scientific_name": row["scientific_name"],
                    }
                    for row in search_birds_query(connection, "blackbird")
                ],
            }
        )


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
    print(f"Seeding DB: {app.config['DATABASE']}")
    inserted, skipped, total = seed_birds(app.config["DATABASE"])
    print(f"Inserted/Skipped: {inserted}/{skipped}")
    print(f"Birds after seed: {total}")


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
