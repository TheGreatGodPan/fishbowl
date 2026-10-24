"""Tests for the groups command: uv run python -m fishbowl.stats.groups <file>."""

from fishbowl.stats.groups import main

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


def test_prints_groups(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(
        f"Commander: {GORECLAW}\n1 {GORECLAW}\n1 Survival of the Fittest\n"
        "33 Forest\n65 Sol Ring\n",
        encoding="utf-8",
    )
    code, shown = run([str(deck)], card_db)
    assert code == 0
    assert shown[0].startswith(f"{GORECLAW}: 99-card library (2,000 simulated hands")
    assert "Mana dorks: none found" in shown
    assert "Tutors: 1 in the library" in shown
    assert "  Survival of the Fittest" in shown
    assert len([line for line in shown if line.startswith("  1 tutor (yours)")]) == 1
    assert len([line for line in shown if line.startswith("  3 tutors")]) == 1
    assert len([line for line in shown if line.startswith("  0 dorks (yours)")]) == 1


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
        f"Commander: {GORECLAW}\n1 {GORECLAW}\n4 Forest\n4 Sol Ring\n", encoding="utf-8"
    )
    code, shown = run([str(deck)], card_db)
    assert code == 1
    assert (
        "Only 8 cards in the library; at least 10 are needed to see 3 turns." in shown
    )


def test_usage_and_missing_file(tmp_path, card_db):
    code, shown = run([], card_db)
    assert code == 1
    assert shown == ["Usage: uv run python -m fishbowl.stats.groups <decklist.txt>"]
    code, shown = run([str(tmp_path / "nope.txt")], card_db)
    assert code == 1
    assert shown[0].startswith("No such file:")


def test_table_header_says_opening_hand_only(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(
        f"Commander: {GORECLAW}\n33 Forest\n65 Sol Ring\n", encoding="utf-8"
    )
    code, shown = run([str(deck)], card_db)
    assert code == 0
    assert any("sim. opening" in line for line in shown)
