"""Tests for picking a bulk file out of Scryfall's bulk-data index."""

import pytest

from fishbowl.data.scryfall import build_request, check_download_url, find_bulk_download

# A tiny fake index copied from the real https://api.scryfall.com/bulk-data
# (checked 2026-10-09), trimmed to the fields we use, so tests don't need the internet.
FAKE_INDEX = {
    "object": "list",
    "data": [
        {
            "type": "default_cards",
            "jsonl_download_uri": "https://data.scryfall.io/default-cards/default.jsonl.gz",
        },
        {
            "type": "oracle_cards",
            "jsonl_download_uri": "https://data.scryfall.io/oracle-cards/oracle.jsonl.gz",
        },
    ],
}


def test_finds_the_requested_bulk_file():
    url = find_bulk_download(FAKE_INDEX, "oracle_cards")
    assert url == "https://data.scryfall.io/oracle-cards/oracle.jsonl.gz"


def test_missing_kind_raises_a_clear_error():
    # pytest.raises: this test passes only if the code raises ValueError.
    with pytest.raises(ValueError, match="rulings"):
        find_bulk_download(FAKE_INDEX, "rulings")


def test_malformed_index_raises_a_clear_error():
    # If Scryfall ever changes its format, fail with our message, not a KeyError.
    with pytest.raises(ValueError):
        find_bulk_download({"unexpected": "shape"}, "oracle_cards")


def test_entry_without_download_link_raises_a_clear_error():
    # The entry exists but its link field is missing: still our ValueError, not KeyError.
    index = {"data": [{"type": "oracle_cards"}]}
    with pytest.raises(ValueError, match="download link"):
        find_bulk_download(index, "oracle_cards")


def test_request_identifies_fishbowl():
    req = build_request("https://api.scryfall.com/bulk-data")
    # urllib stores header names as "User-agent" (only the first letter capitalized).
    assert "Fishbowl" in req.get_header("User-agent")
    assert "github.com/TheGreatGodPan/fishbowl" in req.get_header("User-agent")
    assert req.get_header("Accept") == "application/json"


def test_accepts_scryfall_download_url():
    check_download_url("https://data.scryfall.io/oracle-cards/oracle.json")  # no error


@pytest.mark.parametrize(
    "url",
    [
        "http://data.scryfall.io/oracle.json",  # not encrypted
        "https://evil.example/oracle.json",  # wrong site
        "https://data.scryfall.io.evil.example/oracle.json",  # lookalike: real host is evil.example
        "https://notscryfall.io/oracle.json",  # ends in "scryfall.io" but isn't it
        "https://data.scryfall.io@evil.example/oracle.json",  # userinfo trick: host is evil.example
    ],
)
def test_rejects_untrusted_download_url(url):
    with pytest.raises(ValueError):
        check_download_url(url)
