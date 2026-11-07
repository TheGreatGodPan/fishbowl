"""The goldfish report: play one game and print its log, or play many and summarise.

Run it with:  uv run fishbowl goldfish <decklist.txt>
"""

import sys
import textwrap
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from fishbowl.deck.lookup import DEFAULT_DB, CardLookup
from fishbowl.deck.model import ParsedDeck
from fishbowl.deck.parser import find_deck_file, read_deck
from fishbowl.sim.cards import PlayCard, deck_play_cards
from fishbowl.sim.game import play_game
from fishbowl.stats.curve import curve_odds, land_colours
from fishbowl.stats.lands import HAND_SIZE

DEFAULT_TURNS = 8
# Kinds we list by name, with their labels. Generic spells are only counted:
# a list of 60 names would bury everything else.
_KIND_LABELS = {
    "fetch": "Fetch lands",
    "rock": "Rocks",
    "dork": "Dorks",
    "ramp": "Ramp",
    "draw": "Draw",
}


def _kind_lines(library: list[PlayCard]) -> list[str]:
    """One line per non-land kind that has cards in the library."""
    lines = []
    for kind, label in _KIND_LABELS.items():
        # set(...) drops duplicate names; sorted gives a stable order
        names = sorted({c.name for c in library if c.kind == kind})
        if names:
            # textwrap.wrap splits long text into lines of at most `width` characters
            wrapped = textwrap.wrap(f"{label}: " + ", ".join(names), width=76)
            lines.append("  " + wrapped[0])
            lines.extend("    " + more for more in wrapped[1:])
    generic = sum(1 for c in library if c.kind == "generic")
    if generic:
        lines.append(f"  Other spells: {generic} (not listed)")
    return lines


def _lands_only(library: list[PlayCard]) -> list[PlayCard]:
    """The same library with every spell swapped for one that can never be cast.

    Why: the 4d baseline has no mulligans, and mulligans alone change the odds.
    Running the same engine with spells that never resolve isolates what the
    spells (rocks, dorks, ramp, draw) add. Lands and fetches stay as they are.
    """
    blank = {"kind": "generic", "mana_value": 99, "pips": {}, "colours": ""}
    return [
        c
        if c.kind in ("land", "fetch")
        else replace(c, **blank, amount=0, ramp_lands=0, ramp_to_hand=0, draws=0)
        for c in library
    ]


def _summary(
    cast_turns: list[int | None],
    turns: int,
    baseline: list[str],
    write: Callable[[str], object],
) -> None:
    """Write how often and how early the commander was cast across all games."""
    games = len(cast_turns)
    cast = [t for t in cast_turns if t is not None]
    for t in range(1, turns + 1):
        by_t = sum(1 for c in cast if c <= t)
        write(f"Commander cast by turn {t}: {by_t / games:.1%}")
    if cast:
        write(f"Average turn (when cast): {sum(cast) / len(cast):.1f}")
    else:
        write("Average turn (when cast): never cast")
    write(f"Not cast in {turns} turns: {(games - len(cast)) / games:.1%}")
    for line in baseline:
        write(line)


def report(
    deck: ParsedDeck,
    lookup: CardLookup,
    write: Callable[[str], object],
    seed: int = 42,
    turns: int | None = None,
    games: int = 1,
) -> int:
    """Write the goldfish for a deck: one game's log, or a summary of many games."""
    if games < 1 or (turns is not None and turns < 1):
        raise ValueError("games and turns must be at least 1")
    library, commanders = deck_play_cards(deck, lookup)
    first = commanders[0] if commanders else None
    if turns is None:
        turns = max(DEFAULT_TURNS, first.mana_value + 2) if first else DEFAULT_TURNS

    who = " + ".join(c.name for c in commanders) or "Deck"
    write(f"{who}: goldfish, seed {seed}, {turns} turns")
    for line in _kind_lines(library):
        write(line)
    if deck.problems:
        count = len(deck.problems)
        lines = "1 line" if count == 1 else f"{count} lines"
        write(
            f"Note: {lines} couldn't be read; the goldfish uses the cards that could."
        )
    write("")

    if games == 1:
        for line in play_game(library, commanders, seed, turns).log:
            write(line)
        return 0

    write(f"{games:,} games, {turns} turns each (game i uses seed {seed} + i)")
    if first is None:
        write("No commander: nothing to measure.")
        return 0
    if len(commanders) > 1:
        write(f"Two commanders: measuring {first.name} only.")
    # Each game gets its own seed, so every game differs but the run can be repeated.
    cast_turns = [
        play_game(library, commanders, seed + i, turns).commander_cast_turn
        for i in range(games)
    ]

    mv = first.mana_value
    if mv < 1 or HAND_SIZE + mv > len(library):
        baseline = ["Lands-only baseline (4d, no mulligan): not available"]
    else:
        # Same games (same seeds), but no spell can ever be cast.
        blank = _lands_only(library)
        same = [
            play_game(blank, commanders, seed + i, turns).commander_cast_turn
            for i in range(games)
        ]
        same_by_mv = sum(1 for c in same if c is not None and c <= mv) / games
        odds = curve_odds(mv, first.pips, land_colours(deck, lookup), len(library))
        baseline = [
            f"Lands only, same engine: {same_by_mv:.1%} by turn {mv}",
            (
                "Lands-only baseline (4d, no mulligan): "
                f"{odds.colours_simulated:.1%} by turn {mv}"
            ),
        ]
    _summary(cast_turns, turns, baseline, write)
    return 0


def main(
    argv: list[str] | None = None,
    db_path: Path = DEFAULT_DB,
    read: Callable[[str], str] = input,
    write: Callable[[str], object] = print,
    seed: int = 42,
    turns: int | None = None,
    games: int = 1,
) -> int:
    """Print the goldfish for a decklist."""
    args = sys.argv[1:] if argv is None else argv
    usage = "Usage: uv run fishbowl goldfish <decklist.txt>"
    path = find_deck_file(args, db_path, usage, write)
    if path is None:
        return 1
    with CardLookup(db_path) as lookup:
        deck = read_deck(path, lookup, read, write)
        return report(deck, lookup, write, seed, turns, games)


if __name__ == "__main__":
    sys.exit(main())
