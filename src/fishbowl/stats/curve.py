"""Commander-on-curve odds: will you have the lands (and colours) by turn M?

Run it with:  uv run python -m fishbowl.stats.curve <decklist.txt>
"""

import random
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fishbowl.deck.lookup import DEFAULT_DB, CardLookup
from fishbowl.deck.model import ParsedDeck
from fishbowl.deck.parser import find_deck_file, read_deck
from fishbowl.stats.lands import (
    HAND_SIZE,
    SEED,
    TRIALS,
    exact_at_least,
    is_land,
    library_counts,
)

COLOUR_NAMES = {
    "W": "white",
    "U": "blue",
    "B": "black",
    "R": "red",
    "G": "green",
    "C": "colourless",
}

# One plain colour symbol such as {R} (or {C}, colourless). Hybrid {G/W}, Phyrexian
# {G/P}, generic {3} and {X} don't match, so they add no pips.
_PIP = re.compile(r"\{([WUBRGC])\}")


def colour_pips(mana_cost: str | None) -> dict[str, int]:
    """How many plain pips of each colour a mana cost has, in WUBRGC order."""
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
    land_sources: list[str],
    library: int,
    trials: int = TRIALS,
    seed: int = SEED,
) -> CurveOdds:
    """Odds of having mana_value lands (and the commander's colours) by that turn.

    By turn M you have seen the opening 7 plus one draw per turn: 7 + M cards.
    """
    if mana_value < 1:  # validate first: `seen` below depends on it
        raise ValueError("mana value must be at least 1")
    lands = len(land_sources)
    seen = HAND_SIZE + mana_value
    if seen > library:
        raise ValueError(f"can't see {seen} cards in a library of {library}")
    if lands > library:
        raise ValueError(f"{lands} lands can't fit in a library of {library}")
    if trials < 1:
        raise ValueError("trials must be at least 1")

    # Simulate: cards 0..lands-1 are the lands, and card i makes land_sources[i].
    rng = random.Random(seed)  # our own generator, so the seed only affects this run
    lands_ok = colours_ok = 0
    for _ in range(trials):
        seen_lands = [card for card in rng.sample(range(library), seen) if card < lands]
        if len(seen_lands) < mana_value:
            continue
        lands_ok += 1
        # all(...) is True only if every colour has enough sources among the seen lands.
        if all(
            sum(colour in land_sources[card] for card in seen_lands) >= needed
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


def _colour_row_label(pips: dict[str, int]) -> str:
    """The "...and 1+ green source" label for the colour row."""
    parts = [
        f"{needed}+ {COLOUR_NAMES[colour]} source{'s' if needed > 1 else ''}"
        for colour, needed in pips.items()
    ]
    return "  ...and " + " and ".join(parts)


def main(
    argv: list[str] | None = None,
    db_path: Path = DEFAULT_DB,
    read: Callable[[str], str] = input,
    write: Callable[[str], object] = print,
    trials: int = TRIALS,
) -> int:
    """Print the odds of casting each commander on curve, from lands alone."""
    args = sys.argv[1:] if argv is None else argv
    usage = "Usage: uv run python -m fishbowl.stats.curve <decklist.txt>"
    path = find_deck_file(args, db_path, usage, write)
    if path is None:
        return 1
    with CardLookup(db_path) as lookup:
        deck = read_deck(path, lookup, read, write)
        lands, library = library_counts(deck, lookup)
        colours = land_colours(deck, lookup)  # needs the lookup, so it stays in here
        # Each commander's card (None if the name isn't in the database).
        commander_cards = [
            (entry.name, lookup.find(entry.name)) for entry in deck.commanders
        ]

    who = " + ".join(entry.name for entry in deck.commanders)
    if not who:
        write(f"No commander chosen: using all {library} cards as the library.")
        who = "Deck"
    write(
        f"{who}: {lands} lands in a {library}-card library ({trials:,} simulated hands, "
        f"seed {SEED}; multiplayer: everyone draws on turn 1)"
    )
    if deck.problems:
        count = len(deck.problems)
        lines = "1 line" if count == 1 else f"{count} lines"
        write(f"Note: {lines} couldn't be read; the odds use the cards that could.")
    write("Lands only; ignores dorks, rocks and cost reducers.")
    if not commander_cards:
        write("Nothing to cast on curve.")
        return 0

    for name, card in commander_cards:
        write("")
        mana_value = None if card is None or card.cmc is None else int(card.cmc)
        if card is None or mana_value is None or mana_value < 1:
            write(f"{name}: no mana cost found; skipped")
            continue
        write(
            f"{name} {card.mana_cost}: mana value {mana_value}, cast on turn {mana_value}"
        )
        if HAND_SIZE + mana_value > library:
            write(f"  Can't be cast on curve from lands in a {library}-card library.")
            continue

        pips = colour_pips(card.mana_cost)
        odds = curve_odds(mana_value, pips, colours, library, trials=trials)
        write(f"{'':<34}{'exact':>7}{'simulated':>11}")
        label = f"  {mana_value}+ lands by turn {mana_value}"
        write(f"{label:<34}{odds.lands_exact:>7.1%}{odds.lands_simulated:>11.1%}")
        if pips:
            write(
                f"{_colour_row_label(pips):<34}{'':>7}{odds.colours_simulated:>11.1%}"
            )
        if mana_value >= 8:
            write("  Note: cost reducers aren't modelled.")
        if len(pips) >= 2:
            write("  Note: approximate for multi-colour costs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
