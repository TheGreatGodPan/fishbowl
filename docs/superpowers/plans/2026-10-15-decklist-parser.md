# Decklist Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse pasted Commander decklists (Moxfield, Archidekt, plain text) into a `ParsedDeck` with real card names, the commander, and clear problems, never crashing on odd input.

**Architecture:** `cards.db` gains a `card_aliases` table: alternate printed names from Scryfall `default_cards`, plus front-face names of multi-face cards. A new `src/fishbowl/deck/` package has these modules:
- `model.py` holds the dataclasses.
- `lookup.py` holds read-only name lookups.
- `parser.py` holds the pure line and deck parsing, plus a CLI `main`.
- `commander.py` holds the commander candidates and the interactive pick.

**Tech Stack:** Python 3.12, standard library only (`re`, `dataclasses`, `sqlite3`, `gzip`, `json`, `pathlib`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-decklist-parser-design.md`

## Global Constraints

- Python 3.12+. Run everything through `uv run` (never plain `python`/`pip`). No new dependencies.
- Use `pathlib.Path` for paths. Must run on Windows, macOS and Linux.
- Decklists and downloaded data are untrusted input. No input line ever raises; unreadable lines and unknown names become `Problem`s.
- Text over 1,000 lines is refused with a single `Problem` (line 0). Quantities must be 1–999.
- Never guess the commander from line order. Only use these signals:
  - a `Commander`/`Commanders` header
  - a `Commander: <name>` line
  - a `[Commander...]` tag
  - the final blank-line block of 1–2 cards
- Tests write only to pytest's `tmp_path`. The real `data/cards.db` is only read, and only by `tests/deck/test_real_decks.py`, which skips when it's missing.
- Test data is copied from real Scryfall records and real exports, never written from memory.
- Agents never run `git add`/`commit`/`push`; Ian commits. "Commit (Ian)" steps list his commands.
- Every touched `.py` file must pass `ruff format`, `ruff check` and the edit hook's type check:
  ```
  basedpyright --level error -p C:/Users/iwsch/.claude/hooks/basedpyright-default.json <file>
  ```
  The exe is at `~/.local/bin/basedpyright.exe` if `.venv` has none. In tests, narrow optional values with `assert x is not None` before using them.

## Review Focus

1. **Windows line endings (`\r\n`) and a BOM in a pasted list:** these must parse the same as plain `\n`. (Task 5 test `test_windows_line_endings_and_bom`.)
2. **An explicit `Commander:` line naming a card that doesn't exist:** this must give a problem, not a crash. (Task 5 test `test_explicit_commander_unknown_is_a_problem`.)
3. **Junk lines** (lone `1x`, `[]`, `*F*`, `((((`, control characters, huge numbers): these must never raise. (Task 5 test `test_junk_lines_never_raise`.)
4. **The prompt hitting end-of-input** (piped stdin, Ctrl+Z): this must return `None` instead of a traceback. (Task 6 test `test_end_of_input_returns_none`.)
5. **A decklist file that isn't valid UTF-8:** it must still parse, with undecodable bytes replaced. (Task 7 test `test_main_reads_non_utf8_file`.)

---

### Task 1: `card_aliases` table and shared test fixtures

**Files:**
- Move: `tests/data/conftest.py` → `tests/conftest.py`. Use a plain file move; content unchanged, then extended below. Shared fixtures must be visible to `tests/deck/` too.
- Modify: `src/fishbowl/data/database.py`
- Test: `tests/data/test_database.py`

**Interfaces:**
- Consumes: `build_database(source, dest) -> tuple[int, int]`, `read_card_rows`, `SCHEMA`, `INSERT_SQL`, `main`, `DEFAULT_SOURCE`, `DEFAULT_DEST` (all exist).
- Produces:
  - `build_database(source: Path, dest: Path, printings: Path | None = None) -> tuple[int, int]`, which still returns `(cards_written, lines_skipped)`.
  - `read_flavor_aliases(source: Path) -> list[tuple[str, str]]`
  - `front_face_aliases(rows: list[dict[str, object]]) -> list[tuple[str, str]]`
  - `DEFAULT_PRINTINGS = Path("data") / "default-cards.jsonl.gz"`
  - `main(source=DEFAULT_SOURCE, dest=DEFAULT_DEST, printings=DEFAULT_PRINTINGS) -> int`
  - Table `card_aliases(alias TEXT PRIMARY KEY COLLATE NOCASE, oracle_id TEXT NOT NULL REFERENCES cards (oracle_id))`.
  - Fixtures in `tests/conftest.py`: `great_henge`, `goreclaw`, `banyan_tree_printing`, `card_db` (a `Path` to a built test `cards.db`).

- [ ] **Step 1: Move the conftest and add fixtures.** Move `tests/data/conftest.py` to `tests/conftest.py`. Then, in `tests/conftest.py`, add `import gzip` and `import json` to the imports, plus `from fishbowl.data.database import build_database`. Then append:

```python
GREAT_HENGE = {
    "object": "card",
    "oracle_id": "78427103-9543-41fb-b6d4-72963fe87275",
    "name": "The Great Henge",
    "layout": "normal",
    "mana_cost": "{7}{G}{G}",
    "cmc": 9.0,
    "type_line": "Legendary Artifact",
    "oracle_text": (
        "This spell costs {X} less to cast, where X is the greatest power among "
        "creatures you control.\n{T}: Add {G}{G}. You gain 2 life.\nWhenever a "
        "nontoken creature you control enters, put a +1/+1 counter on it and draw a card."
    ),
    "colors": ["G"],
    "color_identity": ["G"],
    "produced_mana": ["G"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}

GORECLAW = {
    "object": "card",
    "oracle_id": "befb211f-37ca-4083-98d4-9ff1f28be3f2",
    "name": "Goreclaw, Terror of Qal Sisma",
    "layout": "normal",
    "mana_cost": "{3}{G}",
    "cmc": 4.0,
    "type_line": "Legendary Creature \u2014 Bear",
    "oracle_text": (
        "Creature spells you cast with power 4 or greater cost {2} less to cast.\n"
        "Whenever Goreclaw attacks, each creature you control with power 4 or "
        "greater gets +1/+1 and gains trample until end of turn."
    ),
    "colors": ["G"],
    "color_identity": ["G"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}

# One printing from Scryfall's default_cards (TLE 41), trimmed: its card carries a
# different printed name ("flavor_name") than the real card name.
BANYAN_TREE_PRINTING = {
    "object": "card",
    "oracle_id": "78427103-9543-41fb-b6d4-72963fe87275",
    "name": "The Great Henge",
    "flavor_name": "The Banyan Tree",
    "set": "tle",
    "collector_number": "41",
    "layout": "normal",
}


@pytest.fixture
def great_henge():
    return copy.deepcopy(GREAT_HENGE)


@pytest.fixture
def goreclaw():
    return copy.deepcopy(GORECLAW)


@pytest.fixture
def banyan_tree_printing():
    return copy.deepcopy(BANYAN_TREE_PRINTING)


@pytest.fixture
def card_db(tmp_path):
    """A small real cards.db in tmp_path: Sol Ring, Krenko, Witch Enchanter,
    The Great Henge (alias: The Banyan Tree) and Goreclaw."""
    source = tmp_path / "oracle.jsonl.gz"
    printings = tmp_path / "printings.jsonl.gz"
    with gzip.open(source, "wt", encoding="utf-8") as out:
        for card in (SOL_RING, KRENKO, WITCH_ENCHANTER, GREAT_HENGE, GORECLAW):
            out.write(json.dumps(card) + "\n")
    with gzip.open(printings, "wt", encoding="utf-8") as out:
        out.write(json.dumps(BANYAN_TREE_PRINTING) + "\n")
    dest = tmp_path / "cards.db"
    build_database(source, dest, printings)
    return dest
```

Run `uv run pytest`. The existing tests should still pass (the fixtures moved but are unchanged). `card_db` isn't used yet, and will error only if requested before Step 4.

- [ ] **Step 2: Write the failing tests.** In `tests/data/test_database.py`:
  - Change the import to `from fishbowl.data.database import build_database, main`. It is unchanged, but make sure it is exactly that.
  - Replace the body of `test_main_builds_and_reports` with the version below.
  - Append the new tests.

```python
def test_main_builds_and_reports(tmp_path, capsys, sol_ring):
    source = tmp_path / "cards.jsonl.gz"
    write_jsonl_gz(source, [json.dumps(sol_ring)])
    code = main(source, tmp_path / "cards.db", tmp_path / "no-printings.jsonl.gz")
    assert code == 0
    out = capsys.readouterr().out
    assert "1 cards" in out
    assert "0 lines skipped" in out


def test_main_without_printings_says_aliases_are_limited(tmp_path, capsys, sol_ring):
    source = tmp_path / "cards.jsonl.gz"
    write_jsonl_gz(source, [json.dumps(sol_ring)])
    main(source, tmp_path / "cards.db", tmp_path / "no-printings.jsonl.gz")
    assert "alternate printed names won't be recognized" in capsys.readouterr().out


def aliases(db_path):
    return dict(query(db_path, "SELECT alias, oracle_id FROM card_aliases"))


def test_front_face_name_becomes_alias(tmp_path, witch_enchanter):
    source = tmp_path / "cards.jsonl.gz"
    write_jsonl_gz(source, [json.dumps(witch_enchanter)])
    dest = tmp_path / "cards.db"
    build_database(source, dest)
    assert aliases(dest) == {"Witch Enchanter": "0355249a-8e4e-41db-9cea-1b901faffbe6"}


def test_printed_flavor_name_becomes_alias(tmp_path, great_henge, banyan_tree_printing):
    source = tmp_path / "cards.jsonl.gz"
    printings = tmp_path / "printings.jsonl.gz"
    write_jsonl_gz(source, [json.dumps(great_henge)])
    write_jsonl_gz(printings, [json.dumps(banyan_tree_printing), "{broken"])
    dest = tmp_path / "cards.db"
    build_database(source, dest, printings)
    assert aliases(dest) == {"The Banyan Tree": "78427103-9543-41fb-b6d4-72963fe87275"}


def test_alias_lookup_ignores_case(card_db):
    rows = query(card_db, "SELECT oracle_id FROM card_aliases WHERE alias = ?", ("the banyan tree",))
    assert rows == [("78427103-9543-41fb-b6d4-72963fe87275",)]


def test_alias_for_card_not_in_database_is_ignored(tmp_path, sol_ring, banyan_tree_printing):
    source = tmp_path / "cards.jsonl.gz"
    printings = tmp_path / "printings.jsonl.gz"
    write_jsonl_gz(source, [json.dumps(sol_ring)])  # no Great Henge in cards
    write_jsonl_gz(printings, [json.dumps(banyan_tree_printing)])
    dest = tmp_path / "cards.db"
    build_database(source, dest, printings)
    assert aliases(dest) == {}


def test_alias_equal_to_a_real_card_name_is_ignored(tmp_path, sol_ring, great_henge, banyan_tree_printing):
    source = tmp_path / "cards.jsonl.gz"
    printings = tmp_path / "printings.jsonl.gz"
    write_jsonl_gz(source, [json.dumps(sol_ring), json.dumps(great_henge)])
    banyan_tree_printing["flavor_name"] = "sol ring"  # would hijack a real card name
    write_jsonl_gz(printings, [json.dumps(banyan_tree_printing)])
    dest = tmp_path / "cards.db"
    build_database(source, dest, printings)
    assert aliases(dest) == {}


def test_flavor_name_same_as_real_name_is_ignored(tmp_path, great_henge, banyan_tree_printing):
    source = tmp_path / "cards.jsonl.gz"
    printings = tmp_path / "printings.jsonl.gz"
    write_jsonl_gz(source, [json.dumps(great_henge)])
    banyan_tree_printing["flavor_name"] = "The Great Henge"
    write_jsonl_gz(printings, [json.dumps(banyan_tree_printing)])
    dest = tmp_path / "cards.db"
    build_database(source, dest, printings)
    assert aliases(dest) == {}
```

- [ ] **Step 3: Run the tests to verify they fail.**

Run: `uv run pytest tests/data/test_database.py -v`
Expected: the new tests FAIL. The likely errors are `sqlite3.OperationalError: no such table: card_aliases`, or `TypeError` from the extra `printings` argument.

- [ ] **Step 4: Write the implementation** in `src/fishbowl/data/database.py`.

(a) Add below `DEFAULT_DEST`:

```python
DEFAULT_PRINTINGS = Path("data") / "default-cards.jsonl.gz"
```

(b) Append to the end of the `SCHEMA` string, after the `CREATE INDEX` line and before the closing `"""`:

```sql
-- Other names a card is known by: printed alternate names ("The Banyan Tree")
-- and front-face names of double-faced cards ("Witch Enchanter").
CREATE TABLE card_aliases (
    alias     TEXT PRIMARY KEY COLLATE NOCASE,
    oracle_id TEXT NOT NULL REFERENCES cards (oracle_id)
);
```

(c) Add below `INSERT_SQL`:

```python
# ?1 = alias, ?2 = oracle_id. Only for cards we kept, and never shadowing a real name.
ALIAS_SQL = """
INSERT OR IGNORE INTO card_aliases (alias, oracle_id)
SELECT ?1, ?2
WHERE EXISTS (SELECT 1 FROM cards WHERE oracle_id = ?2)
  AND NOT EXISTS (SELECT 1 FROM cards WHERE name = ?1 COLLATE NOCASE)
"""
```

(d) Add these two functions after `read_card_rows`:

```python
def read_flavor_aliases(source: Path) -> list[tuple[str, str]]:
    """(alias, oracle_id) pairs from Scryfall's default_cards file: printings whose
    printed name (flavor_name) differs from the real card name."""
    pairs = []
    with gzip.open(source, "rb") as lines:
        for line in lines:
            try:
                card = json.loads(line)
            except ValueError:
                continue  # broken line: nothing to learn from it
            if not isinstance(card, dict):
                continue
            alias = card.get("flavor_name")
            oracle_id = card.get("oracle_id")
            if (
                isinstance(alias, str)
                and alias
                and isinstance(oracle_id, str)
                and alias != card.get("name")
            ):
                pairs.append((alias, oracle_id))
    return pairs


def front_face_aliases(rows: list[dict[str, object]]) -> list[tuple[str, str]]:
    """(front-face name, oracle_id) for multi-face cards, e.g. "Witch Enchanter"."""
    pairs = []
    for row in rows:
        faces_json = row["card_faces"]
        if not isinstance(faces_json, str):
            continue  # single-face card
        faces = json.loads(faces_json)  # we wrote this JSON ourselves in card_to_row
        front = faces[0].get("name") if faces and isinstance(faces[0], dict) else None
        oracle_id = row["oracle_id"]
        if isinstance(front, str) and front and front != row["name"] and isinstance(oracle_id, str):
            pairs.append((front, oracle_id))
    return pairs
```

(e) Replace `build_database` with:

```python
def build_database(
    source: Path, dest: Path, printings: Path | None = None
) -> tuple[int, int]:
    """Build dest from source (and printings, for alternate names).
    Returns (cards written, lines skipped).

    Builds into dest.part first and renames at the end, so a failed build
    never replaces a working database with a half-built one.
    """
    # raises FileNotFoundError before touching dest
    rows, skipped = read_card_rows(source)
    alias_pairs = front_face_aliases(rows)
    if printings is not None:
        alias_pairs += read_flavor_aliases(printings)

    partial = dest.with_name(dest.name + ".part")
    partial.unlink(missing_ok=True)  # leftover from an earlier crashed build
    connection = sqlite3.connect(partial)
    try:
        connection.executescript(SCHEMA)
        connection.executemany(INSERT_SQL, rows)
        connection.executemany(ALIAS_SQL, alias_pairs)
        connection.commit()
        written = connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    finally:
        connection.close()  # Windows can't rename a file that's still open
    partial.replace(dest)
    return written, skipped
```

(f) Replace `main` with:

```python
def main(
    source: Path = DEFAULT_SOURCE,
    dest: Path = DEFAULT_DEST,
    printings: Path = DEFAULT_PRINTINGS,
) -> int:
    """Build the database and print a summary. Returns an exit code (0 = success)."""
    if not source.is_file():
        print(f"No card data at {source}. Download it first with:")
        print("  uv run python -m fishbowl.data.scryfall")
        return 1
    if not printings.is_file():
        print(f"No printings file at {printings}: alternate printed names won't be recognized.")
        print("  Run: uv run python -m fishbowl.data.refresh")
    written, skipped = build_database(
        source, dest, printings if printings.is_file() else None
    )
    connection = sqlite3.connect(dest)
    try:
        alias_count = connection.execute("SELECT COUNT(*) FROM card_aliases").fetchone()[0]
    finally:
        connection.close()
    print(
        f"Built {dest}: {written:,} cards, {alias_count:,} alternate names, "
        f"{skipped:,} lines skipped"
    )
    return 0
```

- [ ] **Step 5: Run all the tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 6: Commit (Ian).**

```bash
git add tests/conftest.py tests/data/conftest.py src/fishbowl/data/database.py tests/data/test_database.py
git commit -m "Add card_aliases table (printed alternate and front-face names)"
```

---

### Task 2: Download `default_cards` during refresh

**Files:**
- Modify: `src/fishbowl/data/scryfall.py`
- Test: `tests/data/test_scryfall.py`

**Interfaces:**
- Consumes: `fetch_json`, `find_bulk_download`, `check_download_url`, `download_file`, `INDEX_URL`, `DEFAULT_DEST` (exist in `scryfall.py`); `DEFAULT_PRINTINGS` (Task 1, `database.py`).
- Produces:
  - `DEFAULT_PRINTINGS_DEST = Path("data") / "default-cards.jsonl.gz"`
  - `BULK_FILES: tuple[tuple[str, Path], ...]`
  - `download_bulk(index: dict, kind: str, dest: Path) -> None`
  - `main()`, which now downloads both files.
  - `refresh.py` is unchanged: it still calls `scryfall.main`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/data/test_scryfall.py`, and add `from fishbowl.data import database, scryfall` to its imports:

```python
def test_printings_path_matches_database_default():
    # The downloader and the builder must agree on where the printings file lives.
    assert scryfall.DEFAULT_PRINTINGS_DEST == database.DEFAULT_PRINTINGS


def test_refresh_downloads_both_bulk_files():
    assert [kind for kind, _ in scryfall.BULK_FILES] == ["oracle_cards", "default_cards"]


def test_download_bulk_saves_to_dest(tmp_path, monkeypatch):
    # monkeypatch: temporarily swap a function for a fake, for this test only.
    saved = []

    def fake_download(url, dest):
        saved.append((url, dest))
        dest.write_bytes(b"fake")

    monkeypatch.setattr(scryfall, "download_file", fake_download)
    dest = tmp_path / "default-cards.jsonl.gz"
    index = {"data": [{"type": "default_cards", "jsonl_download_uri": "https://data.scryfall.io/default-cards/d.jsonl.gz"}]}
    scryfall.download_bulk(index, "default_cards", dest)
    assert saved == [("https://data.scryfall.io/default-cards/d.jsonl.gz", dest)]


def test_download_bulk_refuses_untrusted_url(tmp_path, monkeypatch):
    monkeypatch.setattr(scryfall, "download_file", lambda url, dest: None)
    index = {"data": [{"type": "default_cards", "jsonl_download_uri": "https://evil.example/d.jsonl.gz"}]}
    with pytest.raises(ValueError):
        scryfall.download_bulk(index, "default_cards", tmp_path / "x.jsonl.gz")
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `uv run pytest tests/data/test_scryfall.py -v`
Expected: the new tests FAIL with `AttributeError: module 'fishbowl.data.scryfall' has no attribute 'DEFAULT_PRINTINGS_DEST'` (or `download_bulk`).

- [ ] **Step 3: Write the implementation** in `src/fishbowl/data/scryfall.py`. Add below `DEFAULT_DEST`:

```python
# Every printing (about 80 MB): only used to learn alternate printed names.
DEFAULT_PRINTINGS_DEST = Path("data") / "default-cards.jsonl.gz"
BULK_FILES = (
    ("oracle_cards", DEFAULT_DEST),
    ("default_cards", DEFAULT_PRINTINGS_DEST),
)
```

Replace `main` with:

```python
def download_bulk(index: dict, kind: str, dest: Path) -> None:
    """Find one bulk file in the index, check its link, and download it to dest."""
    url = find_bulk_download(index, kind)
    check_download_url(url)
    print(f"Downloading {url}")
    download_file(url, dest)
    size_mb = dest.stat().st_size / 1_000_000
    print(f"Saved {dest} ({size_mb:.0f} MB)")


def main() -> None:
    print(f"Fetching bulk-data index from {INDEX_URL}")
    index = fetch_json(INDEX_URL)
    for kind, dest in BULK_FILES:
        download_bulk(index, kind, dest)
```

Update the module docstring's run line to read: `Download the bulk files with:  uv run python -m fishbowl.data.scryfall`.

- [ ] **Step 4: Run all the tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 5: Commit (Ian).**

```bash
git add src/fishbowl/data/scryfall.py tests/data/test_scryfall.py
git commit -m "Download Scryfall default_cards for alternate names"
```

---

### Task 3: `CardLookup` in `deck/lookup.py`

**Files:**
- Create: `src/fishbowl/deck/__init__.py`, `src/fishbowl/deck/lookup.py`
- Test: `tests/deck/test_lookup.py`

**Interfaces:**
- Consumes: fixture `card_db` (Task 1); the tables `cards` and `card_aliases`.
- Produces:
  - `DEFAULT_DB = Path("data") / "cards.db"`
  - `@dataclass(frozen=True) class Card: oracle_id: str; name: str; type_line: str | None; oracle_text: str | None`
  - `class CardLookup`, with:
    - `__init__(self, db_path: Path = DEFAULT_DB)`, which raises `sqlite3.OperationalError` if the file is missing
    - `find(self, name: str) -> Card | None`
    - `close()`
    - context-manager support (`with CardLookup(path) as lookup:`)

- [ ] **Step 1: Write the failing tests** in `tests/deck/test_lookup.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `uv run pytest tests/deck/test_lookup.py -v`
Expected: collection ERROR, `ModuleNotFoundError: No module named 'fishbowl.deck'`.

- [ ] **Step 3: Write the implementation.**

`src/fishbowl/deck/__init__.py`:

```python
"""Decklists: parsing pasted lists into cards and finding the commander."""
```

`src/fishbowl/deck/lookup.py`:

```python
"""Finding cards in data/cards.db by name, including alternate printed names."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB = Path("data") / "cards.db"

_BY_NAME = """
SELECT oracle_id, name, type_line, oracle_text FROM cards
WHERE name = ? COLLATE NOCASE
"""
# The alias column is declared COLLATE NOCASE, so this match ignores case too.
_BY_ALIAS = """
SELECT c.oracle_id, c.name, c.type_line, c.oracle_text
FROM card_aliases AS a JOIN cards AS c ON c.oracle_id = a.oracle_id
WHERE a.alias = ?
"""


@dataclass(frozen=True)
class Card:
    """The few card fields the deck code needs."""

    oracle_id: str
    name: str
    type_line: str | None
    oracle_text: str | None


class CardLookup:
    """Read-only name lookups. Use as:  with CardLookup(path) as lookup: ..."""

    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        # mode=ro: read-only, and fail (instead of creating an empty file) if missing.
        uri = db_path.resolve().as_uri() + "?mode=ro"
        self._connection = sqlite3.connect(uri, uri=True)
        # Databases built before card_aliases existed still work, just without aliases.
        self._has_aliases = (
            self._connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_aliases'"
            ).fetchone()
            is not None
        )

    def find(self, name: str) -> Card | None:
        """The card with this name or alternate name (any case), or None."""
        row = self._connection.execute(_BY_NAME, (name,)).fetchone()
        if row is None and self._has_aliases:
            row = self._connection.execute(_BY_ALIAS, (name,)).fetchone()
        return Card(*row) if row is not None else None

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "CardLookup":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
```

Note: on Windows, `sqlite3.connect` with `mode=ro` on a missing file raises `sqlite3.OperationalError: unable to open database file`. If it raises a different `sqlite3.Error` subclass on some platform, keep the test's `pytest.raises(sqlite3.OperationalError)` and report it as a concern rather than widening the test.

- [ ] **Step 4: Run all the tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 5: Commit (Ian).**

```bash
git add src/fishbowl/deck/__init__.py src/fishbowl/deck/lookup.py tests/deck/test_lookup.py
git commit -m "Add CardLookup: find cards by name or alternate name"
```

---

### Task 4: Deck model and line parsing

**Files:**
- Create: `src/fishbowl/deck/model.py`, `src/fishbowl/deck/parser.py`
- Test: `tests/deck/test_parser_lines.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - In `model.py`:
    - `@dataclass DeckEntry(name: str, oracle_id: str, quantity: int)`
    - `@dataclass Problem(line_number: int, text: str, reason: str)`
    - `@dataclass ParsedDeck`, with fields `cards`, `commanders`, `left_out` (each `list[DeckEntry]`, default empty) and `problems` (`list[Problem]`, default empty), plus the property `total -> int`, which is the sum of `cards` quantities
  - In `parser.py`:
    - `@dataclass(frozen=True) CardLine(quantity: int, name: str, commander_tag: bool = False)`
    - `parse_card_line(text: str) -> CardLine`, which raises `ValueError(reason)`
    - `section_for_header(line: str) -> str | None`, which returns `"commander"`, `"main"`, `"out"` or `None`
    - `explicit_commander_name(line: str) -> str | None`
    - `MAX_QUANTITY = 999`

- [ ] **Step 1: Write the failing tests** in `tests/deck/test_parser_lines.py`:

```python
"""Tests for reading single decklist lines (no database needed)."""

import pytest

from fishbowl.deck.model import DeckEntry, ParsedDeck
from fishbowl.deck.parser import (
    CardLine,
    explicit_commander_name,
    parse_card_line,
    section_for_header,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 Sol Ring", CardLine(1, "Sol Ring")),
        ("1x Sol Ring", CardLine(1, "Sol Ring")),
        ("2X Forest", CardLine(2, "Forest")),
        ("Sol Ring", CardLine(1, "Sol Ring")),
        ("1 Sol Ring (SLC) 19 *F*", CardLine(1, "Sol Ring")),  # real Moxfield line
        ("1 Llanowar Elves (PDMU) 1\u2605 *F*", CardLine(1, "Llanowar Elves")),  # real
        ("1 Forest (TMT) 257 *F*", CardLine(1, "Forest")),  # real
        ("1 Sol Ring (SLC)", CardLine(1, "Sol Ring")),
        ("1x Sol Ring (cmm) 400 [Ramp]", CardLine(1, "Sol Ring")),  # Archidekt
        ("1x Sol Ring (cmm) 400 *E* [Ramp] ^Have,#37d67a^", CardLine(1, "Sol Ring")),
        (
            "1x Goreclaw, Terror of Qal Sisma (m19) 180 [Commander{top}]",
            CardLine(1, "Goreclaw, Terror of Qal Sisma", commander_tag=True),
        ),
        ("1\tSol   Ring  ", CardLine(1, "Sol Ring")),
        ("1 Goreclaw, Terror of Qal Sisma (CMM) 293", CardLine(1, "Goreclaw, Terror of Qal Sisma")),
        ("1 B.F.M. (Big Furry Monster)", CardLine(1, "B.F.M. (Big Furry Monster)")),  # real name with parentheses
    ],
)
def test_parse_card_line(text, expected):
    assert parse_card_line(text) == expected


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("0 Sol Ring", "quantity 0 is outside 1-999"),
        ("1000 Forest", "quantity 1000 is outside 1-999"),
        ("*F*", "no card name"),
        ("[Ramp]", "no card name"),
    ],
)
def test_bad_card_line_raises_with_reason(text, reason):
    with pytest.raises(ValueError, match=reason):
        parse_card_line(text)


@pytest.mark.parametrize(
    ("line", "section"),
    [
        ("Commander", "commander"),
        ("COMMANDERS", "commander"),
        ("Commander (1)", "commander"),
        ("Deck", "main"),
        ("Mainboard:", "main"),
        ("Main", "main"),
        ("Sideboard", "out"),
        ("Maybeboard (12)", "out"),
        ("Companion", "out"),
        ("1 Sol Ring", None),
        ("Commander: Goreclaw, Terror of Qal Sisma", None),
    ],
)
def test_section_for_header(line, section):
    assert section_for_header(line) == section


@pytest.mark.parametrize(
    ("line", "name"),
    [
        ("Commander: Goreclaw, Terror of Qal Sisma", "Goreclaw, Terror of Qal Sisma"),
        ("commander:Krenko, Mob Boss", "Krenko, Mob Boss"),
        ("Commander", None),
        ("Commander:", None),
        ("1 Sol Ring", None),
    ],
)
def test_explicit_commander_name(line, name):
    assert explicit_commander_name(line) == name


def test_parsed_deck_total_adds_quantities():
    deck = ParsedDeck(cards=[DeckEntry("Sol Ring", "a", 1), DeckEntry("Forest", "b", 26)])
    assert deck.total == 27
    assert ParsedDeck().total == 0
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `uv run pytest tests/deck/test_parser_lines.py -v`
Expected: collection ERROR, `ModuleNotFoundError: No module named 'fishbowl.deck.model'`.

- [ ] **Step 3: Write the implementation.**

`src/fishbowl/deck/model.py`:

```python
"""The result of parsing a decklist."""

from dataclasses import dataclass, field


@dataclass
class DeckEntry:
    """One card in the deck and how many copies."""

    name: str  # real card name from the database
    oracle_id: str
    quantity: int


@dataclass
class Problem:
    """A line the parser couldn't use, and why."""

    line_number: int  # 1-based; 0 means the whole list
    text: str  # the original line, trimmed to 200 characters
    reason: str


@dataclass
class ParsedDeck:
    """Cards (including commanders), the commanders, left-out cards and problems."""

    # default_factory: each deck gets its own new list, not one shared list.
    cards: list[DeckEntry] = field(default_factory=list)
    commanders: list[DeckEntry] = field(default_factory=list)
    left_out: list[DeckEntry] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Number of cards in the deck, commanders included."""
        return sum(entry.quantity for entry in self.cards)
```

`src/fishbowl/deck/parser.py`:

```python
"""Turning pasted decklist text into a ParsedDeck."""

import re
from dataclasses import dataclass

MAX_QUANTITY = 999

# "1 Sol Ring", "1x Sol Ring": a number, an optional x, then the name.
_QUANTITY = re.compile(r"^(\d+)[xX]?\s+(.+)$")
# Archidekt decorations at the end of a line: [Category] tags and ^Tag,#color^ tags.
_TAG = re.compile(r"\s*(\[[^\]]*\]|\^[^^]*\^)\s*$")
# Finish markers: *F* (foil), *E* (etched).
_MARKER = re.compile(r"\s*\*[A-Za-z]+\*\s*$")
# Printing: (SET) plus an optional collector number like 19 or 1★.
# Set codes are 2-6 letters/digits, so a real name like "(Big Furry Monster)" is kept.
_PRINTING = re.compile(r"\s+\([A-Za-z0-9]{2,6}\)(\s+\S+)?\s*$")
_HEADER = re.compile(
    r"^(commanders?|deck|mainboard|main|sideboard|maybeboard|companion)\s*:?\s*(\(\d+\))?$",
    re.IGNORECASE,
)
_EXPLICIT_COMMANDER = re.compile(r"^commander\s*:\s*(\S.*)$", re.IGNORECASE)
_SECTIONS = {
    "commander": "commander",
    "commanders": "commander",
    "deck": "main",
    "mainboard": "main",
    "main": "main",
    "sideboard": "out",
    "maybeboard": "out",
    "companion": "out",
}


@dataclass(frozen=True)
class CardLine:
    """What one card line says: how many, which name, and whether it's tagged commander."""

    quantity: int
    name: str
    commander_tag: bool = False


def parse_card_line(text: str) -> CardLine:
    """'1x Sol Ring (CMM) 400 *F* [Ramp]' -> CardLine(1, 'Sol Ring').

    Raises ValueError with a short reason if the line can't be a card.
    """
    line = " ".join(text.split())  # tabs and repeated spaces -> single spaces
    commander_tag = False
    # Strip end-of-line decorations, in any order, until nothing changes.
    while True:
        tag = _TAG.search(line)
        if tag:
            label = tag.group(1).strip("[]^").lower()
            commander_tag = commander_tag or label.startswith("commander")
            line = line[: tag.start()]
            continue
        stripped = _PRINTING.sub("", _MARKER.sub("", line))
        if stripped == line:
            break
        line = stripped

    match = _QUANTITY.match(line)
    if match:
        quantity, name = int(match.group(1)), match.group(2).strip()
    else:
        quantity, name = 1, line.strip()
    if not name:
        raise ValueError("no card name")
    if not 1 <= quantity <= MAX_QUANTITY:
        raise ValueError(f"quantity {quantity} is outside 1-{MAX_QUANTITY}")
    return CardLine(quantity, name, commander_tag)


def section_for_header(line: str) -> str | None:
    """'Commander' -> 'commander', 'Deck' -> 'main', 'Sideboard' -> 'out', else None."""
    match = _HEADER.match(line.strip())
    return _SECTIONS[match.group(1).lower()] if match else None


def explicit_commander_name(line: str) -> str | None:
    """'Commander: Goreclaw, Terror of Qal Sisma' -> 'Goreclaw, Terror of Qal Sisma'."""
    match = _EXPLICIT_COMMANDER.match(line.strip())
    return match.group(1).strip() if match else None
```

- [ ] **Step 4: Run all the tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 5: Commit (Ian).**

```bash
git add src/fishbowl/deck/model.py src/fishbowl/deck/parser.py tests/deck/test_parser_lines.py
git commit -m "Add deck model and decklist line parsing"
```

---

### Task 5: `parse_deck`

**Files:**
- Modify: `src/fishbowl/deck/parser.py`
- Test: `tests/deck/test_parse_deck.py`

**Interfaces:**
- Consumes:
  - `CardLookup`, `Card` (Task 3)
  - `DeckEntry`, `Problem`, `ParsedDeck` (Task 4)
  - `parse_card_line`, `section_for_header`, `explicit_commander_name` (Task 4)
  - fixture `card_db` (Task 1)
- Produces: `parse_deck(text: str, lookup: CardLookup) -> ParsedDeck`, plus `MAX_LINES = 1000`.

- [ ] **Step 1: Write the failing tests** in `tests/deck/test_parse_deck.py`:

```python
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
    deck = parse_deck("1 Sol Ring\n1 Krenko, Mob Boss\n2 Sol Ring (SLC) 19 *F*\n", lookup)
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
    deck = parse_deck("1 Sol Ring\nSideboard\n1 Krenko, Mob Boss\nMaybeboard (1)\n1 The Great Henge\n", lookup)
    assert names(deck.cards) == [("Sol Ring", 1)]
    assert names(deck.left_out) == [("Krenko, Mob Boss", 1), ("The Great Henge", 1)]


def test_archidekt_commander_tag(lookup):
    deck = parse_deck(f"1x {GORECLAW} (m19) 180 [Commander{{top}}]\n1x Sol Ring (cmm) 400 [Ramp]\n", lookup)
    assert names(deck.commanders) == [(GORECLAW, 1)]
    assert deck.total == 2


def test_explicit_commander_line_is_not_counted_twice(lookup):
    deck = parse_deck(f"Commander: {GORECLAW}\n1 {GORECLAW} (CMM) 293\n1 Sol Ring\n", lookup)
    assert names(deck.commanders) == [(GORECLAW, 1)]
    assert names(deck.cards) == [(GORECLAW, 1), ("Sol Ring", 1)]


def test_explicit_commander_line_adds_the_card_when_not_listed(lookup):
    deck = parse_deck(f"Commander: {GORECLAW}\n1 Sol Ring\n", lookup)
    assert names(deck.commanders) == [(GORECLAW, 1)]
    assert deck.total == 2


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
    deck = parse_deck(f"1 Sol Ring\n\n1 {GORECLAW}\n1 Krenko, Mob Boss\n1 The Great Henge\n", lookup)
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
    assert deck.problems[0].reason == "too many lines (1001); a Commander deck has 100 cards"


def test_windows_line_endings_and_bom(lookup):
    deck = parse_deck("\ufeff1 Sol Ring\r\n1 Krenko, Mob Boss\r\n", lookup)
    assert names(deck.cards) == [("Sol Ring", 1), ("Krenko, Mob Boss", 1)]
    assert deck.problems == []


def test_problem_text_is_trimmed_to_200_characters(lookup):
    deck = parse_deck("1 " + "x" * 500, lookup)
    assert len(deck.problems[0].text) == 200


def test_junk_lines_never_raise(lookup):
    junk = ["1x", "[]", "*F*", "((((", "\x00\x01\x02", "99999999999999999999999 Sol Ring", "^^", ":"]
    deck = parse_deck("\n".join(junk), lookup)
    assert deck.cards == []
    assert len(deck.problems) == len(junk)
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `uv run pytest tests/deck/test_parse_deck.py -v`
Expected: collection ERROR, `ImportError: cannot import name 'parse_deck'`.

- [ ] **Step 3: Write the implementation.** In `src/fishbowl/deck/parser.py`:
  - Change `from dataclasses import dataclass` to `from dataclasses import dataclass, field`.
  - Add these imports:
    ```python
    from fishbowl.deck.lookup import Card, CardLookup
    from fishbowl.deck.model import DeckEntry, ParsedDeck, Problem
    ```
  - Append:

```python
MAX_LINES = 1000
MAX_COMMANDERS = 2
_PROBLEM_TEXT_LIMIT = 200


@dataclass
class _Block:
    """Card lines between blank lines, used to find a final commander block."""

    lines: list[tuple[Card, CardLine, str]] = field(default_factory=list)
    has_header: bool = False


def _problem(line_number: int, text: str, reason: str) -> Problem:
    return Problem(line_number, text[:_PROBLEM_TEXT_LIMIT], reason)


def _add(entries: dict[str, DeckEntry], card: Card, quantity: int) -> None:
    """Add copies of a card, merging lines for the same card (dict keeps first-seen order)."""
    if card.oracle_id in entries:
        entries[card.oracle_id].quantity += quantity
    else:
        entries[card.oracle_id] = DeckEntry(card.name, card.oracle_id, quantity)


def parse_deck(text: str, lookup: CardLookup) -> ParsedDeck:
    """Parse pasted decklist text. Never raises on bad lines: they become Problems."""
    deck = ParsedDeck()
    lines = text.lstrip("\ufeff").splitlines()  # BOM off; \r\n and \n both split
    if len(lines) > MAX_LINES:
        deck.problems.append(
            _problem(0, "", f"too many lines ({len(lines)}); a Commander deck has 100 cards")
        )
        return deck

    section = "main"
    blocks = [_Block()]
    explicit: list[Card] = []
    for number, raw in enumerate(lines, start=1):
        line = " ".join(raw.split())
        if not line:
            if blocks[-1].lines or blocks[-1].has_header:
                blocks.append(_Block())  # a blank line ends the block
            continue
        if line.startswith(("//", "#")):
            continue  # comment
        header = section_for_header(line)
        if header is not None:
            section = header
            blocks[-1].has_header = True
            continue
        named = explicit_commander_name(line)
        if named is not None:
            card = lookup.find(named)
            if card is None:
                deck.problems.append(_problem(number, line, f'unknown card "{named}"'))
            else:
                explicit.append(card)
            continue
        try:
            parsed = parse_card_line(line)
        except ValueError as error:
            deck.problems.append(_problem(number, line, str(error)))
            continue
        card = lookup.find(parsed.name)
        if card is None:
            deck.problems.append(_problem(number, line, f'unknown card "{parsed.name}"'))
            continue
        blocks[-1].lines.append((card, parsed, section))

    main: dict[str, DeckEntry] = {}
    out: dict[str, DeckEntry] = {}
    commanders: list[Card] = []
    for block in blocks:
        for card, parsed, line_section in block.lines:
            _add(out if line_section == "out" else main, card, parsed.quantity)
            if line_section == "commander" or parsed.commander_tag:
                commanders.append(card)
    for card in explicit:
        if card.oracle_id not in main:
            _add(main, card, 1)  # named only on the Commander: line
        commanders.append(card)

    if not commanders:
        filled = [block for block in blocks if block.lines]
        last = filled[-1] if filled else None
        if (
            last is not None
            and len(filled) >= 2
            and not last.has_header
            and 1 <= len(last.lines) <= MAX_COMMANDERS
            and all(line_section == "main" for _, _, line_section in last.lines)
        ):
            commanders = [card for card, _, _ in last.lines]

    unique: dict[str, Card] = {}
    for card in commanders:
        unique.setdefault(card.oracle_id, card)
    chosen = list(unique.values())
    if len(chosen) > MAX_COMMANDERS:
        listed = ", ".join(card.name for card in chosen)
        deck.problems.append(
            _problem(0, "", f"more than 2 commanders marked ({listed}); using the first 2")
        )
        chosen = chosen[:MAX_COMMANDERS]

    deck.cards = list(main.values())
    deck.left_out = list(out.values())
    deck.commanders = [DeckEntry(card.name, card.oracle_id, 1) for card in chosen]
    return deck
```

- [ ] **Step 4: Run all the tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 5: Commit (Ian).**

```bash
git add src/fishbowl/deck/parser.py tests/deck/test_parse_deck.py
git commit -m "Add parse_deck: sections, commanders, merged counts, problems"
```

---

### Task 6: Commander candidates and the interactive pick

**Files:**
- Create: `src/fishbowl/deck/commander.py`
- Test: `tests/deck/test_commander.py`

**Interfaces:**
- Consumes: `CardLookup` (Task 3); `ParsedDeck`, `DeckEntry` (Task 4); `parse_deck` (Task 5); fixture `card_db` (Task 1).
- Produces:
  - `commander_candidates(deck: ParsedDeck, lookup: CardLookup) -> list[str]`
  - `ask_for_commander(candidates: list[str], read: Callable[[str], str] = input, write: Callable[[str], object] = print) -> str | None`

- [ ] **Step 1: Write the failing tests** in `tests/deck/test_commander.py`:

```python
"""Tests for finding commander candidates and letting the user pick one."""

import pytest

from fishbowl.deck.commander import ask_for_commander, commander_candidates
from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.parser import parse_deck

GORECLAW = "Goreclaw, Terror of Qal Sisma"
KRENKO = "Krenko, Mob Boss"


def test_candidates_are_legendary_creatures_sorted(card_db):
    with CardLookup(card_db) as lookup:
        deck = parse_deck(f"1 Sol Ring\n1 {KRENKO}\n1 The Great Henge\n1 {GORECLAW}\n", lookup)
        # The Great Henge is legendary but not a creature; Sol Ring is neither.
        assert commander_candidates(deck, lookup) == [GORECLAW, KRENKO]


def fake_input(*answers):
    """A stand-in for input(): returns the given answers one by one."""
    remaining = list(answers)

    def read(prompt):
        if not remaining:
            raise EOFError  # like pressing Ctrl+Z / Ctrl+D
        return remaining.pop(0)

    return read


def test_pick_by_number():
    shown = []
    assert ask_for_commander([GORECLAW, KRENKO], fake_input("2"), shown.append) == KRENKO
    assert f"  1. {GORECLAW}" in shown


def test_type_letters_to_filter_then_pick():
    shown = []
    chosen = ask_for_commander([GORECLAW, KRENKO, "Surrak and Goreclaw"], fake_input("gore", "2"), shown.append)
    assert chosen == "Surrak and Goreclaw"
    assert f"  2. {KRENKO}" in shown  # first, the full list
    assert "  2. Surrak and Goreclaw" in shown  # then, the filtered list


def test_out_of_range_number_asks_again():
    shown = []
    assert ask_for_commander([GORECLAW], fake_input("5", "1"), shown.append) == GORECLAW
    assert "Pick a number from 1 to 1." in shown


def test_no_match_says_so_and_enter_skips():
    shown = []
    assert ask_for_commander([GORECLAW], fake_input("zzz", ""), shown.append) is None
    assert 'No candidates match "zzz".' in shown


def test_no_candidates_returns_none_without_asking():
    shown = []
    assert ask_for_commander([], fake_input(), shown.append) is None
    assert shown == ["No commander candidates found in this deck."]


def test_end_of_input_returns_none():
    assert ask_for_commander([GORECLAW], fake_input(), lambda message: None) is None
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `uv run pytest tests/deck/test_commander.py -v`
Expected: collection ERROR, `ModuleNotFoundError: No module named 'fishbowl.deck.commander'`.

- [ ] **Step 3: Write the implementation** in `src/fishbowl/deck/commander.py`:

```python
"""Finding commander candidates in a deck, and asking the user to pick one."""

from collections.abc import Callable

from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.model import ParsedDeck


def commander_candidates(deck: ParsedDeck, lookup: CardLookup) -> list[str]:
    """Names in the deck that could be a commander: legendary creatures, or cards
    whose text says "can be your commander". Sorted by name."""
    names = []
    for entry in deck.cards:
        card = lookup.find(entry.name)
        if card is None:
            continue
        type_line = card.type_line or ""
        text = card.oracle_text or ""
        legendary_creature = "Legendary" in type_line and "Creature" in type_line
        if legendary_creature or "can be your commander" in text:
            names.append(card.name)
    return sorted(names)


def ask_for_commander(
    candidates: list[str],
    read: Callable[[str], str] = input,
    write: Callable[[str], object] = print,
) -> str | None:
    """Show candidates; letters filter the list, a number picks, Enter skips.

    read and write are parameters so tests can pass fakes instead of a keyboard.
    """
    if not candidates:
        write("No commander candidates found in this deck.")
        return None
    shown = list(candidates)
    while True:
        write("Which card is your commander?")
        for number, name in enumerate(shown, start=1):
            write(f"  {number}. {name}")
        try:
            answer = read("Number to pick, letters to search, Enter to skip: ").strip()
        except EOFError:
            return None  # no keyboard (piped input or Ctrl+Z): skip instead of crashing
        if not answer:
            return None
        if answer.isdecimal():
            index = int(answer)
            if 1 <= index <= len(shown):
                return shown[index - 1]
            write(f"Pick a number from 1 to {len(shown)}.")
            continue
        matches = [name for name in candidates if answer.lower() in name.lower()]
        if matches:
            shown = matches
        else:
            write(f'No candidates match "{answer}".')
```

- [ ] **Step 4: Run all the tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 5: Commit (Ian).**

```bash
git add src/fishbowl/deck/commander.py tests/deck/test_commander.py
git commit -m "Add commander candidates and search-and-pick prompt"
```

---

### Task 7: Parser command, real decks, and the real refresh

**Files:**
- Modify: `src/fishbowl/deck/parser.py`
- Test: `tests/deck/test_parser_main.py`, `tests/deck/test_real_decks.py`
- Already present (written by the controller from Ian's exports): `tests/decks/goreclaw.txt`, `tests/decks/ghalta.txt`. Don't edit them.

**Interfaces:**
- Consumes: `parse_deck`, `CardLookup`, `DEFAULT_DB`, `commander_candidates`, `ask_for_commander`, `DeckEntry`, fixture `card_db`.
- Produces: `main(argv: list[str] | None = None, db_path: Path = DEFAULT_DB, read=input, write=print) -> int`, run by `uv run python -m fishbowl.deck.parser <file>`.

- [ ] **Step 1: Write the failing tests.**

`tests/deck/test_parser_main.py`:

```python
"""Tests for the parser command: uv run python -m fishbowl.deck.parser <file>."""

from fishbowl.deck.parser import main

GORECLAW = "Goreclaw, Terror of Qal Sisma"


def run(argv, card_db, answers=()):
    shown = []
    remaining = list(answers)

    def read(prompt):
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    code = main(argv, db_path=card_db, read=read, write=shown.append)
    return code, shown


def test_clean_deck_with_commander(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(f"1 Sol Ring\n\n1 {GORECLAW}\n", encoding="utf-8")
    code, shown = run([str(deck)], card_db)
    assert code == 0
    assert "Deck: 2 cards" in shown
    assert f"Commander: {GORECLAW}" in shown


def test_asks_for_commander_when_unknown(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(f"1 {GORECLAW}\n1 Krenko, Mob Boss\n1 Sol Ring\n", encoding="utf-8")
    code, shown = run([str(deck)], card_db, answers=["gore", "1"])
    assert code == 0
    assert f"Commander: {GORECLAW}" in shown


def test_skipped_commander_shows_unknown(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(f"1 {GORECLAW}\n1 Sol Ring\n", encoding="utf-8")
    code, shown = run([str(deck)], card_db, answers=[""])
    assert "Commander: unknown" in shown


def test_problems_are_listed_and_exit_code_is_1(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text("1 Sol Ring\n1 Sol Rnig\n\n1 Krenko, Mob Boss\n", encoding="utf-8")
    code, shown = run([str(deck)], card_db)
    assert code == 1
    assert '  line 2: unknown card "Sol Rnig"' in shown


def test_left_out_cards_are_counted(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(f"Commander\n1 {GORECLAW}\nSideboard\n2 Sol Ring\n", encoding="utf-8")
    code, shown = run([str(deck)], card_db)
    assert "Left out (sideboard, maybeboard, companion): 2 cards" in shown


def test_main_reads_non_utf8_file(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_bytes(b"1 Sol Ring\n1 Caf\xe9 Card\n\n1 Krenko, Mob Boss\n")  # \xe9 is Latin-1, not UTF-8
    code, shown = run([str(deck)], card_db)
    assert code == 1  # the odd line is a problem, not a crash
    assert "Deck: 2 cards" in shown


def test_usage_when_no_file_given(card_db):
    code, shown = run([], card_db)
    assert code == 1
    assert shown == ["Usage: uv run python -m fishbowl.deck.parser <decklist.txt>"]


def test_missing_decklist_file(tmp_path, card_db):
    code, shown = run([str(tmp_path / "nope.txt")], card_db)
    assert code == 1
    assert shown[0].startswith("No such file:")


def test_missing_database_explains_what_to_do(tmp_path):
    deck = tmp_path / "deck.txt"
    deck.write_text("1 Sol Ring\n", encoding="utf-8")
    code, shown = run([str(deck)], tmp_path / "no.db")
    assert code == 1
    assert "  uv run python -m fishbowl.data.refresh" in shown
```

`tests/deck/test_real_decks.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `uv run pytest tests/deck/test_parser_main.py -v`
Expected: collection ERROR, `ImportError: cannot import name 'main'`.

(`test_real_decks.py` will be skipped until Step 5's refresh, because the current `data/cards.db` has no `card_aliases` table.)

- [ ] **Step 3: Write the implementation.** In `src/fishbowl/deck/parser.py`:
  - Add these imports:
    ```python
    import sys
    from collections.abc import Callable
    from pathlib import Path
    from fishbowl.deck.commander import ask_for_commander, commander_candidates
    ```
  - Extend the lookup import to `from fishbowl.deck.lookup import DEFAULT_DB, Card, CardLookup`.
  - Add the docstring line `Run it with:  uv run python -m fishbowl.deck.parser <decklist.txt>`.
  - Append:

```python
def main(
    argv: list[str] | None = None,
    db_path: Path = DEFAULT_DB,
    read: Callable[[str], str] = input,
    write: Callable[[str], object] = print,
) -> int:
    """Parse a decklist file and print a summary. Returns 0 if there were no problems."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        write("Usage: uv run python -m fishbowl.deck.parser <decklist.txt>")
        return 1
    path = Path(args[0])
    if not path.is_file():
        write(f"No such file: {path}")
        return 1
    if not db_path.is_file():
        write(f"No card database at {db_path}. Build it first with:")
        write("  uv run python -m fishbowl.data.refresh")
        return 1

    # errors="replace": a list saved in another encoding still parses; odd bytes become �.
    text = path.read_text(encoding="utf-8", errors="replace")
    with CardLookup(db_path) as lookup:
        deck = parse_deck(text, lookup)
        if not deck.commanders:
            chosen = ask_for_commander(commander_candidates(deck, lookup), read, write)
            deck.commanders = [
                DeckEntry(entry.name, entry.oracle_id, 1)
                for entry in deck.cards
                if entry.name == chosen
            ]

    write(f"Deck: {deck.total} cards")
    commander_names = " + ".join(entry.name for entry in deck.commanders)
    write(f"Commander: {commander_names or 'unknown'}")
    if deck.left_out:
        left_out = sum(entry.quantity for entry in deck.left_out)
        write(f"Left out (sideboard, maybeboard, companion): {left_out} cards")
    if deck.problems:
        write("Problems:")
        for problem in deck.problems:
            write(f"  line {problem.line_number}: {problem.reason}")
    return 1 if deck.problems else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run all the tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass. The tests in `test_real_decks.py` are SKIPPED, with the reason "needs data/cards.db with card_aliases".

- [ ] **Step 5: Run the real refresh,** which downloads about 105 MB and rebuilds.

Run: `uv run python -m fishbowl.data.refresh`
Expected output:
- `Saved data\oracle-cards.jsonl.gz (25 MB)`
- `Saved data\default-cards.jsonl.gz (~80 MB)`
- `Built data\cards.db: <about 32,900> cards, <N> alternate names, 0 lines skipped`

- [ ] **Step 6: Run the real-deck tests and the command.**

Run: `uv run pytest tests/deck/test_real_decks.py -v`
Expected: 4 PASSED (no skips).

Run: `uv run python -m fishbowl.deck.parser tests/decks/ghalta.txt`
Expected: `Deck: 100 cards`, `Commander: Ghalta, Primal Hunger`, exit code 0.

Run: `uv run python -m fishbowl.deck.parser tests/decks/goreclaw.txt`
Expected: `Deck: 100 cards`, `Commander: Goreclaw, Terror of Qal Sisma`, exit code 0.

Then run `uv run pytest` once more (all pass, none skipped), and `git status --short` (nothing under `data/`).

- [ ] **Step 7: Commit (Ian).**

```bash
git add src/fishbowl/deck/parser.py tests/deck/test_parser_main.py tests/deck/test_real_decks.py tests/decks/goreclaw.txt tests/decks/ghalta.txt
git commit -m "Add decklist parser command and real-deck tests"
```
