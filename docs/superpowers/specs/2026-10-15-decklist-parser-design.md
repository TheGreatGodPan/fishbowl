# Decklist parser design (Stage 2)

Date: 2026-10-15 · Status: approved in conversation, awaiting spec review

## Goal

Turn a pasted decklist (text) into a `ParsedDeck`: the cards and their counts, resolved to real cards in `data/cards.db`, the commander (or "unknown"), and a list of problems. It must never crash on odd text. Later stages build on it: the validator (Stage 3), statistics (Stage 4) and the simulator (Stage 6).

**Done when:** Ian's decks (Goreclaw, Ghalta/Tramplesaurus Rex, and Krenko when supplied) each parse to 100 cards with the right commander and zero problems, and deliberately broken lines are reported clearly instead of crashing.

## Evidence (real exports, 2026-10-15)

- **Goreclaw** (Moxfield export): `1 Sol Ring (SLC) 19 *F*`. The commander is on the first line with no label. 94 lines, 100 cards. 26 Forests spread over 20 lines. Collector numbers like `1★` and set codes like `PDMU` appear. Two names are printed alternate names: "The Banyan Tree" is really The Great Henge (TLE 41), and "The Cloudsea Djinn" is really Nyxbloom Ancient (FCA 16).
- **Ghalta** (plain): `1 Sol Ring`. The commander is alone after a final blank line. 71 lines, 100 cards, `16 Forest` appears twice.

## Decisions

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | Printed alternate names | `card_aliases` table built during refresh from Scryfall `default_cards` (`flavor_name`), plus front-face names of multi-face cards from `oracle_cards`. | Parsing stays offline and works without set codes. Follows the bulk-data rule. Costs ~80 MB more per refresh. |
| 2 | Finding the commander | Only from clear signals: a `Commander` section header, an explicit `Commander: <name>` line, an Archidekt `[Commander...]` tag, or a final blank-line-separated section of 1–2 cards. Otherwise "unknown". Never guess from line order. | A wrong commander poisons the validator, statistics and goldfish. |
| 3 | Commander unknown | The parser returns candidates (legendary creatures in the deck, plus cards whose text says "can be your commander"). A separate prompt lets the user filter by typing letters and select by number. | Parsing stays pure. The CLI (Stage 5) and the web page (Stage 7.5) can each ask in their own way. |
| 4 | Test decks | Committed under `tests/decks/`. | Card names and counts only. Tests run on both machines and for anyone who clones the repo. |

## Database change: `card_aliases`

```sql
CREATE TABLE card_aliases (
    alias     TEXT PRIMARY KEY COLLATE NOCASE,
    oracle_id TEXT NOT NULL REFERENCES cards (oracle_id)
);
```

- From `default_cards`: every printing with a `flavor_name` different from its `name`, whose `oracle_id` is in `cards`.
- From `oracle_cards` multi-face cards (those with `card_faces`): the first face's name, when it differs from the full name. Example: `Witch Enchanter` → the Witch Enchanter // Witch-Blessed Meadow row.
- An alias equal to an existing card name is not added: the real card wins. If two different cards claim the same alias, the first one wins (`INSERT OR IGNORE`).
- `refresh` downloads `default_cards` to `data/default-cards.jsonl.gz` with the same checks as `oracle_cards`: headers, the scryfall.io URL check and the `.part` rename. The build reads it line by line and keeps only the alias pairs.
- If the `default_cards` file is missing, the build still succeeds with only the front-face aliases, and says so.

## Parser

### Line formats

| Line | Result |
|---|---|
| `1 Sol Ring`, `1x Sol Ring`, `1X Sol Ring` | quantity 1, name "Sol Ring" |
| `Sol Ring` (no number) | quantity 1 |
| `1 Sol Ring (SLC) 19 *F*`, `1 Llanowar Elves (PDMU) 1★ *F*` | set code, collector number and `*F*`/`*E*` markers are stripped |
| `1x Sol Ring (cmm) 400 [Ramp]`, `... [Commander{top}]` | `[...]` tags are stripped. A tag whose text starts with `Commander` marks the card as commander. |
| `Commander`, `Commanders`, `Deck`, `Mainboard`, `Main`, `Sideboard`, `Maybeboard`, `Companion` (any case, optional trailing `:` or ` (N)`) | section header |
| `Commander: Goreclaw, Terror of Qal Sisma` | explicit commander. If the same card is also listed as a normal card line, it is not counted twice. Otherwise it adds 1 copy. |
| blank line | ends the current block |
| `//...`, `#...` | comment, ignored |

Sections: cards under `Commander`/`Commanders` are commanders. Cards under `Sideboard`/`Maybeboard`/`Companion` are left out of the deck and listed in `ParsedDeck.left_out`. Everything else is main deck.

**Final-block rule:** when no other commander signal exists, and the list ends with a blank line followed by 1–2 card lines and no header, those cards are the commander(s).

Quantities for the same card (after name resolution) are added together. Commanders are part of the 100.

### Name resolution

`CardLookup` (in `lookup.py`) opens `cards.db` read-only and resolves a name:
1. `cards.name = ? COLLATE NOCASE`
2. otherwise `card_aliases.alias = ?`

The result is the card's `oracle_id` and real name, or `None`.

### Output

```python
@dataclass
class DeckEntry:
    name: str          # real card name from the database
    oracle_id: str
    quantity: int

@dataclass
class Problem:
    line_number: int   # 1-based
    text: str          # the original line, trimmed to 200 characters
    reason: str        # e.g. 'unknown card "Sol Rnig"'

@dataclass
class ParsedDeck:
    cards: list[DeckEntry]      # main deck including commanders, one entry per card, input order of first appearance
    commanders: list[DeckEntry] # 0, 1 or 2 entries
    left_out: list[DeckEntry]   # sideboard / maybeboard / companion
    problems: list[Problem]
    total: int                  # sum of quantities in cards
```

### Untrusted input

- No input line ever raises. Unreadable lines and unknown names become `Problem`s.
- Text over 1,000 lines is refused with a single `Problem` (line 0, "too many lines (N); a Commander deck has 100 cards") and an empty deck.
- Quantities must be 1–999. Anything else becomes a `Problem` for that line.
- Lines are trimmed. Tabs and repeated spaces are treated as single spaces. A BOM at the start is ignored.

## Commander helpers (`commander.py`)

- `commander_candidates(deck, lookup) -> list[str]`: names from `deck.cards` whose `type_line` contains both `Legendary` and `Creature`, or whose `oracle_text` contains `can be your commander`. Sorted by name.
- `ask_for_commander(candidates, read=input, write=print) -> str | None`: shows a numbered list. Typing letters filters it (case-insensitive substring) and shows the shorter list. Typing a number selects. An empty answer, or no candidates, gives `None`. Tested with fake `read`/`write`.

## Command

`uv run python -m fishbowl.deck.parser <file>` reads the file (UTF-8, replacing undecodable bytes), parses it, asks for the commander if it's unknown, and prints: the total, the commander, any left-out cards, and the problems with line numbers. Exit code 0 when there are no problems, 1 otherwise.

## Testing

- Unit tests for every line format, header, tag and bad-line case.
- Real-deck tests (`tests/decks/goreclaw.txt`, `tests/decks/ghalta.txt`) read the real `data/cards.db` read-only. They are skipped with a clear reason when it is missing, or when it has no `card_aliases` table yet. All other tests use a small database built in `tmp_path` from the real-card fixtures.
- The Goreclaw file gains a first line `Commander: Goreclaw, Terror of Qal Sisma`, because its export has no commander signal. The Ghalta file is committed exactly as exported.
- Alias tests: The Banyan Tree → The Great Henge, The Cloudsea Djinn → Nyxbloom Ancient, Witch Enchanter → the full DFC name.
- `ask_for_commander`: filtering, choosing by number, invalid input and empty input, using fake input.

## Out of scope

- Legality and validation rules: 100 cards, singleton, color identity, banned cards (Stage 3).
- Partner and Background validity (Stage 3). The parser only allows up to 2 commanders.
- Fetching decks from Moxfield/Archidekt URLs.
