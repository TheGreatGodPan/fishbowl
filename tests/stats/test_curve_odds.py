"""Tests for commander-on-curve odds: pips, land colours and the odds."""

import pytest

from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.parser import parse_deck
from fishbowl.stats.curve import colour_pips, curve_odds, land_colours
from fishbowl.stats.lands import exact_at_least

GORECLAW = "Goreclaw, Terror of Qal Sisma"


@pytest.mark.parametrize(
    ("cost", "expected"),
    [
        ("{2}{R}{R}", {"R": 2}),
        ("{3}{G}", {"G": 1}),
        ("{10}{G}{G}", {"G": 2}),
        ("{1}{G/W}", {}),
        ("{X}{U}{B}", {"U": 1, "B": 1}),
        ("{8}{C}{C}", {"C": 2}),
        (None, {}),
        ("", {}),
    ],
)
def test_colour_pips(cost, expected):
    assert colour_pips(cost) == expected


def test_pip_keys_are_in_wubrg_order():
    assert list(colour_pips("{X}{B}{U}")) == ["U", "B"]


def test_lands_row_exact():
    odds = curve_odds(4, {"G": 1}, ["G"] * 33, 99, trials=100)
    assert odds.lands_exact == pytest.approx(exact_at_least(4, 33, 99, 11))
    assert round(odds.lands_exact, 3) == 0.533


@pytest.mark.parametrize(("mana_value", "lands"), [(4, 33), (12, 39)])
def test_simulated_matches_exact(mana_value, lands):
    odds = curve_odds(mana_value, {"G": 1}, ["G"] * lands, 99)
    assert abs(odds.lands_simulated - odds.lands_exact) < 0.01


def test_colours_never_above_lands():
    odds = curve_odds(4, {"G": 2}, ["G"] * 20 + ["R"] * 13, 99)
    assert odds.colours_simulated <= odds.lands_simulated


def test_all_sources_equal_lands():
    odds = curve_odds(4, {"G": 1}, ["G"] * 33, 99)
    assert odds.colours_simulated == odds.lands_simulated


def test_colourless_lands_never_sources():
    odds = curve_odds(4, {"G": 1}, [""] * 33, 99)
    assert odds.colours_simulated == 0.0
    assert odds.lands_simulated > 0


def test_same_seed_same_numbers():
    lands = ["G"] * 20 + ["R"] * 13
    first = curve_odds(4, {"G": 2}, lands, 99, trials=2_000, seed=7)
    again = curve_odds(4, {"G": 2}, lands, 99, trials=2_000, seed=7)
    other = curve_odds(4, {"G": 2}, lands, 99, trials=2_000, seed=8)
    assert first == again
    assert first != other


@pytest.mark.parametrize(
    ("mana_value", "land_list", "library", "trials"),
    [
        (0, ["G"] * 33, 99, 100),
        (5, ["G"] * 5, 11, 100),
        (4, ["G"] * 100, 99, 100),
        (4, ["G"] * 33, 99, 0),
    ],
)
def test_invalid_inputs_raise(mana_value, land_list, library, trials):
    with pytest.raises(ValueError):
        curve_odds(mana_value, {"G": 1}, land_list, library, trials=trials)


def test_land_colours(card_db):
    text = (
        f"Commander: {GORECLAW}\n1 {GORECLAW}\n10 Forest\n1 Command Tower\n5 Sol Ring\n"
    )
    with CardLookup(card_db) as lookup:
        result = land_colours(parse_deck(text, lookup), lookup)
    assert sorted(result) == sorted(["G"] * 10 + [""])
