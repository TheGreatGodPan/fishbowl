"""The `fishbowl` command: one entry point for every tool in the project.

Run it with:  uv run fishbowl --help
"""

from pathlib import Path
from typing import Annotated

import typer

from fishbowl.data.refresh import refresh
from fishbowl.deck import parser
from fishbowl.deck.lookup import DEFAULT_DB, CardLookup
from fishbowl.stats import charts as charts_module
from fishbowl.stats import curve, groups, lands, mulligan
from fishbowl.stats.lands import TRIALS

# Module-level settings, so tests can swap them with monkeypatch
# instead of touching the real data/ and charts/ folders.
DB_PATH = DEFAULT_DB
CHARTS_DIR = Path("charts")

# typer.Typer() is the app; each @app.command() function below becomes a subcommand.
app = typer.Typer(help="Commander deck stats and goldfish coaching.")

# typer.Argument turns a parameter into a positional argument; typer converts
# the text to a Path for us. Annotated[...] holds that extra typer information.
Deck = Annotated[Path, typer.Argument(help="Path to a decklist text file.")]


def _finish(code: int) -> None:
    """Exit with the work's exit code, so shell scripts can check success."""
    # typer.Exit stops the command quietly with that code (no traceback).
    if code != 0:
        raise typer.Exit(code)


@app.command("refresh")
def refresh_command() -> None:
    """Download the latest card data and rebuild the local database."""
    _finish(refresh())


@app.command()
def check(deck: Deck) -> None:
    """Parse a decklist and check it against the Commander rules."""
    _finish(parser.main([str(deck)], DB_PATH))


@app.command("lands")
def lands_command(deck: Deck) -> None:
    """Exact and simulated land odds for the opening turns."""
    _finish(lands.main([str(deck)], DB_PATH, trials=TRIALS))


@app.command("mulligan")
def mulligan_command(deck: Deck) -> None:
    """Exact and simulated mulligan odds."""
    _finish(mulligan.main([str(deck)], DB_PATH, trials=TRIALS))


@app.command("groups")
def groups_command(deck: Deck) -> None:
    """Mana dorks and tutors in the deck, with what-if odds."""
    _finish(groups.main([str(deck)], DB_PATH, trials=TRIALS))


@app.command("curve")
def curve_command(deck: Deck) -> None:
    """Odds of casting each commander on curve."""
    _finish(curve.main([str(deck)], DB_PATH, trials=TRIALS))


@app.command("charts")
def charts_command(deck: Deck) -> None:
    """Save the land-drop and card-group charts as PNG files."""
    _finish(charts_module.main([str(deck)], DB_PATH, trials=TRIALS, out_dir=CHARTS_DIR))


@app.command()
def analyze(
    deck: Deck,
    with_charts: Annotated[
        bool, typer.Option("--charts", help="Also save the charts.")
    ] = False,
) -> None:
    """Run the deck check and every statistic in one report."""
    usage = "Usage: fishbowl analyze <decklist.txt>"
    path = parser.find_deck_file([str(deck)], DB_PATH, usage, print)
    if path is None:
        raise typer.Exit(1)
    # Read the deck once and share it, so the commander prompt (if any) appears once.
    with CardLookup(DB_PATH) as lookup:
        parsed = parser.read_deck(path, lookup, input, print)
        # Every section runs even if an earlier one fails; all must return 0.
        sections = [
            ("Deck check", lambda: parser.report(parsed, lookup, print)),
            ("Land odds", lambda: lands.report(parsed, lookup, print, TRIALS)),
            ("Mulligans", lambda: mulligan.report(parsed, lookup, print, TRIALS)),
            ("Card groups", lambda: groups.report(parsed, lookup, print, TRIALS)),
            (
                "Commander on curve",
                lambda: curve.report(parsed, lookup, print, TRIALS),
            ),
        ]
        if with_charts:
            sections.append(
                (
                    "Charts",
                    lambda: charts_module.report(
                        parsed, lookup, print, TRIALS, CHARTS_DIR, deck.stem
                    ),
                )
            )
        codes = []
        for title, run in sections:
            print(f"\n== {title} ==")
            codes.append(run())
    _finish(0 if all(code == 0 for code in codes) else 1)
