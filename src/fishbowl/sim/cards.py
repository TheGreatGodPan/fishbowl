"""Sorting cards into the kinds the goldfish simulation cares about.

A `PlayCard` is a card boiled down to what the game loop needs: its cost,
what mana it makes, and what it does when cast. Everything else is ignored.
"""

import re
from dataclasses import dataclass
from typing import Literal

from fishbowl.deck.lookup import Card, CardLookup
from fishbowl.deck.model import ParsedDeck
from fishbowl.stats.curve import colour_pips
from fishbowl.stats.groups import is_mana_dork
from fishbowl.stats.lands import is_land

# Literal: a type that only allows these exact strings, so a typo is caught by the checker.
Kind = Literal["land", "fetch", "rock", "dork", "ramp", "draw", "generic"]

# Reminder text "(...)" and quoted text "..." describe things the card is not (yet).
_NOT_OWN_ABILITY = re.compile(r"\([^)]*\)|\"[^\"]*\"")
_FETCH = re.compile(r"search your library for a basic land", re.IGNORECASE)
_TAP_ADD = re.compile(r"\{T\}[^.]*: Add ")
_RAMP = re.compile(
    r"search your library for [^.]*(land|plains|island|swamp|mountain|forest) "
    r"cards?[^.]*onto the battlefield",
    re.IGNORECASE,
)
_DRAW = re.compile(r"\bdraw (a|one|two|three|four|five) cards?\b", re.IGNORECASE)
_MANA_SYMBOL = re.compile(r"\{[^}]*\}")
_DRAW_WORDS = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_COLOUR_ORDER = "WUBRG"


@dataclass(frozen=True)
class PlayCard:
    """One card as the simulation sees it. Frozen: it never changes mid-game."""

    name: str
    kind: Kind
    mana_value: int
    pips: dict[str, int]
    colours: str  # mana it can produce, "" if none
    amount: int  # mana per tap, 0 for non-producers
    enters_tapped: bool
    ramp_lands: int  # basics put onto the battlefield
    ramp_to_hand: int  # basics put into the hand
    ramp_tapped: bool  # do the battlefield lands enter tapped?
    draws: int
    is_basic: bool


def _front(card: Card) -> str:
    """The front face's type line (double-faced cards: front only)."""
    return (card.type_line or "").split(" // ")[0]


def _kind(card: Card, text: str) -> Kind:
    """The first matching kind, checked in the spec's order."""
    front_words = _front(card).split()
    if is_land(card.type_line):
        if not card.produced_mana and _FETCH.search(text):
            return "fetch"
        return "land"
    if is_mana_dork(card):  # already ignores reminder and quoted text itself
        return "dork"
    artifact_only = "Artifact" in front_words and "Creature" not in front_words
    if artifact_only and _TAP_ADD.search(text):
        return "rock"
    spell = "Sorcery" in front_words or "Instant" in front_words
    if spell and _RAMP.search(text):
        return "ramp"
    if spell and _DRAW.search(text):
        return "draw"
    return "generic"


def _mana_amount(text: str) -> int:
    """Mana per tap: the {..} symbols after "Add " in the first tap ability."""
    found = _TAP_ADD.search(text)
    if found is None:
        return 1
    ability = text[found.end() :].split(".")[0]
    # "one mana of any color" or "X mana" has no symbols: count it as 1.
    return len(_MANA_SYMBOL.findall(ability)) or 1


def _ramp_details(text: str) -> tuple[int, int, bool]:
    """(lands to battlefield, lands to hand, enter tapped) for a ramp spell."""
    lower = text.lower()
    start = lower.find("search your library")
    clause = lower[start:].split(".")[0]
    two = "up to two" in clause and "put one onto the battlefield" not in clause
    to_hand = 1 if "the other into your hand" in clause else 0
    return (2 if two else 1), to_hand, "tapped" in clause


def classify(card: Card, commander_identity: str = "") -> PlayCard:
    """Turn a database card into a PlayCard."""
    text = _NOT_OWN_ABILITY.sub("", card.oracle_text or "")
    kind = _kind(card, text)

    colours = ""
    amount = 0
    if kind == "land":
        colours = card.produced_mana
        amount = 1 if colours else 0
    elif kind == "fetch":
        # A fetch can find whatever the commander needs.
        colours = "".join(c for c in _COLOUR_ORDER if c in commander_identity) or "C"
        amount = 1
    elif kind in ("rock", "dork"):
        colours = card.produced_mana
        amount = _mana_amount(text) if colours else 0

    enters_tapped = kind == "fetch" or (
        kind == "land"
        and ("enters tapped" in text or "enters the battlefield tapped" in text)
    )

    ramp_lands, ramp_to_hand, ramp_tapped = (
        _ramp_details(text) if kind == "ramp" else (0, 0, False)
    )
    draws = 0
    if kind == "draw":
        found = _DRAW.search(text)
        draws = _DRAW_WORDS[found.group(1).lower()] if found else 0

    return PlayCard(
        name=card.name,
        kind=kind,
        mana_value=int(card.cmc or 0),
        pips=colour_pips(card.mana_cost),
        colours=colours,
        amount=amount,
        enters_tapped=enters_tapped,
        ramp_lands=ramp_lands,
        ramp_to_hand=ramp_to_hand,
        ramp_tapped=ramp_tapped,
        draws=draws,
        is_basic="Basic" in (card.type_line or "").split(),
    )


def deck_play_cards(
    deck: ParsedDeck, lookup: CardLookup
) -> tuple[list[PlayCard], list[PlayCard]]:
    """(library cards, commander cards). One entry per copy; unknown cards are skipped."""
    # Fetches need the commanders' colours, so look the commanders up first.
    commanders = [lookup.find(entry.name) for entry in deck.commanders]
    identity = "".join(card.color_identity for card in commanders if card is not None)

    # Same commander rule as library_counts: one copy of each is in the command zone.
    commander_ids = {entry.oracle_id for entry in deck.commanders}
    library: list[PlayCard] = []
    for entry in deck.cards:
        copies = entry.quantity - (1 if entry.oracle_id in commander_ids else 0)
        card = lookup.find(entry.name)
        if card is not None:
            library.extend([classify(card, identity)] * copies)
    command = [classify(card, identity) for card in commanders if card is not None]
    return library, command
