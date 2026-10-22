# Mulligans Implementation Plan (Stage 4b)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show how often a deck keeps on each mulligan attempt (exact vs simulated), the average kept hand size, and how mulligans change the land-drop odds for turns 1–5.

**Architecture:** A new `src/fishbowl/stats/mulligan.py` that builds on `lands.py`. It contains:
- pure helpers: `hand_sizes`, `keeps`, `lands_after_bottoming`, `keep_rates`
- a simulation, `mulligan_odds`, which returns a `MulliganOdds` dataclass
- a command, `main`, shaped like `lands.main`

It reuses `OddsRow`, `exact_exactly`, `exact_at_least`, `library_counts` and the constants from `lands.py`, and `find_deck_file`/`read_deck` from `deck/parser.py`.

**Tech Stack:** Python 3.12, standard library only (`random`, `dataclasses`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-21-mulligans-design.md`

## Global Constraints

- Python 3.12+, run through `uv run`. **No new dependencies.**
- Keep rule: keep if the 7 cards drawn contain 2–5 lands. London mulligan: always draw 7, then bottom `7 − hand size` cards. Always keep at 5.
- Hand sizes per attempt: `(7, 7, 6, 5)` with `free_first=True` (default), `(7, 6, 5)` with `free_first=False`.
- Bottoming, one card at a time: if the hand holds more than 3 lands, bottom a land; otherwise bottom a spell.
- Multiplayer draws only: by turn t, t cards have been drawn after the kept hand.
- Import `HAND_SIZE`, `TRIALS` (100_000), `SEED` (42), `LAND_DROP_TURNS` and `OPENING_LANDS` from `lands.py`. Don't redefine them. Agreement tolerance is 0.01 absolute.
- Tests write only to `tmp_path`, using the existing `card_db` fixture from `tests/conftest.py`.
- Agents never run `git add`/`commit`/`push`.
- Every touched `.py` file passes `ruff format`, `ruff check` and `~/.local/bin/basedpyright.exe --level error -p C:/Users/iwsch/.claude/hooks/basedpyright-default.json <file>`.

## Review Focus

1. **A deck with 0 lands:** every hand is a forced keep at 5. The exact and simulated values must both be 100% for the forced row, with an average hand size of 5.00 and no crash. (Task 2 `test_no_lands_all_forced`.)
2. **A deck that is all lands** (lands == library): the same, all forced keeps. Bottoming must remove lands, never a spell the hand doesn't have. (Task 1 `test_bottoming_examples` (7, 2) → 5; Task 2 `test_all_lands_all_forced`.)
3. **A tiny deck** (library < 12): the command prints "Only N cards in the library; at least 12 are needed to see 5 turns." and returns 1, with no traceback. (Task 3 `test_tiny_deck_message`.)
4. **No commander chosen:** the odds still print, using the whole deck, with the 4a note. (Task 3 `test_main_without_commander_uses_whole_deck`.)
5. **Unreadable lines:** the odds still print, with the 4a note. (Task 3 `test_main_notes_unreadable_lines`.)

---

### Task 1: Keep rule, bottoming and exact keep rates

**Files:**
- Create: `src/fishbowl/stats/mulligan.py`
- Test: `tests/stats/test_mulligan_math.py`

**Interfaces:**
- Consumes: `HAND_SIZE`, `OPENING_LANDS` from `fishbowl.stats.lands`.
- Produces:
  - `hand_sizes(free_first: bool = True) -> tuple[int, ...]`: `(7, 7, 6, 5)` or `(7, 6, 5)`.
  - `keeps(lands_in_seven: int) -> bool`
  - `lands_after_bottoming(lands_in_seven: int, to_bottom: int) -> int`
  - `keep_rates(p: float, free_first: bool = True) -> list[float]`: one rate per attempt. Attempt i (counting from 1, but not the last) is `(1−p)**(i−1) * p`; the last attempt is `(1−p)**(attempts−1)`.

- [ ] **Step 1: Write the failing tests** in `tests/stats/test_mulligan_math.py`:

```python
import pytest

from fishbowl.stats.mulligan import hand_sizes, keep_rates, keeps, lands_after_bottoming


def test_hand_sizes():
    assert hand_sizes() == (7, 7, 6, 5)
    assert hand_sizes(free_first=False) == (7, 6, 5)


@pytest.mark.parametrize(
    ("lands", "expected"),
    [(0, False), (1, False), (2, True), (3, True), (5, True), (6, False), (7, False)],
)
def test_keeps(lands, expected):
    assert keeps(lands) is expected


@pytest.mark.parametrize(
    ("lands", "to_bottom", "expected"),
    [(7, 2, 5), (6, 2, 4), (4, 2, 3), (2, 2, 2), (5, 0, 5), (0, 2, 0), (5, 1, 4)],
)
def test_bottoming_examples(lands, to_bottom, expected):
    assert lands_after_bottoming(lands, to_bottom) == expected


@pytest.mark.parametrize("lands", range(8))
@pytest.mark.parametrize("to_bottom", (0, 1, 2))
def test_bottoming_never_exceeds_hand(lands, to_bottom):
    assert lands_after_bottoming(lands, to_bottom) <= 7 - to_bottom


def test_keep_rates_hand_checked():
    assert keep_rates(0.5) == pytest.approx([0.5, 0.25, 0.125, 0.125])
    assert keep_rates(0.5, free_first=False) == pytest.approx([0.5, 0.25, 0.25])


@pytest.mark.parametrize("free_first", (True, False))
def test_keep_rates_edges_and_sum(free_first):
    attempts = len(hand_sizes(free_first))
    assert keep_rates(1.0, free_first) == pytest.approx([1.0] + [0.0] * (attempts - 1))
    assert keep_rates(0.0, free_first) == pytest.approx([0.0] * (attempts - 1) + [1.0])
    for p in (0.1, 0.741, 0.9):
        assert sum(keep_rates(p, free_first)) == pytest.approx(1.0)
```

- [ ] **Step 2: Run them and make sure they fail**

Run: `uv run pytest tests/stats/test_mulligan_math.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fishbowl.stats.mulligan'`.

- [ ] **Step 3: Implement the four functions** in `src/fishbowl/stats/mulligan.py`. Give it a module docstring like `lands.py`'s, with the run command `uv run python -m fishbowl.stats.mulligan <decklist.txt>`. `keeps` uses the range `OPENING_LANDS[0]..OPENING_LANDS[-1]`. `lands_after_bottoming` loops once per card bottomed, applying the "more than 3 lands" rule.

- [ ] **Step 4: Run them and make sure they pass**

Run: `uv run pytest tests/stats/test_mulligan_math.py -v`
Expected: all PASS.

- [ ] **Step 5: Suggested commit (Ian runs it)**

```bash
git add src/fishbowl/stats/mulligan.py tests/stats/test_mulligan_math.py
git commit -m "Add mulligan keep rule, bottoming and exact keep rates (Stage 4b)"
```

---

### Task 2: The mulligan simulation

**Files:**
- Modify: `src/fishbowl/stats/mulligan.py`
- Test: `tests/stats/test_mulligan_odds.py`

**Interfaces:**
- Consumes: Task 1's functions; `OddsRow`, `exact_exactly`, `exact_at_least`, `TRIALS`, `SEED`, `LAND_DROP_TURNS` from `fishbowl.stats.lands`.
- Produces:
  - `@dataclass(frozen=True) class MulliganOdds` with fields:
    - `keep_rows: list[OddsRow]`
    - `hand_size: OddsRow`
    - `drop_rows: list[OddsRow]`. In the drop rows, `exact` is the no-mulligan value and `simulated` is the with-mulligans value.
  - `mulligan_odds(lands: int, library: int, trials: int = TRIALS, seed: int = SEED, free_first: bool = True) -> MulliganOdds`
  - Keep-row labels, in order: `"Keep 7 (first hand)"`, `"Keep 7 (free mulligan)"`, `"Keep 6"`, `"Keep 5 (forced)"`. With `free_first=False`: `"Keep 7"`, `"Keep 6"`, `"Keep 5 (forced)"`.
  - Hand-size label: `"Average hand size"`. Drop labels: `"Land drop through turn {t}"`, as in 4a.

- [ ] **Step 1: Write the failing tests** in `tests/stats/test_mulligan_odds.py`:

```python
import pytest

from fishbowl.stats.lands import exact_at_least
from fishbowl.stats.mulligan import mulligan_odds


@pytest.mark.parametrize("lands", (33, 39))
@pytest.mark.parametrize("free_first", (True, False))
def test_simulated_matches_exact(lands, free_first):
    odds = mulligan_odds(lands, 99, free_first=free_first)
    for row in [*odds.keep_rows, odds.hand_size]:
        assert abs(row.simulated - row.exact) < 0.01, row.label


def test_labels():
    odds = mulligan_odds(33, 99, trials=100)
    assert [r.label for r in odds.keep_rows] == [
        "Keep 7 (first hand)", "Keep 7 (free mulligan)", "Keep 6", "Keep 5 (forced)"
    ]
    assert odds.hand_size.label == "Average hand size"
    assert [r.label for r in odds.drop_rows] == [
        f"Land drop through turn {t}" for t in range(1, 6)
    ]
    no_free = mulligan_odds(33, 99, trials=100, free_first=False)
    assert [r.label for r in no_free.keep_rows] == ["Keep 7", "Keep 6", "Keep 5 (forced)"]


def test_exact_values_for_33_of_99():
    odds = mulligan_odds(33, 99, trials=100)
    assert odds.keep_rows[0].exact == pytest.approx(0.741, abs=0.001)
    assert odds.drop_rows[2].exact == pytest.approx(exact_at_least(3, 33, 99, 10))


def test_mulligans_help_turn_two():
    odds = mulligan_odds(33, 99, trials=20_000)
    assert odds.drop_rows[1].simulated > odds.drop_rows[1].exact


def test_same_seed_same_numbers():
    assert mulligan_odds(33, 99, trials=2000, seed=7) == mulligan_odds(33, 99, trials=2000, seed=7)
    assert mulligan_odds(33, 99, trials=2000, seed=7) != mulligan_odds(33, 99, trials=2000, seed=8)


def test_no_lands_all_forced():
    odds = mulligan_odds(0, 99, trials=500)
    forced = odds.keep_rows[-1]
    assert forced.exact == pytest.approx(1.0) and forced.simulated == 1.0
    assert odds.hand_size.exact == pytest.approx(5.0) and odds.hand_size.simulated == 5.0


def test_all_lands_all_forced():
    odds = mulligan_odds(20, 20, trials=500)
    assert odds.keep_rows[-1].simulated == 1.0
    assert all(row.simulated == 1.0 for row in odds.drop_rows)


@pytest.mark.parametrize(
    ("lands", "library", "trials"), [(5, 11, 100), (-1, 99, 100), (100, 99, 100), (33, 99, 0)]
)
def test_invalid_inputs_raise(lands, library, trials):
    with pytest.raises(ValueError):
        mulligan_odds(lands, library, trials=trials)
```

- [ ] **Step 2: Run them and make sure they fail**

Run: `uv run pytest tests/stats/test_mulligan_odds.py -v`
Expected: FAIL with `ImportError: cannot import name 'mulligan_odds'`.

- [ ] **Step 3: Implement `MulliganOdds` and `mulligan_odds`.** Validate the inputs first, before the slow loop, the same way `land_odds` does (library ≥ 12, lands in 0..library, trials ≥ 1). The exact side:
  - p = the sum of `exact_exactly(k, lands, library, 7)` for k in 2..5
  - the keep rows come from `keep_rates(p, free_first)`
  - the hand size is Σ size × rate
  - the drop rows' `exact` = `exact_at_least(t, lands, library, 7 + t)`

The simulation:

```
rng = random.Random(seed)
for each trial:
    for attempt, size in enumerate(hand_sizes(free_first)):
        top = rng.sample(range(library), 12)          # fresh shuffle each attempt
        in_seven = lands among top[:7]
        if keeps(in_seven) or this is the last attempt: break
    count the kept attempt and add its size
    in_hand = lands_after_bottoming(in_seven, 7 - size)
    for each turn t: hit if in_hand + lands among top[7:7 + t] >= t
```

- [ ] **Step 4: Run them and make sure they pass**, then run the full suite.

Run: `uv run pytest tests/stats/test_mulligan_odds.py -v` → all PASS. Then `uv run pytest` → all PASS.

- [ ] **Step 5: Suggested commit (Ian runs it)**

```bash
git add src/fishbowl/stats/mulligan.py tests/stats/test_mulligan_odds.py
git commit -m "Add mulligan simulation with exact keep rates (Stage 4b)"
```

---

### Task 3: The mulligan command and roadmap

**Files:**
- Modify: `src/fishbowl/stats/mulligan.py`, `docs/ROADMAP.md` (Stage 4 entry: note that 4b is done with its run command; Stage 4 stays 🔄 until 4c)
- Test: `tests/stats/test_mulligan_main.py`

**Interfaces:**
- Consumes: `mulligan_odds` and `MulliganOdds` (Task 2); `library_counts`, `SEED` and `LAND_DROP_TURNS` from `lands.py`; `find_deck_file`, `read_deck` from `fishbowl.deck.parser`; `DEFAULT_DB`, `CardLookup` from `fishbowl.deck.lookup`.
- Produces: `main(argv: list[str] | None = None, db_path: Path = DEFAULT_DB, read: Callable[[str], str] = input, write: Callable[[str], object] = print, trials: int = TRIALS) -> int`, plus an `if __name__ == "__main__": sys.exit(main())` block.

Output, in order:
1. `f"{who}: {lands} lands in a {library}-card library ({trials:,} simulated games, seed {SEED}; multiplayer: everyone draws on turn 1)"`
2. `"Mulligans: free first mulligan; keep 2-5 lands; always keep at 5"`
3. The same no-commander and unreadable-lines notes as `lands.main`, with the same wording.
4. A blank line, then the keep table:
   - header `f"{'Keep rates':<26}{'exact':>8}{'simulated':>11}"`
   - one row per keep row, `f"{label:<26}{exact:>8.1%}{simulated:>11.1%}"`
   - the hand-size row, `f"{label:<26}{exact:>8.2f}{simulated:>11.2f}"`
5. A blank line, then the land-drop table:
   - header `f"{'Land drops':<26}{'no mulligan':>13}{'with mulligans':>16}"`
   - rows `f"{label:<26}{exact:>13.1%}{simulated:>16.1%}"`

Usage text: `"Usage: uv run python -m fishbowl.stats.mulligan <decklist.txt>"`.

- [ ] **Step 1: Write the failing tests** in `tests/stats/test_mulligan_main.py`. Copy the `run` helper and the `GORECLAW` constant from `tests/stats/test_lands_main.py`, changing the import to `fishbowl.stats.mulligan`. The tests:
  - `test_prints_header_and_tables`: a deck of `Commander: Goreclaw`, `1 Goreclaw`, `33 Forest`, `66 Sol Ring`. Checks:
    - returns 0
    - `shown[0]` is the exact header with `2,000 simulated games`
    - `shown[1]` is the Mulligans line
    - exactly one line starts with `"Keep 7 (first hand)"` and contains `"74.1%"`
    - one line starts with `"Average hand size"`
    - lines starting with `"Land drop through turn "` number exactly 5
  - `test_main_without_commander_uses_whole_deck`: `33 Forest`, `66 Sol Ring`, answering `[""]`. Returns 0 and shows `"No commander chosen: using all 99 cards as the library."`.
  - `test_main_notes_unreadable_lines`: as in `test_lands_main.py`. Shows `"Note: 1 line couldn't be read; the odds use the cards that could."`.
  - `test_tiny_deck_message`: `Commander: Goreclaw`, `1 Goreclaw`, `5 Forest`, `5 Sol Ring`. Returns 1 and shows `"Only 10 cards in the library; at least 12 are needed to see 5 turns."`.
  - `test_usage_and_missing_file`: `run([])` returns 1 and shows exactly the usage text.

- [ ] **Step 2: Run them and make sure they fail**

Run: `uv run pytest tests/stats/test_mulligan_main.py -v`
Expected: FAIL with `ImportError: cannot import name 'main'`.

- [ ] **Step 3: Implement `main`**, following `lands.main` step for step. It uses the same tiny-deck check, with 12 cards needed. Update the Stage 4 entry in `docs/ROADMAP.md`.

- [ ] **Step 4: Run the tests and the real command**

Run: `uv run pytest` → all PASS.
Run: `uv run python -m fishbowl.stats.mulligan tests/decks/goreclaw.txt` → both tables print. Goreclaw has 33 lands, so the "Keep 7 (first hand)" row is 74.1% exact.

- [ ] **Step 5: Suggested commit (Ian runs it)**

```bash
git add src/fishbowl/stats/mulligan.py tests/stats/test_mulligan_main.py docs/ROADMAP.md
git commit -m "Add mulligan odds command (Stage 4b)"
```
