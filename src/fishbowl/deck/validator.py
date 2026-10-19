"""Checking a parsed deck against Commander's deck-building rules."""

import re
from dataclasses import dataclass, field

from fishbowl.deck.commander import can_be_commander
from fishbowl.deck.lookup import Card, CardLookup
from fishbowl.deck.model import ParsedDeck

DECK_SIZE = 100
_COLOR_ORDER = "WUBRG"
# "A deck can have up to seven cards named Seven Dwarves." (also Nazgûl: nine)
_UP_TO = re.compile(r"can have up to (\w+) cards named", re.IGNORECASE)
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


@dataclass(frozen=True)
class Issue:
    """One finding: a short code for programs, a sentence for people."""

    code: str
    message: str


def copy_limit(card: Card) -> int | None:
    """How many copies a deck may hold: None means any number."""
    if (card.type_line or "").startswith("Basic"):
        return None  # basic lands, including Snow-Covered and Wastes
    text = card.oracle_text or ""
    if "any number of cards named" in text:
        return None
    match = _UP_TO.search(text)
    if match:
        return _NUMBER_WORDS.get(match.group(1).lower(), 1)  # unknown word: be strict
    return 1


def _identity_text(letters: set[str]) -> str:
    """{'G', 'W'} -> 'WG' in WUBRG order; empty -> 'colorless'."""
    return "".join(c for c in _COLOR_ORDER if c in letters) or "colorless"


def check_unreadable(deck: ParsedDeck, cards: dict[str, Card]) -> list[Issue]:
    """Fail closed: lines we couldn't read might break any rule."""
    count = len(deck.problems)
    if count == 0:
        return []
    lines = "1 line" if count == 1 else f"{count} lines"
    return [
        Issue(
            "unreadable_lines",
            f"{lines} couldn't be read, so the deck can't be fully checked.",
        )
    ]


def check_deck_size(deck: ParsedDeck, cards: dict[str, Card]) -> list[Issue]:
    if deck.total == DECK_SIZE:
        return []
    message = (
        f"Deck has {deck.total} cards; a Commander deck needs exactly {DECK_SIZE}."
    )
    return [Issue("deck_size", message)]


def check_commanders(deck: ParsedDeck, cards: dict[str, Card]) -> list[Issue]:
    if not deck.commanders:
        return [Issue("no_commander", "No commander identified.")]
    issues = []
    for entry in deck.commanders:
        card = cards.get(entry.oracle_id)
        if card is not None and not can_be_commander(card):
            message = (
                f"{card.name} can't be a commander (it isn't a legendary creature)."
            )
            issues.append(Issue("ineligible_commander", message))
    return issues


def check_copies(deck: ParsedDeck, cards: dict[str, Card]) -> list[Issue]:
    issues = []
    for entry in deck.cards:
        card = cards.get(entry.oracle_id)
        if card is None:
            continue
        limit = copy_limit(card)
        if limit is None or entry.quantity <= limit:
            continue
        allowed = "only 1 allowed" if limit == 1 else f"up to {limit} allowed"
        issues.append(
            Issue(
                "too_many_copies", f"{entry.quantity} copies of {card.name}; {allowed}."
            )
        )
    return issues


def check_color_identity(deck: ParsedDeck, cards: dict[str, Card]) -> list[Issue]:
    """Every card's identity must fit inside the commanders' combined identity."""
    commander_cards = [
        cards[e.oracle_id] for e in deck.commanders if e.oracle_id in cards
    ]
    if not commander_cards:
        return []  # check_commanders already reports a missing commander
    allowed: set[str] = set()
    for commander in commander_cards:
        allowed |= set(commander.color_identity)  # |= : add these letters to the set
    issues = []
    for entry in deck.cards:
        card = cards.get(entry.oracle_id)
        if card is None:
            continue
        own = set(card.color_identity)
        if not own <= allowed:  # <= : "is a subset of"
            message = (
                f"{card.name} ({_identity_text(own)}) is outside the commander's "
                f"color identity ({_identity_text(allowed)})."
            )
            issues.append(Issue("off_color", message))
    return issues


def check_legality(deck: ParsedDeck, cards: dict[str, Card]) -> list[Issue]:
    """Uses Scryfall's commander_status, so ban-list changes need no code change."""
    issues = []
    for entry in deck.cards:
        card = cards.get(entry.oracle_id)
        if card is None or card.commander_status == "legal":
            continue
        if card.commander_status == "banned":
            issues.append(Issue("banned", f"{card.name} is banned in Commander."))
        else:
            message = (
                f"{card.name} is not legal in Commander ({card.commander_status})."
            )
            issues.append(Issue("not_legal", message))
    return issues


@dataclass
class ValidationReport:
    """Errors break a rule; notes are worth knowing but aren't rule breaks."""

    errors: list[Issue] = field(default_factory=list)
    notes: list[Issue] = field(default_factory=list)

    @property
    def is_legal(self) -> bool:
        return not self.errors


_CHECKS = (
    check_unreadable,
    check_deck_size,
    check_commanders,
    check_copies,
    check_color_identity,
    check_legality,
)


def validate(deck: ParsedDeck, lookup: CardLookup) -> ValidationReport:
    """Run every check on the deck, then add the notes."""
    cards: dict[str, Card] = {}
    for entry in [*deck.cards, *deck.commanders]:
        card = lookup.find(entry.name)
        if card is not None:  # a hand-built deck may name a card we don't know
            cards[entry.oracle_id] = card

    report = ValidationReport()
    for check in _CHECKS:  # functions in a tuple: run each one the same way
        report.errors.extend(check(deck, cards))

    changers = [
        cards[e.oracle_id].name
        for e in deck.cards
        if e.oracle_id in cards and cards[e.oracle_id].is_game_changer
    ]
    summary = f"Game Changers: {len(changers)}"
    if changers:
        summary += f" ({', '.join(changers)})"
    report.notes.append(Issue("game_changers", summary))
    if len(deck.commanders) == 2:
        report.notes.append(
            Issue(
                "pairing_unchecked",
                "Commander pairing not checked yet (Partner/Background rules come later).",
            )
        )
    if deck.left_out:
        count = sum(entry.quantity for entry in deck.left_out)
        if count == 1:
            message = (
                "1 left-out card (sideboard, maybeboard, companion) wasn't checked."
            )
        else:
            message = f"{count} left-out cards (sideboard, maybeboard, companion) weren't checked."
        report.notes.append(Issue("left_out", message))
    return report
