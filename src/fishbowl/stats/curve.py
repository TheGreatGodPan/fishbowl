"""Commander-on-curve odds: will you have the lands (and colours) by turn M?

Run it with:  uv run python -m fishbowl.stats.curve <decklist.txt>
"""

import random
import re
from dataclasses import dataclass

from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.model import ParsedDeck
from fishbowl.stats.lands import (
    HAND_SIZE,
    SEED,
    TRIALS,
    exact_at_least,
    is_land,
)

COLOUR_NAMES = {"W": "white", "U": "blue", "B": "black", "R": "red", "G": "green"}

# One plain colour symbol such as {R}. Hybrid {G/W}, Phyrexian {G/P}, generic {3}
# and {X} don't match, so they add no pips.
_PIP = re.compile(r"\{([WUBRG])\}")


def colour_pips(mana_cost: str | None) -> dict[str, int]:
    """How many plain pips of each colour a mana cost has, in WUBRG order."""
    found = _PIP.findall(mana_cost or "")  # findall: every match, as a list
    # Looping over COLOUR_NAMES fixes the key order; colours with no pips are left out.
    return {colour: found.count(colour) for colour in COLOUR_NAMES if colour in found}


def land_colours(deck: ParsedDeck, lookup: CardLookup) -> list[str]:
    """The produced_mana of each land copy in the library ("" = makes no colour)."""
    # Same commander rule as library_counts: one copy of each commander is not in the library.
    commander_ids = {entry.oracle_id for entry in deck.commanders}
    colours: list[str] = []
    for entry in deck.cards:
        copies = entry.quantity - (1 if entry.oracle_id in commander_ids else 0)
        card = lookup.find(entry.name)
        if card is not None and is_land(card.type_line):
            colours.extend([card.produced_mana] * copies)  # list * n repeats it n times
    return colours


@dataclass(frozen=True)
class CurveOdds:
    """Odds of casting the commander on curve, by the lands and by the colours."""

    mana_value: int
    pips: dict[str, int]
    lands_exact: float
    lands_simulated: float
    colours_simulated: float


def curve_odds(
    mana_value: int,
    pips: dict[str, int],
    land_colours: list[str],
    library: int,
    trials: int = TRIALS,
    seed: int = SEED,
) -> CurveOdds:
    """Odds of having mana_value lands (and the commander's colours) by that turn.

    By turn M you have seen the opening 7 plus one draw per turn: 7 + M cards.
    """
    lands = len(land_colours)
    seen = HAND_SIZE + mana_value
    if mana_value < 1:
        raise ValueError("mana value must be at least 1")
    if seen > library:
        raise ValueError(f"can't see {seen} cards in a library of {library}")
    if lands > library:
        raise ValueError(f"{lands} lands can't fit in a library of {library}")
    if trials < 1:
        raise ValueError("trials must be at least 1")

    # Simulate: cards 0..lands-1 are the lands, and card i makes land_colours[i].
    rng = random.Random(seed)  # our own generator, so the seed only affects this run
    lands_ok = colours_ok = 0
    for _ in range(trials):
        seen_lands = [card for card in rng.sample(range(library), seen) if card < lands]
        if len(seen_lands) < mana_value:
            continue
        lands_ok += 1
        # all(...) is True only if every colour has enough sources among the seen lands.
        if all(
            sum(colour in land_colours[card] for card in seen_lands) >= needed
            for colour, needed in pips.items()
        ):
            colours_ok += 1

    return CurveOdds(
        mana_value=mana_value,
        pips=pips,
        lands_exact=exact_at_least(mana_value, lands, library, seen),
        lands_simulated=lands_ok / trials,
        colours_simulated=colours_ok / trials,
    )
