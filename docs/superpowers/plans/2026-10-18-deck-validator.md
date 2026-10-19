# Deck Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Check a parsed Commander deck against the deck-building rules, reporting errors and notes, and show the result in the deck command.

**Architecture:** `Card` (in `lookup.py`) gains `color_identity`, `commander_status` and `is_game_changer`. A new `src/fishbowl/deck/validator.py` has one small function per check plus `validate()`, which returns a `ValidationReport`. The deck command in `parser.py` prints the report.

**Tech Stack:** Python 3.12, standard library only, pytest.

**Spec:** `docs/superpowers/specs/2026-10-18-deck-validator-design.md`

## Global Constraints

- Python 3.12+, run through `uv run`. No new dependencies. `pathlib` for paths.
- Format rules come from card data (`commander_status`, `is_game_changer`, `type_line`, `oracle_text`), not hard-coded card lists. The only constants are `DECK_SIZE = 100` and the number words one–ten.
- Fail closed: parser problems mean the deck is not legal.
- No bracket verdict. Game Changers are reported as a note.
- Two commanders: pairing is not checked. The note `pairing_unchecked` says so, and color identity uses both commanders combined.
- Tests write only to `tmp_path`. The real `data/cards.db` is read only in `tests/deck/test_real_decks.py`, which skips when it's missing.
- Test data is copied from real Scryfall records.
- Agents never run `git add`/`commit`/`push`. "Commit (Ian)" steps list his commands.
- Every touched `.py` file passes `ruff format`, `ruff check` and `~/.local/bin/basedpyright.exe --level error -p C:/Users/iwsch/.claude/hooks/basedpyright-default.json <file>`. Narrow optionals with `assert x is not None`.

## Review Focus

1. **A deck with no commander:** this must report `no_commander` and skip `off_color`, not crash or flag every card as off-color. (Task 2 test `test_off_color_skipped_without_commander`.)
2. **A colorless commander** (identity `""`): every colored card is off-color, and the message says `colorless`. (Task 2 test `test_colorless_commander_message`.)
3. **A card whose limit text uses an unexpected number word:** the limit must fall back to 1, not crash. (Task 2 test `test_unknown_number_word_falls_back_to_one`.)
4. **Deck-size wording for one unreadable line:** this must be singular (`1 line couldn't …`). (Task 2 test `test_one_unreadable_line_is_singular`.)
5. **A card missing from the lookup during validation** (for example, a hand-built `ParsedDeck`): it must be skipped, not raise `KeyError`. (Task 3 test `test_card_missing_from_lookup_is_skipped`.)

---

### Task 1: Richer `Card` and new real-card fixtures

**Files:**
- Modify: `src/fishbowl/deck/lookup.py`, `tests/conftest.py`, `tests/deck/test_lookup.py`

**Interfaces:**
- Consumes: the existing `Card` and `CardLookup`; `card_db` in `tests/conftest.py`.
- Produces:
  - `Card(oracle_id: str, name: str, type_line: str | None, oracle_text: str | None, color_identity: str, commander_status: str, is_game_changer: bool)`, frozen.
  - Fixture constants `FOREST`, `RELENTLESS_RATS`, `SEVEN_DWARVES`, `SYLVAN_PRIMORDIAL`, `ABSORB_ENERGY`, `SURVIVAL`, all included in `card_db`.

- [ ] **Step 1: Add the fixtures.** In `tests/conftest.py`, add these constants after `COMMAND_TOWER`. They are copied from `data/oracle-cards.jsonl.gz` on 2026-10-18:

```python
FOREST = {
    "object": "card",
    "oracle_id": "b34bb2dc-c1af-4d77-b0b3-a0fb342a5fc6",
    "name": "Forest",
    "layout": "normal",
    "mana_cost": "",
    "cmc": 0.0,
    "type_line": "Basic Land \u2014 Forest",
    "oracle_text": "({T}: Add {G}.)",
    "colors": [],
    "color_identity": ["G"],
    "produced_mana": ["G"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}

RELENTLESS_RATS = {
    "object": "card",
    "oracle_id": "104ea189-14cd-420f-afdc-57b0f827ab8e",
    "name": "Relentless Rats",
    "layout": "normal",
    "mana_cost": "{1}{B}{B}",
    "cmc": 3.0,
    "type_line": "Creature \u2014 Rat",
    "oracle_text": (
        "This creature gets +1/+1 for each other creature on the battlefield "
        "named Relentless Rats.\nA deck can have any number of cards named "
        "Relentless Rats."
    ),
    "colors": ["B"],
    "color_identity": ["B"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}

SEVEN_DWARVES = {
    "object": "card",
    "oracle_id": "526ca4a9-3f50-4f7a-8169-2bda95792401",
    "name": "Seven Dwarves",
    "layout": "normal",
    "mana_cost": "{1}{R}",
    "cmc": 2.0,
    "type_line": "Creature \u2014 Dwarf",
    "oracle_text": (
        "This creature gets +1/+1 for each other creature named Seven Dwarves "
        "you control.\nA deck can have up to seven cards named Seven Dwarves."
    ),
    "colors": ["R"],
    "color_identity": ["R"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}

SYLVAN_PRIMORDIAL = {
    "object": "card",
    "oracle_id": "52b88034-bf0f-4d29-b776-40ce421f1107",
    "name": "Sylvan Primordial",
    "layout": "normal",
    "mana_cost": "{5}{G}{G}",
    "cmc": 7.0,
    "type_line": "Creature \u2014 Avatar",
    "oracle_text": (
        "Reach\nWhen this creature enters, for each opponent, destroy target "
        "noncreature permanent that player controls. Search your library for up "
        "to X Forest cards, where X is the number of permanents destroyed this "
        "way, put those cards onto the battlefield tapped, then shuffle."
    ),
    "colors": ["G"],
    "color_identity": ["G"],
    "keywords": ["Reach"],
    "legalities": {"commander": "banned", "vintage": "legal", "legacy": "legal"},
    "game_changer": False,
}

# An Alchemy card: legal in some digital formats, not_legal in Commander.
ABSORB_ENERGY = {
    "object": "card",
    "oracle_id": "3010f11c-8ee1-4854-96d2-ae33ea3fe4e8",
    "name": "Absorb Energy",
    "layout": "normal",
    "mana_cost": "{1}{U}{U}",
    "cmc": 3.0,
    "type_line": "Instant",
    "oracle_text": (
        "Counter target spell. Cards in your hand that share a card type with "
        'that spell perpetually gain "This spell costs {1} less to cast."'
    ),
    "colors": ["U"],
    "color_identity": ["U"],
    "keywords": [],
    "legalities": {"historic": "legal", "brawl": "legal", "commander": "not_legal"},
    "game_changer": False,
}

SURVIVAL = {
    "object": "card",
    "oracle_id": "119d719d-e965-45b4-9bc9-ac03211b10c2",
    "name": "Survival of the Fittest",
    "layout": "normal",
    "mana_cost": "{1}{G}",
    "cmc": 2.0,
    "type_line": "Enchantment",
    "oracle_text": (
        "{G}, Discard a creature card: Search your library for a creature card, "
        "reveal that card, put it into your hand, then shuffle."
    ),
    "colors": ["G"],
    "color_identity": ["G"],
    "keywords": [],
    "legalities": {"commander": "legal", "vintage": "legal", "legacy": "banned"},
    "game_changer": True,
}
```

Add all six to the tuple of cards written in `card_db` (after `COMMAND_TOWER`), and update `card_db`'s docstring to list them.

- [ ] **Step 2: Write the failing test.** In `tests/deck/test_lookup.py`, replace `test_finds_exact_name` with the version below, and append the new test:

```python
def test_finds_exact_name(card_db):
    with CardLookup(card_db) as lookup:
        card = lookup.find("Sol Ring")
    assert card == Card(
        oracle_id="6ad8011d-3471-4369-9d68-b264cc027487",
        name="Sol Ring",
        type_line="Artifact",
        oracle_text="{T}: Add {C}{C}.",
        color_identity="",
        commander_status="legal",
        is_game_changer=False,
    )


def test_card_carries_rules_fields(card_db):
    with CardLookup(card_db) as lookup:
        survival = lookup.find("Survival of the Fittest")
        primordial = lookup.find("Sylvan Primordial")
    assert survival is not None
    assert primordial is not None
    assert survival.color_identity == "G"
    assert survival.is_game_changer is True  # a real bool, not SQLite's 1
    assert primordial.commander_status == "banned"
```

- [ ] **Step 3: Run the tests to verify they fail.**

Run: `uv run pytest tests/deck/test_lookup.py -v`
Expected: FAIL with `TypeError: Card.__init__() got an unexpected keyword argument 'color_identity'`.

- [ ] **Step 4: Write the implementation** in `src/fishbowl/deck/lookup.py`. Replace both queries and `Card`, and change the `return` in `find`:

```python
_FIELDS = (
    "c.oracle_id, c.name, c.type_line, c.oracle_text, "
    "c.color_identity, c.commander_status, c.is_game_changer"
)
_BY_NAME = f"SELECT {_FIELDS} FROM cards AS c WHERE c.name = ? COLLATE NOCASE"
# The alias column is declared COLLATE NOCASE, so this match ignores case too.
_BY_ALIAS = f"""
SELECT {_FIELDS}
FROM card_aliases AS a JOIN cards AS c ON c.oracle_id = a.oracle_id
WHERE a.alias = ?
"""


@dataclass(frozen=True)
class Card:
    """The card fields the deck code needs."""

    oracle_id: str
    name: str
    type_line: str | None
    oracle_text: str | None
    color_identity: str  # WUBRG letters, "" if colorless
    commander_status: str  # "legal", "banned", "not_legal", ...
    is_game_changer: bool
```

In `find`, replace `return Card(*row) if row is not None else None` with:

```python
        if row is None:
            return None
        *fields, game_changer = row
        return Card(*fields, is_game_changer=bool(game_changer))  # SQLite stores 1/0
```

(`_FIELDS` holds only fixed column names, never user input. The name is still passed as a `?` placeholder.)

- [ ] **Step 5: Run all the tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 6: Commit (Ian).**

```bash
git add src/fishbowl/deck/lookup.py tests/conftest.py tests/deck/test_lookup.py
git commit -m "Add color identity, legality and Game Changer fields to Card"
```

---

### Task 2: The checks in `validator.py`

**Files:**
- Create: `src/fishbowl/deck/validator.py`
- Test: `tests/deck/test_validator_checks.py`

**Interfaces:**
- Consumes:
  - `Card`, `CardLookup` (Task 1)
  - `ParsedDeck`, `DeckEntry`, `Problem` (`model.py`)
  - `parse_deck` (`parser.py`, in tests only)
  - `can_be_commander(card: Card) -> bool` (`commander.py`)
  - fixture `card_db`
- Produces:
  - `DECK_SIZE = 100`
  - `@dataclass(frozen=True) Issue(code: str, message: str)`
  - `copy_limit(card: Card) -> int | None`
  - the checks, each `(deck: ParsedDeck, cards: dict[str, Card]) -> list[Issue]`:
    - `check_unreadable`
    - `check_deck_size`
    - `check_commanders`
    - `check_copies`
    - `check_color_identity`
    - `check_legality`

- [ ] **Step 1: Write the failing tests** in `tests/deck/test_validator_checks.py`:

```python
"""Tests for each deck-building check, one at a time."""

import dataclasses

import pytest

from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.model import ParsedDeck, Problem
from fishbowl.deck.parser import parse_deck
from fishbowl.deck.validator import (
    Issue,
    check_color_identity,
    check_commanders,
    check_copies,
    check_deck_size,
    check_legality,
    check_unreadable,
    copy_limit,
)

GORECLAW = "Goreclaw, Terror of Qal Sisma"


@pytest.fixture
def lookup(card_db):
    with CardLookup(card_db) as opened:
        yield opened


def parsed(text, lookup):
    """Parse text and gather the Card for every card in it, keyed by oracle_id."""
    deck = parse_deck(text, lookup)
    cards = {}
    for entry in [*deck.cards, *deck.commanders]:
        card = lookup.find(entry.name)
        assert card is not None
        cards[entry.oracle_id] = card
    return deck, cards


def codes(issues):
    return [issue.code for issue in issues]


# --- copy_limit ---


@pytest.mark.parametrize(
    ("name", "limit"),
    [
        ("Sol Ring", 1),
        ("Forest", None),  # basic land: any number
        ("Relentless Rats", None),  # "any number of cards named"
        ("Seven Dwarves", 7),  # "up to seven cards named"
    ],
)
def test_copy_limit(lookup, name, limit):
    card = lookup.find(name)
    assert card is not None
    assert copy_limit(card) == limit


def test_unknown_number_word_falls_back_to_one(lookup):
    card = lookup.find("Seven Dwarves")
    assert card is not None
    odd = dataclasses.replace(card, oracle_text="A deck can have up to umpteen cards named Seven Dwarves.")
    assert copy_limit(odd) == 1


# --- unreadable lines ---


def test_unreadable_lines_plural():
    deck = ParsedDeck(problems=[Problem(2, "x", "r"), Problem(5, "y", "r")])
    assert check_unreadable(deck, {}) == [
        Issue("unreadable_lines", "2 lines couldn't be read, so the deck can't be fully checked.")
    ]


def test_one_unreadable_line_is_singular():
    deck = ParsedDeck(problems=[Problem(2, "x", "r")])
    assert check_unreadable(deck, {})[0].message == (
        "1 line couldn't be read, so the deck can't be fully checked."
    )


def test_no_problems_no_issue():
    assert check_unreadable(ParsedDeck(), {}) == []


# --- deck size ---


def test_exactly_100_is_fine(lookup):
    deck, cards = parsed(f"Commander: {GORECLAW}\n99 Forest\n", lookup)
    assert check_deck_size(deck, cards) == []


def test_wrong_size_is_an_error(lookup):
    deck, cards = parsed(f"Commander: {GORECLAW}\n98 Forest\n", lookup)
    assert check_deck_size(deck, cards) == [
        Issue("deck_size", "Deck has 99 cards; a Commander deck needs exactly 100.")
    ]


# --- commanders ---


def test_no_commander(lookup):
    deck, cards = parsed("1 Sol Ring\n", lookup)
    assert check_commanders(deck, cards) == [Issue("no_commander", "No commander identified.")]


def test_eligible_commanders_are_fine(lookup):
    for name in (GORECLAW, "Teferi, Temporal Archmage"):  # creature, and "can be your commander"
        deck, cards = parsed(f"Commander: {name}\n", lookup)
        assert check_commanders(deck, cards) == []


def test_ineligible_commander(lookup):
    deck, cards = parsed("Commander: Sol Ring\n", lookup)
    assert check_commanders(deck, cards) == [
        Issue("ineligible_commander", "Sol Ring can't be a commander (it isn't a legendary creature).")
    ]


# --- copies ---


def test_two_sol_rings(lookup):
    deck, cards = parsed("2 Sol Ring\n50 Forest\n30 Relentless Rats\n7 Seven Dwarves\n", lookup)
    assert check_copies(deck, cards) == [Issue("too_many_copies", "2 copies of Sol Ring; only 1 allowed.")]


def test_eight_dwarves(lookup):
    deck, cards = parsed("8 Seven Dwarves\n", lookup)
    assert check_copies(deck, cards) == [
        Issue("too_many_copies", "8 copies of Seven Dwarves; up to 7 allowed.")
    ]


# --- color identity ---


def test_on_color_deck_is_fine(lookup):
    deck, cards = parsed(f"Commander: {GORECLAW}\n1 Sol Ring\n1 Forest\n1 The Great Henge\n", lookup)
    assert check_color_identity(deck, cards) == []


def test_off_color_card(lookup):
    deck, cards = parsed(f"Commander: {GORECLAW}\n1 Witch Enchanter\n", lookup)
    assert check_color_identity(deck, cards) == [
        Issue(
            "off_color",
            "Witch Enchanter // Witch-Blessed Meadow (W) is outside the commander's color identity (G).",
        )
    ]


def test_two_commanders_combine_identity(lookup):
    text = f"Commander\n1 {GORECLAW}\n1 Krenko, Mob Boss\nDeck\n1 Forest\n1 Seven Dwarves\n"
    deck, cards = parsed(text, lookup)
    assert check_color_identity(deck, cards) == []  # G + R covers both


def test_off_color_skipped_without_commander(lookup):
    deck, cards = parsed("1 Witch Enchanter\n1 Forest\n", lookup)
    assert check_color_identity(deck, cards) == []  # no_commander already reports it


def test_colorless_commander_message(lookup):
    # A colorless commander: build one by giving Goreclaw an empty identity in memory.
    deck, cards = parsed(f"Commander: {GORECLAW}\n1 Forest\n", lookup)
    commander_id = deck.commanders[0].oracle_id
    cards[commander_id] = dataclasses.replace(cards[commander_id], color_identity="")
    assert check_color_identity(deck, cards) == [
        Issue("off_color", "Forest (G) is outside the commander's color identity (colorless).")
    ]


# --- legality ---


def test_banned_and_not_legal(lookup):
    deck, cards = parsed("1 Sylvan Primordial\n1 Absorb Energy\n1 Sol Ring\n", lookup)
    assert check_legality(deck, cards) == [
        Issue("banned", "Sylvan Primordial is banned in Commander."),
        Issue("not_legal", "Absorb Energy is not legal in Commander (not_legal)."),
    ]
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `uv run pytest tests/deck/test_validator_checks.py -v`
Expected: collection ERROR, `ModuleNotFoundError: No module named 'fishbowl.deck.validator'`.

- [ ] **Step 3: Write the implementation** in `src/fishbowl/deck/validator.py`:

```python
"""Checking a parsed deck against Commander's deck-building rules."""

import re
from dataclasses import dataclass

from fishbowl.deck.commander import can_be_commander
from fishbowl.deck.lookup import Card
from fishbowl.deck.model import ParsedDeck

DECK_SIZE = 100
_COLOR_ORDER = "WUBRG"
# "A deck can have up to seven cards named Seven Dwarves." (also Nazgûl: nine)
_UP_TO = re.compile(r"can have up to (\w+) cards named", re.IGNORECASE)
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
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
    return [Issue("unreadable_lines", f"{lines} couldn't be read, so the deck can't be fully checked.")]


def check_deck_size(deck: ParsedDeck, cards: dict[str, Card]) -> list[Issue]:
    if deck.total == DECK_SIZE:
        return []
    message = f"Deck has {deck.total} cards; a Commander deck needs exactly {DECK_SIZE}."
    return [Issue("deck_size", message)]


def check_commanders(deck: ParsedDeck, cards: dict[str, Card]) -> list[Issue]:
    if not deck.commanders:
        return [Issue("no_commander", "No commander identified.")]
    issues = []
    for entry in deck.commanders:
        card = cards.get(entry.oracle_id)
        if card is not None and not can_be_commander(card):
            message = f"{card.name} can't be a commander (it isn't a legendary creature)."
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
        issues.append(Issue("too_many_copies", f"{entry.quantity} copies of {card.name}; {allowed}."))
    return issues


def check_color_identity(deck: ParsedDeck, cards: dict[str, Card]) -> list[Issue]:
    """Every card's identity must fit inside the commanders' combined identity."""
    commander_cards = [cards[e.oracle_id] for e in deck.commanders if e.oracle_id in cards]
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
            message = f"{card.name} is not legal in Commander ({card.commander_status})."
            issues.append(Issue("not_legal", message))
    return issues
```

- [ ] **Step 4: Run all the tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 5: Commit (Ian).**

```bash
git add src/fishbowl/deck/validator.py tests/deck/test_validator_checks.py
git commit -m "Add Commander deck checks: size, commander, copies, colors, legality"
```

---

### Task 3: `validate()`, notes, and the broken deck

**Files:**
- Modify: `src/fishbowl/deck/validator.py`
- Test: `tests/deck/test_validate.py`

**Interfaces:**
- Consumes: the Task 2 checks and `Issue`; `CardLookup`; `parse_deck`; fixture `card_db`.
- Produces:
  - `@dataclass ValidationReport(errors: list[Issue], notes: list[Issue])`, with both defaulting to empty, plus the property `is_legal -> bool`
  - `validate(deck: ParsedDeck, lookup: CardLookup) -> ValidationReport`

- [ ] **Step 1: Write the failing tests** in `tests/deck/test_validate.py`:

```python
"""Tests for validate(): all checks together, plus notes."""

import pytest

from fishbowl.deck.lookup import CardLookup
from fishbowl.deck.model import DeckEntry, ParsedDeck
from fishbowl.deck.parser import parse_deck
from fishbowl.deck.validator import Issue, validate

GORECLAW = "Goreclaw, Terror of Qal Sisma"


@pytest.fixture
def lookup(card_db):
    with CardLookup(card_db) as opened:
        yield opened


def test_legal_deck(lookup):
    deck = parse_deck(f"Commander: {GORECLAW}\n1 Sol Ring\n98 Forest\n", lookup)
    report = validate(deck, lookup)
    assert report.errors == []
    assert report.is_legal is True
    assert report.notes == [Issue("game_changers", "Game Changers: 0")]


def test_game_changers_are_named(lookup):
    deck = parse_deck(f"Commander: {GORECLAW}\n1 Survival of the Fittest\n98 Forest\n", lookup)
    report = validate(deck, lookup)
    assert report.is_legal is True
    assert report.notes == [Issue("game_changers", "Game Changers: 1 (Survival of the Fittest)")]


def test_broken_deck_reports_every_error(lookup):
    text = (
        "Commander: Sol Ring\n"  # ineligible commander
        "2 Sol Ring\n"  # too many copies
        "1 Witch Enchanter\n"  # off-color (W) for a colorless commander
        "1 Sylvan Primordial\n"  # banned (and off-color)
        "1 Absorb Energy\n"  # not legal (and off-color)
        "1 Not A Real Card\n"  # unreadable
    )
    report = validate(parse_deck(text, lookup), lookup)
    assert report.is_legal is False
    assert [issue.code for issue in report.errors] == [
        "unreadable_lines",
        "deck_size",
        "ineligible_commander",
        "too_many_copies",
        "off_color",
        "off_color",
        "off_color",
        "banned",
        "not_legal",
    ]


def test_no_commander_error(lookup):
    report = validate(parse_deck("1 Sol Ring\n99 Forest\n", lookup), lookup)
    assert [issue.code for issue in report.errors] == ["no_commander"]


def test_two_commanders_note(lookup):
    text = f"Commander\n1 {GORECLAW}\n1 Krenko, Mob Boss\nDeck\n98 Forest\n"
    report = validate(parse_deck(text, lookup), lookup)
    assert report.is_legal is True
    assert Issue(
        "pairing_unchecked",
        "Commander pairing not checked yet (Partner/Background rules come later).",
    ) in report.notes


def test_left_out_note(lookup):
    text = f"Commander: {GORECLAW}\n99 Forest\nSideboard\n2 Sol Ring\n1 Krenko, Mob Boss\n"
    report = validate(parse_deck(text, lookup), lookup)
    assert report.is_legal is True  # sideboard cards aren't checked
    assert Issue(
        "left_out", "3 left-out cards (sideboard, maybeboard, companion) weren't checked."
    ) in report.notes


def test_card_missing_from_lookup_is_skipped(lookup):
    deck = ParsedDeck(
        cards=[DeckEntry("Imaginary Card", "no-such-id", 1)],
        commanders=[DeckEntry("Imaginary Card", "no-such-id", 1)],
    )
    report = validate(deck, lookup)  # must not raise
    assert "deck_size" in [issue.code for issue in report.errors]
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `uv run pytest tests/deck/test_validate.py -v`
Expected: collection ERROR, `ImportError: cannot import name 'validate'`.

- [ ] **Step 3: Write the implementation.** In `src/fishbowl/deck/validator.py`:
  - change `from dataclasses import dataclass` to `from dataclasses import dataclass, field`
  - change the lookup import to `from fishbowl.deck.lookup import Card, CardLookup`
  - append:

```python
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
        report.notes.append(
            Issue(
                "left_out",
                f"{count} left-out cards (sideboard, maybeboard, companion) weren't checked.",
            )
        )
    return report
```

- [ ] **Step 4: Run all the tests to verify they pass.**

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 5: Commit (Ian).**

```bash
git add src/fishbowl/deck/validator.py tests/deck/test_validate.py
git commit -m "Add validate(): full Commander check with Game Changer notes"
```

---

### Task 4: Show the report in the deck command, real decks, roadmap

**Files:**
- Modify: `src/fishbowl/deck/parser.py` (`main`), `tests/deck/test_parser_main.py`, `tests/deck/test_real_decks.py`, `docs/ROADMAP.md`

**Interfaces:**
- Consumes: `validate`, `ValidationReport` (Task 3).
- Produces: `main(...)` prints the validation report and returns 0 only when the deck is legal.

- [ ] **Step 1: Write the failing tests.** In `tests/deck/test_parser_main.py`:
  - In `test_clean_deck_with_commander`, change `assert code == 0` to `assert code == 1  # 2 cards: parses fine but isn't a legal deck`, and add `assert "Legal: no (1 errors)" in shown`.
  - In `test_asks_for_commander_when_unknown`, change `assert code == 0` to `assert code == 1  # 3 cards: not a legal deck`.
  - Append:

```python
def test_legal_deck_prints_report_and_exits_0(tmp_path, card_db):
    deck = tmp_path / "deck.txt"
    deck.write_text(f"Commander: {GORECLAW}\n1 {GORECLAW}\n1 Sol Ring\n98 Forest\n", encoding="utf-8")
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
    assert "Legal: no (1 errors)" in shown
    assert "Errors:" in shown
    assert "  2 copies of Sol Ring; only 1 allowed." in shown
```

In `tests/deck/test_real_decks.py`:
- add `from fishbowl.deck.validator import validate`
- append:

```python
@pytest.mark.parametrize("filename", ["goreclaw.txt", "ghalta.txt", "krenko.txt"])
def test_real_deck_is_legal(filename):
    text = (DECKS / filename).read_text(encoding="utf-8")
    with CardLookup(REAL_DB) as lookup:
        report = validate(parse_deck(text, lookup), lookup)
    assert report.errors == []
    assert report.notes[0].message == "Game Changers: 0"
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `uv run pytest tests/deck/test_parser_main.py -v`
Expected: the new tests FAIL (no `Legal:` line yet). The two edited tests FAIL with `assert 0 == 1`. `test_real_deck_is_legal` should already PASS, because `validate` exists from Task 3. That's fine: it confirms the real decks.

- [ ] **Step 3: Write the implementation.** In `src/fishbowl/deck/parser.py`:
  - add `from fishbowl.deck.validator import validate`
  - change `main`'s docstring to `"""Parse and check a decklist file. Returns 0 only for a legal, fully readable deck."""`
  - move `report = validate(deck, lookup)` inside the `with CardLookup(db_path) as lookup:` block, as its last statement after the commander prompt, because the lookup must still be open
  - replace the final `return 1 if deck.problems else 0` with:

```python
    if report.is_legal:
        write("Legal: yes")
    else:
        write(f"Legal: no ({len(report.errors)} errors)")
        write("Errors:")
        for issue in report.errors:
            write(f"  {issue.message}")
    if report.notes:
        write("Notes:")
        for issue in report.notes:
            write(f"  {issue.message}")
    return 0 if report.is_legal else 1
```

(`validator.py` imports `commander.py`, `lookup.py` and `model.py`, never `parser.py`, so there's no import cycle.)

- [ ] **Step 4: Run all the tests, then the real decks.**

Run: `uv run pytest`
Expected: all pass, none skipped.

Then, for each of `goreclaw`, `ghalta` and `krenko`, run:
```
uv run python -m fishbowl.deck.parser tests/decks/<name>.txt </dev/null
```
Expected for each: `Deck: 100 cards`, the right commander, `Legal: yes`, `Notes:`, `  Game Changers: 0`, and exit code 0.

- [ ] **Step 5: Mark Stage 3 in the roadmap.** In `docs/ROADMAP.md`:
  - change `### 🔄 Stage 3: Deck validator` to `### ✅ Stage 3: Deck validator`
  - change `### ⬜ Stage 4: Opening-hand stats` to `### 🔄 Stage 4: Opening-hand stats`
  - in the Stage 3 paragraph, change the words `partner/Background pairings later.` to `partner/Background pairings later (reported as a note, not checked yet).`

- [ ] **Step 6: Commit (Ian).**

```bash
git add src/fishbowl/deck/parser.py tests/deck/test_parser_main.py tests/deck/test_real_decks.py docs/ROADMAP.md
git commit -m "Show deck validation in the deck command; Stage 3 complete"
```
