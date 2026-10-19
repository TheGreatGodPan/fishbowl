"""Tests for each deck-building check, one at a time."""

import dataclasses

import pytest

from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.model import ParsedDeck, Problem
from fishbowl.deck.parser import parse_deck
from fishbowl.deck.validator import (
    Issue,
    check_color_identity,
    check_commanders,
    check_copies,
    check_deck_size,
    check_legality,
    check_unreadable,
    copy_limit,
)

GORECLAW = "Goreclaw, Terror of Qal Sisma"


@pytest.fixture
def lookup(card_db):
    with CardLookup(card_db) as opened:
        yield opened


def parsed(text, lookup):
    """Parse text and gather the Card for every card in it, keyed by oracle_id."""
    deck = parse_deck(text, lookup)
    cards = {}
    for entry in [*deck.cards, *deck.commanders]:
        card = lookup.find(entry.name)
        assert card is not None
        cards[entry.oracle_id] = card
    return deck, cards


def codes(issues):
    return [issue.code for issue in issues]


# --- copy_limit ---


@pytest.mark.parametrize(
    ("name", "limit"),
    [
        ("Sol Ring", 1),
        ("Forest", None),  # basic land: any number
        ("Relentless Rats", None),  # "any number of cards named"
        ("Seven Dwarves", 7),  # "up to seven cards named"
    ],
)
def test_copy_limit(lookup, name, limit):
    card = lookup.find(name)
    assert card is not None
    assert copy_limit(card) == limit


def test_unknown_number_word_falls_back_to_one(lookup):
    card = lookup.find("Seven Dwarves")
    assert card is not None
    odd = dataclasses.replace(
        card, oracle_text="A deck can have up to umpteen cards named Seven Dwarves."
    )
    assert copy_limit(odd) == 1


# --- unreadable lines ---


def test_unreadable_lines_plural():
    deck = ParsedDeck(problems=[Problem(2, "x", "r"), Problem(5, "y", "r")])
    assert check_unreadable(deck, {}) == [
        Issue(
            "unreadable_lines",
            "2 lines couldn't be read, so the deck can't be fully checked.",
        )
    ]


def test_one_unreadable_line_is_singular():
    deck = ParsedDeck(problems=[Problem(2, "x", "r")])
    assert check_unreadable(deck, {})[0].message == (
        "1 line couldn't be read, so the deck can't be fully checked."
    )


def test_no_problems_no_issue():
    assert check_unreadable(ParsedDeck(), {}) == []


# --- deck size ---


def test_exactly_100_is_fine(lookup):
    deck, cards = parsed(f"Commander: {GORECLAW}\n99 Forest\n", lookup)
    assert check_deck_size(deck, cards) == []


def test_wrong_size_is_an_error(lookup):
    deck, cards = parsed(f"Commander: {GORECLAW}\n98 Forest\n", lookup)
    assert check_deck_size(deck, cards) == [
        Issue("deck_size", "Deck has 99 cards; a Commander deck needs exactly 100.")
    ]


# --- commanders ---


def test_no_commander(lookup):
    deck, cards = parsed("1 Sol Ring\n", lookup)
    assert check_commanders(deck, cards) == [
        Issue("no_commander", "No commander identified.")
    ]


def test_eligible_commanders_are_fine(lookup):
    for name in (
        GORECLAW,
        "Teferi, Temporal Archmage",
    ):  # creature, and "can be your commander"
        deck, cards = parsed(f"Commander: {name}\n", lookup)
        assert check_commanders(deck, cards) == []


def test_ineligible_commander(lookup):
    deck, cards = parsed("Commander: Sol Ring\n", lookup)
    assert check_commanders(deck, cards) == [
        Issue(
            "ineligible_commander",
            "Sol Ring can't be a commander (it isn't a legendary creature).",
        )
    ]


# --- copies ---


def test_two_sol_rings(lookup):
    deck, cards = parsed(
        "2 Sol Ring\n50 Forest\n30 Relentless Rats\n7 Seven Dwarves\n", lookup
    )
    assert check_copies(deck, cards) == [
        Issue("too_many_copies", "2 copies of Sol Ring; only 1 allowed.")
    ]


def test_eight_dwarves(lookup):
    deck, cards = parsed("8 Seven Dwarves\n", lookup)
    assert check_copies(deck, cards) == [
        Issue("too_many_copies", "8 copies of Seven Dwarves; up to 7 allowed.")
    ]


# --- color identity ---


def test_on_color_deck_is_fine(lookup):
    deck, cards = parsed(
        f"Commander: {GORECLAW}\n1 Sol Ring\n1 Forest\n1 The Great Henge\n", lookup
    )
    assert check_color_identity(deck, cards) == []


def test_off_color_card(lookup):
    deck, cards = parsed(f"Commander: {GORECLAW}\n1 Witch Enchanter\n", lookup)
    assert check_color_identity(deck, cards) == [
        Issue(
            "off_color",
            "Witch Enchanter // Witch-Blessed Meadow (W) is outside the commander's color identity (G).",
        )
    ]


def test_two_commanders_combine_identity(lookup):
    text = f"Commander\n1 {GORECLAW}\n1 Krenko, Mob Boss\nDeck\n1 Forest\n1 Seven Dwarves\n"
    deck, cards = parsed(text, lookup)
    assert check_color_identity(deck, cards) == []  # G + R covers both


def test_off_color_skipped_without_commander(lookup):
    deck, cards = parsed("1 Witch Enchanter\n1 Forest\n", lookup)
    assert check_color_identity(deck, cards) == []  # no_commander already reports it


def test_colorless_commander_message(lookup):
    # A colorless commander: build one by giving Goreclaw an empty identity in memory.
    deck, cards = parsed(f"Commander: {GORECLAW}\n1 Forest\n", lookup)
    commander_id = deck.commanders[0].oracle_id
    cards[commander_id] = dataclasses.replace(cards[commander_id], color_identity="")
    assert check_color_identity(deck, cards) == [
        Issue(
            "off_color",
            "Forest (G) is outside the commander's color identity (colorless).",
        )
    ]


# --- legality ---


def test_banned_and_not_legal(lookup):
    deck, cards = parsed("1 Sylvan Primordial\n1 Absorb Energy\n1 Sol Ring\n", lookup)
    assert check_legality(deck, cards) == [
        Issue("banned", "Sylvan Primordial is banned in Commander."),
        Issue("not_legal", "Absorb Energy is not legal in Commander (not_legal)."),
    ]


def test_back_face_creature_cannot_be_commander(lookup):
    deck, cards = parsed("Commander: Westvale Abbey\n", lookup)
    assert check_commanders(deck, cards) == [
        Issue(
            "ineligible_commander",
            "Westvale Abbey // Ormendahl, Profane Prince can't be a commander "
            "(it isn't a legendary creature).",
        )
    ]


def test_grist_can_be_commander(lookup):
    deck, cards = parsed("Commander: Grist, the Hunger Tide\n", lookup)
    assert check_commanders(deck, cards) == []
