"""Tests for finding cards by name in cards.db."""

import shutil
import sqlite3

import pytest

from fishbowl.deck.lookup import Card, CardLookup


def test_finds_exact_name(card_db):
    with CardLookup(card_db) as lookup:
        card = lookup.find("Sol Ring")
    assert card == Card(
        oracle_id="6ad8011d-3471-4369-9d68-b264cc027487",
        name="Sol Ring",
        type_line="Artifact",
        oracle_text="{T}: Add {C}{C}.",
    )


def test_name_ignores_case(card_db):
    with CardLookup(card_db) as lookup:
        card = lookup.find("sOL rING")
    assert card is not None
    assert card.name == "Sol Ring"


def test_printed_alternate_name_finds_real_card(card_db):
    with CardLookup(card_db) as lookup:
        card = lookup.find("The Banyan Tree")
    assert card is not None
    assert card.name == "The Great Henge"


def test_front_face_name_finds_double_faced_card(card_db):
    with CardLookup(card_db) as lookup:
        card = lookup.find("witch enchanter")
    assert card is not None
    assert card.name == "Witch Enchanter // Witch-Blessed Meadow"


def test_unknown_name_gives_none(card_db):
    with CardLookup(card_db) as lookup:
        assert lookup.find("Sol Rnig") is None


def test_database_without_alias_table_still_finds_real_names(card_db, tmp_path):
    old = tmp_path / "old.db"
    shutil.copy(card_db, old)
    connection = sqlite3.connect(old)
    connection.execute("DROP TABLE card_aliases")
    connection.commit()
    connection.close()
    with CardLookup(old) as lookup:
        assert lookup.find("Sol Ring") is not None
        assert lookup.find("The Banyan Tree") is None


def test_missing_database_raises_and_creates_nothing(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        CardLookup(missing)
    assert not missing.exists()  # read-only open must not create an empty file
