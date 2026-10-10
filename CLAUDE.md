# Fishbowl

Fishbowl is an open-source Commander (EDH) deck-tuning and goldfish-coaching tool for Magic: The Gathering. You paste a decklist; it validates the deck, shows mana and curve statistics, and finds the best play line for the first turns of a game played against an empty board ("goldfishing"). A later phase plays against opponent decks using the Argentum Engine.

- Repo: github.com/TheGreatGodPan/fishbowl
- License: Apache-2.0
- Plan and current stage: `docs/ROADMAP.md`. Read it at the start of every session.
- Contributors may keep personal instructions in a gitignored `CLAUDE.local.md`. When it exists, its workflow instructions take priority over the defaults below.

## How to work in this repo

- Work in small, reviewable changes: one function, file or feature at a time.
- Explain the plan before making non-trivial changes.
- Run `uv run pytest` after every change and show the result.
- Don't commit or push unless explicitly asked.
- Keep `docs/ROADMAP.md` status marks up to date as stages finish.

## Tech stack (current phase)

- Python 3.12+, managed with **uv** (`uv add`, `uv run`). Don't use pip directly.
- **pytest** for tests, in `tests/`.
- **Pandas** for exploring data; **SQLite** (standard-library `sqlite3`) as the local card database.
- Use `pathlib` for file paths; the project must run on Windows, macOS and Linux.
- Stay in Python until Stage 8 of the roadmap. Don't introduce Rust, TypeScript or other languages early.
- Add a dependency only when it's needed, and say what it is and why.

## Project layout (target)

```
fishbowl/
  src/fishbowl/      # the package: data/, deck/, sim/ as they're needed
  tests/             # pytest tests, mirroring src/
  data/              # downloaded card data, never committed
  docs/              # ROADMAP.md and other project docs
  CLAUDE.md
  README.md
  LICENSE
```

## Rules that never bend

- **No Wizards of the Coast assets in the repo.** Never commit card images, bulk card data, or the Comprehensive Rules. `data/` stays in `.gitignore`. Card data is downloaded on first run.
- **Scryfall:** use the bulk data files, not thousands of API calls. Any API call sends a descriptive `User-Agent` and `Accept` header. Card images are fetched at runtime and never altered or cropped.
- **README must show the Fan Content notice:** "Fishbowl is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards. Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC."
- **Never copy code from Forge or Manabrew** (GPL/AGPL licensed). Reading their docs for ideas is fine; copying code is not. Argentum (Kotlin) is only used in Phase 2, as a separate program.
- **Format rules are data, not code.** Banned list, "banned as companion", and the Game Changers list load from a data file or Scryfall fields so they can be updated without code changes.
- **Treat decklists as untrusted input.** Parsers handle bad lines gracefully and report them; they never crash on odd text.
- **Never commit secrets, personal paths, or anything listed in `.gitignore`.** Never use `git add -f` on an ignored file.

## Commands

```
uv run python <script>.py   # run a script
uv run pytest               # run all tests
uv add <package>            # add a dependency
```
