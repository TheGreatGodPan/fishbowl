# Commander on Curve Implementation Plan (Stage 4d)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For each commander, show the chance of having enough lands, and enough lands of the right colours, to cast it on the turn its mana value says. Lands only.

**Architecture:** `Card` gains `mana_cost`, `cmc` and `produced_mana`. A new `src/fishbowl/stats/curve.py` holds:
- `colour_pips` and `land_colours`
- `curve_odds`, which returns `CurveOdds` (exact lands row + simulated lands and colours rows)
- a command `main`, shaped like the 4a–4c commands

**Tech Stack:** Python 3.12, standard library only (`re`, `random`, `dataclasses`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-commander-on-curve-design.md`

## Global Constraints

- Python 3.12+, `uv run`. **No new dependencies.**
- M = `int(cmc)`. By turn M, 7 + M cards are seen (multiplayer).
- **Lands row:** at least M lands among the seen cards. Exact: `exact_at_least(M, L, N, 7 + M)`. Also simulated.
- **Colours row** (simulated only): the lands row holds, and for each colour c in the pips, the number of seen lands whose `produced_mana` contains c is at least pips[c]. Each colour is checked on its own.
- **Pips:** count only `{W}`, `{U}`, `{B}`, `{R}`, `{G}`. Hybrid, Phyrexian, generic and X symbols add nothing.
- **Land colours:** one entry per land copy (`is_land`), commanders excluded, as in `library_counts`. An empty `produced_mana` (fetch lands) is a land with no colour.
- 100,000 trials, seed 42, with a fresh `random.Random(seed)` per commander. Tolerance 0.01 on the lands row. Import `HAND_SIZE`, `TRIALS`, `SEED`, `exact_at_least`, `is_land`, `library_counts` from `fishbowl.stats.lands`.
- Tests write only to `tmp_path`. The real `data/cards.db` is read only in `tests/deck/test_real_decks.py`.
- Agents never run `git add`/`commit`/`push`. Ian commits after each task.
- Every touched `.py` file passes `ruff format`, `ruff check` and `~/.local/bin/basedpyright.exe --level error -p C:/Users/iwsch/.claude/hooks/basedpyright-default.json <file>`.

## Review Focus

1. **A commander with no cost found** (lookup misses, `cmc` is None, or M = 0): print "{name}: no mana cost found; skipped". Don't crash. (Task 2 `test_skips_commander_without_cost`.)
2. **A commander too expensive for the library** (7 + M > N): print the "Can't be cast on curve…" line and run no simulation. (Task 2 `test_too_big_to_cast`.)
3. **Hybrid or missing mana cost:** `colour_pips("{1}{G/W}") == {}` and `colour_pips(None) == {}`. (Task 1 `test_colour_pips`.)
4. **Fetch lands with `produced_mana == ""`:** they count toward the lands row but never the colours row. (Task 1 `test_colourless_lands_never_sources`.)
5. **Two commanders:** one block each, each with its own cost. (Task 2 `test_two_commanders_two_blocks`.)

---

### Task 1: Card fields, pips and the odds

**Files:**
- Modify: `src/fishbowl/deck/lookup.py` (`Card`, `_FIELDS`, `find`), `tests/deck/test_lookup.py` (its `Card(...)` equality)
- Create: `src/fishbowl/stats/curve.py`
- Test: `tests/stats/test_curve_odds.py`; add `test_real_curve` to `tests/deck/test_real_decks.py`

**Interfaces:**
- Produces:
  - `Card` gets three new fields, added at the end with defaults, so existing positional `Card(...)` calls still work: `mana_cost: str | None = None`, `cmc: float | None = None`, `produced_mana: str = ""`.
    - `_FIELDS` also selects `c.mana_cost, c.cmc, c.produced_mana`.
    - `find` currently does `*fields, game_changer = row`, which relies on `is_game_changer` being the last column. Change that unpacking so `is_game_changer` still becomes a `bool` and the three new columns land in their fields.
  - `COLOUR_NAMES = {"W": "white", "U": "blue", "B": "black", "R": "red", "G": "green"}` (in `curve.py`)
  - `colour_pips(mana_cost: str | None) -> dict[str, int]`: keys only for colours present, in WUBRG order.
  - `land_colours(deck: ParsedDeck, lookup: CardLookup) -> list[str]`: the `produced_mana` of each land copy in the library.
  - `@dataclass(frozen=True) class CurveOdds`:
    - `mana_value: int`
    - `pips: dict[str, int]`
    - `lands_exact: float`
    - `lands_simulated: float`
    - `colours_simulated: float`
  - `curve_odds(mana_value: int, pips: dict[str, int], land_colours: list[str], library: int, trials: int = TRIALS, seed: int = SEED) -> CurveOdds`. L = `len(land_colours)`. It raises `ValueError` if `mana_value < 1`, if `HAND_SIZE + mana_value > library`, if L > library, or if `trials < 1`. Validation comes before the loop.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/deck/test_lookup.py`, update the existing Sol Ring equality to include `mana_cost="{1}"`, `cmc=1.0` and `produced_mana="C"`.
  - In `tests/stats/test_curve_odds.py`:
    - `test_colour_pips`:
      - `"{2}{R}{R}"` → `{"R": 2}`
      - `"{3}{G}"` → `{"G": 1}`
      - `"{10}{G}{G}"` → `{"G": 2}`
      - `"{1}{G/W}"` → `{}`
      - `"{X}{U}{B}"` → `{"U": 1, "B": 1}`, with keys in that order
      - `None` → `{}`
      - `""` → `{}`
    - `test_lands_row_exact`: `curve_odds(4, {"G": 1}, ["G"] * 33, 99, trials=100).lands_exact == pytest.approx(exact_at_least(4, 33, 99, 11))`, and its `round(..., 3) == 0.533`.
    - `test_simulated_matches_exact`: parametrized over (4, 33) and (12, 39) in 99, with the default trials and `["G"] * lands`. Assert `abs(lands_simulated - lands_exact) < 0.01`.
    - `test_colours_never_above_lands`: with `["G"] * 20 + ["R"] * 13`, pips `{"G": 2}`, M = 4, check `colours_simulated <= lands_simulated`.
    - `test_all_sources_equal_lands`: with `["G"] * 33` and pips `{"G": 1}`, `colours_simulated == lands_simulated`.
    - `test_colourless_lands_never_sources`: with `[""] * 33` and pips `{"G": 1}`, check `colours_simulated == 0.0` and `lands_simulated > 0`.
    - `test_same_seed_same_numbers`: seed 7 twice gives equal results; seeds 7 and 8 differ (2,000 trials).
    - `test_invalid_inputs_raise`:
      - M = 0
      - M = 5 with a library of 11
      - 100 land colours with a library of 99
      - trials = 0
    - `test_land_colours` (`card_db` fixture): the deck is `Commander: Goreclaw`, `1 Goreclaw…`, `10 Forest`, `1 Command Tower`, `5 Sol Ring`. The result is a list with 10 `"G"` and 1 `""`, compared order-insensitively. The `COMMAND_TOWER` fixture in `tests/conftest.py` has no `produced_mana`, so the DB stores `""`. That doubles as the fetch-land case.
  - In `tests/deck/test_real_decks.py`, add `test_real_curve`. For each of Ian's decks:
    - each commander's `(int(card.cmc), colour_pips(card.mana_cost))`:
      - Goreclaw `(4, {"G": 1})`
      - Krenko `(4, {"R": 2})`
      - Ghalta `(12, {"G": 2})`
    - `len(land_colours(deck, lookup)) == library_counts(deck, lookup)[0]`

- [ ] **Step 2: Run them and make sure they fail:** `uv run pytest tests/stats/test_curve_odds.py tests/deck/test_lookup.py -v`. Expected: an import error, plus the lookup equality failing.

- [ ] **Step 3: Implement** the `Card`/`lookup` change and `curve.py`. Give `curve.py` a module docstring with the run command `uv run python -m fishbowl.stats.curve <decklist.txt>`.
  - `colour_pips` uses a module-level compiled regex for a single `{W}`…`{G}` symbol.
  - The simulation number trick: cards `0..L−1` are the lands, and card i's colours are `land_colours[i]`. Sample `HAND_SIZE + M` cards per trial.

- [ ] **Step 4: Run them and make sure they pass:** the same command, then `uv run pytest`. Everything passes.

- [ ] **Step 5: Suggested commit (Ian runs it)**

```bash
git add src/fishbowl/deck/lookup.py tests/deck/test_lookup.py src/fishbowl/stats/curve.py tests/stats/test_curve_odds.py tests/deck/test_real_decks.py docs/superpowers/specs/2026-10-23-commander-on-curve-design.md docs/superpowers/plans/2026-10-23-commander-on-curve.md
git commit -m "Add mana cost and produced mana to cards; commander-on-curve odds (Stage 4d)"
```

---

### Task 2: The curve command and roadmap

**Files:**
- Modify: `src/fishbowl/stats/curve.py`, `docs/ROADMAP.md`
- Test: `tests/stats/test_curve_main.py`

**Interfaces:**
- Consumes:
  - Task 1's `colour_pips`, `land_colours`, `curve_odds`, `CurveOdds` and `COLOUR_NAMES`
  - `library_counts` and `SEED` from `lands.py`
  - `find_deck_file`, `read_deck`, `DEFAULT_DB`, `CardLookup`
- Produces: `main(argv: list[str] | None = None, db_path: Path = DEFAULT_DB, read: Callable[[str], str] = input, write: Callable[[str], object] = print, trials: int = TRIALS) -> int`, plus an `if __name__ == "__main__": sys.exit(main())` block.

Output, in order:
1. Header: `f"{who}: {lands} lands in a {library}-card library ({trials:,} simulated hands, seed {SEED}; multiplayer: everyone draws on turn 1)"`. The no-commander note and the unreadable-lines note follow, with `lands.main`'s wording.
2. `"Lands only; ignores dorks, rocks and cost reducers."`
3. With no commanders: `"No commander chosen: nothing to cast on curve."`, then return 0.
4. Per commander, after a blank line, one of these:
   - `f"{name}: no mana cost found; skipped"` if the lookup misses, `cmc` is None, or M < 1.
   - `f"{name} {mana_cost}: mana value {M}, cast on turn {M}"`, then `f"  Can't be cast on curve from lands in a {library}-card library."` if `HAND_SIZE + M > library`.
   - Otherwise, the title line, then:
     - `f"{'':<34}{'exact':>7}{'simulated':>11}"`
     - `f"{label:<34}{exact:>7.1%}{sim:>11.1%}"` with label `f"  {M}+ lands by turn {M}"`
     - when there are pips, a colours row: `f"{label:<34}{'':>7}{sim:>11.1%}"`. The label is `"  ...and "` followed by the pip parts joined with `" and "`. Each part is `f"{n}+ {COLOUR_NAMES[c]} source"`, with an `s` added when n > 1.
     - `"  Note: cost reducers aren't modelled."` when M ≥ 8
     - `"  Note: approximate for multi-colour costs."` when there are 2 or more pip colours
5. Return 0.

Usage: `"Usage: uv run python -m fishbowl.stats.curve <decklist.txt>"`.

Roadmap:
- Stage 4: add "commander on curve done in Stage 4d: `uv run python -m fishbowl.stats.curve <decklist>`".
- Change the 4d "next" note to "Stage 4e (next): Matplotlib charts".

Stage 4 stays 🔄.

- [ ] **Step 1: Write the failing tests** in `tests/stats/test_curve_main.py`. Copy the `run` helper from `tests/stats/test_lands_main.py`. The tests:
  - `test_prints_commander_block`: deck `Commander: Goreclaw`, `1 Goreclaw`, `33 Forest`, `66 Sol Ring`. That's 1 + 33 + 66 = 100 cards, so a 99-card library. Check:
    - returns 0
    - `shown[0]` starts with `"Goreclaw, Terror of Qal Sisma: 33 lands in a 99-card library (2,000 simulated hands"`
    - the lands-only line is shown
    - `"Goreclaw, Terror of Qal Sisma {3}{G}: mana value 4, cast on turn 4"` is shown
    - one line starts with `"  4+ lands by turn 4"` and contains `"53.3%"`
    - one line starts with `"  ...and 1+ green source"`
  - `test_main_without_commander`: `33 Forest`, `66 Sol Ring`, answering `[""]`. Returns 0 and shows `"No commander chosen: nothing to cast on curve."`.
  - `test_main_notes_unreadable_lines`: as in `test_lands_main.py`.
  - `test_too_big_to_cast`: `Commander: Goreclaw`, `1 Goreclaw`, `5 Forest`, `4 Sol Ring` (a 9-card library). Shows `"  Can't be cast on curve from lands in a 9-card library."` and returns 0.
  - `test_skips_commander_without_cost`: call `main` with `monkeypatch`, patching `curve.CardLookup.find` so that it returns the real card with `cmc=None` (use `dataclasses.replace`) when the commander is looked up. Shows `"Goreclaw, Terror of Qal Sisma: no mana cost found; skipped"`.
  - `test_two_commanders_two_blocks`: reuse the deck from `tests/stats/test_library_counts.py::test_two_commanders_both_leave_the_library`, which is `Commander`, `1 Goreclaw…`, `1 Krenko, Mob Boss`, `Deck`, `10 Forest`, `2 Sol Ring`. The library has 12 cards, so both commanders (M = 4, 11 cards seen) get full blocks. Assert that two "mana value 4" title lines are shown.
  - `test_usage_and_missing_file`: as in `test_groups_main.py`.
  - `test_notes_for_big_and_multicolour`: test `main`'s note logic through a helper or with monkeypatched costs. Patch Goreclaw's `mana_cost` to `"{6}{G}{U}"` and `cmc` to `8.0` with a 99-card library. Expect both notes.

- [ ] **Step 2: Run them and make sure they fail:** `uv run pytest tests/stats/test_curve_main.py -v`. Expected: `ImportError`.

- [ ] **Step 3: Implement `main`** following `groups.main` step for step, and update the roadmap.

- [ ] **Step 4: Run everything:** `uv run pytest`, then the command on `tests/decks/goreclaw.txt`, `krenko.txt` and `ghalta.txt`. Paste the outputs into the report. Goreclaw and Krenko show about 53.3%. Ghalta shows 1.9% plus the cost-reducer note.

- [ ] **Step 5: Suggested commit (Ian runs it)**

```bash
git add src/fishbowl/stats/curve.py tests/stats/test_curve_main.py docs/ROADMAP.md
git commit -m "Add commander on curve command (Stage 4d)"
```
