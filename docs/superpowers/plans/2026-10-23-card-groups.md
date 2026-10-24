# Card Groups Implementation Plan (Stage 4c)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For each deck, detect mana dorks and tutors from card text, print the matches, and show a what-if table of "at least one by turn t" for the current count and nearby counts.

**Architecture:** A new `src/fishbowl/stats/groups.py` with three layers:
- detection: `is_mana_dork`, `is_tutor`, `find_groups` → `list[CardGroup]`
- maths: `what_if` → `list[WhatIfRow]`, with the exact rows from `exact_at_least` and the current row also simulated
- a command `main`, shaped like `lands.main`/`mulligan.main`

**Tech Stack:** Python 3.12, standard library only (`re`, `random`, `dataclasses`, `textwrap`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-card-groups-design.md`

## Global Constraints

- Python 3.12+, run through `uv run`. **No new dependencies.**
- Dork: the front face of `type_line` (the text before `" // "`) contains the word `Creature`, and `oracle_text` matches the regex `\{T\}[^.]*: Add `.
- Tutor: `oracle_text` contains "search your library for" (case-insensitive), and the text after it, up to the next `.`, mentions none of `land`, `plains`, `island`, `swamp`, `mountain` or `forest` (case-insensitive).
- Empty or missing `oracle_text` matches no group. Don't change `Card` or `CardLookup`.
- Commanders: one copy of each is left out of group counts and names, as in `library_counts`.
- Checkpoints: opening hand 7 cards, turn 1 = 8, turn 2 = 9, turn 3 = 10 (multiplayer draws).
- What-if counts: current −4, −2, current, +2, +4, dropping any below 0 or above the library size.
- Every row is exact. The current row is also simulated for the opening hand: 100,000 hands, seed 42, within 0.01 of exact. Import `HAND_SIZE`, `TRIALS`, `SEED`, `exact_at_least`, `library_counts` from `fishbowl.stats.lands`. Don't redefine them.
- Tests write only to `tmp_path` (the `card_db` fixture). The real `data/cards.db` is read only in `tests/deck/test_real_decks.py`.
- Agents never run `git add`/`commit`/`push`. Ian commits after each task.
- Every touched `.py` file passes `ruff format`, `ruff check` and `~/.local/bin/basedpyright.exe --level error -p C:/Users/iwsch/.claude/hooks/basedpyright-default.json <file>`.

## Review Focus

1. **"Island" contains "land":** "search your library for an Island card" must not be a tutor. That's correct under the rule, but it must be pinned. (Task 1 `test_basic_land_searches_are_not_tutors`.)
2. **A card with no rules text** (vanilla creatures, some double-faced cards with `oracle_text=None`) must not crash the detectors. (Task 1 `test_no_text_matches_nothing`.)
3. **A group with 0 cards** (Krenko's dorks): prints "none found" and still shows the 0, 2, 4 what-if rows. (Task 2 `test_zero_count_rows`, Task 3 `test_prints_groups`.)
4. **A count near the library size** (a tiny or odd deck): the what-if rows must drop counts above the library, never error. (Task 2 `test_rows_clipped_at_library`.)
5. **The commander matches a group** (for example a dork as commander): it must not be counted. (Task 1 `test_commander_not_counted`.)

---

### Task 1: Detect mana dorks and tutors

**Files:**
- Create: `src/fishbowl/stats/groups.py`
- Test: `tests/stats/test_group_detection.py`; add one real-deck test to `tests/deck/test_real_decks.py`

**Interfaces:**
- Consumes:
  - `Card(oracle_id, name, type_line, oracle_text, color_identity, commander_status, is_game_changer)` from `fishbowl.deck.lookup`
  - `ParsedDeck` from `fishbowl.deck.model`
  - `CardLookup.find(name) -> Card | None`
- Produces:
  - `is_mana_dork(card: Card) -> bool`
  - `is_tutor(card: Card) -> bool`
  - `@dataclass(frozen=True) class CardGroup` with fields:
    - `name: str` (e.g. `"Mana dorks"`)
    - `unit: str` (singular, e.g. `"dork"`)
    - `units: str` (plural, e.g. `"dorks"`)
    - `count: int` (copies in the library)
    - `names: list[str]` (matched card names, sorted alphabetically)
  - `find_groups(deck: ParsedDeck, lookup: CardLookup) -> list[CardGroup]`: always two groups, in order: `("Mana dorks", "dork", "dorks")`, then `("Tutors", "tutor", "tutors")`.

- [ ] **Step 1: Write the failing tests** in `tests/stats/test_group_detection.py`. Use a small helper, `card(name, type_line, text)`, that builds a `Card` with dummy values for the other fields. The cases:
  - `test_dorks`:
    - These are dorks:
      - Llanowar Elves: `"Creature — Elf Druid"`, `"{T}: Add {G}."`
      - Selvala: `"Legendary Creature — Elf Scout"`, `"…\n{G}, {T}: Add X mana in any combination of colors, where X is the greatest power among creatures you control."`
    - These are not dorks:
      - Arbor Elf: `"{T}: Untap target Forest."`
      - Arcane Signet: `"Artifact"`, `"{T}: Add one mana of any color in your commander's color identity."`
      - Krenko: `"{T}: Create X 1/1 red Goblin creature tokens, …"`
  - `test_tutors`:
    - These are tutors:
      - Goblin Matron: `"When this creature enters, you may search your library for a Goblin card, reveal it, put it into your hand, then shuffle."`
      - Demonic Tutor: `"Search your library for a card, put that card into your hand, then shuffle."`
  - `test_basic_land_searches_are_not_tutors`: not tutors:
    - Nature's Lore: `"Search your library for a Forest card, put that card onto the battlefield, then shuffle."`
    - Cultivate: `"Search your library for up to two basic land cards, …"`
    - `"Search your library for an Island card, …"`
  - `test_no_text_matches_nothing`: `oracle_text=None` and `""` give False for both detectors. `type_line=None` gives False for the dork detector.
  - `test_find_groups` (`card_db` fixture): a deck of `Commander: Goreclaw`, `1 Goreclaw…`, `1 Survival of the Fittest`, `1 Sylvan Primordial`, `1 Sol Ring`, `10 Forest`. Expect:
    - Mana dorks: count 0, names `[]`
    - Tutors: count 1, names `["Survival of the Fittest"]`
    
    Sylvan Primordial's fixture text searches for Forest cards, so it's correctly a non-tutor.
  - `test_commander_not_counted`: parse `"1 Survival of the Fittest\n1 Goreclaw, Terror of Qal Sisma\n10 Forest"`. Then set the deck's `commanders` to a `DeckEntry` for Survival, built as in `tests/stats/test_library_counts.py`, or by whatever means that file uses. Tutors count is 0.
- Add to `tests/deck/test_real_decks.py`: `test_real_groups`.
  - Goreclaw dorks names == `["Elvish Mystic", "Fanatic of Rhonas", "Fyndhorn Elves", "Karametra's Acolyte", "Llanowar Elves", "Selvala, Heart of the Wilds", "Whisperer of the Wilds"]`.
  - Krenko tutors include `"Goblin Matron"` and `"Goblin Recruiter"`.
  - Goreclaw tutors include none of `"Nature's Lore"`, `"Three Visits"`, `"Skyshroud Claim"`.

- [ ] **Step 2: Run them and make sure they fail**

Run: `uv run pytest tests/stats/test_group_detection.py -v`. Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement** in `groups.py`, with a module docstring naming the run command `uv run python -m fishbowl.stats.groups <decklist.txt>`.
  - Compile the dork regex and the basic-land word list once, at module level, each with a one-line "why" comment.
  - The tutor check reads the text after "search your library for" up to the first `.`.
  - `find_groups` counts copies the same way `library_counts` does: quantity, minus 1 for a commander.

- [ ] **Step 4: Run them and make sure they pass:** `uv run pytest tests/stats/test_group_detection.py tests/deck/test_real_decks.py -v`. Then run `uv run pytest`. All pass.

- [ ] **Step 5: Suggested commit (Ian runs it)**

```bash
git add src/fishbowl/stats/groups.py tests/stats/test_group_detection.py tests/deck/test_real_decks.py docs/superpowers/specs/2026-10-23-card-groups-design.md docs/superpowers/plans/2026-10-23-card-groups.md
git commit -m "Detect mana dorks and tutors from card text (Stage 4c)"
```

---

### Task 2: The what-if table

**Files:**
- Modify: `src/fishbowl/stats/groups.py`
- Test: `tests/stats/test_what_if.py`

**Interfaces:**
- Consumes: `exact_at_least(k, lands, library, drawn)`, `HAND_SIZE`, `TRIALS`, `SEED` from `fishbowl.stats.lands`.
- Produces:
  - `CHECKPOINTS = (7, 8, 9, 10)`: cards seen in the opening hand and by turns 1, 2 and 3.
  - `@dataclass(frozen=True) class WhatIfRow` with fields:
    - `count: int`
    - `chances: list[float]` (one per checkpoint, exact)
    - `simulated: float | None` (opening hand, current row only)
    - `is_current: bool`
  - `what_if(count: int, library: int, trials: int = TRIALS, seed: int = SEED) -> list[WhatIfRow]`: the rows run from the lowest count to the highest. It raises `ValueError` if `library < CHECKPOINTS[-1]`, if `count` is outside 0..library, or if `trials < 1`.

- [ ] **Step 1: Write the failing tests** in `tests/stats/test_what_if.py`:
  - `test_rows_around_current`: `[r.count for r in what_if(7, 99, trials=100)] == [3, 5, 7, 9, 11]`. Only the 7 row has `is_current`, and only it has a non-`None` `simulated`.
  - `test_zero_count_rows`: the counts for `what_if(0, 99, trials=100)` are `[0, 2, 4]`. The 0 row's chances are all 0.0.
  - `test_rows_clipped_at_library`: the counts for `what_if(10, 12, trials=100)` are `[6, 8, 10, 12]`. The 12 row's chances are all 1.0.
  - `test_exact_values`: for the 7-of-99 row:
    - `chances[0] == pytest.approx(exact_at_least(1, 7, 99, 7))`
    - `round(chances[0], 3) == 0.412`
    - `chances` is non-decreasing along the checkpoints
    - each column is non-decreasing as the count rises
  - `test_simulated_matches_exact`: for counts 0, 2, 7 and 12 of 99, using the default trials, `abs(current.simulated - current.chances[0]) < 0.01`.
  - `test_same_seed_same_numbers`: the same seed gives equal results; seeds 7 and 8 differ, with count 7 and 2000 trials.
  - `test_invalid_inputs_raise`: `(7, 9)`, `(-1, 99)`, `(100, 99)`, and trials 0 all raise `ValueError`.

- [ ] **Step 2: Run them and make sure they fail:** `uv run pytest tests/stats/test_what_if.py -v`. Expected: `ImportError`.

- [ ] **Step 3: Implement `CHECKPOINTS`, `WhatIfRow` and `what_if`.** The simulation follows 4a's numbering trick. Cards numbered below `count` are in the group. Each trial runs `rng.sample(range(library), HAND_SIZE)` and counts a hit if any card is in the group. Only the current count is simulated, and only for the opening hand.

- [ ] **Step 4: Run them and make sure they pass:** `uv run pytest tests/stats/test_what_if.py -v`, then `uv run pytest`.

- [ ] **Step 5: Suggested commit (Ian runs it)**

```bash
git add src/fishbowl/stats/groups.py tests/stats/test_what_if.py
git commit -m "Add what-if odds for card groups (Stage 4c)"
```

---

### Task 3: The groups command and roadmap

**Files:**
- Modify: `src/fishbowl/stats/groups.py`, `docs/ROADMAP.md`
- Test: `tests/stats/test_groups_main.py`

**Interfaces:**
- Consumes:
  - `find_groups` and `CardGroup` (Task 1); `what_if`, `WhatIfRow` and `CHECKPOINTS` (Task 2)
  - `library_counts` and `SEED` from `lands.py`
  - `find_deck_file` and `read_deck` from `fishbowl.deck.parser`
  - `DEFAULT_DB` and `CardLookup` from `fishbowl.deck.lookup`
- Produces: `main(argv: list[str] | None = None, db_path: Path = DEFAULT_DB, read: Callable[[str], str] = input, write: Callable[[str], object] = print, trials: int = TRIALS) -> int`, plus an `if __name__ == "__main__": sys.exit(main())` block.

Output, in order:
1. The header: `f"{who}: {library}-card library ({trials:,} simulated hands, seed {SEED}; multiplayer: everyone draws on turn 1)"`.
2. The no-commander and unreadable-lines notes, with `lands.main`'s exact wording.
3. For each group: a blank line, then either `f"{group.name}: {group.count} in the library"` or `f"{group.name}: none found"`. Then the names, joined with `", "`, wrapped with `textwrap.wrap(width=76)`, each line indented 2 spaces. A blank line follows, then the table:
   - header `f"{'At least one':<22}{'opening':>9}{'turn 1':>9}{'turn 2':>9}{'turn 3':>9}{'simulated':>11}"`
   - each row's label is `f"  {count} {unit if count == 1 else units}"`, plus `" (yours)"` on the current row, padded with `:<22`
   - each chance is `f"{chance:>9.0%}"`
   - then `f"{simulated:>11.1%}"` on the current row, or nothing on other rows
4. Tiny deck (library < `CHECKPOINTS[-1]`): `f"Only {library} cards in the library; at least 10 are needed to see 3 turns."`, built from the constants, and return 1.

Usage: `"Usage: uv run python -m fishbowl.stats.groups <decklist.txt>"`.

Roadmap: split Stage 4's remaining work, in the 4a/4b style:
- "card groups done in Stage 4c: `uv run python -m fishbowl.stats.groups <decklist>`"
- "Stage 4d (next): commander castable on curve (lands-only baseline) and Matplotlib charts"

Stage 4 stays 🔄.

- [ ] **Step 1: Write the failing tests** in `tests/stats/test_groups_main.py`. Copy the `run` helper from `tests/stats/test_lands_main.py`, changing the import. The tests:
  - `test_prints_groups`: deck `Commander: Goreclaw`, `1 Goreclaw…`, `1 Survival of the Fittest`, `33 Forest`, `65 Sol Ring`. Checks:
    - returns 0
    - `shown[0]` is the header with `99-card library (2,000 simulated hands`
    - `"Mana dorks: none found"` is shown
    - `"Tutors: 1 in the library"` is shown
    - `"  Survival of the Fittest"` is shown
    - one line starts with `"  1 tutor (yours)"`
    - one line starts with `"  3 tutors"`
    - one line starts with `"  0 dorks (yours)"`
  - `test_main_without_commander_uses_whole_deck` and `test_main_notes_unreadable_lines`: as in `test_lands_main.py`, with the same messages.
  - `test_tiny_deck_message`: Goreclaw commander with `4 Forest` and `4 Sol Ring`. Returns 1 and shows `"Only 8 cards in the library; at least 10 are needed to see 3 turns."`.
  - `test_usage_and_missing_file`: `run([])` returns 1 and shows exactly the usage text.

- [ ] **Step 2: Run them and make sure they fail:** `uv run pytest tests/stats/test_groups_main.py -v`. Expected: `ImportError`.

- [ ] **Step 3: Implement `main`** following `mulligan.main` step for step, and update `docs/ROADMAP.md`.

- [ ] **Step 4: Run all the tests and the real command:** `uv run pytest`, then `uv run python -m fishbowl.stats.groups tests/decks/goreclaw.txt` and `… tests/decks/krenko.txt`. Paste both outputs into the report. Goreclaw shows the 7 dorks with an opening-hand chance of 41%. Krenko lists Goblin Matron and Goblin Recruiter among its tutors.

- [ ] **Step 5: Suggested commit (Ian runs it)**

```bash
git add src/fishbowl/stats/groups.py tests/stats/test_groups_main.py docs/ROADMAP.md
git commit -m "Add card groups command (Stage 4c)"
```
