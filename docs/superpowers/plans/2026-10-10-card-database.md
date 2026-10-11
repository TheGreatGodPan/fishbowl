# Card Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `data/cards.db`, a SQLite table of every game card, from Scryfall's `data/oracle-cards.jsonl.gz`, with one command.

**Architecture:** `src/fishbowl/data/cards.py` holds pure functions that turn one Scryfall card (a dict) into one database row. `src/fishbowl/data/database.py` reads the gzipped JSON Lines file line by line, keeps game cards, inserts rows into a staging file `cards.db.part`, then renames it to `cards.db`.

**Tech Stack:** Python 3.12, standard library only (`gzip`, `json`, `sqlite3`, `pathlib`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-10-card-database-design.md`

## Global Constraints

- Python 3.12+, run everything through `uv run` (never plain `python`).
- No new dependencies. Pandas is not used by the build.
- Use `pathlib.Path` for every file path; must run on Windows, macOS and Linux.
- Downloaded data is untrusted input: bad lines and malformed fields are skipped or defaulted, never crash the build.
- `data/` is gitignored; never commit card data or `cards.db`.
- Tests live in `tests/data/`, mirroring `src/fishbowl/data/`. Tests write only to pytest's `tmp_path`, never to `data/`.
- Ian runs `git add` / `git commit` / `git push` himself. "Commit" steps list the commands for him.
- Test data is copied from the real Scryfall file (trimmed), never written from memory.

## Review Focus

1. A leftover `cards.db.part` from an earlier crashed build: the next build should overwrite it and succeed. (Task 3 test `test_leftover_part_file_is_replaced`.)
2. Rebuilding when `cards.db` already exists: the new database fully replaces the old one, with no stale rows. (Task 3 test `test_rebuild_replaces_old_database`.)
3. The same `oracle_id` appearing twice: the build keeps the first and does not crash. (Task 3 test `test_duplicate_oracle_id_keeps_first`.)
4. Running the build before downloading: a friendly message and exit code 1, not a traceback. (Task 4 test `test_main_without_source_explains_what_to_do`.)
5. Fields with the wrong type (e.g. `colors` as a string, `legalities` as `null`, `all_parts` entries that aren't dicts): defaults are used, no crash. (Task 1 and Task 2 tests.)

---

### Task 1: Small converters in `cards.py`

**Files:**
- Modify: `src/fishbowl/data/cards.py`
- Test: `tests/data/test_cards.py`

**Interfaces:**
- Consumes: `legal_in_commander(legalities: object) -> bool` (exists).
- Produces:
  - `is_game_card(legalities: object) -> bool`
  - `commander_status(legalities: object) -> str`
  - `color_letters(symbols: object) -> str`
  - `token_links(all_parts: object) -> list[dict[str, str]]`

- [ ] **Step 1: Write the failing tests.** Change the import line at the top of `tests/data/test_cards.py` to:

```python
from fishbowl.data.cards import (
    color_letters,
    commander_status,
    is_game_card,
    legal_in_commander,
    token_links,
)
```

and append:

```python
@pytest.mark.parametrize("status", ["legal", "banned", "restricted"])
def test_card_legal_banned_or_restricted_anywhere_is_a_game_card(status):
    assert is_game_card({"commander": "not_legal", "vintage": status}) is True


@pytest.mark.parametrize(
    "legalities", [{"commander": "not_legal", "vintage": "not_legal"}, {}, None, "legal"]
)
def test_card_legal_nowhere_is_not_a_game_card(legalities):
    assert is_game_card(legalities) is False


def test_commander_status_passes_scryfall_value_through():
    assert commander_status({"commander": "banned"}) == "banned"


@pytest.mark.parametrize("legalities", [{}, None, {"commander": 7}])
def test_commander_status_missing_or_malformed_is_missing(legalities):
    assert commander_status(legalities) == "missing"


@pytest.mark.parametrize(
    ("symbols", "expected"),
    [
        ([], ""),
        (["R"], "R"),
        (["G", "W"], "WG"),  # always WUBRG order, whatever order Scryfall uses
        (["C"], "C"),
        (["U", "C", "B"], "UBC"),
    ],
)
def test_color_letters_in_wubrg_order(symbols, expected):
    assert color_letters(symbols) == expected


@pytest.mark.parametrize("symbols", [None, "WG", ["X", 3, None], 42])
def test_color_letters_ignores_bad_input(symbols):
    assert color_letters(symbols) == ""


def test_token_links_keeps_only_tokens():
    all_parts = [
        {"id": "70f8a1de-cd4c-4afa-bf03-0245d375d42e", "component": "token", "name": "Goblin"},
        {"id": "824b2d73-2151-4e5e-9f05-8f63e2bdcaa9", "component": "combo_piece", "name": "Krenko, Mob Boss"},
    ]
    assert token_links(all_parts) == [
        {"id": "70f8a1de-cd4c-4afa-bf03-0245d375d42e", "name": "Goblin"}
    ]


@pytest.mark.parametrize(
    "all_parts",
    [None, "Goblin", [None, "x", {"component": "token"}, {"component": "token", "name": "Goblin"}]],
)
def test_token_links_ignores_bad_input(all_parts):
    assert token_links(all_parts) == []
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `uv run pytest tests/data/test_cards.py -v`
Expected: collection ERROR, `ImportError: cannot import name 'color_letters'`.

- [ ] **Step 3: Write the implementation.** Append to `src/fishbowl/data/cards.py`:

```python
# Statuses that mean "this is a real card in some format", even if banned there.
GAME_STATUSES = {"legal", "banned", "restricted"}
# Magic's standard color order, then C for colorless mana.
COLOR_ORDER = "WUBRGC"


def is_game_card(legalities: object) -> bool:
    """True if any format lists the card as legal, banned or restricted.

    Tokens, art cards, planes and joke cards are not_legal everywhere, so they drop out.
    """
    if not isinstance(legalities, dict):
        return False
    return any(status in GAME_STATUSES for status in legalities.values())


def commander_status(legalities: object) -> str:
    """Scryfall's raw commander value ("legal", "banned", ...), or "missing"."""
    if not isinstance(legalities, dict):
        return "missing"
    status = legalities.get("commander")
    return status if isinstance(status, str) and status else "missing"


def color_letters(symbols: object) -> str:
    """["G", "W"] -> "WG": the letters present, in WUBRGC order."""
    if not isinstance(symbols, list):
        return ""
    present = {s for s in symbols if isinstance(s, str)}  # set comprehension
    return "".join(letter for letter in COLOR_ORDER if letter in present)


def token_links(all_parts: object) -> list[dict[str, str]]:
    """The tokens a card makes, as [{"id": ..., "name": ...}], from Scryfall's all_parts."""
    if not isinstance(all_parts, list):
        return []
    links = []
    for part in all_parts:
        if not isinstance(part, dict) or part.get("component") != "token":
            continue
        token_id, name = part.get("id"), part.get("name")
        if isinstance(token_id, str) and isinstance(name, str):
            links.append({"id": token_id, "name": name})
    return links
```

- [ ] **Step 4: Run all tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass (26 existing + the new cases).

- [ ] **Step 5: Commit (Ian).**

```bash
git add src/fishbowl/data/cards.py tests/data/test_cards.py
git commit -m "Add card field converters: is_game_card, commander_status, color_letters, token_links"
```

---

### Task 2: `card_to_row` and shared real-card fixtures

**Files:**
- Create: `tests/data/conftest.py`
- Modify: `src/fishbowl/data/cards.py`
- Test: `tests/data/test_cards.py`

**Interfaces:**
- Consumes: the Task 1 functions and `legal_in_commander`.
- Produces:
  - `card_to_row(card: object) -> dict[str, object] | None`, whose keys are exactly the `cards` table columns, in order: `oracle_id, name, layout, mana_cost, cmc, type_line, oracle_text, colors, color_identity, produced_mana, keywords, legal_commander, commander_status, is_game_changer, card_faces, tokens`.
  - pytest fixtures `sol_ring`, `krenko`, `witch_enchanter`, `goblin_token` (each a fresh `dict`), available to every test in `tests/data/`.

- [ ] **Step 1: Create the fixtures** in `tests/data/conftest.py`. pytest loads `conftest.py` automatically, and any test can ask for a fixture by naming it as a parameter.

```python
"""Real Scryfall cards (trimmed), shared by tests in tests/data/.

Copied from data/oracle-cards.jsonl.gz on 2026-10-10. Only the fields we use are kept,
and legalities are cut down to three formats.
"""

import copy

import pytest

SOL_RING = {
    "object": "card",
    "oracle_id": "6ad8011d-3471-4369-9d68-b264cc027487",
    "name": "Sol Ring",
    "layout": "normal",
    "mana_cost": "{1}",
    "cmc": 1.0,
    "type_line": "Artifact",
    "oracle_text": "{T}: Add {C}{C}.",
    "colors": [],
    "color_identity": [],
    "produced_mana": ["C"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "restricted", "legacy": "banned"},
    "game_changer": False,
}

KRENKO = {
    "object": "card",
    "oracle_id": "68418069-f615-40ef-ae0d-764192acae00",
    "name": "Krenko, Mob Boss",
    "layout": "normal",
    "mana_cost": "{2}{R}{R}",
    "cmc": 4.0,
    "type_line": "Legendary Creature — Goblin Warrior",
    "oracle_text": (
        "{T}: Create X 1/1 red Goblin creature tokens, "
        "where X is the number of Goblins you control."
    ),
    "colors": ["R"],
    "color_identity": ["R"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
    "all_parts": [
        {
            "id": "70f8a1de-cd4c-4afa-bf03-0245d375d42e",
            "component": "token",
            "name": "Goblin",
            "type_line": "Token Creature — Goblin",
        },
        {
            "id": "824b2d73-2151-4e5e-9f05-8f63e2bdcaa9",
            "component": "combo_piece",
            "name": "Krenko, Mob Boss",
            "type_line": "Legendary Creature — Goblin Warrior",
        },
    ],
}

WITCH_ENCHANTER = {
    "object": "card",
    "oracle_id": "0355249a-8e4e-41db-9cea-1b901faffbe6",
    "name": "Witch Enchanter // Witch-Blessed Meadow",
    "layout": "modal_dfc",
    "cmc": 4.0,
    "type_line": "Creature — Human Warlock // Land",
    "color_identity": ["W"],
    "produced_mana": ["W"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
    "card_faces": [
        {
            "name": "Witch Enchanter",
            "mana_cost": "{3}{W}",
            "type_line": "Creature — Human Warlock",
            "oracle_text": (
                "When this creature enters, destroy target artifact or "
                "enchantment an opponent controls."
            ),
        },
        {
            "name": "Witch-Blessed Meadow",
            "mana_cost": "",
            "type_line": "Land",
            "oracle_text": (
                "As this land enters, you may pay 3 life. If you don't, it enters "
                "tapped.\n{T}: Add {W}."
            ),
        },
    ],
}

GOBLIN_TOKEN = {
    "object": "card",
    "oracle_id": "0cd035f0-bb53-40b7-b320-5d921268295a",
    "name": "Goblin",
    "layout": "token",
    "mana_cost": "",
    "cmc": 0.0,
    "type_line": "Token Creature — Goblin",
    "oracle_text": "",
    "colors": ["R"],
    "color_identity": ["R"],
    "keywords": [],
    "legalities": {"commander": "not_legal", "vintage": "not_legal", "legacy": "not_legal"},
    "game_changer": False,
}


# deepcopy: each test gets its own copy, so one test changing it can't affect another.
@pytest.fixture
def sol_ring():
    return copy.deepcopy(SOL_RING)


@pytest.fixture
def krenko():
    return copy.deepcopy(KRENKO)


@pytest.fixture
def witch_enchanter():
    return copy.deepcopy(WITCH_ENCHANTER)


@pytest.fixture
def goblin_token():
    return copy.deepcopy(GOBLIN_TOKEN)
```

- [ ] **Step 2: Write the failing tests.** Add `import json` at the top of `tests/data/test_cards.py`, add `card_to_row` to the `fishbowl.data.cards` import, and append:

```python
def test_sol_ring_row(sol_ring):
    assert card_to_row(sol_ring) == {
        "oracle_id": "6ad8011d-3471-4369-9d68-b264cc027487",
        "name": "Sol Ring",
        "layout": "normal",
        "mana_cost": "{1}",
        "cmc": 1.0,
        "type_line": "Artifact",
        "oracle_text": "{T}: Add {C}{C}.",
        "colors": "",
        "color_identity": "",
        "produced_mana": "C",
        "keywords": "[]",
        "legal_commander": 1,
        "commander_status": "legal",
        "is_game_changer": 0,
        "card_faces": None,
        "tokens": "[]",
    }


def test_row_keys_match_table_columns_in_order(sol_ring):
    assert list(card_to_row(sol_ring)) == [
        "oracle_id", "name", "layout", "mana_cost", "cmc", "type_line", "oracle_text",
        "colors", "color_identity", "produced_mana", "keywords", "legal_commander",
        "commander_status", "is_game_changer", "card_faces", "tokens",
    ]


def test_krenko_row_links_goblin_token(krenko):
    row = card_to_row(krenko)
    assert row["color_identity"] == "R"
    assert row["produced_mana"] == ""  # Krenko has no produced_mana field at all
    assert json.loads(row["tokens"]) == [
        {"id": "70f8a1de-cd4c-4afa-bf03-0245d375d42e", "name": "Goblin"}
    ]


def test_double_faced_row_keeps_faces_and_null_top_level(witch_enchanter):
    row = card_to_row(witch_enchanter)
    assert row["mana_cost"] is None
    assert row["oracle_text"] is None
    assert row["colors"] == ""
    assert row["type_line"] == "Creature — Human Warlock // Land"
    faces = json.loads(row["card_faces"])
    assert [face["mana_cost"] for face in faces] == ["{3}{W}", ""]


def test_game_changer_is_1(sol_ring):
    sol_ring["game_changer"] = True
    assert card_to_row(sol_ring)["is_game_changer"] == 1


@pytest.mark.parametrize("missing", ["oracle_id", "name"])
def test_card_without_id_or_name_gives_none(sol_ring, missing):
    del sol_ring[missing]
    assert card_to_row(sol_ring) is None


@pytest.mark.parametrize("card", [None, "Sol Ring", [], 42])
def test_non_dict_card_gives_none(card):
    assert card_to_row(card) is None


def test_wrong_types_get_defaults(sol_ring):
    sol_ring.update(
        colors="R", keywords="Flying", legalities=None, all_parts=[None], layout=None
    )
    row = card_to_row(sol_ring)
    assert row["colors"] == ""
    assert row["keywords"] == "[]"
    assert row["legal_commander"] == 0
    assert row["commander_status"] == "missing"
    assert row["tokens"] == "[]"
    assert row["layout"] == "unknown"
```

- [ ] **Step 3: Run the tests to verify they fail.**

Run: `uv run pytest tests/data/test_cards.py -v`
Expected: collection ERROR, `ImportError: cannot import name 'card_to_row'`.

- [ ] **Step 4: Write the implementation.** Add `import json` at the top of `src/fishbowl/data/cards.py` (below the docstring) and append:

```python
def card_to_row(card: object) -> dict[str, object] | None:
    """One Scryfall card -> one `cards` table row, or None if it has no id or name.

    Keys are in the table's column order. Lists become letters or JSON text,
    because SQLite has no list type.
    """
    if not isinstance(card, dict):
        return None
    oracle_id, name = card.get("oracle_id"), card.get("name")
    if not (isinstance(oracle_id, str) and oracle_id and isinstance(name, str) and name):
        return None

    legalities = card.get("legalities")
    keywords = card.get("keywords")
    faces = card.get("card_faces")
    layout = card.get("layout")
    return {
        "oracle_id": oracle_id,
        "name": name,
        "layout": layout if isinstance(layout, str) and layout else "unknown",
        "mana_cost": card.get("mana_cost"),  # None for double-faced cards
        "cmc": card.get("cmc"),
        "type_line": card.get("type_line"),
        "oracle_text": card.get("oracle_text"),
        "colors": color_letters(card.get("colors")),
        "color_identity": color_letters(card.get("color_identity")),
        "produced_mana": color_letters(card.get("produced_mana")),
        "keywords": json.dumps(keywords if isinstance(keywords, list) else []),
        "legal_commander": int(legal_in_commander(legalities)),  # True/False -> 1/0
        "commander_status": commander_status(legalities),
        "is_game_changer": int(card.get("game_changer") is True),
        "card_faces": json.dumps(faces) if isinstance(faces, list) else None,
        "tokens": json.dumps(token_links(card.get("all_parts"))),
    }
```

- [ ] **Step 5: Run all tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 6: Commit (Ian).**

```bash
git add src/fishbowl/data/cards.py tests/data/conftest.py tests/data/test_cards.py
git commit -m "Add card_to_row and real-card test fixtures"
```

---

### Task 3: `build_database` in `database.py`

**Files:**
- Create: `src/fishbowl/data/database.py`
- Test: `tests/data/test_database.py`

**Interfaces:**
- Consumes: `card_to_row(card) -> dict | None`, `is_game_card(legalities) -> bool`; fixtures `sol_ring`, `krenko`, `witch_enchanter`, `goblin_token`.
- Produces:
  - `SCHEMA: str`, the `CREATE TABLE` and `CREATE INDEX` SQL.
  - `build_database(source: Path, dest: Path) -> tuple[int, int]`, returning `(cards_written, lines_skipped)`.

- [ ] **Step 1: Write the failing tests** in `tests/data/test_database.py`:

```python
"""Tests for building the SQLite card database from a gzipped JSON Lines file."""

import gzip
import json
import sqlite3

import pytest

from fishbowl.data.database import build_database


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
    assert counts == (3, 1)  # token left out on purpose (not skipped), broken line skipped


def test_sol_ring_done_when_query(built):
    dest, _ = built
    rows = query(dest, "SELECT mana_cost, color_identity FROM cards WHERE name = 'Sol Ring'")
    assert rows == [("{1}", "")]


def test_token_is_left_out(built):
    dest, _ = built
    assert query(dest, "SELECT COUNT(*) FROM cards WHERE name = 'Goblin'") == [(0,)]


def test_krenko_keeps_token_link(built):
    dest, _ = built
    [(tokens,)] = query(dest, "SELECT tokens FROM cards WHERE name = 'Krenko, Mob Boss'")
    assert json.loads(tokens)[0]["name"] == "Goblin"


def test_name_lookup_ignores_case(built):
    dest, _ = built
    rows = query(dest, "SELECT name FROM cards WHERE name = ? COLLATE NOCASE", ("SOL RING",))
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
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `uv run pytest tests/data/test_database.py -v`
Expected: collection ERROR, `ModuleNotFoundError: No module named 'fishbowl.data.database'`.

- [ ] **Step 3: Write the implementation** in `src/fishbowl/data/database.py`:

```python
"""Building the local card database (data/cards.db) from Scryfall's bulk file.

Build it with:  uv run python -m fishbowl.data.database
"""

import gzip
import json
import sqlite3
from pathlib import Path

from fishbowl.data.cards import card_to_row, is_game_card

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
    with gzip.open(source, "rt", encoding="utf-8") as lines:
        for line in lines:
            try:
                card = json.loads(line)
            except json.JSONDecodeError:
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
    rows, skipped = read_card_rows(source)  # raises FileNotFoundError before touching dest

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
```

- [ ] **Step 4: Run all tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 5: Commit (Ian).**

```bash
git add src/fishbowl/data/database.py tests/data/test_database.py
git commit -m "Add build_database: Scryfall bulk file to SQLite cards table"
```

---

### Task 4: The build command, real build, and roadmap

**Files:**
- Modify: `src/fishbowl/data/database.py`
- Test: `tests/data/test_database.py`
- Modify: `docs/ROADMAP.md` (mark Part 2 ✅)

**Interfaces:**
- Consumes: `build_database(source, dest) -> tuple[int, int]`.
- Produces: `main(source: Path = DEFAULT_SOURCE, dest: Path = DEFAULT_DEST) -> int` (exit code), plus the constants `DEFAULT_SOURCE` and `DEFAULT_DEST`.

- [ ] **Step 1: Write the failing tests.** Change the import in `tests/data/test_database.py` to `from fishbowl.data.database import build_database, main` and append:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `uv run pytest tests/data/test_database.py -v`
Expected: collection ERROR, `ImportError: cannot import name 'main'`.

- [ ] **Step 3: Write the implementation.** In `src/fishbowl/data/database.py`, add `import sys` to the imports, add these constants below the imports:

```python
DEFAULT_SOURCE = Path("data") / "oracle-cards.jsonl.gz"
DEFAULT_DEST = Path("data") / "cards.db"
```

and append at the end of the file:

```python
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
```

- [ ] **Step 4: Run all tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 5: Build the real database.**

Run: `uv run python -m fishbowl.data.database`
Expected: `Built data\cards.db: 32,870 cards, 0 lines skipped` (the exact count may shift slightly as Scryfall updates).

- [ ] **Step 6: Run the "done when" query.**

Run:
```bash
uv run python -c "import sqlite3; c = sqlite3.connect('data/cards.db'); print(c.execute(\"SELECT name, mana_cost, color_identity FROM cards WHERE name = 'Sol Ring'\").fetchall())"
```
Expected: `[('Sol Ring', '{1}', '')]`

Also check: `git status --short` shows nothing under `data/`.

- [ ] **Step 7: Mark Part 2 done** in `docs/ROADMAP.md`: change `- ⬜ Part 2: Build a SQLite database of the useful columns.` to `- ✅ Part 2: Build a SQLite database of the useful columns.`

- [ ] **Step 8: Commit (Ian).**

```bash
git add src/fishbowl/data/database.py tests/data/test_database.py docs/ROADMAP.md
git commit -m "Add database build command and mark Stage 1 Part 2 done"
```
