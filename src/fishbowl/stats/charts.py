"""PNG charts of the stats: land drops (and, later, card groups).

Run it with:  uv run python -m fishbowl.stats.charts <decklist.txt>
"""

import matplotlib

# Agg draws into memory and files only, with no window, so it works anywhere.
# It must be chosen before pyplot is imported.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

from fishbowl.stats.mulligan import MulliganOdds

# Colours live in one place so every chart looks like part of the same family.
BACKGROUND = "#fcfcfb"
GRID = "#e1e0d9"
AXIS = "#898781"  # spines and ticks
TITLE_TEXT = "#0b0b0b"
BODY_TEXT = "#52514e"
NO_MULLIGAN = "#2a78d6"
WITH_MULLIGANS = "#eb6834"

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
