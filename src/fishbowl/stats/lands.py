"""Land odds for a deck: exact (hypergeometric formula) and simulated.

Run it with:  uv run python -m fishbowl.stats.lands <decklist.txt>
"""

import random
import sys
from collections.abc import Callable
from dataclasses import dataclass
from math import comb
from pathlib import Path

from fishbowl.deck.lookup import DEFAULT_DB, CardLookup
from fishbowl.deck.model import ParsedDeck
from fishbowl.deck.parser import find_deck_file, read_deck

HAND_SIZE = 7
TRIALS = 100_000
SEED = 42  # a fixed seed makes every run give the same "random" numbers
OPENING_LANDS = (2, 3, 4, 5)
LAND_DROP_TURNS = (1, 2, 3, 4, 5)


def is_land(type_line: str | None) -> bool:
    """True if the card's front face is a land ("Basic Land — Forest", "Artifact Land")."""
    front = (type_line or "").split(" // ")[0]  # double-faced cards: front face only
    return "Land" in front.split()  # whole word, so a type like "Landfall" can't match


def _check(lands: int, library: int, drawn: int) -> None:
    if not 0 <= lands <= library:
        raise ValueError(
            f"lands must be between 0 and the library size ({library}), got {lands}"
        )
    if not 0 <= drawn <= library:
        raise ValueError(f"can't draw {drawn} cards from a library of {library}")


def exact_exactly(k: int, lands: int, library: int, drawn: int) -> float:
    """Chance of exactly k lands among `drawn` cards: the hypergeometric formula.

    C(lands, k) ways to pick the lands, times C(non-lands, drawn - k) ways to pick
    the rest, out of C(library, drawn) equally likely hands.
    """
    _check(lands, library, drawn)
    if not 0 <= k <= drawn:
        return 0.0
    # comb(n, r) is 0 when r > n, so impossible hands count as 0 automatically.
    return comb(lands, k) * comb(library - lands, drawn - k) / comb(library, drawn)


def exact_at_least(k: int, lands: int, library: int, drawn: int) -> float:
    """Chance of k or more lands among `drawn` cards."""
    return sum(
        exact_exactly(i, lands, library, drawn) for i in range(max(k, 0), drawn + 1)
    )


@dataclass(frozen=True)
class OddsRow:
    """One question, answered two ways."""

    label: str
    exact: float
    simulated: float


def _cards_seen(turn: int, skip_first_draw: bool) -> int:
    """Cards seen by the given turn: the opening 7 plus one draw per turn."""
    return HAND_SIZE + turn - (1 if skip_first_draw else 0)


def land_odds(
    lands: int,
    library: int,
    trials: int = TRIALS,
    seed: int = SEED,
    skip_first_draw: bool = False,
) -> list[OddsRow]:
    """Exact and simulated odds for opening-hand lands and land drops."""
    seen = [_cards_seen(turn, skip_first_draw) for turn in LAND_DROP_TURNS]
    most = max(seen)
    if library < most:
        raise ValueError(f"library of {library} cards is too small to see {most}")
    _check(lands, library, most)  # fail before the slow simulation, not after
    if trials < 1:
        raise ValueError("trials must be at least 1")

    # Simulate: number the library 0..library-1; numbers below `lands` are the lands.
    # rng.sample(...) takes `most` different cards: the top of a shuffled library.
    rng = random.Random(seed)  # our own generator, so the seed only affects this run
    opening = {count: 0 for count in OPENING_LANDS}
    drops = [0] * len(LAND_DROP_TURNS)
    for _ in range(trials):
        top = [card < lands for card in rng.sample(range(library), most)]
        in_hand = sum(top[:HAND_SIZE])  # True counts as 1
        if in_hand in opening:
            opening[in_hand] += 1
        for i, (turn, cards) in enumerate(zip(LAND_DROP_TURNS, seen)):
            if sum(top[:cards]) >= turn:
                drops[i] += 1

    rows = []
    for count in OPENING_LANDS:
        exact = exact_exactly(count, lands, library, HAND_SIZE)
        rows.append(
            OddsRow(f"Opening hand: {count} lands", exact, opening[count] / trials)
        )
    low, high = OPENING_LANDS[0], OPENING_LANDS[-1]
    rows.append(
        OddsRow(
            f"Opening hand: {low}-{high} lands",
            sum(row.exact for row in rows),
            sum(opening.values()) / trials,
        )
    )
    for i, (turn, cards) in enumerate(zip(LAND_DROP_TURNS, seen)):
        exact = exact_at_least(turn, lands, library, cards)
        rows.append(OddsRow(f"Land drop through turn {turn}", exact, drops[i] / trials))
    return rows


def library_counts(deck: ParsedDeck, lookup: CardLookup) -> tuple[int, int]:
    """(lands, library size) for a deck. Commanders start in the command zone,
    so one copy of each is left out of the library."""
    commander_ids = {entry.oracle_id for entry in deck.commanders}
    lands = size = 0
    for entry in deck.cards:
        copies = entry.quantity - (1 if entry.oracle_id in commander_ids else 0)
        card = lookup.find(entry.name)
        size += copies
        if card is not None and is_land(card.type_line):
            lands += copies
    return lands, size


def main(
    argv: list[str] | None = None,
    db_path: Path = DEFAULT_DB,
    read: Callable[[str], str] = input,
    write: Callable[[str], object] = print,
    trials: int = TRIALS,
) -> int:
    """Print exact and simulated land odds for a decklist file."""
    args = sys.argv[1:] if argv is None else argv
    usage = "Usage: uv run python -m fishbowl.stats.lands <decklist.txt>"
    path = find_deck_file(args, db_path, usage, write)
    if path is None:
        return 1
    with CardLookup(db_path) as lookup:
        deck = read_deck(path, lookup, read, write)
        lands, library = library_counts(deck, lookup)

    # Too few cards to see every turn: say so plainly instead of crashing.
    needed = _cards_seen(LAND_DROP_TURNS[-1], False)
    if library < needed:
        write(
            f"Only {library} cards in the library; at least {needed} are needed "
            f"to see {LAND_DROP_TURNS[-1]} turns."
        )
        return 1

    who = " + ".join(entry.name for entry in deck.commanders)
    if not who:
        write(f"No commander chosen: using all {library} cards as the library.")
        who = "Deck"
    write(
        f"{who}: {lands} lands in a {library}-card library ({trials:,} simulated hands, seed {SEED}; "
        "multiplayer: everyone draws on turn 1)"
    )
    if deck.problems:
        count = len(deck.problems)
        lines = "1 line" if count == 1 else f"{count} lines"
        write(f"Note: {lines} couldn't be read; the odds use the cards that could.")
    write("")
    write(f"{'':<26}{'exact':>8}{'simulated':>11}")
    for row in land_odds(lands, library, trials=trials):
        write(
            f"{row.label:<26}{row.exact:>8.1%}{row.simulated:>11.1%}"
        )  # .1% = percent, 1 decimal
    return 0


if __name__ == "__main__":
    sys.exit(main())
