import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_hex

from fishbowl.stats.charts import land_drop_chart
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
