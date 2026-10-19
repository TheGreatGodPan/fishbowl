"""Finding commander candidates in a deck, and asking the user to pick one."""

from collections.abc import Callable

from fishbowl.deck.lookup import Card, CardLookup
from fishbowl.deck.model import ParsedDeck


def can_be_commander(card: Card) -> bool:
    """True for legendary creatures and cards whose text says "can be your commander"."""
    # Only the front face counts: a "Land // Legendary Creature" is cast as a land.
    front = (card.type_line or "").split(" // ")[0]
    text = card.oracle_text or ""
    legendary_creature = "Legendary" in front and "Creature" in front
    # Grist, the Hunger Tide is a legendary planeswalker that is a creature while
    # in the command zone ("As long as Grist isn't on the battlefield, it's a ...").
    marker = "isn't on the battlefield, it's a"
    creature_off_battlefield = (
        "Legendary" in front
        and marker in text
        and "creature" in text.split(marker, 1)[1].split(".", 1)[0]
    )
    return (
        legendary_creature
        or creature_off_battlefield
        or "can be your commander" in text
    )


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
