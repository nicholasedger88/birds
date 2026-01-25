from __future__ import annotations

import json
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Iterable
from dataclasses import dataclass

import click
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
                observer TEXT NOT NULL DEFAULT 'Nicholas',
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
                wiki_status TEXT,
                wiki_last_checked TEXT,
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
            "wiki_status": "TEXT",
            "wiki_last_checked": "TEXT",
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
            "observer": "TEXT NOT NULL DEFAULT 'Nicholas'",
        }
        for column, column_type in optional_columns.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE sightings ADD COLUMN {column} {column_type}"
                )


init_db()


def warn_if_birds_empty() -> None:
    with get_connection() as connection:
        birds_count = connection.execute("SELECT COUNT(*) FROM birds").fetchone()[0]
    if birds_count == 0:
        print("Birds table is empty. Run: flask seed-birds")


warn_if_birds_empty()

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

ALLOWED_OBSERVERS = {"Nicholas", "Mark", "Andy"}


@dataclass(frozen=True)
class ParsedMapsLink:
    lat: float
    lng: float
    label_guess: str | None


def normalize_text(value: str) -> str:
    value = value.casefold().strip()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_observer(value: str) -> str:
    if value in ALLOWED_OBSERVERS:
        return value
    return "Nicholas"


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


def parse_maps_link(value: str) -> ParsedMapsLink | None:
    parsed = urllib.parse.urlparse(value)
    query = urllib.parse.parse_qs(parsed.query)
    label_guess = None

    at_match = re.search(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", value)
    if at_match:
        return ParsedMapsLink(
            lat=float(at_match.group(1)),
            lng=float(at_match.group(2)),
            label_guess=None,
        )

    def parse_coord_pair(raw: str) -> tuple[float, float] | None:
        cleaned = raw.strip().replace(" ", "")
        match = re.match(r"^(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)$", cleaned)
        if match:
            return float(match.group(1)), float(match.group(2))
        return None

    for key in ("q", "ll"):
        if key in query:
            candidate = query[key][0]
            coords = parse_coord_pair(candidate)
            if coords:
                return ParsedMapsLink(lat=coords[0], lng=coords[1], label_guess=None)
            label_guess = candidate

    if "query" in query:
        candidate = query["query"][0]
        coords = parse_coord_pair(candidate)
        if coords:
            return ParsedMapsLink(lat=coords[0], lng=coords[1], label_guess=None)
        label_guess = candidate

    return None


@app.route("/api/parse-maps-link", methods=["GET", "POST"])
def parse_maps_link_api():
    url_value = request.values.get("url", "").strip()
    if not url_value:
        return jsonify({"error": "Please provide a Google Maps link."}), 400
    parsed = parse_maps_link(url_value)
    if not parsed:
        return (
            jsonify({"error": "Unable to find coordinates in that Google Maps link."}),
            400,
        )
    google_maps_url = f"https://www.google.com/maps?q={parsed.lat},{parsed.lng}"
    return jsonify(
        {
            "lat": parsed.lat,
            "lng": parsed.lng,
            "label_guess": parsed.label_guess,
            "google_maps_url": google_maps_url,
        }
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


def fetch_wikipedia_thumbnail(title: str) -> tuple[str, str | None]:
    if not title:
        return "error", None
    encoded_title = urllib.parse.quote(title)
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "BirdLog/1.0 (+https://github.com/nicholasedger88/birds)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return "not_found", None
        return "error", None
    except (urllib.error.URLError, json.JSONDecodeError):
        return "error", None
    if payload.get("type") == "disambiguation":
        return "disambiguation", None
    thumbnail = payload.get("thumbnail", {})
    image_url = thumbnail.get("source")
    if not image_url:
        original = payload.get("originalimage", {})
        image_url = original.get("source")
    if image_url and image_url.startswith("http://"):
        image_url = image_url.replace("http://", "https://", 1)
    if image_url:
        return "ok", image_url
    return "no_image", None


def get_bird_thumbnail(connection: sqlite3.Connection, row: sqlite3.Row) -> str | None:
    if row["image_url"]:
        return row["image_url"] or None
    titles = [
        row["wikipedia_title"],
        row["scientific_name"],
        row["common_name_uk"],
    ]
    titles = [title for title in titles if title]
    status = "error"
    image_url = None
    attempted_title = None
    for title in titles:
        status, image_url = fetch_wikipedia_thumbnail(title)
        attempted_title = title
        if status == "ok":
            break
    if not image_url and row["common_name_uk"]:
        common = row["common_name_uk"].strip()
        if len(common.split()) == 1:
            fallback_title = f"{common} (bird)"
            status, image_url = fetch_wikipedia_thumbnail(fallback_title)
            attempted_title = fallback_title
    last_checked = datetime.now(timezone.utc).isoformat()
    if image_url:
        connection.execute(
            """
            UPDATE birds
            SET image_url = ?, wiki_status = ?, wiki_last_checked = ?
            WHERE id = ?
            """,
            (image_url, status, last_checked, row["id"]),
        )
        return image_url
    connection.execute(
        """
        UPDATE birds
        SET wiki_status = ?, wiki_last_checked = ?
        WHERE id = ?
        """,
        (status, last_checked, row["id"]),
    )
    return None


def fetch_sightings() -> Iterable[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                sightings.id,
                sightings.bird_name,
                sightings.location,
                sightings.observer,
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
    observer = request.args.get("observer", "").strip()

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
    if observer:
        observer_value = normalize_observer(observer)
        filters.append("sightings.observer = :observer")
        params["observer"] = observer_value

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
                sightings.observer,
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
                    "observer": row["observer"],
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
    if not image_url:
        image_url = payload.get("originalimage", {}).get("source")
    if image_url and image_url.startswith("http://"):
        image_url = image_url.replace("http://", "https://", 1)
    return jsonify(
        {
            "status": status,
            "title": title,
            "page_type": payload.get("type"),
            "image_url": image_url,
        }
    )


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
    lat = parse_float(request.form.get("lat", "").strip() or None)
    lng = parse_float(request.form.get("lng", "").strip() or None)
    notes = request.form.get("notes", "").strip()
    bird_id = request.form.get("bird_id", "").strip() or None
    bird_text = bird_name if not bird_id else None
    observer = normalize_observer(request.form.get("observer", "").strip())

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
                    notes,
                    observer
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    observer,
                ),
            )

    return redirect(url_for("index"))


@app.cli.command("seed-birds")
def seed_birds_command() -> None:
    print(f"Seeding DB: {app.config['DATABASE']}")
    inserted, skipped, total = seed_birds(app.config["DATABASE"])
    print(f"Inserted/Skipped: {inserted}/{skipped}")
    print(f"Birds after seed: {total}")


def fetch_thumbnails(connection: sqlite3.Connection, limit: int, force: bool) -> dict[str, int]:
    where_clause = ""
    params: dict[str, object] = {"limit": limit}
    if not force:
        where_clause = "WHERE image_url IS NULL OR wiki_status IS NULL OR wiki_status != 'ok'"
    rows = connection.execute(
        f"""
        SELECT id, common_name_uk, scientific_name, wikipedia_title, image_url, wiki_status
        FROM birds
        {where_clause}
        ORDER BY common_name_uk
        LIMIT :limit
        """,
        params,
    ).fetchall()
    counts: dict[str, int] = {
        "ok": 0,
        "not_found": 0,
        "disambiguation": 0,
        "no_image": 0,
        "error": 0,
    }
    for row in rows:
        get_bird_thumbnail(connection, row)
        status_row = connection.execute(
            "SELECT wiki_status FROM birds WHERE id = ?",
            (row["id"],),
        ).fetchone()
        status = status_row["wiki_status"] if status_row else "error"
        counts[status] = counts.get(status, 0) + 1
    return counts


@app.cli.command("fetch-thumbnails")
@click.option("--limit", default=200, show_default=True, type=int)
@click.option("--force", is_flag=True, default=False, help="Refetch even if previously checked.")
def fetch_thumbnails_command(limit: int, force: bool) -> None:
    with get_connection() as connection:
        counts = fetch_thumbnails(connection, limit, force)
    for status, count in counts.items():
        print(f"{status}: {count}")


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
