"""Tests for turning a whole decklist into a ParsedDeck."""

import pytest

from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.parser import parse_deck

SOL = "6ad8011d-3471-4369-9d68-b264cc027487"
GORECLAW = "Goreclaw, Terror of Qal Sisma"


@pytest.fixture
def lookup(card_db):
    with CardLookup(card_db) as opened:
        yield opened  # yield: the test runs here, then the lookup is closed


def names(entries):
    return [(entry.name, entry.quantity) for entry in entries]


def test_adds_up_the_same_card_across_lines(lookup):
    deck = parse_deck(
        "1 Sol Ring\n1 Krenko, Mob Boss\n2 Sol Ring (SLC) 19 *F*\n", lookup
    )
    assert names(deck.cards) == [("Sol Ring", 3), ("Krenko, Mob Boss", 1)]
    assert deck.cards[0].oracle_id == SOL
    assert deck.total == 4
    assert deck.problems == []


def test_alternate_and_front_face_names_resolve(lookup):
    deck = parse_deck("1 The Banyan Tree (TLE) 41 *F*\n1 Witch Enchanter\n", lookup)
    assert names(deck.cards) == [
        ("The Great Henge", 1),
        ("Witch Enchanter // Witch-Blessed Meadow", 1),
    ]


def test_unknown_card_is_a_problem_and_the_rest_still_parses(lookup):
    deck = parse_deck("1 Sol Ring\n1 Sol Rnig\n", lookup)
    assert names(deck.cards) == [("Sol Ring", 1)]
    assert len(deck.problems) == 1
    problem = deck.problems[0]
    assert (problem.line_number, problem.text, problem.reason) == (
        2,
        "1 Sol Rnig",
        'unknown card "Sol Rnig"',
    )


def test_bad_quantity_is_a_problem(lookup):
    deck = parse_deck("0 Sol Ring\n", lookup)
    assert deck.cards == []
    assert deck.problems[0].reason == "quantity 0 is outside 1-999"


def test_comments_and_blank_lines_are_ignored(lookup):
    deck = parse_deck("// my deck\n# notes\n\n1 Sol Ring\n\n", lookup)
    assert names(deck.cards) == [("Sol Ring", 1)]
    assert deck.problems == []


def test_commander_section_header(lookup):
    deck = parse_deck(f"Commander\n1 {GORECLAW}\n\nDeck\n1 Sol Ring\n", lookup)
    assert names(deck.commanders) == [(GORECLAW, 1)]
    assert deck.total == 2  # commanders are part of the deck


def test_sideboard_and_maybeboard_are_left_out(lookup):
    deck = parse_deck(
        "1 Sol Ring\nSideboard\n1 Krenko, Mob Boss\nMaybeboard (1)\n1 The Great Henge\n",
        lookup,
    )
    assert names(deck.cards) == [("Sol Ring", 1)]
    assert names(deck.left_out) == [("Krenko, Mob Boss", 1), ("The Great Henge", 1)]


def test_archidekt_commander_tag(lookup):
    deck = parse_deck(
        f"1x {GORECLAW} (m19) 180 [Commander{{top}}]\n1x Sol Ring (cmm) 400 [Ramp]\n",
        lookup,
    )
    assert names(deck.commanders) == [(GORECLAW, 1)]
    assert deck.total == 2


def test_explicit_commander_line_is_not_counted_twice(lookup):
    deck = parse_deck(
        f"Commander: {GORECLAW}\n1 {GORECLAW} (CMM) 293\n1 Sol Ring\n", lookup
    )
    assert names(deck.commanders) == [(GORECLAW, 1)]
    assert names(deck.cards) == [(GORECLAW, 1), ("Sol Ring", 1)]


def test_explicit_commander_line_adds_the_card_when_not_listed(lookup):
    deck = parse_deck(f"Commander: {GORECLAW}\n1 Sol Ring\n", lookup)
    assert names(deck.commanders) == [(GORECLAW, 1)]
    assert deck.total == 2


def test_explicit_commander_line_with_printing_details(lookup):
    deck = parse_deck(f"Commander: {GORECLAW} (CMM) 293 *F*\n1 Sol Ring\n", lookup)
    assert names(deck.commanders) == [(GORECLAW, 1)]


def test_explicit_commander_unknown_is_a_problem(lookup):
    deck = parse_deck("Commander: Not A Real Card\n1 Sol Ring\n", lookup)
    assert deck.commanders == []
    assert deck.problems[0].line_number == 1
    assert deck.problems[0].reason == 'unknown card "Not A Real Card"'


def test_final_block_after_blank_line_is_the_commander(lookup):
    # The real Ghalta export ends this way: the list, a blank line, then the commander.
    deck = parse_deck(f"1 Sol Ring\n1 Krenko, Mob Boss\n\n1 {GORECLAW}\n", lookup)
    assert names(deck.commanders) == [(GORECLAW, 1)]
    assert deck.total == 3


def test_no_signal_means_no_commander(lookup):
    deck = parse_deck(f"1 {GORECLAW}\n1 Sol Ring\n", lookup)
    assert deck.commanders == []  # never guess from line order


def test_final_block_of_three_is_not_a_commander(lookup):
    deck = parse_deck(
        f"1 Sol Ring\n\n1 {GORECLAW}\n1 Krenko, Mob Boss\n1 The Great Henge\n", lookup
    )
    assert deck.commanders == []


def test_more_than_two_commanders_is_a_problem(lookup):
    text = f"Commander\n1 {GORECLAW}\n1 Krenko, Mob Boss\n1 The Great Henge\n"
    deck = parse_deck(text, lookup)
    assert names(deck.commanders) == [(GORECLAW, 1), ("Krenko, Mob Boss", 1)]
    assert deck.problems[0].line_number == 0
    assert "more than 2 commanders" in deck.problems[0].reason


def test_too_many_lines_is_refused(lookup):
    deck = parse_deck("1 Sol Ring\n" * 1001, lookup)
    assert deck.cards == []
    assert len(deck.problems) == 1
    assert deck.problems[0].line_number == 0
    assert (
        deck.problems[0].reason
        == "too many lines (1001); a Commander deck has 100 cards"
    )


def test_windows_line_endings_and_bom(lookup):
    deck = parse_deck("\ufeff1 Sol Ring\r\n1 Krenko, Mob Boss\r\n", lookup)
    assert names(deck.cards) == [("Sol Ring", 1), ("Krenko, Mob Boss", 1)]
    assert deck.problems == []


def test_problem_text_is_trimmed_to_200_characters(lookup):
    deck = parse_deck("1 " + "x" * 500, lookup)
    assert len(deck.problems[0].text) == 200


def test_junk_lines_never_raise(lookup):
    junk = [
        "1x",
        "[]",
        "*F*",
        "((((",
        "\x00\x01\x02",
        "99999999999999999999999 Sol Ring",
        "^^",
        ":",
        "\ud800x",
    ]
    deck = parse_deck("\n".join(junk), lookup)
    assert deck.cards == []
    assert len(deck.problems) == len(junk)


def test_commander_tag_in_sideboard_is_ignored(lookup):
    deck = parse_deck(f"1 Sol Ring\nSideboard\n1 {GORECLAW} [Commander]\n", lookup)
    assert deck.commanders == []
    assert names(deck.left_out) == [(GORECLAW, 1)]


def test_blank_line_ends_commander_section(lookup):
    deck = parse_deck(
        f"Commander\n1 {GORECLAW}\n\n1 Sol Ring\n1 Krenko, Mob Boss\n", lookup
    )
    assert names(deck.commanders) == [(GORECLAW, 1)]
    assert deck.problems == []
    assert deck.total == 3


def test_blank_line_does_not_end_sideboard(lookup):
    deck = parse_deck(
        "1 Sol Ring\nSideboard\n1 Krenko, Mob Boss\n\n1 The Great Henge\n", lookup
    )
    assert names(deck.left_out) == [("Krenko, Mob Boss", 1), ("The Great Henge", 1)]


def test_explicit_commander_line_ignores_final_block(lookup):
    deck = parse_deck(
        f"Commander: {GORECLAW}\n1 Sol Ring\n\n1 Krenko, Mob Boss\n", lookup
    )
    assert names(deck.commanders) == [(GORECLAW, 1)]


def test_final_block_of_two_is_partner_commanders(lookup):
    deck = parse_deck(f"1 Sol Ring\n\n1 {GORECLAW}\n1 Krenko, Mob Boss\n", lookup)
    assert names(deck.commanders) == [(GORECLAW, 1), ("Krenko, Mob Boss", 1)]


def test_final_block_of_lands_is_not_a_commander(lookup):
    deck = parse_deck("1 Sol Ring\n1 Krenko, Mob Boss\n\n1 Command Tower\n", lookup)
    assert deck.commanders == []


def test_final_block_with_quantity_over_one_is_not_a_commander(lookup):
    deck = parse_deck("1 Sol Ring\n\n2 Krenko, Mob Boss\n", lookup)
    assert deck.commanders == []


def test_final_block_of_non_creature_is_not_a_commander(lookup):
    deck = parse_deck("1 Krenko, Mob Boss\n\n1 Sol Ring\n", lookup)
    assert deck.commanders == []


def test_final_block_planeswalker_commander(lookup):
    deck = parse_deck("1 Sol Ring\n\n1 Teferi, Temporal Archmage\n", lookup)
    assert names(deck.commanders) == [("Teferi, Temporal Archmage", 1)]
