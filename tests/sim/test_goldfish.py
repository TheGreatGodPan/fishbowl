"""Tests for the goldfish report: one game, many games, no commander."""

import pytest

from fishbowl.sim import goldfish

DECK = (
    "Commander: Goreclaw, Terror of Qal Sisma\n"
    "1 Goreclaw, Terror of Qal Sisma\n33 Forest\n66 Sol Ring\n"
)
NO_COMMANDER = "34 Forest\n66 Sol Ring\n"


def run(tmp_path, card_db, text=DECK, **kwargs) -> list[str]:
    deck = tmp_path / "deck.txt"
    deck.write_text(text, encoding="utf-8")
    shown: list[str] = []
    code = goldfish.main([str(deck)], card_db, input, shown.append, **kwargs)
    assert code == 0
    return shown


def test_single_game_prints_kinds_log_and_footer(tmp_path, card_db):
    lines = run(tmp_path, card_db)
    assert lines[0] == "Goreclaw, Terror of Qal Sisma: goldfish, seed 42, 8 turns"
    assert "  Rocks: Sol Ring" in lines
    assert any(line.startswith("Turn 1:") for line in lines)
    assert any("Simplified:" in line for line in lines)


def test_many_games_prints_summary(tmp_path, card_db):
    lines = run(tmp_path, card_db, games=200)
    text = "\n".join(lines)
    assert "Commander cast by turn 1:" in text
    assert "Commander cast by turn 8:" in text
    assert "Average turn (when cast):" in text
    assert "Not cast in 8 turns:" in text
    assert "Lands-only baseline (4d, no mulligan):" in text
    assert "Lands only, same engine:" in text
    assert "% by turn 4" in text
    assert not any(line.startswith("Turn 1:") for line in lines)  # no per-game log


def test_goldfish_no_commander(tmp_path, card_db):
    lines = run(tmp_path, card_db, NO_COMMANDER, games=20)
    assert "No commander: nothing to measure." in lines
    assert not any("Commander cast by turn" in line for line in lines)


def test_turns_option_sets_summary_length(tmp_path, card_db):
    lines = run(tmp_path, card_db, games=10, turns=10)
    assert any("Commander cast by turn 10:" in line for line in lines)


def test_same_seed_is_reproducible(tmp_path, card_db):
    assert run(tmp_path, card_db, seed=7) == run(tmp_path, card_db, seed=7)
    assert run(tmp_path, card_db, seed=7) != run(tmp_path, card_db, seed=8)


def _pct(lines: list[str], prefix: str) -> float:
    line = next(x for x in lines if x.startswith(prefix))
    return float(line.split(": ")[1].split("%")[0])


def test_same_engine_baseline_not_above_full(tmp_path, card_db):
    lines = run(tmp_path, card_db, games=200)
    full = _pct(lines, "Commander cast by turn 4:")
    same = _pct(lines, "Lands only, same engine:")
    assert same <= full
    # the same-engine line sits right before the 4d line
    i = next(n for n, x in enumerate(lines) if x.startswith("Lands only, same"))
    assert lines[i + 1].startswith("Lands-only baseline (4d, no mulligan)")


def test_report_rejects_zero_games_or_turns(tmp_path, card_db):
    with pytest.raises(ValueError):
        run(tmp_path, card_db, games=0)
    with pytest.raises(ValueError):
        run(tmp_path, card_db, turns=0)
