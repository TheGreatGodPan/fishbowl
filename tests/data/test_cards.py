"""Tests for flattening Scryfall card fields into simple database values."""

import pytest

from fishbowl.data.cards import legal_in_commander


def test_legal_card_is_true():
    assert legal_in_commander({"commander": "legal", "vintage": "restricted"}) is True


@pytest.mark.parametrize("status", ["not_legal", "banned", "restricted", ""])
def test_anything_but_legal_is_false(status):
    assert legal_in_commander({"commander": status}) is False


@pytest.mark.parametrize("legalities", [{}, {"modern": "legal"}, None, "legal", 42])
def test_missing_or_malformed_legalities_is_false(legalities):
    # Safe default: if we can't confirm it's legal, treat it as not legal.
    assert legal_in_commander(legalities) is False
