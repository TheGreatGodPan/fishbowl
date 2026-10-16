"""The result of parsing a decklist."""

from dataclasses import dataclass, field


@dataclass
class DeckEntry:
    """One card in the deck and how many copies."""

    name: str  # real card name from the database
    oracle_id: str
    quantity: int


@dataclass
class Problem:
    """A line the parser couldn't use, and why."""

    line_number: int  # 1-based; 0 means the whole list
    text: str  # the original line, trimmed to 200 characters
    reason: str


@dataclass
class ParsedDeck:
    """Cards (including commanders), the commanders, left-out cards and problems."""

    # default_factory: each deck gets its own new list, not one shared list.
    cards: list[DeckEntry] = field(default_factory=list)
    commanders: list[DeckEntry] = field(default_factory=list)
    left_out: list[DeckEntry] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Number of cards in the deck, commanders included."""
        return sum(entry.quantity for entry in self.cards)
