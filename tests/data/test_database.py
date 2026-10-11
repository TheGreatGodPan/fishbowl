"""Tests for building the SQLite card database from a gzipped JSON Lines file."""

import gzip
import json
import sqlite3

import pytest

from fishbowl.data.database import build_database, main


def write_jsonl_gz(path, lines):
    """Write text lines into a gzipped file, like Scryfall's bulk file."""
    with gzip.open(path, "wt", encoding="utf-8") as out:
        for line in lines:
            out.write(line + "\n")


def query(db_path, sql, params=()):
    connection = sqlite3.connect(db_path)
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


@pytest.fixture
def built(tmp_path, sol_ring, krenko, witch_enchanter, goblin_token):
    """Build a database from four real cards plus one broken line."""
    source = tmp_path / "cards.jsonl.gz"
    write_jsonl_gz(
        source,
        [
            json.dumps(sol_ring),
            json.dumps(krenko),
            "{this is not json",
            json.dumps(witch_enchanter),
            json.dumps(goblin_token),
        ],
    )
    dest = tmp_path / "cards.db"
    counts = build_database(source, dest)
    return dest, counts


def test_counts_written_and_skipped(built):
    _, counts = built
    # token left out on purpose (not skipped), broken line skipped
    assert counts == (3, 1)


def test_sol_ring_done_when_query(built):
    dest, _ = built
    rows = query(
        dest, "SELECT mana_cost, color_identity FROM cards WHERE name = 'Sol Ring'"
    )
    assert rows == [("{1}", "")]


def test_token_is_left_out(built):
    dest, _ = built
    assert query(dest, "SELECT COUNT(*) FROM cards WHERE name = 'Goblin'") == [(0,)]


def test_krenko_keeps_token_link(built):
    dest, _ = built
    [(tokens,)] = query(
        dest, "SELECT tokens FROM cards WHERE name = 'Krenko, Mob Boss'"
    )
    assert json.loads(tokens)[0]["name"] == "Goblin"


def test_name_lookup_ignores_case(built):
    dest, _ = built
    rows = query(
        dest, "SELECT name FROM cards WHERE name = ? COLLATE NOCASE", ("SOL RING",)
    )
    assert rows == [("Sol Ring",)]


def test_no_part_file_left_after_success(built):
    dest, _ = built
    assert dest.exists()
    assert not dest.with_name("cards.db.part").exists()


def test_duplicate_oracle_id_keeps_first(tmp_path, sol_ring):
    source = tmp_path / "cards.jsonl.gz"
    second = dict(sol_ring, name="Sol Ring Copy")
    write_jsonl_gz(source, [json.dumps(sol_ring), json.dumps(second)])
    dest = tmp_path / "cards.db"
    assert build_database(source, dest) == (1, 0)
    assert query(dest, "SELECT name FROM cards") == [("Sol Ring",)]


def test_invalid_utf8_line_is_skipped(tmp_path, sol_ring):
    source = tmp_path / "cards.jsonl.gz"
    good_line = json.dumps(sol_ring).encode("utf-8") + b"\n"
    bad_line = b"\xff\xfe not utf-8\n"
    source.write_bytes(gzip.compress(good_line + bad_line))
    assert build_database(source, tmp_path / "cards.db") == (1, 1)


def test_leftover_part_file_is_replaced(tmp_path, sol_ring):
    source = tmp_path / "cards.jsonl.gz"
    write_jsonl_gz(source, [json.dumps(sol_ring)])
    dest = tmp_path / "cards.db"
    dest.with_name("cards.db.part").write_text("junk from a crashed build")
    assert build_database(source, dest) == (1, 0)


def test_rebuild_replaces_old_database(tmp_path, sol_ring, krenko):
    source = tmp_path / "cards.jsonl.gz"
    dest = tmp_path / "cards.db"
    write_jsonl_gz(source, [json.dumps(sol_ring), json.dumps(krenko)])
    build_database(source, dest)
    write_jsonl_gz(source, [json.dumps(krenko)])
    build_database(source, dest)
    assert query(dest, "SELECT name FROM cards") == [("Krenko, Mob Boss",)]


def test_missing_source_leaves_old_database_alone(tmp_path):
    dest = tmp_path / "cards.db"
    dest.write_text("pretend this is the old, working database")
    with pytest.raises(FileNotFoundError):
        build_database(tmp_path / "missing.jsonl.gz", dest)
    assert dest.read_text() == "pretend this is the old, working database"


def test_main_without_source_explains_what_to_do(tmp_path, capsys):
    # capsys: a pytest fixture that captures what the code prints.
    code = main(tmp_path / "missing.jsonl.gz", tmp_path / "cards.db")
    assert code == 1
    assert "uv run python -m fishbowl.data.scryfall" in capsys.readouterr().out


def test_main_builds_and_reports(tmp_path, capsys, sol_ring):
    source = tmp_path / "cards.jsonl.gz"
    write_jsonl_gz(source, [json.dumps(sol_ring)])
    code = main(source, tmp_path / "cards.db")
    assert code == 0
    assert "1 cards, 0 lines skipped" in capsys.readouterr().out
