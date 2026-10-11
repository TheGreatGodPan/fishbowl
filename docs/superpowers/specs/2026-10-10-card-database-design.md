# Card database design (Stage 1, Part 2)

Date: 2026-10-10 · Status: approved in conversation, awaiting spec review

## Goal

Turn Scryfall's `oracle_cards` bulk file (`data/oracle-cards.jsonl.gz`, from Part 1) into a local SQLite database, `data/cards.db`, that later stages query by card name: the parser (Stage 2), the validator (Stage 3), the statistics (Stage 4) and the simulator (Stage 6).

**Done when:** a SQL query returns Sol Ring's mana cost (`{1}`) and color identity (`""`), and the database rebuilds from a single command.

## Decisions

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | Which rows go in? | Only game cards: rows legal, banned or restricted in at least one format. | Drops tokens, art series, planes, emblems and Un/playtest cards (5,838 rows on 2026-10-09) without a hand-kept layout list. Format rules stay data, not code. No commander-legal card is dropped. |
| 2 | Double-faced cards? | Store top-level fields exactly as Scryfall gives them; `card_faces` as JSON text. | Never invent values. `cmc`, `color_identity` and `type_line` are complete at the top level, which covers Stages 2–4. A faces table can come in Stage 6 if needed. |
| 3 | Color lists? | Compact letters in WUBRG order, then C (`""`, `"R"`, `"WG"`, `"C"`). | Readable, easy SQL (`= 'R'`, `LIKE '%G%'`), and `set("WG")` gives the set Stage 3 needs. Every value in these columns is a single letter. |
| 4 | Tokens? | Not a table yet. Each card keeps its token links (from Scryfall's `all_parts`) as JSON. | Tokens matter for Krenko in Stage 6. Keeping the links now means no rebuild later; the tokens table is designed when the simulator needs it. |
| 5 | Banned vs not legal? | Keep `legal_commander` (0/1) **and** raw `commander_status`. | Stage 3 can say "banned" rather than just "not legal". |

## The `cards` table

```sql
CREATE TABLE cards (
    oracle_id        TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    layout           TEXT NOT NULL,
    mana_cost        TEXT,              -- NULL for multi-face cards (see card_faces)
    cmc              REAL,
    type_line        TEXT,
    oracle_text      TEXT,              -- NULL for multi-face cards
    colors           TEXT NOT NULL,     -- WUBRG letters, '' if none
    color_identity   TEXT NOT NULL,     -- WUBRG letters, '' if colorless
    produced_mana    TEXT NOT NULL,     -- WUBRGC letters, '' if none
    keywords         TEXT NOT NULL,     -- JSON list
    legal_commander  INTEGER NOT NULL,  -- 1 = legal, 0 = anything else
    commander_status TEXT NOT NULL,     -- Scryfall's value, e.g. 'legal', 'banned', 'not_legal'
    is_game_changer  INTEGER NOT NULL,  -- 1 / 0
    card_faces       TEXT,              -- JSON list, NULL for single-face cards
    tokens           TEXT NOT NULL      -- JSON list of {"id", "name"}, '[]' if none
);
CREATE INDEX idx_cards_name ON cards (name COLLATE NOCASE);
```

Example rows: Sol Ring → `mana_cost '{1}'`, `color_identity ''`, `produced_mana 'C'`, `legal_commander 1`. Krenko, Mob Boss → `color_identity 'R'`, `tokens '[{"id": "…", "name": "Goblin"}]'`.

Missing values: `colors`, `color_identity` and `produced_mana` become `''`; `keywords` and `tokens` become `'[]'`; `commander_status` becomes `'missing'` if Scryfall has no commander entry.

## Code

**`src/fishbowl/data/cards.py`**: pure functions, one Scryfall card dict in, plain values out. No files, no database.

- `legal_in_commander(legalities) -> bool` (exists, Part 1)
- `is_game_card(legalities) -> bool`: True if any format says `legal`, `banned` or `restricted`. Malformed input → False.
- `color_letters(symbols) -> str`: list of symbols → letters in WUBRGC order. Unknown symbols ignored; non-list → `''`.
- `token_links(all_parts) -> list[dict]`: the `component == "token"` entries as `{"id", "name"}`. Malformed → `[]`.
- `card_to_row(card) -> dict | None`: one card → one row matching the table. Returns `None` if `oracle_id` or `name` is missing.

**`src/fishbowl/data/database.py`**: builds the database.

- `SCHEMA`: the SQL above.
- `build_database(source: Path, dest: Path) -> tuple[int, int]`: reads the gzipped JSON Lines file line by line, skips non-game cards, inserts rows with `executemany`. Returns `(cards_written, lines_skipped)`. Builds into `dest` + `.part`, then renames, so a failed build never leaves a half-built `cards.db`.
- `main()`: `uv run python -m fishbowl.data.database` builds `data/cards.db` from `data/oracle-cards.jsonl.gz` and prints a summary. If the source file is missing, it prints a message telling you to run the download first.

Pandas is not used by the build. Streaming line by line keeps memory low, and one line is one card. Pandas stays for exploration and Stage 4.

## Error handling

Decklists and downloaded data are untrusted input.

- A line that isn't valid JSON, or isn't a JSON object → skipped and counted.
- A card missing `oracle_id` or `name` → skipped and counted.
- A non-game card → left out on purpose. Not counted as skipped.
- A duplicate `oracle_id` → the first one wins (`INSERT OR IGNORE`). Scryfall shouldn't send duplicates, but a build must not crash if it does.
- Summary line, e.g. `Built data/cards.db: 32,870 cards, 0 lines skipped`.

## Testing

- Unit tests (TDD) for every function in `cards.py`, including malformed inputs.
- One integration test: build a database in pytest's `tmp_path` from a small `.jsonl.gz` fixture (Sol Ring, Krenko, a double-faced card and a token, copied from the real file and trimmed, plus one broken line). Then query it: Sol Ring's values, Krenko's token link, the token left out, `skipped == 1`.
- Real-data check after building: row count, and the "done when" SQL query.

## Out of scope

- A tokens table, a card-faces table (Stage 6 if needed).
- Name lookup rules such as front-face names and case handling (Stage 2 parser).
- One command that downloads and builds (Part 3).
