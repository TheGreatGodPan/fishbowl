"""Flattening Scryfall card fields into simple values a database can store."""

import json


def legal_in_commander(legalities: object) -> bool:
    """True only if Scryfall's legalities say "commander": "legal".

    Anything else (banned, not_legal, missing, malformed) is False: if we
    can't confirm a card is legal, we treat it as not legal.
    """
    # isinstance: checks the type, so a bad value (None, text, a number) can't crash .get
    if not isinstance(legalities, dict):
        return False
    return legalities.get("commander") == "legal"


# Statuses that mean "this is a real card in some format", even if banned there.
GAME_STATUSES = {"legal", "banned", "restricted"}
# Magic's standard color order, then C for colorless mana.
COLOR_ORDER = "WUBRGC"


def is_game_card(legalities: object) -> bool:
    """True if any format lists the card as legal, banned or restricted.

    Tokens, art cards, planes and joke cards are not_legal everywhere, so they drop out.
    """
    if not isinstance(legalities, dict):
        return False
    return any(isinstance(s, str) and s in GAME_STATUSES for s in legalities.values())


def commander_status(legalities: object) -> str:
    """Scryfall's raw commander value ("legal", "banned", ...), or "missing"."""
    if not isinstance(legalities, dict):
        return "missing"
    status = legalities.get("commander")
    return status if isinstance(status, str) and status else "missing"


def color_letters(symbols: object) -> str:
    """["G", "W"] -> "WG": the letters present, in WUBRGC order."""
    if not isinstance(symbols, list):
        return ""
    present = {s for s in symbols if isinstance(s, str)}  # set comprehension
    return "".join(letter for letter in COLOR_ORDER if letter in present)


def token_links(all_parts: object) -> list[dict[str, str]]:
    """The tokens a card makes, as [{"id": ..., "name": ...}], from Scryfall's all_parts."""
    if not isinstance(all_parts, list):
        return []
    links = []
    for part in all_parts:
        if not isinstance(part, dict) or part.get("component") != "token":
            continue
        token_id, name = part.get("id"), part.get("name")
        if isinstance(token_id, str) and isinstance(name, str):
            links.append({"id": token_id, "name": name})
    return links


def text_or_none(value: object) -> str | None:
    """The value if it is text, else None (missing or wrong type)."""
    return value if isinstance(value, str) else None


def number_or_none(value: object) -> float | None:
    """The value as a float if it is a number, else None."""
    # bool is a subclass of int in Python, so True would otherwise pass as 1
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def card_to_row(card: object) -> dict[str, object] | None:
    """One Scryfall card -> one `cards` table row, or None if it has no id or name.

    Keys are in the table's column order. Lists become letters or JSON text,
    because SQLite has no list type.
    """
    if not isinstance(card, dict):
        return None
    oracle_id, name = card.get("oracle_id"), card.get("name")
    if not (
        isinstance(oracle_id, str) and oracle_id and isinstance(name, str) and name
    ):
        return None

    legalities = card.get("legalities")
    keywords = card.get("keywords")
    faces = card.get("card_faces")
    layout = card.get("layout")
    return {
        "oracle_id": oracle_id,
        "name": name,
        "layout": layout if isinstance(layout, str) and layout else "unknown",
        "mana_cost": text_or_none(card.get("mana_cost")),  # None for double-faced cards
        "cmc": number_or_none(card.get("cmc")),
        "type_line": text_or_none(card.get("type_line")),
        "oracle_text": text_or_none(card.get("oracle_text")),
        "colors": color_letters(card.get("colors")),
        "color_identity": color_letters(card.get("color_identity")),
        "produced_mana": color_letters(card.get("produced_mana")),
        "keywords": json.dumps(keywords if isinstance(keywords, list) else []),
        "legal_commander": int(legal_in_commander(legalities)),  # True/False -> 1/0
        "commander_status": commander_status(legalities),
        "is_game_changer": int(card.get("game_changer") is True),
        "card_faces": json.dumps(faces) if isinstance(faces, list) else None,
        "tokens": json.dumps(token_links(card.get("all_parts"))),
    }
