"""Ian's real exported decklists against the real card database."""

import sqlite3
from pathlib import Path

import pytest

from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.parser import parse_deck
from fishbowl.deck.validator import validate
from fishbowl.stats.groups import find_groups
from fishbowl.stats.lands import library_counts

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
        ("krenko.txt", "Krenko, Mob Boss"),
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


@pytest.mark.parametrize("filename", ["goreclaw.txt", "ghalta.txt", "krenko.txt"])
def test_real_deck_is_legal(filename):
    text = (DECKS / filename).read_text(encoding="utf-8")
    with CardLookup(REAL_DB) as lookup:
        report = validate(parse_deck(text, lookup), lookup)
    assert report.errors == []
    assert report.notes[0].message == "Game Changers: 0"


@pytest.mark.parametrize(
    ("filename", "expected"),
    [("goreclaw.txt", (33, 99)), ("ghalta.txt", (39, 99)), ("krenko.txt", (33, 99))],
)
def test_real_deck_library_counts(filename, expected):
    text = (DECKS / filename).read_text(encoding="utf-8")
    with CardLookup(REAL_DB) as lookup:
        assert library_counts(parse_deck(text, lookup), lookup) == expected


def test_real_groups():
    def groups_for(filename):
        text = (DECKS / filename).read_text(encoding="utf-8")
        with CardLookup(REAL_DB) as lookup:
            dorks, tutors = find_groups(parse_deck(text, lookup), lookup)
        return dorks, tutors

    goreclaw_dorks, goreclaw_tutors = groups_for("goreclaw.txt")
    assert goreclaw_dorks.names == [
        "Elvish Mystic",
        "Fanatic of Rhonas",
        "Fyndhorn Elves",
        "Karametra's Acolyte",
        "Llanowar Elves",
        "Selvala, Heart of the Wilds",
        "Whisperer of the Wilds",
    ]
    for land_search in ("Nature's Lore", "Three Visits", "Skyshroud Claim"):
        assert land_search not in goreclaw_tutors.names

    _, krenko_tutors = groups_for("krenko.txt")
    assert "Goblin Matron" in krenko_tutors.names
    assert "Goblin Recruiter" in krenko_tutors.names
