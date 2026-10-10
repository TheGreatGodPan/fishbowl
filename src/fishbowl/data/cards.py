"""Flattening Scryfall card fields into simple values a database can store."""


def legal_in_commander(legalities: object) -> bool:
    """True only if Scryfall's legalities say "commander": "legal".

    Anything else (banned, not_legal, missing, malformed) is False: if we
    can't confirm a card is legal, we treat it as not legal.
    """
    # isinstance: checks the type, so a bad value (None, text, a number) can't crash .get
    if not isinstance(legalities, dict):
        return False
    return legalities.get("commander") == "legal"
