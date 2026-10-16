"""Ian's real exported decklists against the real card database."""

import sqlite3
from pathlib import Path

import pytest

from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.parser import parse_deck

REAL_DB = Path("data") / "cards.db"
DECKS = Path(__file__).parent.parent / "decks"


def real_db_ready() -> bool:
    if not REAL_DB.is_file():  # check first: connect() would create an empty file
        return False
    connection = sqlite3.connect(REAL_DB)
    try:
        found = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_aliases'"
        ).fetchone()
    finally:
        connection.close()
    return found is not None


pytestmark = pytest.mark.skipif(
    not real_db_ready(),
    reason="needs data/cards.db with card_aliases: run uv run python -m fishbowl.data.refresh",
)


@pytest.mark.parametrize(
    ("filename", "commander"),
    [
        ("goreclaw.txt", "Goreclaw, Terror of Qal Sisma"),
        ("ghalta.txt", "Ghalta, Primal Hunger"),
    ],
)
def test_real_deck_parses_cleanly(filename, commander):
    text = (DECKS / filename).read_text(encoding="utf-8")
    with CardLookup(REAL_DB) as lookup:
        deck = parse_deck(text, lookup)
    assert deck.problems == []
    assert deck.total == 100
    assert [entry.name for entry in deck.commanders] == [commander]


def test_goreclaw_alternate_names_and_forests():
    text = (DECKS / "goreclaw.txt").read_text(encoding="utf-8")
    with CardLookup(REAL_DB) as lookup:
        deck = parse_deck(text, lookup)
    counts = {entry.name: entry.quantity for entry in deck.cards}
    assert counts["The Great Henge"] == 1  # exported as "The Banyan Tree"
    assert counts["Nyxbloom Ancient"] == 1  # exported as "The Cloudsea Djinn"
    assert counts["Forest"] == 26  # 26 Forests across 20 lines


def test_ghalta_forests_on_two_lines():
    text = (DECKS / "ghalta.txt").read_text(encoding="utf-8")
    with CardLookup(REAL_DB) as lookup:
        deck = parse_deck(text, lookup)
    assert {entry.name: entry.quantity for entry in deck.cards}["Forest"] == 32
