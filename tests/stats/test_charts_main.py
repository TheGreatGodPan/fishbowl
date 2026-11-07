"""Tests for the charts command: uv run python -m fishbowl.stats.charts <file>."""

from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.parser import parse_deck
from fishbowl.stats.charts import main, report

GORECLAW = "Goreclaw, Terror of Qal Sisma"


def run(argv, card_db, tmp_path, answers=(), trials=2000):
    shown = []
    remaining = list(answers)

    def read(prompt):
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    code = main(
        argv,
        db_path=card_db,
        read=read,
        write=shown.append,
        trials=trials,
        out_dir=tmp_path / "charts",
    )
    return code, shown


def test_writes_pngs(tmp_path, card_db):
    deck = tmp_path / "goreclaw-deck.txt"
    deck.write_text(
        f"Commander: {GORECLAW}\n1 {GORECLAW}\n1 Survival of the Fittest\n"
        "33 Forest\n65 Sol Ring\n",
        encoding="utf-8",
    )
    code, shown = run([str(deck)], card_db, tmp_path)
    assert code == 0
    out = tmp_path / "charts"
    for name in ("goreclaw-deck-land-drops.png", "goreclaw-deck-card-groups.png"):
        assert (out / name).read_bytes().startswith(b"\x89PNG")
        assert any(line.startswith("Saved ") and line.endswith(name) for line in shown)
    # A second run overwrites the files without complaint.
    code, _ = run([str(deck)], card_db, tmp_path)
    assert code == 0


def test_tiny_deck_writes_nothing(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(
        f"Commander: {GORECLAW}\n1 {GORECLAW}\n5 Forest\n5 Sol Ring\n", encoding="utf-8"
    )
    code, shown = run([str(deck)], card_db, tmp_path)
    assert code == 1
    assert (
        "Only 10 cards in the library; at least 12 are needed to see 5 turns." in shown
    )
    assert not (tmp_path / "charts").exists()


def test_main_without_commander_uses_whole_deck(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text("33 Forest\n66 Sol Ring\n", encoding="utf-8")
    code, shown = run([str(deck)], card_db, tmp_path, answers=[""])
    assert code == 0
    assert "No commander chosen: using all 99 cards as the library." in shown


def test_main_notes_unreadable_lines(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(
        f"Commander: {GORECLAW}\n33 Forest\n65 Sol Ring\n1 Sol Rnig\n", encoding="utf-8"
    )
    code, shown = run([str(deck)], card_db, tmp_path)
    assert code == 0
    assert "Note: 1 line couldn't be read; the odds use the cards that could." in shown


def test_usage_and_missing_file(tmp_path, card_db):
    code, shown = run([], card_db, tmp_path)
    assert code == 1
    assert shown == ["Usage: uv run python -m fishbowl.stats.charts <decklist.txt>"]
    code, shown = run([str(tmp_path / "nope.txt")], card_db, tmp_path)
    assert code == 1
    assert shown[0].startswith("No such file:")


def test_report_matches_main(tmp_path, card_db):
    path = tmp_path / "deck.txt"
    path.write_text(
        f"Commander: {GORECLAW}\n1 {GORECLAW}\n1 Survival of the Fittest\n"
        "33 Forest\n65 Sol Ring\n",
        encoding="utf-8",
    )
    expected_code, expected = run([str(path)], card_db, tmp_path)
    shown: list[str] = []
    with CardLookup(card_db) as lookup:
        deck = parse_deck(path.read_text(encoding="utf-8"), lookup)
        code = report(
            deck,
            lookup,
            shown.append,
            trials=2000,
            out_dir=tmp_path / "charts",
            stem="deck",
        )
    assert code == expected_code
    assert shown == expected
