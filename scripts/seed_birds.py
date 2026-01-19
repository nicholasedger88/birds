from __future__ import annotations

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "birds.db"

BIRDS = [
    {
        "common_name_uk": "Blackbird",
        "scientific_name": "Turdus merula",
        "aliases": "Eurasian Blackbird",
    },
    {
        "common_name_uk": "Robin",
        "scientific_name": "Erithacus rubecula",
        "aliases": "European Robin",
    },
    {"common_name_uk": "Blue Tit", "scientific_name": "Cyanistes caeruleus"},
    {"common_name_uk": "Great Tit", "scientific_name": "Parus major"},
    {"common_name_uk": "Coal Tit", "scientific_name": "Periparus ater"},
    {"common_name_uk": "Long-tailed Tit", "scientific_name": "Aegithalos caudatus"},
    {"common_name_uk": "Wren", "scientific_name": "Troglodytes troglodytes"},
    {"common_name_uk": "Dunnock", "scientific_name": "Prunella modularis"},
    {"common_name_uk": "Chaffinch", "scientific_name": "Fringilla coelebs"},
    {"common_name_uk": "Goldfinch", "scientific_name": "Carduelis carduelis"},
    {"common_name_uk": "Greenfinch", "scientific_name": "Chloris chloris"},
    {"common_name_uk": "Bullfinch", "scientific_name": "Pyrrhula pyrrhula"},
    {"common_name_uk": "House Sparrow", "scientific_name": "Passer domesticus"},
    {"common_name_uk": "Tree Sparrow", "scientific_name": "Passer montanus"},
    {"common_name_uk": "Starling", "scientific_name": "Sturnus vulgaris"},
    {"common_name_uk": "Magpie", "scientific_name": "Pica pica"},
    {"common_name_uk": "Jay", "scientific_name": "Garrulus glandarius"},
    {"common_name_uk": "Jackdaw", "scientific_name": "Corvus monedula"},
    {"common_name_uk": "Carrion Crow", "scientific_name": "Corvus corone"},
    {"common_name_uk": "Rook", "scientific_name": "Corvus frugilegus"},
    {"common_name_uk": "Song Thrush", "scientific_name": "Turdus philomelos"},
    {"common_name_uk": "Mistle Thrush", "scientific_name": "Turdus viscivorus"},
    {"common_name_uk": "Blackcap", "scientific_name": "Sylvia atricapilla"},
    {"common_name_uk": "Garden Warbler", "scientific_name": "Sylvia borin"},
    {"common_name_uk": "Chiffchaff", "scientific_name": "Phylloscopus collybita"},
    {"common_name_uk": "Willow Warbler", "scientific_name": "Phylloscopus trochilus"},
    {"common_name_uk": "Sedge Warbler", "scientific_name": "Acrocephalus schoenobaenus"},
    {"common_name_uk": "Whitethroat", "scientific_name": "Curruca communis"},
    {"common_name_uk": "Linnet", "scientific_name": "Linaria cannabina"},
    {"common_name_uk": "Redpoll", "scientific_name": "Acanthis flammea"},
    {"common_name_uk": "Siskin", "scientific_name": "Spinus spinus"},
    {"common_name_uk": "Nuthatch", "scientific_name": "Sitta europaea"},
    {"common_name_uk": "Treecreeper", "scientific_name": "Certhia familiaris"},
    {"common_name_uk": "Great Spotted Woodpecker", "scientific_name": "Dendrocopos major"},
    {"common_name_uk": "Green Woodpecker", "scientific_name": "Picus viridis"},
    {"common_name_uk": "Kestrel", "scientific_name": "Falco tinnunculus"},
    {"common_name_uk": "Sparrowhawk", "scientific_name": "Accipiter nisus"},
    {"common_name_uk": "Buzzard", "scientific_name": "Buteo buteo"},
    {"common_name_uk": "Barn Owl", "scientific_name": "Tyto alba"},
    {"common_name_uk": "Tawny Owl", "scientific_name": "Strix aluco"},
    {"common_name_uk": "Pheasant", "scientific_name": "Phasianus colchicus"},
    {"common_name_uk": "Grey Partridge", "scientific_name": "Perdix perdix"},
    {"common_name_uk": "Collared Dove", "scientific_name": "Streptopelia decaocto"},
    {"common_name_uk": "Woodpigeon", "scientific_name": "Columba palumbus"},
    {"common_name_uk": "Stock Dove", "scientific_name": "Columba oenas"},
    {"common_name_uk": "Swift", "scientific_name": "Apus apus"},
    {"common_name_uk": "Swallow", "scientific_name": "Hirundo rustica"},
    {"common_name_uk": "House Martin", "scientific_name": "Delichon urbicum"},
    {"common_name_uk": "Sand Martin", "scientific_name": "Riparia riparia"},
    {"common_name_uk": "Coot", "scientific_name": "Fulica atra"},
    {"common_name_uk": "Moorhen", "scientific_name": "Gallinula chloropus"},
    {"common_name_uk": "Mallard", "scientific_name": "Anas platyrhynchos"},
    {"common_name_uk": "Mute Swan", "scientific_name": "Cygnus olor"},
    {"common_name_uk": "Canada Goose", "scientific_name": "Branta canadensis"},
    {"common_name_uk": "Greylag Goose", "scientific_name": "Anser anser"},
    {"common_name_uk": "Heron", "scientific_name": "Ardea cinerea", "aliases": "Grey Heron"},
    {"common_name_uk": "Little Egret", "scientific_name": "Egretta garzetta"},
    {"common_name_uk": "Oystercatcher", "scientific_name": "Haematopus ostralegus"},
    {"common_name_uk": "Lapwing", "scientific_name": "Vanellus vanellus"},
    {"common_name_uk": "Curlew", "scientific_name": "Numenius arquata"},
    {"common_name_uk": "Redshank", "scientific_name": "Tringa totanus"},
]


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS birds (
            id INTEGER PRIMARY KEY,
            common_name_uk TEXT NOT NULL,
            scientific_name TEXT,
            aliases TEXT,
            image_url TEXT
        )
        """
    )


def seed_birds() -> None:
    with get_connection() as connection:
        ensure_table(connection)
        for bird in BIRDS:
            existing = connection.execute(
                "SELECT id FROM birds WHERE common_name_uk = ?",
                (bird["common_name_uk"],),
            ).fetchone()
            if existing:
                continue
            connection.execute(
                """
                INSERT INTO birds (common_name_uk, scientific_name, aliases, image_url)
                VALUES (?, ?, ?, ?)
                """,
                (
                    bird["common_name_uk"],
                    bird.get("scientific_name"),
                    bird.get("aliases"),
                    bird.get("image_url"),
                ),
            )


if __name__ == "__main__":
    seed_birds()
    print(f"Seeded {len(BIRDS)} UK birds into {DB_PATH}.")
