"""Card groups (mana dorks, tutors): find them from card text and count them.

Run it with:  uv run python -m fishbowl.stats.groups <decklist.txt>
"""

import random
import re
from dataclasses import dataclass

from fishbowl.deck.lookup import Card, CardLookup
from fishbowl.deck.model import ParsedDeck
from fishbowl.stats.lands import HAND_SIZE, SEED, TRIALS, _check, exact_at_least

# Cards seen: the opening hand, then by turns 1, 2 and 3 (one draw per turn).
CHECKPOINTS = (7, 8, 9, 10)
# The what-if table shows the current count and these steps either side of it.
_STEPS = (-4, -2, 0, 2, 4)

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


@dataclass(frozen=True)
class WhatIfRow:
    """Odds of seeing at least one group card, if the deck held `count` of them."""

    count: int
    chances: list[float]  # exact, one per checkpoint
    simulated: float | None  # opening hand only, and only for the current row
    is_current: bool


def what_if(
    count: int, library: int, trials: int = TRIALS, seed: int = SEED
) -> list[WhatIfRow]:
    """Odds of at least one group card by each checkpoint, for the current count
    and for a few more or fewer copies. Rows run from the lowest count to the highest."""
    most = CHECKPOINTS[-1]
    if library < most:
        raise ValueError(f"library of {library} cards is too small to see {most}")
    _check(count, library, most)  # fail before the slow simulation, not after
    if trials < 1:
        raise ValueError("trials must be at least 1")

    # Simulate the current count only: numbers below `count` are the group cards,
    # as in land_odds. A hit is any group card in the opening hand.
    rng = random.Random(seed)
    hits = 0
    for _ in range(trials):
        hand = rng.sample(range(library), HAND_SIZE)
        if any(card < count for card in hand):
            hits += 1

    rows = []
    for step in _STEPS:
        row_count = count + step
        if not 0 <= row_count <= library:  # drop rows that make no sense
            continue
        is_current = step == 0
        rows.append(
            WhatIfRow(
                count=row_count,
                chances=[
                    exact_at_least(1, row_count, library, seen) for seen in CHECKPOINTS
                ],
                simulated=hits / trials if is_current else None,
                is_current=is_current,
            )
        )
    return rows
