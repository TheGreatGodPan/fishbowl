"""Tests for the mulligan command: uv run python -m fishbowl.stats.mulligan <file>."""

from fishbowl.stats.mulligan import main

GORECLAW = "Goreclaw, Terror of Qal Sisma"


def run(argv, card_db, answers=(), trials=2000):
    shown = []
    remaining = list(answers)

    def read(prompt):
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    code = main(argv, db_path=card_db, read=read, write=shown.append, trials=trials)
    return code, shown


def test_prints_header_and_tables(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(
        f"Commander: {GORECLAW}\n1 {GORECLAW}\n33 Forest\n66 Sol Ring\n",
        encoding="utf-8",
    )
    code, shown = run([str(deck)], card_db)
    assert code == 0
    assert (
        shown[0]
        == f"{GORECLAW}: 33 lands in a 99-card library (2,000 simulated games, seed 42; "
        "multiplayer: everyone draws on turn 1)"
    )
    assert (
        shown[1] == "Mulligans: free first mulligan; keep 2-5 lands; always keep at 5"
    )
    first_hand = [line for line in shown if line.startswith("Keep 7 (first hand)")]
    assert len(first_hand) == 1
    assert "74.1%" in first_hand[0]  # the exact column
    assert len([line for line in shown if line.startswith("Average hand size")]) == 1
    drops = [line for line in shown if line.startswith("Land drop through turn ")]
    assert len(drops) == 5


def test_main_without_commander_uses_whole_deck(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text("33 Forest\n66 Sol Ring\n", encoding="utf-8")
    code, shown = run([str(deck)], card_db, answers=[""])
    assert code == 0
    assert "No commander chosen: using all 99 cards as the library." in shown


def test_main_notes_unreadable_lines(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(
        f"Commander: {GORECLAW}\n33 Forest\n65 Sol Ring\n1 Sol Rnig\n", encoding="utf-8"
    )
    code, shown = run([str(deck)], card_db)
    assert code == 0
    assert "Note: 1 line couldn't be read; the odds use the cards that could." in shown


def test_tiny_deck_message(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(
        f"Commander: {GORECLAW}\n1 {GORECLAW}\n5 Forest\n5 Sol Ring\n", encoding="utf-8"
    )
    code, shown = run([str(deck)], card_db)
    assert code == 1
    assert (
        "Only 10 cards in the library; at least 12 are needed to see 5 turns." in shown
    )


def test_usage_and_missing_file(tmp_path, card_db):
    code, shown = run([], card_db)
    assert code == 1
    assert shown == ["Usage: uv run python -m fishbowl.stats.mulligan <decklist.txt>"]
