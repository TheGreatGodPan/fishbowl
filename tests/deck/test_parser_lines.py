"""Tests for reading single decklist lines (no database needed)."""

import pytest

from fishbowl.deck.model import DeckEntry, ParsedDeck
from fishbowl.deck.parser import (
    CardLine,
    explicit_commander_name,
    parse_card_line,
    section_for_header,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 Sol Ring", CardLine(1, "Sol Ring")),
        ("1x Sol Ring", CardLine(1, "Sol Ring")),
        ("2X Forest", CardLine(2, "Forest")),
        ("Sol Ring", CardLine(1, "Sol Ring")),
        ("1 Sol Ring (SLC) 19 *F*", CardLine(1, "Sol Ring")),  # real Moxfield line
        ("1 Llanowar Elves (PDMU) 1★ *F*", CardLine(1, "Llanowar Elves")),  # real
        ("1 Forest (TMT) 257 *F*", CardLine(1, "Forest")),  # real
        ("1 Sol Ring (SLC)", CardLine(1, "Sol Ring")),
        ("1x Sol Ring (cmm) 400 [Ramp]", CardLine(1, "Sol Ring")),  # Archidekt
        ("1x Sol Ring (cmm) 400 *E* [Ramp] ^Have,#37d67a^", CardLine(1, "Sol Ring")),
        (
            "1x Goreclaw, Terror of Qal Sisma (m19) 180 [Commander{top}]",
            CardLine(1, "Goreclaw, Terror of Qal Sisma", commander_tag=True),
        ),
        ("1\tSol   Ring  ", CardLine(1, "Sol Ring")),
        (
            "1 Goreclaw, Terror of Qal Sisma (CMM) 293",
            CardLine(1, "Goreclaw, Terror of Qal Sisma"),
        ),
        (
            "1 B.F.M. (Big Furry Monster)",
            CardLine(1, "B.F.M. (Big Furry Monster)"),
        ),  # real name with parentheses
    ],
)
def test_parse_card_line(text, expected):
    assert parse_card_line(text) == expected


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("0 Sol Ring", "quantity 0 is outside 1-999"),
        ("1000 Forest", "quantity 1000 is outside 1-999"),
        ("*F*", "no card name"),
        ("[Ramp]", "no card name"),
    ],
)
def test_bad_card_line_raises_with_reason(text, reason):
    with pytest.raises(ValueError, match=reason):
        parse_card_line(text)


def test_very_long_line_is_refused_quickly():
    # Length is checked before any regex, so a huge pasted line fails at once.
    with pytest.raises(ValueError, match=r"line too long \(100000 characters\)"):
        parse_card_line("[a]" * 33333 + "x")


def test_long_digit_quantity_gives_our_reason():
    with pytest.raises(ValueError, match="is outside 1-999"):
        parse_card_line("1" * 400 + " Sol Ring")


def test_line_at_the_limit_is_still_parsed():
    assert parse_card_line("1 " + "a" * 498) == CardLine(1, "a" * 498)


@pytest.mark.parametrize(
    ("line", "section"),
    [
        ("Commander", "commander"),
        ("COMMANDERS", "commander"),
        ("Commander (1)", "commander"),
        ("Deck", "main"),
        ("Mainboard:", "main"),
        ("Main", "main"),
        ("Sideboard", "out"),
        ("Maybeboard (12)", "out"),
        ("Companion", "out"),
        ("1 Sol Ring", None),
        ("Commander: Goreclaw, Terror of Qal Sisma", None),
    ],
)
def test_section_for_header(line, section):
    assert section_for_header(line) == section


@pytest.mark.parametrize(
    ("line", "name"),
    [
        ("Commander: Goreclaw, Terror of Qal Sisma", "Goreclaw, Terror of Qal Sisma"),
        ("commander:Krenko, Mob Boss", "Krenko, Mob Boss"),
        ("Commander", None),
        ("Commander:", None),
        ("1 Sol Ring", None),
    ],
)
def test_explicit_commander_name(line, name):
    assert explicit_commander_name(line) == name


def test_parsed_deck_total_adds_quantities():
    deck = ParsedDeck(
        cards=[DeckEntry("Sol Ring", "a", 1), DeckEntry("Forest", "b", 26)]
    )
    assert deck.total == 27
    assert ParsedDeck().total == 0
