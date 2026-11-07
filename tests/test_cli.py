"""Tests for the fishbowl command (typer app in fishbowl.cli)."""

import pytest
from typer.testing import CliRunner

from fishbowl import cli
from fishbowl.cli import app
from fishbowl.deck import parser
from fishbowl.stats import curve, groups, lands, mulligan

runner = CliRunner()

DECK = "Commander: Goreclaw, Terror of Qal Sisma\n1 Goreclaw, Terror of Qal Sisma\n33 Forest\n66 Sol Ring\n"

# command name -> the module main() it should behave like
MAINS = {
    "check": parser.main,
    "lands": lands.main,
    "mulligan": mulligan.main,
    "groups": groups.main,
    "curve": curve.main,
}


@pytest.fixture(autouse=True)
def small_trials(monkeypatch):
    # Fewer simulated games keeps the tests fast; same value goes to both sides.
    monkeypatch.setattr(cli, "TRIALS", 2000)


def test_help_lists_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in (
        "refresh",
        "check",
        "lands",
        "mulligan",
        "groups",
        "curve",
        "charts",
        "analyze",
    ):
        assert name in result.output


@pytest.mark.parametrize("name", list(MAINS))
def test_check_and_stats_commands(name, tmp_path, card_db, monkeypatch):
    monkeypatch.setattr(cli, "DB_PATH", card_db)
    deck = tmp_path / "deck.txt"
    deck.write_text(DECK, encoding="utf-8")

    result = runner.invoke(app, [name, str(deck)])

    shown: list[str] = []
    main = MAINS[name]
    kwargs = {"trials": 2000} if name != "check" else {}
    code = main([str(deck)], card_db, input, shown.append, **kwargs)
    assert result.exit_code == code
    assert result.output.splitlines()[0] == shown[0]


def test_charts_command(tmp_path, card_db, monkeypatch):
    monkeypatch.setattr(cli, "DB_PATH", card_db)
    monkeypatch.setattr(cli, "CHARTS_DIR", tmp_path / "charts")
    deck = tmp_path / "deck.txt"
    deck.write_text(DECK, encoding="utf-8")

    result = runner.invoke(app, ["charts", str(deck)])

    assert result.exit_code == 0
    assert len(list((tmp_path / "charts").glob("*.png"))) == 2


def test_missing_db_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "missing.db")
    deck = tmp_path / "deck.txt"
    deck.write_text(DECK, encoding="utf-8")

    result = runner.invoke(app, ["check", str(deck)])

    assert result.exit_code == 1
    assert "uv run fishbowl refresh" in result.output


@pytest.mark.parametrize("command", ["lands", "analyze"])
def test_missing_deck_file(tmp_path, card_db, monkeypatch, command):
    monkeypatch.setattr(cli, "DB_PATH", card_db)
    result = runner.invoke(app, [command, str(tmp_path / "nope.txt")])
    assert result.exit_code == 1
    assert "No such file" in result.output
    assert "nope.txt" in result.output


def test_refresh_calls_refresh(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "refresh", lambda: calls.append(1) or 0)
    result = runner.invoke(app, ["refresh"])
    assert result.exit_code == 0
    assert len(calls) == 1


HEADINGS = [
    "== Deck check ==",
    "== Land odds ==",
    "== Mulligans ==",
    "== Card groups ==",
    "== Commander on curve ==",
]


def write_deck(tmp_path, text=DECK):
    deck = tmp_path / "deck.txt"
    deck.write_text(text, encoding="utf-8")
    return deck


def test_analyze_headings(tmp_path, card_db, monkeypatch):
    monkeypatch.setattr(cli, "DB_PATH", card_db)
    deck = write_deck(tmp_path)

    result = runner.invoke(app, ["analyze", str(deck)])

    shown: list[str] = []
    check_code = parser.main([str(deck)], card_db, input, shown.append)
    assert result.exit_code == check_code
    positions = [result.output.index(heading) for heading in HEADINGS]
    assert positions == sorted(positions)
    assert "== Charts ==" not in result.output


def test_analyze_asks_once(tmp_path, card_db, monkeypatch):
    monkeypatch.setattr(cli, "DB_PATH", card_db)
    deck = write_deck(
        tmp_path, "1 Goreclaw, Terror of Qal Sisma\n33 Forest\n66 Sol Ring\n"
    )

    result = runner.invoke(app, ["analyze", str(deck)], input="1\n")

    assert result.output.count("Which card is your commander?") == 1


def test_analyze_charts(tmp_path, card_db, monkeypatch):
    monkeypatch.setattr(cli, "DB_PATH", card_db)
    monkeypatch.setattr(cli, "CHARTS_DIR", tmp_path / "charts")
    deck = write_deck(tmp_path)

    result = runner.invoke(app, ["analyze", str(deck), "--charts"])

    assert "== Charts ==" in result.output
    assert len(list((tmp_path / "charts").glob("*.png"))) == 2


def test_analyze_tiny_deck(tmp_path, card_db, monkeypatch):
    monkeypatch.setattr(cli, "DB_PATH", card_db)
    deck = write_deck(
        tmp_path,
        "Commander: Goreclaw, Terror of Qal Sisma\n1 Goreclaw, Terror of Qal Sisma\n"
        "4 Forest\n4 Sol Ring\n",
    )

    result = runner.invoke(app, ["analyze", str(deck)])

    assert result.exit_code == 1
    for heading in HEADINGS:
        assert heading in result.output
    assert "Only 8 cards in the library" in result.output


def test_help_lists_goldfish():
    result = runner.invoke(app, ["--help"])
    assert "goldfish" in result.output


def test_goldfish_command(tmp_path, card_db, monkeypatch):
    monkeypatch.setattr(cli, "DB_PATH", card_db)
    deck = write_deck(tmp_path)
    result = runner.invoke(app, ["goldfish", str(deck), "--games", "50"])
    assert result.exit_code == 0
    assert "Commander cast by turn 4:" in result.output


def test_goldfish_zero_games_is_usage_error(tmp_path, card_db, monkeypatch):
    monkeypatch.setattr(cli, "DB_PATH", card_db)
    deck = write_deck(tmp_path)
    result = runner.invoke(app, ["goldfish", str(deck), "--games", "0"])
    assert result.exit_code == 2  # typer's usage error: no traceback
    assert not isinstance(result.exception, ValueError)
