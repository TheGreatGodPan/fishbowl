import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_hex

from fishbowl.stats.charts import card_group_chart, land_drop_chart
from fishbowl.stats.groups import CardGroup, what_if
from fishbowl.stats.mulligan import mulligan_odds


def test_uses_agg_backend():
    assert matplotlib.get_backend().lower() == "agg"


def test_land_drop_chart_lines():
    odds = mulligan_odds(33, 99, trials=2000)
    fig = land_drop_chart(odds, "Test deck")
    try:
        lines = fig.axes[0].get_lines()
        assert len(lines) == 2
        for line in lines:
            assert np.asarray(line.get_xdata()).tolist() == [1, 2, 3, 4, 5]
        assert np.asarray(lines[0].get_ydata()).tolist() == [
            r.exact for r in odds.drop_rows
        ]
        assert np.asarray(lines[1].get_ydata()).tolist() == [
            r.simulated for r in odds.drop_rows
        ]
        assert to_hex(lines[0].get_color()) == "#2a78d6"
        assert to_hex(lines[1].get_color()) == "#eb6834"
    finally:
        plt.close(fig)


def test_land_drop_chart_text():
    odds = mulligan_odds(33, 99, trials=2000)
    fig = land_drop_chart(odds, "Test deck")
    try:
        ax = fig.axes[0]
        legend = ax.get_legend()
        assert legend is not None
        assert [t.get_text() for t in legend.get_texts()] == [
            "No mulligan",
            "With mulligans",
        ]
        assert ax.get_title() == "Test deck"
        assert ax.get_ylim() == (0, 1)
        assert not ax.spines["top"].get_visible()
        assert not ax.spines["right"].get_visible()
    finally:
        plt.close(fig)


def _group_chart():
    groups = [
        CardGroup("Mana dorks", "dork", "dorks", 7, ["Llanowar Elves"]),
        CardGroup("Tutors", "tutor", "tutors", 0, []),
    ]
    rows = [what_if(7, 99, trials=100), what_if(0, 99, trials=100)]
    return card_group_chart(groups, rows, "Test deck")


def _texts(ax):
    return [t.get_text() for t in ax.texts]


def test_card_group_chart_panels():
    fig = _group_chart()
    try:
        assert len(fig.axes) == 2
        assert [ax.get_title() for ax in fig.axes] == [
            "Mana dorks (7)",
            "Tutors (none found)",
        ]
    finally:
        plt.close(fig)


def test_card_group_chart_lines():
    fig = _group_chart()
    try:
        ax = fig.axes[0]
        lines = ax.get_lines()
        assert len(lines) == 5
        by_count = dict(zip(range(3, 12, 2), lines, strict=True))
        assert by_count[7].get_linewidth() == 3
        assert to_hex(by_count[7].get_color()) == "#2a78d6"
        assert to_hex(by_count[11].get_color()) == "#104281"
        assert [t.get_text() for t in ax.get_xticklabels()] == [
            "Opening",
            "Turn 1",
            "Turn 2",
            "Turn 3",
        ]
        assert "7 dorks (yours)" in _texts(ax)
    finally:
        plt.close(fig)


def test_zero_group_panel():
    fig = _group_chart()
    try:
        ax = fig.axes[1]
        lines = ax.get_lines()
        assert len(lines) == 3
        assert to_hex(lines[0].get_color()) == "#2a78d6"
        assert to_hex(lines[1].get_color()) == "#1c5cab"
        assert "0 tutors (yours)" in _texts(ax)
    finally:
        plt.close(fig)
