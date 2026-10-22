"""Mulligan odds for a deck: how often each hand size ends up being kept.

Run it with:  uv run python -m fishbowl.stats.mulligan <decklist.txt>
"""

from fishbowl.stats.lands import HAND_SIZE, OPENING_LANDS

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
