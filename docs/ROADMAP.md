# Fishbowl Roadmap

Fishbowl is a Commander deck-tuning and goldfish-coaching tool. It builds on the [Argentum Engine](https://github.com/wingedsheep/argentum-engine) for Phase 2 instead of competing with it: Argentum knows the rules of Magic; Fishbowl answers "how does my deck perform, and what should I play next?"

Status key: ✅ done · 🔄 in progress · ⬜ not started

Update the status marks as stages finish.

## Phase 1: Goldfish (Python)

### ✅ Stage 0: Setup
The GitHub repo exists with an Apache-2.0 `LICENSE` and nothing else.

Placed by hand from the setup kit (see the kit's `SETUP.md`), before Claude Code starts:
- ✅ Clone the repo to `C:\Projects\fishbowl`.
- ✅ Add `.gitignore`, `CLAUDE.md` and `docs/ROADMAP.md`; first commit and push.
- ✅ Add `CLAUDE.local.md` (gitignored, never pushed).

Built with Claude Code, one slice at a time:
- ✅ `README.md` with a one-paragraph description and the Fan Content notice.
- ✅ Initialize the uv project (`uv init`), pinned to Python 3.12+.
- ✅ Create `src/fishbowl/` and `tests/` folders, with one passing placeholder test so `uv run pytest` works.
- ✅ A `hello.py` (`src/fishbowl/hello.py`, run with `uv run python -m fishbowl.hello <file>`) that reads a text decklist and prints how many cards it has. Sample deck in `examples/`.
- ✅ Start `docs/LEARNING_LOG.md` (gitignored, local only) with its first entry.

Concepts: Git basics, `.gitignore`, virtual environments, running scripts and tests from the terminal.
**Done when:** `hello.py` prints 100 for a sample deck, `uv run pytest` passes, everything except the personal files is pushed to GitHub, and `git status` shows the personal files are ignored.

### 🔄 Stage 1: Card data
- ⬜ Part 1: Download Scryfall's `oracle_cards` bulk data and explore it in Pandas; flatten commander legality into a simple yes/no column.
- ⬜ Part 2: Build a SQLite database of the useful columns.
- ⬜ Part 3: A download/refresh script so anyone can rebuild `data/` from Scryfall with one command.

Suggested `cards` table: `oracle_id` (primary key), `name`, `mana_cost`, `cmc`, `type_line`, `oracle_text`, `colors`, `color_identity`, `produced_mana`, `legal_commander`, `is_game_changer`, `card_faces` (JSON text for double-faced cards).

**Done when:** a SQL query returns Sol Ring's mana cost and color identity, and the database rebuilds from a single command.

### ⬜ Stage 2: Decklist parser
Turn pasted text into a list of cards. Formats: plain (`1 Sol Ring`, `1x Sol Ring`), Moxfield (`1 Sol Ring (CMM) 400 *F*` with section headers like `Commander`), Archidekt (`1x Sol Ring (cmm) 400 [Ramp]`). Look up names in the SQLite database; report unknown lines instead of crashing.
Concepts: functions, strings, regular expressions, error handling, first pytest tests.
**Done when:** Ian's decks (Goreclaw, Krenko, Tramplesaurus Rex) and bad test lines parse correctly.

### ⬜ Stage 3: Deck validator
Check: exactly 100 cards including commander(s); singleton by card name (basic lands and "any number of cards named..." cards exempt); every card inside the commander's color identity; banned cards; commander eligibility; partner/Background pairings later.
Concepts: sets, dictionaries, dataclasses, modules.
**Done when:** valid decks pass and a deliberately broken deck fails with clear messages.

### ⬜ Stage 4: Opening-hand stats
Simulate thousands of shuffles and opening hands; compare with exact math (`scipy.stats.hypergeom`). Report P(2–5 lands in opening hand), P(land drop each turn 1–5), P(commander castable on curve). Mulligan rules: London mulligan, first mulligan free in multiplayer (configurable).
Concepts: randomness, loops at scale, simulation vs exact probability, Matplotlib charts.
**Done when:** simulated and exact land probabilities agree within 1%.

### ⬜ Stage 5: Command-line app
`fishbowl analyze mydeck.txt` using `typer`. README with install instructions.
**Done when:** someone else can install and run it from the repo.

### ⬜ Stage 6: Goldfish turns
Simulate turns: draw, play a land, tap mana, cast spells, commander tax (+2 per previous cast from the command zone). Simplified card behaviors: lands, mana rocks, mana dorks, ramp spells, card draw, "generic spell". Unknown cards count as generic spells. Seeded randomness so any game can be replayed.
Concepts: classes, game state as data, copying state.
**Done when:** a hand plays out turn by turn and the log reads correctly.

### ⬜ Stage 7: Best 5-turn line
Search every sensible play order and pick the best for a chosen goal (most mana on turn 5, earliest commander cast). The search must not "know" future draws: resample the unseen library at each draw. Add "card impact": how much each card helps or hurts the result.
Concepts: recursion, depth-first search, memoization, profiling.
**Done when:** it prints an optimal line for a sample hand, and its speed has been measured.

### ⬜ Stage 7.5: Simple UI
A Streamlit page: paste a deck, see stats and the best line.
**Done when:** the whole Stage 2–7 flow works in a browser window.

## Phase 1, later: Faster engine and desktop app

### ⬜ Stage 8: Rust port
Rewrite the Stage 6–7 engine in Rust, called from Python with PyO3. The Python tests become the Rust engine's tests.

### ⬜ Stage 9: Desktop app
Tauri + React + TypeScript desktop app replacing Streamlit.

### ⬜ Stage 10: Smarter AI
Monte Carlo Tree Search for goldfish lines past turn 5; later, PyTorch.

## Phase 2: Opponents

### ⬜ Stage 11: Argentum integration
Confirm Argentum's license with its maintainer. Audit its Commander support (command zone, commander tax, commander damage, partners); contribute fixes upstream; then connect Fishbowl's AI through Argentum's gym API (bound to localhost only).

## Notes
- Commander format rules change: the banned list and Game Changers list are managed by Wizards of the Coast, with bracket guidance still in beta. Load them as data.
- Forge (GPL) may be used later only as a separate program for benchmarking; its code never enters this repo.
