"""Tests for picking a bulk file out of Scryfall's bulk-data index."""

import pytest

from fishbowl.data.scryfall import find_bulk_download

# A tiny fake index shaped like https://api.scryfall.com/bulk-data,
# so tests don't need the internet.
FAKE_INDEX = {
    "object": "list",
    "data": [
        {
            "type": "default_cards",
            "download_uri": "https://data.scryfall.io/default-cards/default.json",
        },
        {
            "type": "oracle_cards",
            "download_uri": "https://data.scryfall.io/oracle-cards/oracle.json",
        },
    ],
}


def test_finds_the_requested_bulk_file():
    url = find_bulk_download(FAKE_INDEX, "oracle_cards")
    assert url == "https://data.scryfall.io/oracle-cards/oracle.json"


def test_missing_kind_raises_a_clear_error():
    # pytest.raises: this test passes only if the code raises ValueError.
    with pytest.raises(ValueError, match="rulings"):
        find_bulk_download(FAKE_INDEX, "rulings")


def test_malformed_index_raises_a_clear_error():
    # If Scryfall ever changes its format, fail with our message, not a KeyError.
    with pytest.raises(ValueError):
        find_bulk_download({"unexpected": "shape"}, "oracle_cards")
