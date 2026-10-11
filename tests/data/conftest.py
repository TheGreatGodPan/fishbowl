"""Real Scryfall cards (trimmed), shared by tests in tests/data/.

Copied from data/oracle-cards.jsonl.gz on 2026-10-10. Only the fields we use are kept,
and legalities are cut down to three formats.
"""

import copy

import pytest

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
