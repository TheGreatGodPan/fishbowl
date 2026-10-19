"""Tests for validate(): all checks together, plus notes."""

import pytest

from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.model import DeckEntry, ParsedDeck
from fishbowl.deck.parser import parse_deck
from fishbowl.deck.validator import Issue, validate

GORECLAW = "Goreclaw, Terror of Qal Sisma"


@pytest.fixture
def lookup(card_db):
    with CardLookup(card_db) as opened:
        yield opened


def test_legal_deck(lookup):
    deck = parse_deck(f"Commander: {GORECLAW}\n1 Sol Ring\n98 Forest\n", lookup)
    report = validate(deck, lookup)
    assert report.errors == []
    assert report.is_legal is True
    assert report.notes == [Issue("game_changers", "Game Changers: 0")]


def test_game_changers_are_named(lookup):
    deck = parse_deck(
        f"Commander: {GORECLAW}\n1 Survival of the Fittest\n98 Forest\n", lookup
    )
    report = validate(deck, lookup)
    assert report.is_legal is True
    assert report.notes == [
        Issue("game_changers", "Game Changers: 1 (Survival of the Fittest)")
    ]


def test_broken_deck_reports_every_error(lookup):
    text = (
        "Commander: Sol Ring\n"  # ineligible commander
        "2 Sol Ring\n"  # too many copies
        "1 Witch Enchanter\n"  # off-color (W) for a colorless commander
        "1 Sylvan Primordial\n"  # banned (and off-color)
        "1 Absorb Energy\n"  # not legal (and off-color)
        "1 Not A Real Card\n"  # unreadable
    )
    report = validate(parse_deck(text, lookup), lookup)
    assert report.is_legal is False
    assert [issue.code for issue in report.errors] == [
        "unreadable_lines",
        "deck_size",
        "ineligible_commander",
        "too_many_copies",
        "off_color",
        "off_color",
        "off_color",
        "banned",
        "not_legal",
    ]


def test_no_commander_error(lookup):
    report = validate(parse_deck("1 Sol Ring\n99 Forest\n", lookup), lookup)
    assert [issue.code for issue in report.errors] == ["no_commander"]


def test_two_commanders_note(lookup):
    text = f"Commander\n1 {GORECLAW}\n1 Krenko, Mob Boss\nDeck\n98 Forest\n"
    report = validate(parse_deck(text, lookup), lookup)
    assert report.is_legal is True
    assert (
        Issue(
            "pairing_unchecked",
            "Commander pairing not checked yet (Partner/Background rules come later).",
        )
        in report.notes
    )


def test_left_out_note(lookup):
    text = (
        f"Commander: {GORECLAW}\n99 Forest\nSideboard\n2 Sol Ring\n1 Krenko, Mob Boss\n"
    )
    report = validate(parse_deck(text, lookup), lookup)
    assert report.is_legal is True  # sideboard cards aren't checked
    assert (
        Issue(
            "left_out",
            "3 left-out cards (sideboard, maybeboard, companion) weren't checked.",
        )
        in report.notes
    )


def test_card_missing_from_lookup_is_skipped(lookup):
    deck = ParsedDeck(
        cards=[DeckEntry("Imaginary Card", "no-such-id", 1)],
        commanders=[DeckEntry("Imaginary Card", "no-such-id", 1)],
    )
    report = validate(deck, lookup)  # must not raise
    assert "deck_size" in [issue.code for issue in report.errors]


def test_one_left_out_card_is_singular(lookup):
    text = f"Commander: {GORECLAW}\n99 Forest\nSideboard\n1 Sol Ring\n"
    report = validate(parse_deck(text, lookup), lookup)
    assert (
        Issue(
            "left_out",
            "1 left-out card (sideboard, maybeboard, companion) wasn't checked.",
        )
        in report.notes
    )
