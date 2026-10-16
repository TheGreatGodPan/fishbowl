"""Tests for finding commander candidates and letting the user pick one."""

from fishbowl.deck.commander import ask_for_commander, commander_candidates
from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.parser import parse_deck

GORECLAW = "Goreclaw, Terror of Qal Sisma"
KRENKO = "Krenko, Mob Boss"


def test_candidates_are_legendary_creatures_sorted(card_db):
    with CardLookup(card_db) as lookup:
        deck = parse_deck(
            f"1 Sol Ring\n1 {KRENKO}\n1 The Great Henge\n1 {GORECLAW}\n", lookup
        )
        # The Great Henge is legendary but not a creature; Sol Ring is neither.
        assert commander_candidates(deck, lookup) == [GORECLAW, KRENKO]


def fake_input(*answers):
    """A stand-in for input(): returns the given answers one by one."""
    remaining = list(answers)

    def read(prompt):
        if not remaining:
            raise EOFError  # like pressing Ctrl+Z / Ctrl+D
        return remaining.pop(0)

    return read


def test_pick_by_number():
    shown = []
    assert (
        ask_for_commander([GORECLAW, KRENKO], fake_input("2"), shown.append) == KRENKO
    )
    assert f"  1. {GORECLAW}" in shown


def test_type_letters_to_filter_then_pick():
    shown = []
    chosen = ask_for_commander(
        [GORECLAW, KRENKO, "Surrak and Goreclaw"], fake_input("gore", "2"), shown.append
    )
    assert chosen == "Surrak and Goreclaw"
    assert f"  2. {KRENKO}" in shown  # first, the full list
    assert "  2. Surrak and Goreclaw" in shown  # then, the filtered list


def test_out_of_range_number_asks_again():
    shown = []
    assert ask_for_commander([GORECLAW], fake_input("5", "1"), shown.append) == GORECLAW
    assert "Pick a number from 1 to 1." in shown


def test_no_match_says_so_and_enter_skips():
    shown = []
    assert ask_for_commander([GORECLAW], fake_input("zzz", ""), shown.append) is None
    assert 'No candidates match "zzz".' in shown


def test_no_candidates_returns_none_without_asking():
    shown = []
    assert ask_for_commander([], fake_input(), shown.append) is None
    assert shown == ["No commander candidates found in this deck."]


def test_end_of_input_returns_none():
    assert ask_for_commander([GORECLAW], fake_input(), lambda message: None) is None


def test_can_be_your_commander_text_makes_a_candidate(card_db):
    with CardLookup(card_db) as lookup:
        deck = parse_deck(
            "1 Sol Ring\n1 Teferi, Temporal Archmage\n1 Command Tower\n", lookup
        )
        # Teferi is a planeswalker: only his "can be your commander" text qualifies him.
        assert commander_candidates(deck, lookup) == ["Teferi, Temporal Archmage"]
