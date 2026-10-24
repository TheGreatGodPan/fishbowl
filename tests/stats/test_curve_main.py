"""Tests for the curve command: uv run python -m fishbowl.stats.curve <file>."""

from dataclasses import replace

from fishbowl.stats import curve
from fishbowl.stats.curve import main

GORECLAW = "Goreclaw, Terror of Qal Sisma"
LANDS_ONLY = "Lands only; ignores dorks, rocks and cost reducers."


def run(argv, card_db, answers=(), trials=2000):
    shown = []
    remaining = list(answers)

    def read(prompt):
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    code = main(argv, db_path=card_db, read=read, write=shown.append, trials=trials)
    return code, shown


def write_deck(tmp_path, text):
    deck = tmp_path / "deck.txt"
    deck.write_text(text, encoding="utf-8")
    return deck


def test_prints_commander_block(tmp_path, card_db):
    deck = write_deck(
        tmp_path, f"Commander: {GORECLAW}\n1 {GORECLAW}\n33 Forest\n66 Sol Ring\n"
    )
    code, shown = run([str(deck)], card_db)
    assert code == 0
    assert shown[0].startswith(
        f"{GORECLAW}: 33 lands in a 99-card library (2,000 simulated hands"
    )
    assert LANDS_ONLY in shown
    assert f"{GORECLAW} {{3}}{{G}}: mana value 4, cast on turn 4" in shown
    lands_rows = [line for line in shown if line.startswith("  4+ lands by turn 4")]
    assert len(lands_rows) == 1
    assert "53.3%" in lands_rows[0]
    assert any(line.startswith("  ...and 1+ green source") for line in shown)


def test_main_without_commander(tmp_path, card_db):
    deck = write_deck(tmp_path, "33 Forest\n66 Sol Ring\n")
    code, shown = run([str(deck)], card_db, answers=[""])
    assert code == 0
    assert "No commander chosen: using all 99 cards as the library." in shown
    assert "Nothing to cast on curve." in shown


def test_main_notes_unreadable_lines(tmp_path, card_db):
    deck = write_deck(
        tmp_path,
        f"Commander: {GORECLAW}\n33 Forest\n65 Sol Ring\n1 Sol Rnig\n",
    )
    code, shown = run([str(deck)], card_db)
    assert code == 0
    assert "Note: 1 line couldn't be read; the odds use the cards that could." in shown


def test_too_big_to_cast(tmp_path, card_db):
    deck = write_deck(
        tmp_path, f"Commander: {GORECLAW}\n1 {GORECLAW}\n5 Forest\n4 Sol Ring\n"
    )
    code, shown = run([str(deck)], card_db)
    assert code == 0
    assert "  Can't be cast on curve from lands in a 9-card library." in shown


def test_skips_commander_without_cost(tmp_path, card_db, monkeypatch):
    deck = write_deck(
        tmp_path, f"Commander: {GORECLAW}\n1 {GORECLAW}\n33 Forest\n66 Sol Ring\n"
    )
    real_find = curve.CardLookup.find

    def find_without_cost(self, name):
        card = real_find(self, name)
        assert card is not None
        return replace(card, cmc=None) if name == GORECLAW else card

    monkeypatch.setattr(curve.CardLookup, "find", find_without_cost)
    code, shown = run([str(deck)], card_db)
    assert code == 0
    assert f"{GORECLAW}: no mana cost found; skipped" in shown


def test_two_commanders_two_blocks(tmp_path, card_db):
    deck = write_deck(
        tmp_path,
        f"Commander\n1 {GORECLAW}\n1 Krenko, Mob Boss\nDeck\n10 Forest\n2 Sol Ring\n",
    )
    code, shown = run([str(deck)], card_db)
    assert code == 0
    assert len([line for line in shown if "mana value 4" in line]) == 2


def test_usage_and_missing_file(tmp_path, card_db):
    code, shown = run([], card_db)
    assert code == 1
    assert shown == ["Usage: uv run python -m fishbowl.stats.curve <decklist.txt>"]
    code, shown = run([str(tmp_path / "nope.txt")], card_db)
    assert code == 1
    assert shown[0].startswith("No such file:")


def test_notes_for_big_and_multicolour(tmp_path, card_db, monkeypatch):
    deck = write_deck(
        tmp_path, f"Commander: {GORECLAW}\n1 {GORECLAW}\n33 Forest\n66 Sol Ring\n"
    )
    real_find = curve.CardLookup.find

    def find_big_cost(self, name):
        card = real_find(self, name)
        assert card is not None
        if name == GORECLAW:
            return replace(card, mana_cost="{6}{G}{U}", cmc=8.0)
        return card

    monkeypatch.setattr(curve.CardLookup, "find", find_big_cost)
    code, shown = run([str(deck)], card_db)
    assert code == 0
    assert "  Note: cost reducers aren't modelled." in shown
    assert "  Note: approximate for multi-colour costs." in shown
