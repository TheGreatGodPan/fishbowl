"""PNG charts of the stats: land drops and card groups.

Run it with:  uv run python -m fishbowl.stats.charts <decklist.txt>
"""

import sys
from collections.abc import Callable
from pathlib import Path

import matplotlib

# Agg draws into memory and files only, with no window, so it works anywhere.
# It must be chosen before pyplot is imported.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

from fishbowl.deck.lookup import DEFAULT_DB, CardLookup
from fishbowl.deck.parser import find_deck_file, read_deck
from fishbowl.stats.groups import (
    CHECKPOINTS,
    CardGroup,
    WhatIfRow,
    find_groups,
    what_if,
)
from fishbowl.stats.lands import LAND_DROP_TURNS, TRIALS, library_counts
from fishbowl.stats.mulligan import CARDS_NEEDED, MulliganOdds, mulligan_odds

# Colours live in one place so every chart looks like part of the same family.
BACKGROUND = "#fcfcfb"
GRID = "#e1e0d9"
AXIS = "#898781"  # spines and ticks
TITLE_TEXT = "#0b0b0b"
BODY_TEXT = "#52514e"
NO_MULLIGAN = "#2a78d6"
WITH_MULLIGANS = "#eb6834"
# Card-group lines are one blue family, darker for more copies. The colour is
# keyed by how far a row is from the deck's real count, not by its position.
OFFSET_COLOURS = {
    -4: "#86b6ef",
    -2: "#5598e7",
    0: "#2a78d6",
    2: "#1c5cab",
    4: "#104281",
}
CHECKPOINT_LABELS = ["Opening", "Turn 1", "Turn 2", "Turn 3"]

FIGSIZE = (8, 4.5)  # inches; with dpi=150 this is a 1200 x 675 pixel image
DPI = 150


def _new_figure() -> tuple[Figure, Axes]:
    """A blank figure with one set of axes.

    Figure = the whole image; Axes = one plot inside it (the box with the data).
    """
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI, facecolor=BACKGROUND)
    return fig, ax


def _style_axes(ax: Axes) -> None:
    """Apply the shared look: quiet chrome so the data lines stand out."""
    ax.set_facecolor(BACKGROUND)
    # Spines are the four lines that frame the plot; keep only left and bottom.
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=AXIS, labelcolor=BODY_TEXT)
    # Horizontal gridlines only, drawn behind the data, to read values across.
    ax.yaxis.grid(True, color=GRID, linewidth=0.5)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    # PercentFormatter(1.0): the axis holds 0..1 and shows it as 0%..100%.
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_ylim(0, 1)
    ax.xaxis.label.set_color(BODY_TEXT)
    ax.yaxis.label.set_color(BODY_TEXT)


def _label_line_end(ax: Axes, x: float, y: float, text: str) -> None:
    """Write the series name just right of the line's last point.

    The text is grey, not the series colour, so it stays readable; the coloured
    line beside it shows which series it is.
    """
    ax.annotate(
        text,
        xy=(x, y),
        xytext=(8, 0),  # points to the right of the data point
        textcoords="offset points",
        va="center",
        color=BODY_TEXT,
        fontsize=9,
        annotation_clip=False,  # draw even though it sits outside the axes
    )


def land_drop_chart(odds: MulliganOdds, title: str) -> Figure:
    """Chance of hitting every land drop through turns 1-5, with and without mulligans."""
    turns = list(range(1, len(odds.drop_rows) + 1))
    exact = [row.exact for row in odds.drop_rows]
    simulated = [row.simulated for row in odds.drop_rows]

    fig, ax = _new_figure()
    _style_axes(ax)
    series = (
        ("No mulligan", exact, NO_MULLIGAN),
        ("With mulligans", simulated, WITH_MULLIGANS),
    )
    for label, values, colour in series:
        ax.plot(
            turns,
            values,
            color=colour,
            linewidth=2,
            marker="o",
            markersize=6,
            label=label,
        )
        _label_line_end(ax, turns[-1], values[-1], label)

    ax.set_title(title, color=TITLE_TEXT)
    ax.set_xlabel("Turn")
    ax.set_ylabel("Chance of making every land drop")
    ax.set_xticks(turns)
    ax.legend(loc="lower right", frameon=False, labelcolor=BODY_TEXT)
    # Leave room on the right for the end labels, which sit outside the axes.
    fig.subplots_adjust(right=0.82)
    return fig


def card_group_chart(
    groups: list[CardGroup], rows_by_group: list[list[WhatIfRow]], title: str
) -> Figure:
    """One panel per card group: chance of seeing at least one, by checkpoint,
    for the current count and a few more or fewer copies."""
    # subplots(1, 2): one row of two panels. sharey=True makes them share the
    # y-axis, so the odds in different panels are directly comparable.
    fig, _ = plt.subplots(
        1,
        len(groups),
        sharey=True,
        figsize=FIGSIZE,
        dpi=DPI,
        facecolor=BACKGROUND,
    )
    xs = list(range(len(CHECKPOINTS)))
    for ax, group, rows in zip(fig.axes, groups, rows_by_group, strict=True):
        _style_axes(ax)
        current = next(row.count for row in rows if row.is_current)
        for row in rows:
            offset = row.count - current
            ax.plot(
                xs,
                row.chances,
                color=OFFSET_COLOURS[offset],
                linewidth=3 if row.is_current else 2,
                marker="o",
                markersize=5,
            )
            label = f"{row.count} {group.unit if row.count == 1 else group.units}"
            if row.is_current:
                label += " (yours)"
            _label_line_end(ax, xs[-1], row.chances[-1], label)
        found = f"({group.count})" if group.count else "(none found)"
        ax.set_title(f"{group.name} {found}", color=TITLE_TEXT, fontsize=10)
        ax.set_xticks(xs, CHECKPOINT_LABELS)
        # A little extra room on the right keeps labels off the next panel.
        ax.set_xlim(-0.2, xs[-1] + 0.2)
    fig.axes[0].set_ylabel("Chance of at least one")
    # suptitle = the title over the whole figure, above the panel titles.
    fig.suptitle(title, color=TITLE_TEXT)
    fig.subplots_adjust(left=0.09, right=0.84, wspace=0.55, bottom=0.12)
    return fig


def main(
    argv: list[str] | None = None,
    db_path: Path = DEFAULT_DB,
    read: Callable[[str], str] = input,
    write: Callable[[str], object] = print,
    trials: int = TRIALS,
    out_dir: Path = Path("charts"),
) -> int:
    """Save the land-drop and card-group charts for a decklist as PNG files."""
    args = sys.argv[1:] if argv is None else argv
    usage = "Usage: uv run python -m fishbowl.stats.charts <decklist.txt>"
    path = find_deck_file(args, db_path, usage, write)
    if path is None:
        return 1
    with CardLookup(db_path) as lookup:
        deck = read_deck(path, lookup, read, write)
        lands, library = library_counts(deck, lookup)
        groups = find_groups(deck, lookup)  # needs the lookup, so it stays in here

    # Too few cards to see every turn: say so, and write no files.
    if library < CARDS_NEEDED:
        write(
            f"Only {library} cards in the library; at least {CARDS_NEEDED} are needed "
            f"to see {LAND_DROP_TURNS[-1]} turns."
        )
        return 1

    who = " + ".join(entry.name for entry in deck.commanders)
    if not who:
        write(f"No commander chosen: using all {library} cards as the library.")
        who = "Deck"
    if deck.problems:
        count = len(deck.problems)
        lines = "1 line" if count == 1 else f"{count} lines"
        write(f"Note: {lines} couldn't be read; the odds use the cards that could.")

    odds = mulligan_odds(lands, library, trials=trials)
    rows_by_group = [what_if(group.count, library, trials=trials) for group in groups]
    figures = {
        out_dir / f"{path.stem}-land-drops.png": land_drop_chart(
            odds, f"{who}: land drops, with and without mulligans"
        ),
        out_dir / f"{path.stem}-card-groups.png": card_group_chart(
            groups, rows_by_group, f"{who}: at least one card from each group"
        ),
    }
    # parents=True makes missing folders too; exist_ok=True allows re-running.
    out_dir.mkdir(parents=True, exist_ok=True)
    for file, fig in figures.items():
        fig.savefig(file, facecolor=BACKGROUND)
        plt.close(fig)  # free the figure's memory once it's saved
        write(f"Saved {file.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
