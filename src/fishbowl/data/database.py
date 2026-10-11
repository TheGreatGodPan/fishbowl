"""Building the local card database (data/cards.db) from Scryfall's bulk file.

Build it with:  uv run python -m fishbowl.data.database
"""

import gzip
import json
import sqlite3
import sys
from pathlib import Path

from fishbowl.data.cards import card_to_row, is_game_card

# Relative to the project folder, where `uv run` is started from.
DEFAULT_SOURCE = Path("data") / "oracle-cards.jsonl.gz"
DEFAULT_DEST = Path("data") / "cards.db"

SCHEMA = """
CREATE TABLE cards (
    oracle_id        TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    layout           TEXT NOT NULL,
    mana_cost        TEXT,
    cmc              REAL,
    type_line        TEXT,
    oracle_text      TEXT,
    colors           TEXT NOT NULL,
    color_identity   TEXT NOT NULL,
    produced_mana    TEXT NOT NULL,
    keywords         TEXT NOT NULL,
    legal_commander  INTEGER NOT NULL,
    commander_status TEXT NOT NULL,
    is_game_changer  INTEGER NOT NULL,
    card_faces       TEXT,
    tokens           TEXT NOT NULL
);
-- Lookups must use WHERE name = ? COLLATE NOCASE to use this index (plain name = ? scans).
CREATE INDEX idx_cards_name ON cards (name COLLATE NOCASE);
"""

# Named placeholders (:oracle_id, ...) are filled from each row dict by key.
# Values never get pasted into the SQL text, which is what prevents SQL injection.
INSERT_SQL = """
INSERT OR IGNORE INTO cards VALUES (
    :oracle_id, :name, :layout, :mana_cost, :cmc, :type_line, :oracle_text,
    :colors, :color_identity, :produced_mana, :keywords, :legal_commander,
    :commander_status, :is_game_changer, :card_faces, :tokens
)
"""


def read_card_rows(source: Path) -> tuple[list[dict[str, object]], int]:
    """Read the gzipped JSON Lines file. Returns (rows for game cards, lines skipped)."""
    rows = []
    skipped = 0
    # Read bytes and let json.loads decode them inside the try: a bad-UTF-8 line
    # then counts as one skipped line instead of crashing the whole build.
    with gzip.open(source, "rb") as lines:
        for line in lines:
            try:
                card = json.loads(line)
            except ValueError:  # JSONDecodeError and UnicodeDecodeError both land here
                skipped += 1  # broken line: count it, keep going
                continue
            if not isinstance(card, dict):
                skipped += 1
                continue
            if not is_game_card(card.get("legalities")):
                continue  # token, art card, etc.: left out on purpose, not "skipped"
            row = card_to_row(card)
            if row is None:
                skipped += 1
                continue
            rows.append(row)
    return rows, skipped


def build_database(source: Path, dest: Path) -> tuple[int, int]:
    """Build dest from source. Returns (cards written, lines skipped).

    Builds into dest.part first and renames at the end, so a failed build
    never replaces a working database with a half-built one.
    """
    # raises FileNotFoundError before touching dest
    rows, skipped = read_card_rows(source)

    partial = dest.with_name(dest.name + ".part")
    partial.unlink(missing_ok=True)  # leftover from an earlier crashed build
    connection = sqlite3.connect(partial)
    try:
        connection.executescript(SCHEMA)
        connection.executemany(INSERT_SQL, rows)
        connection.commit()
        written = connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    finally:
        connection.close()  # Windows can't rename a file that's still open
    partial.replace(dest)
    return written, skipped


def main(source: Path = DEFAULT_SOURCE, dest: Path = DEFAULT_DEST) -> int:
    """Build the database and print a summary. Returns an exit code (0 = success)."""
    if not source.is_file():
        print(f"No card data at {source}. Download it first with:")
        print("  uv run python -m fishbowl.data.scryfall")
        return 1
    written, skipped = build_database(source, dest)
    print(f"Built {dest}: {written:,} cards, {skipped:,} lines skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
