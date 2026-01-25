from __future__ import annotations

import sqlite3
from typing import Iterable

from db import DB_PATH

BASE_BIRDS: list[dict[str, str]] = [
    {
        "common_name_uk": "Blackbird",
        "scientific_name": "Turdus merula",
        "aliases": "Eurasian Blackbird",
        "wikipedia_title": "Common blackbird",
    },
    {
        "common_name_uk": "European robin",
        "scientific_name": "Erithacus rubecula",
        "aliases": "Robin",
        "wikipedia_title": "European robin",
    },
    {"common_name_uk": "Blue tit", "scientific_name": "Cyanistes caeruleus"},
    {"common_name_uk": "Great tit", "scientific_name": "Parus major"},
    {"common_name_uk": "Coal tit", "scientific_name": "Periparus ater"},
    {"common_name_uk": "Long-tailed tit", "scientific_name": "Aegithalos caudatus"},
    {"common_name_uk": "Wren", "scientific_name": "Troglodytes troglodytes"},
    {"common_name_uk": "Dunnock", "scientific_name": "Prunella modularis"},
    {"common_name_uk": "Chaffinch", "scientific_name": "Fringilla coelebs"},
    {"common_name_uk": "Goldfinch", "scientific_name": "Carduelis carduelis"},
    {"common_name_uk": "Greenfinch", "scientific_name": "Chloris chloris"},
    {"common_name_uk": "Bullfinch", "scientific_name": "Pyrrhula pyrrhula"},
    {"common_name_uk": "House sparrow", "scientific_name": "Passer domesticus"},
    {"common_name_uk": "Tree sparrow", "scientific_name": "Passer montanus"},
    {"common_name_uk": "Starling", "scientific_name": "Sturnus vulgaris"},
    {"common_name_uk": "Magpie", "scientific_name": "Pica pica"},
    {"common_name_uk": "Jay", "scientific_name": "Garrulus glandarius"},
    {"common_name_uk": "Jackdaw", "scientific_name": "Corvus monedula"},
    {"common_name_uk": "Carrion crow", "scientific_name": "Corvus corone"},
    {"common_name_uk": "Rook", "scientific_name": "Corvus frugilegus"},
    {"common_name_uk": "Song thrush", "scientific_name": "Turdus philomelos"},
    {"common_name_uk": "Mistle thrush", "scientific_name": "Turdus viscivorus"},
    {"common_name_uk": "Blackcap", "scientific_name": "Sylvia atricapilla"},
    {"common_name_uk": "Garden warbler", "scientific_name": "Sylvia borin"},
    {"common_name_uk": "Chiffchaff", "scientific_name": "Phylloscopus collybita"},
    {"common_name_uk": "Willow warbler", "scientific_name": "Phylloscopus trochilus"},
    {"common_name_uk": "Sedge warbler", "scientific_name": "Acrocephalus schoenobaenus"},
    {"common_name_uk": "Whitethroat", "scientific_name": "Curruca communis"},
    {"common_name_uk": "Linnet", "scientific_name": "Linaria cannabina"},
    {"common_name_uk": "Redpoll", "scientific_name": "Acanthis flammea"},
    {"common_name_uk": "Siskin", "scientific_name": "Spinus spinus"},
    {"common_name_uk": "Nuthatch", "scientific_name": "Sitta europaea"},
    {"common_name_uk": "Treecreeper", "scientific_name": "Certhia familiaris"},
    {"common_name_uk": "Great spotted woodpecker", "scientific_name": "Dendrocopos major"},
    {"common_name_uk": "Green woodpecker", "scientific_name": "Picus viridis"},
    {"common_name_uk": "Kestrel", "scientific_name": "Falco tinnunculus"},
    {"common_name_uk": "Sparrowhawk", "scientific_name": "Accipiter nisus"},
    {"common_name_uk": "Buzzard", "scientific_name": "Buteo buteo"},
    {"common_name_uk": "Barn owl", "scientific_name": "Tyto alba"},
    {"common_name_uk": "Tawny owl", "scientific_name": "Strix aluco"},
    {"common_name_uk": "Pheasant", "scientific_name": "Phasianus colchicus"},
    {"common_name_uk": "Grey partridge", "scientific_name": "Perdix perdix"},
    {"common_name_uk": "Collared dove", "scientific_name": "Streptopelia decaocto"},
    {"common_name_uk": "Woodpigeon", "scientific_name": "Columba palumbus"},
    {"common_name_uk": "Stock dove", "scientific_name": "Columba oenas"},
    {"common_name_uk": "Swift", "scientific_name": "Apus apus"},
    {"common_name_uk": "Swallow", "scientific_name": "Hirundo rustica"},
    {"common_name_uk": "House martin", "scientific_name": "Delichon urbicum"},
    {"common_name_uk": "Sand martin", "scientific_name": "Riparia riparia"},
    {"common_name_uk": "Coot", "scientific_name": "Fulica atra"},
    {"common_name_uk": "Moorhen", "scientific_name": "Gallinula chloropus"},
    {"common_name_uk": "Mallard", "scientific_name": "Anas platyrhynchos"},
    {"common_name_uk": "Mute swan", "scientific_name": "Cygnus olor"},
    {"common_name_uk": "Canada goose", "scientific_name": "Branta canadensis"},
    {"common_name_uk": "Greylag goose", "scientific_name": "Anser anser"},
    {
        "common_name_uk": "Grey heron",
        "scientific_name": "Ardea cinerea",
        "aliases": "Heron",
        "wikipedia_title": "Grey heron",
    },
    {"common_name_uk": "Little egret", "scientific_name": "Egretta garzetta"},
    {"common_name_uk": "Oystercatcher", "scientific_name": "Haematopus ostralegus"},
    {"common_name_uk": "Lapwing", "scientific_name": "Vanellus vanellus"},
    {"common_name_uk": "Curlew", "scientific_name": "Numenius arquata"},
    {"common_name_uk": "Redshank", "scientific_name": "Tringa totanus"},
]

EXTRA_NAMES = [
    "Avocet",
    "Bittern",
    "Black grouse",
    "Black-necked grebe",
    "Black-tailed godwit",
    "Black-throated diver",
    "Blue-headed wagtail",
    "Bonaparte's gull",
    "Brent goose",
    "Brent goose (dark-bellied)",
    "Brent goose (pale-bellied)",
    "Bullfinch (Azores)",
    "Buzzard (European honey)",
    "Common redstart",
    "Common sandpiper",
    "Common tern",
    "Corn bunting",
    "Cuckoo",
    "Dipper",
    "Dotterel",
    "Eider",
    "Fieldfare",
    "Firecrest",
    "Fulmar",
    "Gadwall",
    "Gannet",
    "Garganey",
    "Golden plover",
    "Goosander",
    "Grasshopper warbler",
    "Great crested grebe",
    "Great northern diver",
    "Great skua",
    "Great white egret",
    "Greenshank",
    "Grey wagtail",
    "Guillemot",
    "Hawfinch",
    "Hen harrier",
    "Herring gull",
    "Hobby",
    "Hoopoe",
    "House sparrow",
    "Iceland gull",
    "Jack snipe",
    "Kittiwake",
    "Lapland bunting",
    "Leach's storm petrel",
    "Lesser black-backed gull",
    "Lesser spotted woodpecker",
    "Lesser whitethroat",
    "Little grebe",
    "Little gull",
    "Little tern",
    "Marsh harrier",
    "Marsh tit",
    "Meadow pipit",
    "Mediterranean gull",
    "Merlin",
    "Nightjar",
    "Night heron",
    "Osprey",
    "Peregrine",
    "Pied wagtail",
    "Pintail",
    "Pochard",
    "Puffin",
    "Quail",
    "Raven",
    "Red grouse",
    "Red kite",
    "Red-legged partridge",
    "Redwing",
    "Reed bunting",
    "Reed warbler",
    "Ringed plover",
    "Rock pipit",
    "Roseate tern",
    "Sanderling",
    "Sandwich tern",
    "Scaup",
    "Shag",
    "Shelduck",
    "Shoveler",
    "Skylark",
    "Snipe",
    "Snow bunting",
    "Spoonbill",
    "Spotted flycatcher",
    "Stonechat",
    "Stone-curlew",
    "Storm petrel",
    "Teal",
    "Tree pipit",
    "Turnstone",
    "Twite",
    "Waxwing",
    "Whimbrel",
    "Whooper swan",
    "Wood warbler",
    "Woodcock",
    "Yellow wagtail",
    "Yellowhammer",
]

MORE_NAMES = [
    "Alpine swift",
    "Arctic skua",
    "Arctic tern",
    "Bar-tailed godwit",
    "Barnacle goose",
    "Bewick's swan",
    "Black redstart",
    "Black-headed gull",
    "Black-tailed skimmer",
    "Bluethroat",
    "Brambling",
    "Bridled tern",
    "Caspian tern",
    "Cetti's warbler",
    "Chough",
    "Common buzzard",
    "Common gull",
    "Common scoter",
    "Cormorant",
    "Crossbill",
    "Curlew sandpiper",
    "Dark-bellied brent goose",
    "Dotterel (Eurasian)",
    "Dunlin",
    "Eurasian golden plover",
    "Eurasian wigeon",
    "Fieldfare (Eurasian)",
    "Gadwall (Eurasian)",
    "Golden eagle",
    "Golden oriole",
    "Great grey shrike",
    "Great reed warbler",
    "Green sandpiper",
    "Grey plover",
    "Greylag goose (Eurasian)",
    "Grey seal gull",
    "Gyr falcon",
    "Hen harrier (western)",
    "Honey buzzard",
    "Hooded crow",
    "Knot",
    "Lapland longspur",
    "Leucistic blackbird",
    "Little owl",
    "Little stint",
    "Long-eared owl",
    "Magpie (Eurasian)",
    "Manx shearwater",
    "Marsh warbler",
    "Merlin (Eurasian)",
    "Nightingale",
    "Norfolk plover",
    "Ortolan bunting",
    "Pallid harrier",
    "Parrot crossbill",
    "Peregrine falcon",
    "Purple sandpiper",
    "Razorbill",
    "Red-necked grebe",
    "Red-throated diver",
    "Ring ouzel",
    "Rough-legged buzzard",
    "Ruff",
    "Sabine's gull",
    "Savi's warbler",
    "Scottish crossbill",
    "Sedge warbler (common)",
    "Short-eared owl",
    "Slavonian grebe",
    "Snowy owl",
    "Sooty shearwater",
    "Spotted redshank",
    "Spotted woodpecker",
    "Stork (white)",
    "Storm petrel (European)",
    "Subalpine warbler",
    "Temminck's stint",
    "Treecreeper (Eurasian)",
    "Tufted duck",
    "Velvet scoter",
    "Whinchat",
    "White wagtail",
    "Wood sandpiper",
    "Wryneck",
]

BIRDS: list[dict[str, str]] = [
    *BASE_BIRDS,
    *[
        {"common_name_uk": name}
        for name in sorted({*EXTRA_NAMES, *MORE_NAMES})
        if name
    ],
]


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path or str(DB_PATH))
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


def seed_birds(
    db_path: str | None = None, birds: Iterable[dict[str, str]] = BIRDS
) -> tuple[int, int, int]:
    inserted = 0
    skipped = 0
    with get_connection(db_path) as connection:
        ensure_table(connection)
        connection.execute(
            """
            DELETE FROM birds
            WHERE common_name_uk = 'Robin' AND scientific_name = 'Erithacus rubecula'
            """
        )
        for bird in birds:
            cursor = connection.execute(
                """
                INSERT INTO birds (
                    common_name_uk,
                    scientific_name,
                    aliases,
                    wikipedia_title,
                    image_url
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(common_name_uk, scientific_name) DO NOTHING
                """,
                (
                    bird["common_name_uk"],
                    bird.get("scientific_name"),
                    bird.get("aliases"),
                    bird.get("wikipedia_title"),
                    bird.get("image_url"),
                ),
            )
            if cursor.rowcount == 1:
                inserted += 1
            else:
                skipped += 1
        birds_count = connection.execute("SELECT COUNT(*) FROM birds").fetchone()[0]
    return inserted, skipped, birds_count
