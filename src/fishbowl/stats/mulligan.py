"""Mulligan odds for a deck: how often each hand size ends up being kept.

Run it with:  uv run python -m fishbowl.stats.mulligan <decklist.txt>
"""

import random
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fishbowl.deck.lookup import DEFAULT_DB, CardLookup
from fishbowl.deck.parser import find_deck_file, read_deck
from fishbowl.stats.lands import (
    HAND_SIZE,
    LAND_DROP_TURNS,
    OPENING_LANDS,
    SEED,
    TRIALS,
    OddsRow,
    _check,
    exact_at_least,
    exact_exactly,
    library_counts,
)

BOTTOM_ABOVE = 3  # with more lands than this, bottom a land; otherwise a spell
CARDS_NEEDED = HAND_SIZE + LAND_DROP_TURNS[-1]  # a 7-card hand plus a draw per turn


def hand_sizes(free_first: bool = True) -> tuple[int, ...]:
    """Hand size of each attempt. Commander's first mulligan is free: a second 7."""
    if free_first:
        return (HAND_SIZE, HAND_SIZE, HAND_SIZE - 1, HAND_SIZE - 2)
    return (HAND_SIZE, HAND_SIZE - 1, HAND_SIZE - 2)


def keeps(lands_in_seven: int) -> bool:
    """Keep rule: keep a seven-card hand with 2 to 5 lands."""
    return OPENING_LANDS[0] <= lands_in_seven <= OPENING_LANDS[-1]


def lands_after_bottoming(lands_in_seven: int, to_bottom: int) -> int:
    """Lands left in the hand after putting `to_bottom` cards on the library bottom.

    Each time: with more than 3 lands bottom a land, otherwise bottom a spell.
    """
    lands = lands_in_seven
    for _ in range(to_bottom):
        if lands > BOTTOM_ABOVE:
            lands -= 1
    return lands


def keep_rates(p: float, free_first: bool = True) -> list[float]:
    """Chance of keeping on each attempt, given `p`, the chance a seven is a keep.

    Attempt i is kept only after i-1 rejected hands, each with chance (1 - p).
    The last attempt is kept no matter what, so it skips the final "* p".
    """
    attempts = len(hand_sizes(free_first))
    rates = [(1 - p) ** (i - 1) * p for i in range(1, attempts)]  # list comprehension
    rates.append((1 - p) ** (attempts - 1))
    return rates


@dataclass(frozen=True)
class MulliganOdds:
    """Mulligan results. In drop_rows, `exact` is the no-mulligan odds and
    `simulated` is the odds with mulligans."""

    keep_rows: list[OddsRow]
    hand_size: OddsRow
    drop_rows: list[OddsRow]


def _keep_labels(free_first: bool) -> list[str]:
    if free_first:
        return [
            "Keep 7 (first hand)",
            "Keep 7 (free mulligan)",
            "Keep 6",
            "Keep 5 (forced)",
        ]
    return ["Keep 7", "Keep 6", "Keep 5 (forced)"]


def _draw_kept_hand(
    rng: random.Random, lands: int, library: int, attempts: int, most: int
) -> tuple[int, list[bool]]:
    """Mulligan until a keep: (index of the kept attempt, that shuffle's top cards).

    Each attempt is a fresh shuffle; cards numbered below `lands` are lands (True).
    """
    for attempt in range(attempts):
        top = [card < lands for card in rng.sample(range(library), most)]
        if keeps(sum(top[:HAND_SIZE])) or attempt == attempts - 1:  # last is forced
            return attempt, top
    raise AssertionError("unreachable: the last attempt always returns")


def mulligan_odds(
    lands: int,
    library: int,
    trials: int = TRIALS,
    seed: int = SEED,
    free_first: bool = True,
) -> MulliganOdds:
    """Which hand size gets kept and how land drops fare, exact and simulated."""
    # Enough cards for a 7-card hand plus a draw every turn we track.
    most = CARDS_NEEDED
    if library < most:
        raise ValueError(f"library of {library} cards is too small to see {most}")
    _check(lands, library, most)  # fail before the slow simulation, not after
    if trials < 1:
        raise ValueError("trials must be at least 1")

    sizes = hand_sizes(free_first)

    # Simulate.
    rng = random.Random(seed)
    kept_counts = [0] * len(sizes)
    total_size = 0
    drops = [0] * len(LAND_DROP_TURNS)
    for _ in range(trials):
        attempt, top = _draw_kept_hand(rng, lands, library, len(sizes), most)
        size = sizes[attempt]
        in_seven = sum(top[:HAND_SIZE])  # True counts as 1
        kept_counts[attempt] += 1
        total_size += size
        in_hand = lands_after_bottoming(in_seven, HAND_SIZE - size)
        # Bottomed cards go under the library, so the draws still come from top[7:].
        for i, turn in enumerate(LAND_DROP_TURNS):
            if in_hand + sum(top[HAND_SIZE : HAND_SIZE + turn]) >= turn:
                drops[i] += 1

    # Exact side: chance a seven is a keep, then the keep rate of each attempt.
    p_keep = sum(exact_exactly(k, lands, library, HAND_SIZE) for k in OPENING_LANDS)
    rates = keep_rates(p_keep, free_first)
    keep_rows = [
        OddsRow(label, rate, count / trials)
        for label, rate, count in zip(_keep_labels(free_first), rates, kept_counts)
    ]
    hand_size = OddsRow(
        "Average hand size",
        sum(size * rate for size, rate in zip(sizes, rates)),
        total_size / trials,
    )
    drop_rows = [
        OddsRow(
            f"Land drop through turn {turn}",
            exact_at_least(turn, lands, library, HAND_SIZE + turn),
            drops[i] / trials,
        )
        for i, turn in enumerate(LAND_DROP_TURNS)
    ]
    return MulliganOdds(keep_rows, hand_size, drop_rows)


def main(
    argv: list[str] | None = None,
    db_path: Path = DEFAULT_DB,
    read: Callable[[str], str] = input,
    write: Callable[[str], object] = print,
    trials: int = TRIALS,
) -> int:
    """Print exact and simulated mulligan odds for a decklist file."""
    args = sys.argv[1:] if argv is None else argv
    usage = "Usage: uv run python -m fishbowl.stats.mulligan <decklist.txt>"
    path = find_deck_file(args, db_path, usage, write)
    if path is None:
        return 1
    with CardLookup(db_path) as lookup:
        deck = read_deck(path, lookup, read, write)
        lands, library = library_counts(deck, lookup)

    # Too few cards to see every turn: say so plainly instead of crashing.
    if library < CARDS_NEEDED:
        write(
            f"Only {library} cards in the library; at least {CARDS_NEEDED} are needed "
            f"to see {LAND_DROP_TURNS[-1]} turns."
        )
        return 1

    who = " + ".join(entry.name for entry in deck.commanders)
    if not who:
        write(f"No commander chosen: using all {library} cards as the library.")
        who = "Deck"
    write(
        f"{who}: {lands} lands in a {library}-card library ({trials:,} simulated games, seed {SEED}; "
        "multiplayer: everyone draws on turn 1)"
    )
    write("Mulligans: free first mulligan; keep 2-5 lands; always keep at 5")
    if deck.problems:
        count = len(deck.problems)
        lines = "1 line" if count == 1 else f"{count} lines"
        write(f"Note: {lines} couldn't be read; the odds use the cards that could.")

    odds = mulligan_odds(lands, library, trials=trials)
    write("")
    write(f"{'Keep rates':<26}{'exact':>8}{'simulated':>11}")
    for row in odds.keep_rows:
        write(f"{row.label:<26}{row.exact:>8.1%}{row.simulated:>11.1%}")
    size = odds.hand_size  # a count of cards, not a percentage
    write(f"{size.label:<26}{size.exact:>8.2f}{size.simulated:>11.2f}")
    write("")
    write(f"{'Land drops':<26}{'no mulligan':>13}{'with mulligans':>16}")
    for row in odds.drop_rows:
        write(f"{row.label:<26}{row.exact:>13.1%}{row.simulated:>16.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
