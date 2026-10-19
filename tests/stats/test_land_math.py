"""Tests for the exact land maths (hypergeometric formula)."""

import pytest

from fishbowl.stats.lands import exact_at_least, exact_exactly, is_land


@pytest.mark.parametrize(
    ("type_line", "expected"),
    [
        ("Basic Land — Forest", True),
        ("Land", True),
        ("Artifact Land", True),
        ("Land Creature — Forest Dryad", True),
        ("Land // Legendary Creature — Demon", True),  # Westvale Abbey: front is a land
        ("Creature — Human Warlock // Land", False),  # land only on the back
        ("Artifact", False),
        ("Legendary Creature — Bear", False),
        ("", False),
        (None, False),
    ],
)
def test_is_land(type_line, expected):
    assert is_land(type_line) is expected


def test_hand_checkable_cases():
    # 2 lands in a 4-card library; draw 1: half the time it's a land.
    assert exact_exactly(1, lands=2, library=4, drawn=1) == pytest.approx(0.5)
    # Draw 2 of those 4: no lands only if both non-lands come up: 1 way out of C(4,2)=6.
    assert exact_exactly(0, lands=2, library=4, drawn=2) == pytest.approx(1 / 6)
    assert exact_at_least(1, lands=2, library=4, drawn=2) == pytest.approx(5 / 6)


def test_all_outcomes_add_up_to_one():
    total = sum(exact_exactly(k, lands=33, library=99, drawn=7) for k in range(8))
    assert total == pytest.approx(1.0)
    assert exact_at_least(0, lands=33, library=99, drawn=7) == pytest.approx(1.0)


def test_real_deck_number():
    # 33 lands in 99 cards: P(2-5 lands in 7) = 0.7411 (checked separately).
    p = sum(exact_exactly(k, lands=33, library=99, drawn=7) for k in range(2, 6))
    assert p == pytest.approx(0.7411, abs=1e-4)


def test_no_lands_and_all_lands():
    assert exact_at_least(1, lands=0, library=99, drawn=7) == 0.0
    assert exact_exactly(7, lands=99, library=99, drawn=7) == pytest.approx(1.0)


def test_more_lands_than_drawn_is_zero_not_an_error():
    assert exact_exactly(8, lands=33, library=99, drawn=7) == 0.0


@pytest.mark.parametrize(
    ("lands", "library", "drawn"),
    [(100, 99, 7), (-1, 99, 7), (33, 99, 100), (33, 99, -1)],
)
def test_invalid_inputs_raise(lands, library, drawn):
    with pytest.raises(ValueError):
        exact_exactly(1, lands=lands, library=library, drawn=drawn)
