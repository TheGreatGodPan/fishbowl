"""Tests for count_cards: adds up card quantities in a plain-text decklist."""

from fishbowl.hello import count_cards


def test_adds_up_quantities():
    assert count_cards("1 Sol Ring\n36 Forest\n") == 37


def test_skips_blank_lines():
    assert count_cards("1 Sol Ring\n\n   \n1 Command Tower\n") == 2


def test_line_without_number_counts_as_one():
    assert count_cards("Sol Ring\n") == 1


def test_odd_digit_characters_do_not_crash():
    # "²" (superscript two) looks like a digit to some checks, but int() rejects it.
    assert count_cards("² Sol Ring\n") == 1
