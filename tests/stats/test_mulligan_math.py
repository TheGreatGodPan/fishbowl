import pytest

from fishbowl.stats.mulligan import hand_sizes, keep_rates, keeps, lands_after_bottoming


def test_hand_sizes():
    assert hand_sizes() == (7, 7, 6, 5)
    assert hand_sizes(free_first=False) == (7, 6, 5)


@pytest.mark.parametrize(
    ("lands", "expected"),
    [(0, False), (1, False), (2, True), (3, True), (5, True), (6, False), (7, False)],
)
def test_keeps(lands, expected):
    assert keeps(lands) is expected


@pytest.mark.parametrize(
    ("lands", "to_bottom", "expected"),
    [(7, 2, 5), (6, 2, 4), (4, 2, 3), (2, 2, 2), (5, 0, 5), (0, 2, 0), (5, 1, 4)],
)
def test_bottoming_examples(lands, to_bottom, expected):
    assert lands_after_bottoming(lands, to_bottom) == expected


@pytest.mark.parametrize("lands", range(8))
@pytest.mark.parametrize("to_bottom", (0, 1, 2))
def test_bottoming_never_exceeds_hand(lands, to_bottom):
    assert lands_after_bottoming(lands, to_bottom) <= 7 - to_bottom


def test_keep_rates_hand_checked():
    assert keep_rates(0.5) == pytest.approx([0.5, 0.25, 0.125, 0.125])
    assert keep_rates(0.5, free_first=False) == pytest.approx([0.5, 0.25, 0.25])


@pytest.mark.parametrize("free_first", (True, False))
def test_keep_rates_edges_and_sum(free_first):
    attempts = len(hand_sizes(free_first))
    assert keep_rates(1.0, free_first) == pytest.approx([1.0] + [0.0] * (attempts - 1))
    assert keep_rates(0.0, free_first) == pytest.approx([0.0] * (attempts - 1) + [1.0])
    for p in (0.1, 0.741, 0.9):
        assert sum(keep_rates(p, free_first)) == pytest.approx(1.0)
