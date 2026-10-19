"""Tests for the land odds command: uv run python -m fishbowl.stats.lands <file>."""

from fishbowl.stats.lands import main

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


def test_prints_header_and_table(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(
        f"Commander: {GORECLAW}\n1 {GORECLAW}\n33 Forest\n66 Sol Ring\n",
        encoding="utf-8",
    )
    code, shown = run([str(deck)], card_db)
    assert code == 0
    assert (
        shown[0]
        == f"{GORECLAW}: 33 lands in a 99-card library (2,000 simulated hands, seed 42; "
        "multiplayer: everyone draws on turn 1)"
    )
    table = [line for line in shown if line.startswith("Opening hand: 2-5 lands")]
    assert len(table) == 1
    assert "74.1%" in table[0]  # the exact column


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


def test_usage_and_missing_file(tmp_path, card_db):
    code, shown = run([], card_db)
    assert code == 1
    assert shown == ["Usage: uv run python -m fishbowl.stats.lands <decklist.txt>"]
    code, shown = run([str(tmp_path / "nope.txt")], card_db)
    assert code == 1
    assert shown[0].startswith("No such file:")


def test_tiny_deck_gives_a_message_not_a_crash(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(
        f"Commander: {GORECLAW}\n1 {GORECLAW}\n5 Forest\n", encoding="utf-8"
    )
    code, shown = run([str(deck)], card_db)
    assert code == 1
    assert (
        "Only 5 cards in the library; at least 12 are needed to see 5 turns." in shown
    )
    assert not any(line.startswith("Goreclaw") for line in shown)  # no header


def test_empty_file_gives_a_message_not_a_crash(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text("", encoding="utf-8")
    code, shown = run([str(deck)], card_db, answers=[""])
    assert code == 1
    assert (
        "Only 0 cards in the library; at least 12 are needed to see 5 turns." in shown
    )
