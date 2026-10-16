"""Finding commander candidates in a deck, and asking the user to pick one."""

from collections.abc import Callable

from fishbowl.deck.lookup import Card, CardLookup
from fishbowl.deck.model import ParsedDeck


def can_be_commander(card: Card) -> bool:
    """True for legendary creatures and cards whose text says "can be your commander"."""
    type_line = card.type_line or ""
    text = card.oracle_text or ""
    legendary_creature = "Legendary" in type_line and "Creature" in type_line
    return legendary_creature or "can be your commander" in text


def commander_candidates(deck: ParsedDeck, lookup: CardLookup) -> list[str]:
    """Names in the deck that could be a commander: legendary creatures, or cards
    whose text says "can be your commander". Sorted by name."""
    names = []
    for entry in deck.cards:
        card = lookup.find(entry.name)
        if card is None:
            continue
        if can_be_commander(card):
            names.append(card.name)
    return sorted(names)


def ask_for_commander(
    candidates: list[str],
    read: Callable[[str], str] = input,
    write: Callable[[str], object] = print,
) -> str | None:
    """Show candidates; letters filter the list, a number picks, Enter skips.

    read and write are parameters so tests can pass fakes instead of a keyboard.
    """
    if not candidates:
        write("No commander candidates found in this deck.")
        return None
    shown = list(candidates)
    while True:
        write("Which card is your commander?")
        for number, name in enumerate(shown, start=1):
            write(f"  {number}. {name}")
        try:
            answer = read("Number to pick, letters to search, Enter to skip: ").strip()
        except EOFError:
            return None  # no keyboard (piped input or Ctrl+Z): skip instead of crashing
        if not answer:
            return None
        if answer.isdecimal():
            index = int(answer)
            if 1 <= index <= len(shown):
                return shown[index - 1]
            write(f"Pick a number from 1 to {len(shown)}.")
            continue
        matches = [name for name in candidates if answer.lower() in name.lower()]
        if matches:
            shown = matches
        else:
            write(f'No candidates match "{answer}".')
