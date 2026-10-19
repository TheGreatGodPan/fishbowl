"""Turning pasted decklist text into a ParsedDeck.

Run it with:  uv run python -m fishbowl.deck.parser <decklist.txt>
"""

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from fishbowl.deck.commander import (
    ask_for_commander,
    can_be_commander,
    commander_candidates,
)
from fishbowl.deck.lookup import DEFAULT_DB, Card, CardLookup
from fishbowl.deck.model import DeckEntry, ParsedDeck, Problem
from fishbowl.deck.validator import validate

MAX_QUANTITY = 999
# The longest real card name is about 140 characters. Capping the line keeps one
# giant pasted line from stalling the strip loop below.
MAX_LINE_LENGTH = 500

# "1 Sol Ring", "1x Sol Ring": a number, an optional x, then the name.
_QUANTITY = re.compile(r"^(\d+)[xX]?\s+(.+)$")
# Archidekt decorations at the end of a line: [Category] tags and ^Tag,#color^ tags.
_TAG = re.compile(r"\s*(\[[^\]]*\]|\^[^^]*\^)\s*$")
# Finish markers: *F* (foil), *E* (etched).
_MARKER = re.compile(r"\s*\*[A-Za-z]+\*\s*$")
# Printing: (SET) plus an optional collector number like 19 or 1★.
# Set codes are 2-6 letters/digits, so a real name like "(Big Furry Monster)" is kept.
_PRINTING = re.compile(r"\s+\([A-Za-z0-9]{2,6}\)(\s+\S+)?\s*$")
_HEADER = re.compile(
    r"^(commanders?|deck|mainboard|main|sideboard|maybeboard|companion)\s*:?\s*(\(\d+\))?$",
    re.IGNORECASE,
)
_EXPLICIT_COMMANDER = re.compile(r"^commander\s*:\s*(\S.*)$", re.IGNORECASE)
_SECTIONS = {
    "commander": "commander",
    "commanders": "commander",
    "deck": "main",
    "mainboard": "main",
    "main": "main",
    "sideboard": "out",
    "maybeboard": "out",
    "companion": "out",
}


@dataclass(frozen=True)
class CardLine:
    """What one card line says: how many, which name, and whether it's tagged commander."""

    quantity: int
    name: str
    commander_tag: bool = False


def parse_card_line(text: str) -> CardLine:
    """'1x Sol Ring (CMM) 400 *F* [Ramp]' -> CardLine(1, 'Sol Ring').

    Raises ValueError with a short reason if the line can't be a card.
    Lines longer than MAX_LINE_LENGTH characters are refused before any parsing.
    """
    # Checked first, before any regex runs, so a huge line costs almost nothing.
    if len(text) > MAX_LINE_LENGTH:
        raise ValueError(f"line too long ({len(text)} characters)")
    line = " ".join(text.split())  # tabs and repeated spaces -> single spaces
    commander_tag = False
    # Strip end-of-line decorations, in any order, until nothing changes.
    while True:
        tag = _TAG.search(line)
        if tag:
            label = tag.group(1).strip("[]^").lower()
            commander_tag = commander_tag or label.startswith("commander")
            line = line[: tag.start()]
            continue
        stripped = _PRINTING.sub("", _MARKER.sub("", line))
        if stripped == line:
            break
        line = stripped

    match = _QUANTITY.match(line)
    if match:
        quantity, name = int(match.group(1)), match.group(2).strip()
    else:
        quantity, name = 1, line.strip()
    if not name:
        raise ValueError("no card name")
    if not 1 <= quantity <= MAX_QUANTITY:
        raise ValueError(f"quantity {quantity} is outside 1-{MAX_QUANTITY}")
    return CardLine(quantity, name, commander_tag)


def section_for_header(line: str) -> str | None:
    """'Commander' -> 'commander', 'Deck' -> 'main', 'Sideboard' -> 'out', else None."""
    match = _HEADER.match(line.strip())
    return _SECTIONS[match.group(1).lower()] if match else None


def explicit_commander_name(line: str) -> str | None:
    """'Commander: Goreclaw, Terror of Qal Sisma' -> 'Goreclaw, Terror of Qal Sisma'."""
    match = _EXPLICIT_COMMANDER.match(line.strip())
    return match.group(1).strip() if match else None


MAX_LINES = 1000
MAX_COMMANDERS = 2
_PROBLEM_TEXT_LIMIT = 200


@dataclass
class _Block:
    """Card lines between blank lines, used to find a final commander block."""

    lines: list[tuple[Card, CardLine, str]] = field(default_factory=list)
    has_header: bool = False


def _problem(line_number: int, text: str, reason: str) -> Problem:
    return Problem(line_number, text[:_PROBLEM_TEXT_LIMIT], reason)


def _add(entries: dict[str, DeckEntry], card: Card, quantity: int) -> None:
    """Add copies of a card, merging lines for the same card (dict keeps first-seen order)."""
    if card.oracle_id in entries:
        entries[card.oracle_id].quantity += quantity
    else:
        entries[card.oracle_id] = DeckEntry(card.name, card.oracle_id, quantity)


def parse_deck(text: str, lookup: CardLookup) -> ParsedDeck:
    """Parse pasted decklist text. Never raises on bad lines: they become Problems."""
    deck = ParsedDeck()
    lines = text.lstrip("\ufeff").splitlines()  # BOM off; \r\n and \n both split
    if len(lines) > MAX_LINES:
        deck.problems.append(
            _problem(
                0, "", f"too many lines ({len(lines)}); a Commander deck has 100 cards"
            )
        )
        return deck

    section = "main"
    blocks = [_Block()]
    explicit: list[Card] = []
    for number, raw in enumerate(lines, start=1):
        # A lone surrogate (e.g. "\ud800") can't be encoded, and the lookup would raise.
        # Replacing it up front keeps the "no line ever raises" promise.
        raw = raw.encode("utf-8", "replace").decode("utf-8")
        line = " ".join(raw.split())
        if not line:
            if blocks[-1].lines or blocks[-1].has_header:
                blocks.append(_Block())  # a blank line ends the block
            if section == "commander":
                section = (
                    "main"  # a blank line ends the Commander list; sideboards persist
                )
            continue
        if line.startswith(("//", "#")):
            continue  # comment
        header = section_for_header(line)
        if header is not None:
            section = header
            blocks[-1].has_header = True
            continue
        named = explicit_commander_name(line)
        if named is not None:
            # Same decoration stripping as card lines, so "(CMM) 293 *F*" doesn't block the lookup.
            try:
                named = parse_card_line(named).name
            except ValueError as error:
                deck.problems.append(_problem(number, line, str(error)))
                continue
            card = lookup.find(named)
            if card is None:
                deck.problems.append(_problem(number, line, f'unknown card "{named}"'))
            else:
                explicit.append(card)
            continue
        try:
            parsed = parse_card_line(line)
        except ValueError as error:
            deck.problems.append(_problem(number, line, str(error)))
            continue
        card = lookup.find(parsed.name)
        if card is None:
            deck.problems.append(
                _problem(number, line, f'unknown card "{parsed.name}"')
            )
            continue
        blocks[-1].lines.append((card, parsed, section))

    main: dict[str, DeckEntry] = {}
    out: dict[str, DeckEntry] = {}
    commanders: list[Card] = []
    for block in blocks:
        for card, parsed, line_section in block.lines:
            _add(out if line_section == "out" else main, card, parsed.quantity)
            if line_section == "commander" or (
                parsed.commander_tag and line_section != "out"
            ):
                commanders.append(card)
    for card in explicit:
        if card.oracle_id not in main:
            _add(main, card, 1)  # named only on the Commander: line
        commanders.append(card)

    if not commanders:
        filled = [block for block in blocks if block.lines]
        last = filled[-1] if filled else None
        if (
            last is not None
            and len(filled) >= 2
            and not last.has_header
            and 1 <= len(last.lines) <= MAX_COMMANDERS
            and all(line_section == "main" for _, _, line_section in last.lines)
            # Grouped lists end with lands, so only single copies of cards that
            # could really be commanders count; otherwise the CLI asks instead.
            and all(
                parsed.quantity == 1 and can_be_commander(card)
                for card, parsed, _ in last.lines
            )
        ):
            commanders = [card for card, _, _ in last.lines]

    unique: dict[str, Card] = {}
    for card in commanders:
        unique.setdefault(card.oracle_id, card)
    chosen = list(unique.values())
    if len(chosen) > MAX_COMMANDERS:
        listed = ", ".join(card.name for card in chosen)
        deck.problems.append(
            _problem(
                0, "", f"more than 2 commanders marked ({listed}); using the first 2"
            )
        )
        chosen = chosen[:MAX_COMMANDERS]

    deck.cards = list(main.values())
    deck.left_out = list(out.values())
    deck.commanders = [DeckEntry(card.name, card.oracle_id, 1) for card in chosen]
    return deck


def find_deck_file(
    args: list[str], db_path: Path, usage: str, write: Callable[[str], object]
) -> Path | None:
    """The decklist path from the command line, or None after explaining what's wrong."""
    if len(args) != 1:
        write(usage)
        return None
    path = Path(args[0])
    if not path.is_file():
        write(f"No such file: {path}")
        return None
    if not db_path.is_file():
        write(f"No card database at {db_path}. Build it first with:")
        write("  uv run python -m fishbowl.data.refresh")
        return None
    return path


def read_deck(
    path: Path,
    lookup: CardLookup,
    read: Callable[[str], str] = input,
    write: Callable[[str], object] = print,
) -> ParsedDeck:
    """Read and parse a decklist file, asking for the commander if none was found."""
    # errors="replace": a list saved in another encoding still parses; odd bytes become �.
    text = path.read_text(encoding="utf-8", errors="replace")
    deck = parse_deck(text, lookup)
    if not deck.commanders:
        chosen = ask_for_commander(commander_candidates(deck, lookup), read, write)
        deck.commanders = [
            DeckEntry(entry.name, entry.oracle_id, 1)
            for entry in deck.cards
            if entry.name == chosen
        ]
    return deck


def main(
    argv: list[str] | None = None,
    db_path: Path = DEFAULT_DB,
    read: Callable[[str], str] = input,
    write: Callable[[str], object] = print,
) -> int:
    """Parse and check a decklist file. Returns 0 only for a legal, fully readable deck."""
    args = sys.argv[1:] if argv is None else argv
    usage = "Usage: uv run python -m fishbowl.deck.parser <decklist.txt>"
    path = find_deck_file(args, db_path, usage, write)
    if path is None:
        return 1
    with CardLookup(db_path) as lookup:
        deck = read_deck(path, lookup, read, write)
        report = validate(deck, lookup)  # needs the lookup, so it runs inside the with

    write(f"Deck: {deck.total} cards")
    commander_names = " + ".join(entry.name for entry in deck.commanders)
    write(f"Commander: {commander_names or 'unknown'}")
    if deck.left_out:
        left_out = sum(entry.quantity for entry in deck.left_out)
        write(f"Left out (sideboard, maybeboard, companion): {left_out} cards")
    if deck.problems:
        write("Problems:")
        for problem in deck.problems:
            if problem.line_number == 0:
                write(f"  {problem.reason}")  # about the whole list, not one line
            else:
                write(f"  line {problem.line_number}: {problem.reason}")
    if report.is_legal:
        write("Legal: yes")
    else:
        count = len(report.errors)
        write(f"Legal: no ({count} {'error' if count == 1 else 'errors'})")
        write("Errors:")
        for issue in report.errors:
            write(f"  {issue.message}")
    if report.notes:
        write("Notes:")
        for issue in report.notes:
            write(f"  {issue.message}")
    return 0 if report.is_legal else 1


if __name__ == "__main__":
    sys.exit(main())
