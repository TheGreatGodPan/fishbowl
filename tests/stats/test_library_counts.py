"""Tests for counting lands and library size from a parsed deck."""

import pytest

from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.parser import parse_deck
from fishbowl.stats.lands import library_counts

GORECLAW = "Goreclaw, Terror of Qal Sisma"


@pytest.fixture
def lookup(card_db):
    with CardLookup(card_db) as opened:
        yield opened


def test_commander_is_not_in_the_library(lookup):
    deck = parse_deck(
        f"Commander: {GORECLAW}\n1 {GORECLAW}\n30 Forest\n1 Sol Ring\n", lookup
    )
    assert library_counts(deck, lookup) == (30, 31)


def test_two_commanders_both_leave_the_library(lookup):
    text = f"Commander\n1 {GORECLAW}\n1 Krenko, Mob Boss\nDeck\n10 Forest\n2 Sol Ring\n"
    assert library_counts(parse_deck(text, lookup), lookup) == (10, 12)


def test_no_commander_uses_every_card(lookup):
    deck = parse_deck("10 Forest\n2 Sol Ring\n", lookup)
    assert library_counts(deck, lookup) == (10, 12)


def test_front_face_decides_land(lookup):
    text = (
        f"Commander: {GORECLAW}\n1 Westvale Abbey\n1 Witch Enchanter\n1 Command Tower\n"
    )
    # Westvale Abbey (front: Land) and Command Tower are lands; Witch Enchanter's land is its back.
    assert library_counts(parse_deck(text, lookup), lookup) == (2, 3)
