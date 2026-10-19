"""Tests for the parser command: uv run python -m fishbowl.deck.parser <file>."""

from fishbowl.deck.parser import main

GORECLAW = "Goreclaw, Terror of Qal Sisma"


def run(argv, card_db, answers=()):
    shown = []
    remaining = list(answers)

    def read(prompt):
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    code = main(argv, db_path=card_db, read=read, write=shown.append)
    return code, shown


def test_clean_deck_with_commander(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(f"1 Sol Ring\n\n1 {GORECLAW}\n", encoding="utf-8")
    code, shown = run([str(deck)], card_db)
    assert code == 1  # 2 cards: parses fine but isn't a legal deck
    assert "Deck: 2 cards" in shown
    assert f"Commander: {GORECLAW}" in shown
    assert "Legal: no (1 error)" in shown


def test_asks_for_commander_when_unknown(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(f"1 {GORECLAW}\n1 Krenko, Mob Boss\n1 Sol Ring\n", encoding="utf-8")
    code, shown = run([str(deck)], card_db, answers=["gore", "1"])
    assert code == 1  # 3 cards: not a legal deck
    assert f"Commander: {GORECLAW}" in shown
    assert "Legal: no (2 errors)" in shown


def test_skipped_commander_shows_unknown(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(f"1 {GORECLAW}\n1 Sol Ring\n", encoding="utf-8")
    _, shown = run([str(deck)], card_db, answers=[""])
    assert "Commander: unknown" in shown


def test_problems_are_listed_and_exit_code_is_1(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text("1 Sol Ring\n1 Sol Rnig\n\n1 Krenko, Mob Boss\n", encoding="utf-8")
    code, shown = run([str(deck)], card_db)
    assert code == 1
    assert '  line 2: unknown card "Sol Rnig"' in shown


def test_left_out_cards_are_counted(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(
        f"Commander\n1 {GORECLAW}\nSideboard\n2 Sol Ring\n", encoding="utf-8"
    )
    _, shown = run([str(deck)], card_db)
    assert "Left out (sideboard, maybeboard, companion): 2 cards" in shown


def test_main_reads_non_utf8_file(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_bytes(
        b"1 Sol Ring\n1 Caf\xe9 Card\n\n1 Krenko, Mob Boss\n"
    )  # \xe9 is Latin-1, not UTF-8
    code, shown = run([str(deck)], card_db)
    assert code == 1  # the odd line is a problem, not a crash
    assert "Deck: 2 cards" in shown


def test_usage_when_no_file_given(card_db):
    code, shown = run([], card_db)
    assert code == 1
    assert shown == ["Usage: uv run python -m fishbowl.deck.parser <decklist.txt>"]


def test_missing_decklist_file(tmp_path, card_db):
    code, shown = run([str(tmp_path / "nope.txt")], card_db)
    assert code == 1
    assert shown[0].startswith("No such file:")


def test_missing_database_explains_what_to_do(tmp_path):
    deck = tmp_path / "deck.txt"
    deck.write_text("1 Sol Ring\n", encoding="utf-8")
    code, shown = run([str(deck)], tmp_path / "no.db")
    assert code == 1
    assert "  uv run python -m fishbowl.data.refresh" in shown


def test_whole_list_problem_prints_without_a_line_number(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text("1 Sol Ring\n" * 1001, encoding="utf-8")
    code, shown = run([str(deck)], card_db)
    assert code == 1
    assert "  too many lines (1001); a Commander deck has 100 cards" in shown
    assert not any(item.startswith("  line 0") for item in shown)


def test_legal_deck_prints_report_and_exits_0(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(
        f"Commander: {GORECLAW}\n1 {GORECLAW}\n1 Sol Ring\n98 Forest\n",
        encoding="utf-8",
    )
    code, shown = run([str(deck)], card_db)
    assert code == 0
    assert "Legal: yes" in shown
    assert "Notes:" in shown
    assert "  Game Changers: 0" in shown
    assert "Errors:" not in shown


def test_illegal_deck_lists_errors(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(f"Commander: {GORECLAW}\n2 Sol Ring\n97 Forest\n", encoding="utf-8")
    code, shown = run([str(deck)], card_db)
    assert code == 1
    assert "Legal: no (1 error)" in shown
    assert "Errors:" in shown
    assert "  2 copies of Sol Ring; only 1 allowed." in shown
