"""Real Scryfall cards (trimmed), shared by all tests under tests/.

Copied from data/oracle-cards.jsonl.gz on 2026-10-10. Only the fields we use are kept,
and legalities are cut down to three formats.
"""

import copy
import gzip
import json

import pytest

from fishbowl.data.database import build_database

SOL_RING = {
    "object": "card",
    "oracle_id": "6ad8011d-3471-4369-9d68-b264cc027487",
    "name": "Sol Ring",
    "layout": "normal",
    "mana_cost": "{1}",
    "cmc": 1.0,
    "type_line": "Artifact",
    "oracle_text": "{T}: Add {C}{C}.",
    "colors": [],
    "color_identity": [],
    "produced_mana": ["C"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "restricted", "legacy": "banned"},
    "game_changer": False,
}

KRENKO = {
    "object": "card",
    "oracle_id": "68418069-f615-40ef-ae0d-764192acae00",
    "name": "Krenko, Mob Boss",
    "layout": "normal",
    "mana_cost": "{2}{R}{R}",
    "cmc": 4.0,
    "type_line": "Legendary Creature — Goblin Warrior",
    "oracle_text": (
        "{T}: Create X 1/1 red Goblin creature tokens, "
        "where X is the number of Goblins you control."
    ),
    "colors": ["R"],
    "color_identity": ["R"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
    "all_parts": [
        {
            "id": "70f8a1de-cd4c-4afa-bf03-0245d375d42e",
            "component": "token",
            "name": "Goblin",
            "type_line": "Token Creature — Goblin",
        },
        {
            "id": "824b2d73-2151-4e5e-9f05-8f63e2bdcaa9",
            "component": "combo_piece",
            "name": "Krenko, Mob Boss",
            "type_line": "Legendary Creature — Goblin Warrior",
        },
    ],
}

WITCH_ENCHANTER = {
    "object": "card",
    "oracle_id": "0355249a-8e4e-41db-9cea-1b901faffbe6",
    "name": "Witch Enchanter // Witch-Blessed Meadow",
    "layout": "modal_dfc",
    "cmc": 4.0,
    "type_line": "Creature — Human Warlock // Land",
    "color_identity": ["W"],
    "produced_mana": ["W"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
    "card_faces": [
        {
            "name": "Witch Enchanter",
            "mana_cost": "{3}{W}",
            "type_line": "Creature — Human Warlock",
            "oracle_text": (
                "When this creature enters, destroy target artifact or "
                "enchantment an opponent controls."
            ),
        },
        {
            "name": "Witch-Blessed Meadow",
            "mana_cost": "",
            "type_line": "Land",
            "oracle_text": (
                "As this land enters, you may pay 3 life. If you don't, it enters "
                "tapped.\n{T}: Add {W}."
            ),
        },
    ],
}

GOBLIN_TOKEN = {
    "object": "card",
    "oracle_id": "0cd035f0-bb53-40b7-b320-5d921268295a",
    "name": "Goblin",
    "layout": "token",
    "mana_cost": "",
    "cmc": 0.0,
    "type_line": "Token Creature — Goblin",
    "oracle_text": "",
    "colors": ["R"],
    "color_identity": ["R"],
    "keywords": [],
    "legalities": {
        "commander": "not_legal",
        "vintage": "not_legal",
        "legacy": "not_legal",
    },
    "game_changer": False,
}


# deepcopy: each test gets its own copy, so one test changing it can't affect another.
@pytest.fixture
def sol_ring():
    return copy.deepcopy(SOL_RING)


@pytest.fixture
def krenko():
    return copy.deepcopy(KRENKO)


@pytest.fixture
def witch_enchanter():
    return copy.deepcopy(WITCH_ENCHANTER)


@pytest.fixture
def goblin_token():
    return copy.deepcopy(GOBLIN_TOKEN)


GREAT_HENGE = {
    "object": "card",
    "oracle_id": "78427103-9543-41fb-b6d4-72963fe87275",
    "name": "The Great Henge",
    "layout": "normal",
    "mana_cost": "{7}{G}{G}",
    "cmc": 9.0,
    "type_line": "Legendary Artifact",
    "oracle_text": (
        "This spell costs {X} less to cast, where X is the greatest power among "
        "creatures you control.\n{T}: Add {G}{G}. You gain 2 life.\nWhenever a "
        "nontoken creature you control enters, put a +1/+1 counter on it and draw a card."
    ),
    "colors": ["G"],
    "color_identity": ["G"],
    "produced_mana": ["G"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}

GORECLAW = {
    "object": "card",
    "oracle_id": "befb211f-37ca-4083-98d4-9ff1f28be3f2",
    "name": "Goreclaw, Terror of Qal Sisma",
    "layout": "normal",
    "mana_cost": "{3}{G}",
    "cmc": 4.0,
    "type_line": "Legendary Creature — Bear",
    "oracle_text": (
        "Creature spells you cast with power 4 or greater cost {2} less to cast.\n"
        "Whenever Goreclaw attacks, each creature you control with power 4 or "
        "greater gets +1/+1 and gains trample until end of turn."
    ),
    "colors": ["G"],
    "color_identity": ["G"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}

# One printing from Scryfall's default_cards (TLE 41), trimmed: its card carries a
# different printed name ("flavor_name") than the real card name.
BANYAN_TREE_PRINTING = {
    "object": "card",
    "oracle_id": "78427103-9543-41fb-b6d4-72963fe87275",
    "name": "The Great Henge",
    "flavor_name": "The Banyan Tree",
    "set": "tle",
    "collector_number": "41",
    "layout": "normal",
}

# Copied from data/oracle-cards.jsonl.gz on 2026-10-15.
TEFERI = {
    "object": "card",
    "oracle_id": "07d0b06b-80cb-4518-92c9-84ea87a7e08a",
    "name": "Teferi, Temporal Archmage",
    "layout": "normal",
    "mana_cost": "{4}{U}{U}",
    "cmc": 6.0,
    "type_line": "Legendary Planeswalker — Teferi",
    "oracle_text": (
        "+1: Look at the top two cards of your library. Put one of them into your "
        "hand and the other on the bottom of your library.\n"
        "−1: Untap up to four target permanents.\n"
        '−10: You get an emblem with "You may activate loyalty abilities of '
        "planeswalkers you control on any player's turn any time you could cast an "
        'instant."\n'
        "Teferi, Temporal Archmage can be your commander."
    ),
    "colors": ["U"],
    "color_identity": ["U"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}

COMMAND_TOWER = {
    "object": "card",
    "oracle_id": "0895c9b7-ae7d-4bb3-af17-3b75deb50a25",
    "name": "Command Tower",
    "layout": "normal",
    "mana_cost": "",
    "cmc": 0.0,
    "type_line": "Land",
    "oracle_text": "{T}: Add one mana of any color in your commander's color identity.",
    "colors": [],
    "color_identity": [],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}


@pytest.fixture
def great_henge():
    return copy.deepcopy(GREAT_HENGE)


@pytest.fixture
def goreclaw():
    return copy.deepcopy(GORECLAW)


@pytest.fixture
def teferi():
    return copy.deepcopy(TEFERI)


@pytest.fixture
def command_tower():
    return copy.deepcopy(COMMAND_TOWER)


@pytest.fixture
def banyan_tree_printing():
    return copy.deepcopy(BANYAN_TREE_PRINTING)


@pytest.fixture
def card_db(tmp_path):
    """A small real cards.db in tmp_path: Sol Ring, Krenko, Witch Enchanter,
    The Great Henge (alias: The Banyan Tree), Goreclaw, Teferi and Command Tower."""
    source = tmp_path / "oracle.jsonl.gz"
    printings = tmp_path / "printings.jsonl.gz"
    with gzip.open(source, "wt", encoding="utf-8") as out:
        for card in (
            SOL_RING,
            KRENKO,
            WITCH_ENCHANTER,
            GREAT_HENGE,
            GORECLAW,
            TEFERI,
            COMMAND_TOWER,
        ):
            out.write(json.dumps(card) + "\n")
    with gzip.open(printings, "wt", encoding="utf-8") as out:
        out.write(json.dumps(BANYAN_TREE_PRINTING) + "\n")
    dest = tmp_path / "cards.db"
    build_database(source, dest, printings)
    return dest
