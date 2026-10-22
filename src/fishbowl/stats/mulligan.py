"""Mulligan odds for a deck: how often each hand size ends up being kept.

Run it with:  uv run python -m fishbowl.stats.mulligan <decklist.txt>
"""

import random
from dataclasses import dataclass

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
)

BOTTOM_ABOVE = 3  # with more lands than this, bottom a land; otherwise a spell


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
    most = HAND_SIZE + LAND_DROP_TURNS[-1]
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
