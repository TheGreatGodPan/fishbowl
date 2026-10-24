"""Card groups (mana dorks, tutors): find them from card text and count them.

Run it with:  uv run python -m fishbowl.stats.groups <decklist.txt>
"""

import re
from dataclasses import dataclass

from fishbowl.deck.lookup import Card, CardLookup
from fishbowl.deck.model import ParsedDeck

# re.compile builds the pattern once, instead of on every card checked.
# "{T}" then anything but a full stop, then ": Add ": a mana ability that taps.
# Stopping at "." keeps "{T}: Untap target Forest. ... Add" style text from matching.
_DORK_ABILITY = re.compile(r"\{T\}[^.]*: Add ")

# Searching for these is ramp or fixing, not tutoring, so it doesn't count as a tutor.
_LAND_WORDS = ("land", "plains", "island", "swamp", "mountain", "forest")

_SEARCH = "search your library for"


def is_mana_dork(card: Card) -> bool:
    """True if the card is a creature with a "{T}: Add ..." mana ability."""
    # Double-faced cards: front face only.
    front = (card.type_line or "").split(" // ")[0]
    if "Creature" not in front.split():  # whole word, so a longer type can't match
        return False
    return _DORK_ABILITY.search(card.oracle_text or "") is not None


def is_tutor(card: Card) -> bool:
    """True if the card searches the library for something other than a land."""
    text = (card.oracle_text or "").lower()
    start = text.find(_SEARCH)
    if start == -1:
        return False
    # Only the first sentence of the search matters: "...a Forest card, put it..."
    searched = text[start + len(_SEARCH) :].split(".")[0]
    # any(...) is True as soon as one word in the list is found
    return not any(word in searched for word in _LAND_WORDS)


@dataclass(frozen=True)
class CardGroup:
    """A kind of card, and how many copies of it are in the library."""

    name: str  # "Mana dorks"
    unit: str  # "dork"
    units: str  # "dorks"
    count: int  # copies in the library
    names: list[str]  # matched card names, sorted


def find_groups(deck: ParsedDeck, lookup: CardLookup) -> list[CardGroup]:
    """The mana dork and tutor groups for a deck. Commanders start in the command
    zone, so one copy of each is left out, as in library_counts."""
    commander_ids = {entry.oracle_id for entry in deck.commanders}
    dork_count = tutor_count = 0
    dork_names: list[str] = []
    tutor_names: list[str] = []
    for entry in deck.cards:
        copies = entry.quantity - (1 if entry.oracle_id in commander_ids else 0)
        card = lookup.find(entry.name)
        if card is None or copies <= 0:
            continue
        if is_mana_dork(card):
            dork_count += copies
            dork_names.append(card.name)
        if is_tutor(card):
            tutor_count += copies
            tutor_names.append(card.name)
    return [
        CardGroup("Mana dorks", "dork", "dorks", dork_count, sorted(dork_names)),
        CardGroup("Tutors", "tutor", "tutors", tutor_count, sorted(tutor_names)),
    ]
