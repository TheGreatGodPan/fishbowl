# Command-line app design (Stage 5)

Date: 2026-10-26 · Status: design approved in conversation; spec awaiting Ian's review

## Intent

Make Fishbowl one installable command, `fishbowl`, instead of a set of `python -m` modules, and write README instructions good enough that someone else can install and run it.

**Done when:** a fresh clone in an empty folder, following only the README, gets from `git clone` to a printed `fishbowl analyze` report for a sample deck, and `docs/ROADMAP.md` marks Stage 5 ✅.

## Goals

- `fishbowl` subcommands:
  - `refresh`
  - `check DECK`
  - `lands DECK`, `mulligan DECK`, `groups DECK`, `curve DECK`
  - `charts DECK`
  - `analyze DECK [--charts]`
- `analyze` reads the deck once (one commander question at most) and prints every report under section headings.
- A README "Install and run" section.

## Non-goals

- New options beyond `--charts`, such as the free-mulligan toggle, trials or seed. These can come later.
- Publishing to PyPI. Installation is from the repo.
- Removing the `python -m fishbowl...` entry points. They keep working.
- Removing `hello.py` or the `fishbowl.main` placeholder in `__init__.py`. They're left alone. *(My call: no churn.)*

## Decisions

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | Library | **typer**, added with `uv add typer`. | It turns type-hinted functions into commands with `--help` and argument checks. The roadmap names it. |
| 2 | Where | A new `src/fishbowl/cli.py` with `app = typer.Typer(...)`. In `pyproject.toml`, `[project.scripts]` changes to `fishbowl = "fishbowl.cli:app"`. | The script entry already exists; it just points at a placeholder. |
| 3 | Simple subcommands | `check`, `lands`, `mulligan`, `groups`, `curve` and `charts` call the existing `main(argv=[str(deck)])` of `deck.parser` and each stats module, then exit with its return code (`raise typer.Exit(code)`). `refresh` calls `data.refresh.refresh()`. | It reuses everything, with no duplicated logic. |
| 4 | Read once for analyze | Each stats module and `deck.parser` gets a `report(deck, lookup, write, ...) -> int` that prints its section from an already-read deck. It's the body of today's `main` after `read_deck`. Each `main` becomes find file → open lookup → read deck → `return report(...)`. Existing tests pass unchanged. | Otherwise `analyze` would ask for the commander up to six times. |
| 5 | analyze output | It checks the file and database once, opens one lookup, and reads the deck once. Then it prints these sections in order, each preceded by a blank line and a heading: `== Deck check ==`, `== Land odds ==`, `== Mulligans ==`, `== Card groups ==`, `== Commander on curve ==`, and with `--charts` also `== Charts ==`. Every section runs even if an earlier one returns 1. The exit code is 0 if every section returned 0, and 1 otherwise. | You see the whole picture even for an illegal or odd deck. *(My call: each report keeps its own header line, which repeats the deck summary. That's acceptable for now.)* |
| 6 | Refresh hint | The missing-database message in `find_deck_file` and the hint in `data/database.py` now say `uv run fishbowl refresh`. The tests that check the old text are updated. | It points to the new command. |
| 7 | README | A new "Install and run" section after the intro. It covers: requirements (Git, Python 3.12+ via uv, and uv itself with a link to its install page); `git clone https://github.com/TheGreatGodPan/fishbowl.git`; `cd fishbowl`; `uv sync`; `uv run fishbowl refresh` (a one-time download of about 100 MB of Scryfall data, noted); `uv run fishbowl analyze examples/sample_deck.txt`. The sample has no `Commander:` line, so Fishbowl asks which card is the commander (answer 2, Goreclaw); the README says so and gives the tip "add `Commander: <name>` as the first line to skip the question". and a table of the other commands. `uv run fishbowl --help` lists them. Windows and macOS/Linux commands are identical; note this. | uv installs the right Python itself, so the steps are short. |
| 8 | Charts location | `charts` and `analyze --charts` write to `charts/` in the current folder, as 4e does. | |

## Testing

- CLI tests use `typer.testing.CliRunner` against `app`. They cover:
  - `--help` lists every subcommand.
  - Each simple subcommand runs on a `card_db` deck and exits with the wrapped `main`'s code. They're called with `db_path` patched: the CLI passes a module-level `DEFAULT_DB`, and the tests monkeypatch it or the commands accept a hidden `--db` option. *(Builder's choice; it must not touch the real `data/`.)*
  - `analyze` prints all five headings in order and asks for the commander only once (a deck with no commander line, answered once through the runner's `input`).
  - `analyze --charts` adds the Charts heading and writes PNGs to a temporary folder.
- Each module's `report` gets one direct test that passes a parsed deck and checks that the first line matches what `main` printed.
- **The fresh-clone check, run by the builder:**
  1. `git clone` the local repo (not GitHub, so it includes unpushed commits) into a new folder under the scratchpad.
  2. Follow the README commands exactly. `refresh` may be replaced by copying `data/` from the working repo to save a 100 MB download, and the report says so.
  3. Run `analyze` on `examples/sample_deck.txt` and paste the output.

## Left to the builder

- Help text wording for each command.
- How the tests point the CLI at the test database.
