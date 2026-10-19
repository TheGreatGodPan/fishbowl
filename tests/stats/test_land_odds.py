"""Tests for the exact-vs-simulated land odds table."""

import pytest

from fishbowl.stats.lands import exact_at_least, land_odds

LABELS = [
    "Opening hand: 2 lands",
    "Opening hand: 3 lands",
    "Opening hand: 4 lands",
    "Opening hand: 5 lands",
    "Opening hand: 2-5 lands",
    "Land drop through turn 1",
    "Land drop through turn 2",
    "Land drop through turn 3",
    "Land drop through turn 4",
    "Land drop through turn 5",
]


def test_row_labels():
    assert [row.label for row in land_odds(33, 99, trials=100)] == LABELS


def test_exact_column():
    rows = {row.label: row for row in land_odds(33, 99, trials=100)}
    assert rows["Opening hand: 2-5 lands"].exact == pytest.approx(0.7411, abs=1e-4)
    # Turn 3 in multiplayer: 10 cards seen (7 + 3), need 3 lands.
    assert rows["Land drop through turn 3"].exact == pytest.approx(
        exact_at_least(3, 33, 99, 10)
    )


def test_skip_first_draw_sees_one_card_fewer():
    rows = {
        row.label: row for row in land_odds(33, 99, trials=100, skip_first_draw=True)
    }
    assert rows["Land drop through turn 1"].exact == pytest.approx(
        exact_at_least(1, 33, 99, 7)
    )


def test_same_seed_same_numbers():
    assert land_odds(33, 99, trials=2000, seed=1) == land_odds(
        33, 99, trials=2000, seed=1
    )


def test_different_seed_different_numbers():
    first = [row.simulated for row in land_odds(33, 99, trials=2000, seed=1)]
    second = [row.simulated for row in land_odds(33, 99, trials=2000, seed=2)]
    assert first != second


@pytest.mark.parametrize(
    ("lands", "skip_first_draw"),
    [(33, False), (39, False), (33, True)],  # Goreclaw/Krenko, Ghalta, 2-player draw
)
def test_simulation_agrees_with_exact_within_one_point(lands, skip_first_draw):
    for row in land_odds(lands, 99, skip_first_draw=skip_first_draw):
        assert abs(row.simulated - row.exact) <= 0.01, row


def test_library_too_small_raises():
    with pytest.raises(ValueError, match="library of 10 cards is too small to see 12"):
        land_odds(5, 10, trials=10)


def test_too_many_lands_raises_before_simulating():
    with pytest.raises(ValueError):
        land_odds(100, 99, trials=10)


def test_zero_trials_raises():
    with pytest.raises(ValueError, match="trials must be at least 1"):
        land_odds(33, 99, trials=0)
