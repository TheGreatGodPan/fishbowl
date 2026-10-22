import pytest

from fishbowl.stats.lands import exact_at_least
from fishbowl.stats.mulligan import mulligan_odds


@pytest.mark.parametrize("lands", (33, 39))
@pytest.mark.parametrize("free_first", (True, False))
def test_simulated_matches_exact(lands, free_first):
    odds = mulligan_odds(lands, 99, free_first=free_first)
    for row in [*odds.keep_rows, odds.hand_size]:
        assert abs(row.simulated - row.exact) < 0.01, row.label


def test_labels():
    odds = mulligan_odds(33, 99, trials=100)
    assert [r.label for r in odds.keep_rows] == [
        "Keep 7 (first hand)",
        "Keep 7 (free mulligan)",
        "Keep 6",
        "Keep 5 (forced)",
    ]
    assert odds.hand_size.label == "Average hand size"
    assert [r.label for r in odds.drop_rows] == [
        f"Land drop through turn {t}" for t in range(1, 6)
    ]
    no_free = mulligan_odds(33, 99, trials=100, free_first=False)
    assert [r.label for r in no_free.keep_rows] == [
        "Keep 7",
        "Keep 6",
        "Keep 5 (forced)",
    ]


def test_exact_values_for_33_of_99():
    odds = mulligan_odds(33, 99, trials=100)
    assert odds.keep_rows[0].exact == pytest.approx(0.741, abs=0.001)
    assert odds.drop_rows[2].exact == pytest.approx(exact_at_least(3, 33, 99, 10))


def test_mulligans_help_turn_two():
    odds = mulligan_odds(33, 99, trials=20_000)
    assert odds.drop_rows[1].simulated > odds.drop_rows[1].exact


def test_same_seed_same_numbers():
    assert mulligan_odds(33, 99, trials=2000, seed=7) == mulligan_odds(
        33, 99, trials=2000, seed=7
    )
    assert mulligan_odds(33, 99, trials=2000, seed=7) != mulligan_odds(
        33, 99, trials=2000, seed=8
    )


def test_no_lands_all_forced():
    odds = mulligan_odds(0, 99, trials=500)
    forced = odds.keep_rows[-1]
    assert forced.exact == pytest.approx(1.0) and forced.simulated == 1.0
    assert (
        odds.hand_size.exact == pytest.approx(5.0) and odds.hand_size.simulated == 5.0
    )


def test_all_lands_all_forced():
    odds = mulligan_odds(20, 20, trials=500)
    assert odds.keep_rows[-1].simulated == 1.0
    assert all(row.simulated == 1.0 for row in odds.drop_rows)


@pytest.mark.parametrize(
    ("lands", "library", "trials"),
    [(5, 11, 100), (-1, 99, 100), (100, 99, 100), (33, 99, 0)],
)
def test_invalid_inputs_raise(lands, library, trials):
    with pytest.raises(ValueError):
        mulligan_odds(lands, library, trials=trials)
