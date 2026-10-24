import pytest

from fishbowl.stats.groups import CHECKPOINTS, what_if
from fishbowl.stats.lands import exact_at_least


def counts(rows):
    return [row.count for row in rows]


def test_rows_around_current():
    rows = what_if(7, 99, trials=100)
    assert counts(rows) == [3, 5, 7, 9, 11]
    assert [row.is_current for row in rows] == [False, False, True, False, False]
    assert [row.simulated is not None for row in rows] == [
        False,
        False,
        True,
        False,
        False,
    ]


def test_zero_count_rows():
    rows = what_if(0, 99, trials=100)
    assert counts(rows) == [0, 2, 4]
    assert rows[0].chances == [0.0] * len(CHECKPOINTS)


def test_rows_clipped_at_library():
    rows = what_if(10, 12, trials=100)
    assert counts(rows) == [6, 8, 10, 12]
    assert rows[-1].chances == [1.0] * len(CHECKPOINTS)


def test_exact_values():
    rows = what_if(7, 99, trials=100)
    current = next(row for row in rows if row.is_current)
    assert current.chances[0] == pytest.approx(exact_at_least(1, 7, 99, 7))
    assert round(current.chances[0], 3) == 0.412  # 1 - C(92,7)/C(99,7)
    # more cards seen can only help
    assert current.chances == sorted(current.chances)
    # more group cards can only help, in every column
    for column in range(len(CHECKPOINTS)):
        values = [row.chances[column] for row in rows]
        assert values == sorted(values)


@pytest.mark.parametrize("count", [0, 2, 7, 12])
def test_simulated_matches_exact(count):
    rows = what_if(count, 99)
    current = next(row for row in rows if row.is_current)
    assert current.simulated is not None
    assert abs(current.simulated - current.chances[0]) < 0.01


def test_same_seed_same_numbers():
    assert what_if(7, 99, trials=2000, seed=7) == what_if(7, 99, trials=2000, seed=7)
    assert what_if(7, 99, trials=2000, seed=7) != what_if(7, 99, trials=2000, seed=8)


@pytest.mark.parametrize(
    "args, kwargs",
    [((7, 9), {}), ((-1, 99), {}), ((100, 99), {}), ((7, 99), {"trials": 0})],
)
def test_invalid_inputs_raise(args, kwargs):
    with pytest.raises(ValueError):
        what_if(*args, **kwargs)
