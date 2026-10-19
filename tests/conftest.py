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

FOREST = {
    "object": "card",
    "oracle_id": "b34bb2dc-c1af-4d77-b0b3-a0fb342a5fc6",
    "name": "Forest",
    "layout": "normal",
    "mana_cost": "",
    "cmc": 0.0,
    "type_line": "Basic Land — Forest",
    "oracle_text": "({T}: Add {G}.)",
    "colors": [],
    "color_identity": ["G"],
    "produced_mana": ["G"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}

RELENTLESS_RATS = {
    "object": "card",
    "oracle_id": "104ea189-14cd-420f-afdc-57b0f827ab8e",
    "name": "Relentless Rats",
    "layout": "normal",
    "mana_cost": "{1}{B}{B}",
    "cmc": 3.0,
    "type_line": "Creature — Rat",
    "oracle_text": (
        "This creature gets +1/+1 for each other creature on the battlefield "
        "named Relentless Rats.\nA deck can have any number of cards named "
        "Relentless Rats."
    ),
    "colors": ["B"],
    "color_identity": ["B"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}

SEVEN_DWARVES = {
    "object": "card",
    "oracle_id": "526ca4a9-3f50-4f7a-8169-2bda95792401",
    "name": "Seven Dwarves",
    "layout": "normal",
    "mana_cost": "{1}{R}",
    "cmc": 2.0,
    "type_line": "Creature — Dwarf",
    "oracle_text": (
        "This creature gets +1/+1 for each other creature named Seven Dwarves "
        "you control.\nA deck can have up to seven cards named Seven Dwarves."
    ),
    "colors": ["R"],
    "color_identity": ["R"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}

SYLVAN_PRIMORDIAL = {
    "object": "card",
    "oracle_id": "52b88034-bf0f-4d29-b776-40ce421f1107",
    "name": "Sylvan Primordial",
    "layout": "normal",
    "mana_cost": "{5}{G}{G}",
    "cmc": 7.0,
    "type_line": "Creature — Avatar",
    "oracle_text": (
        "Reach\nWhen this creature enters, for each opponent, destroy target "
        "noncreature permanent that player controls. Search your library for up "
        "to X Forest cards, where X is the number of permanents destroyed this "
        "way, put those cards onto the battlefield tapped, then shuffle."
    ),
    "colors": ["G"],
    "color_identity": ["G"],
    "keywords": ["Reach"],
    "legalities": {"commander": "banned", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}

# An Alchemy card: legal in some digital formats, not_legal in Commander.
ABSORB_ENERGY = {
    "object": "card",
    "oracle_id": "3010f11c-8ee1-4854-96d2-ae33ea3fe4e8",
    "name": "Absorb Energy",
    "layout": "normal",
    "mana_cost": "{1}{U}{U}",
    "cmc": 3.0,
    "type_line": "Instant",
    "oracle_text": (
        "Counter target spell. Cards in your hand that share a card type with "
        'that spell perpetually gain "This spell costs {1} less to cast."'
    ),
    "colors": ["U"],
    "color_identity": ["U"],
    "keywords": [],
    "legalities": {"historic": "legal", "brawl": "legal", "commander": "not_legal"},
    "game_changer": False,
}

SURVIVAL = {
    "object": "card",
    "oracle_id": "119d719d-e965-45b4-9bc9-ac03211b10c2",
    "name": "Survival of the Fittest",
    "layout": "normal",
    "mana_cost": "{1}{G}",
    "cmc": 2.0,
    "type_line": "Enchantment",
    "oracle_text": (
        "{G}, Discard a creature card: Search your library for a creature card, "
        "reveal that card, put it into your hand, then shuffle."
    ),
    "colors": ["G"],
    "color_identity": ["G"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "banned"},
    "game_changer": True,
}


# A transform land whose back face is a legendary creature: not a commander.
WESTVALE_ABBEY = {
    "object": "card",
    "oracle_id": "04eeb9ad-5c59-411b-8809-db8349838588",
    "name": "Westvale Abbey // Ormendahl, Profane Prince",
    "layout": "transform",
    "cmc": 0.0,
    "type_line": "Land // Legendary Creature — Demon",
    "color_identity": ["B"],
    "produced_mana": ["C"],
    "keywords": ["Flying", "Lifelink", "Indestructible", "Transform", "Haste"],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
    "card_faces": [
        {
            "name": "Westvale Abbey",
            "mana_cost": "",
            "type_line": "Land",
            "oracle_text": (
                "{T}: Add {C}.\n{5}, {T}, Pay 1 life: Create a 1/1 white and black "
                "Human Cleric creature token.\n{5}, {T}, Sacrifice five creatures: "
                "Transform this land, then untap it."
            ),
        },
        {
            "name": "Ormendahl, Profane Prince",
            "mana_cost": "",
            "type_line": "Legendary Creature — Demon",
            "oracle_text": "Flying, lifelink, indestructible, haste",
        },
    ],
}

# A planeswalker that is a creature in the command zone, so it can be a commander.
GRIST = {
    "object": "card",
    "oracle_id": "0efb0d7e-dea0-4817-a243-15066e9ef333",
    "name": "Grist, the Hunger Tide",
    "layout": "normal",
    "mana_cost": "{1}{B}{G}",
    "cmc": 3.0,
    "type_line": "Legendary Planeswalker — Grist",
    "oracle_text": (
        "As long as Grist isn't on the battlefield, it's a 1/1 Insect creature in "
        "addition to its other types.\n+1: Create a 1/1 black and green Insect "
        "creature token, then mill a card. If an Insect card was milled this way, "
        "put a loyalty counter on Grist and repeat this process.\n−2: You may "
        "sacrifice a creature. When you do, destroy target creature or "
        "planeswalker.\n−5: Each opponent loses life equal to the number of "
        "creature cards in your graveyard."
    ),
    "colors": ["B", "G"],
    "color_identity": ["B", "G"],
    "keywords": ["Mill"],
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
def westvale_abbey():
    return copy.deepcopy(WESTVALE_ABBEY)


@pytest.fixture
def grist():
    return copy.deepcopy(GRIST)


@pytest.fixture
def card_db(tmp_path):
    """A small real cards.db in tmp_path: Sol Ring, Krenko, Witch Enchanter,
    The Great Henge (alias: The Banyan Tree), Goreclaw, Teferi, Command Tower,
    Forest, Relentless Rats, Seven Dwarves, Sylvan Primordial, Absorb Energy
    Survival of the Fittest, Westvale Abbey and Grist."""
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
            FOREST,
            RELENTLESS_RATS,
            SEVEN_DWARVES,
            SYLVAN_PRIMORDIAL,
            ABSORB_ENERGY,
            SURVIVAL,
            WESTVALE_ABBEY,
            GRIST,
        ):
            out.write(json.dumps(card) + "\n")
    with gzip.open(printings, "wt", encoding="utf-8") as out:
        out.write(json.dumps(BANYAN_TREE_PRINTING) + "\n")
    dest = tmp_path / "cards.db"
    build_database(source, dest, printings)
    return dest
