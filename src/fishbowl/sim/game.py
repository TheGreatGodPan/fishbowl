"""The goldfish game: the board, how mana is paid, and one turn of play.

Rules live in docs/superpowers/specs/2026-11-06-goldfish-design.md. The turn
engine is deliberately simple: it follows a fixed priority list, no search.
"""

import random
from dataclasses import dataclass, field

from fishbowl.sim.cards import PlayCard
from fishbowl.stats.lands import HAND_SIZE
from fishbowl.stats.mulligan import BOTTOM_ABOVE, hand_sizes, keeps

_COLOURS = "WUBRG"


@dataclass
class Permanent:
    """A card on the battlefield. Not frozen: it taps and untaps."""

    card: PlayCard
    tapped: bool = False
    sick: bool = False  # summoning sickness: a dork can't tap the turn it enters


@dataclass
class GameState:
    """Everything about one game in progress."""

    library: list[PlayCard]
    hand: list[PlayCard]
    battlefield: list[Permanent]
    graveyard: list[PlayCard]
    command_zone: list[PlayCard]
    turn: int = 0
    land_played: bool = False
    # Tax is per commander (partners are taxed separately), keyed by card name.
    commander_casts: dict[str, int] = field(default_factory=dict)
    # The turn command_zone's FIRST commander was first cast (the one we measure).
    commander_cast_turn: int | None = None
    # commanders[0], remembered because the command zone shrinks as they are cast.
    first_commander: PlayCard | None = None
    # field(default_factory=list): a fresh empty list per game, not one shared list
    log: list[str] = field(default_factory=list)

    # A method is a function that belongs to a class; `self` is the object it is called on.
    def copy(self) -> "GameState":
        """An independent copy, so a what-if can't change the real game.

        Why new lists: `b = a` only gives the same list a second name
        ("aliasing"), so changing one would change both. PlayCard is frozen,
        so cards can be shared; Permanent changes, so each gets a new object.
        """
        return GameState(
            library=list(self.library),
            hand=list(self.hand),
            battlefield=[Permanent(p.card, p.tapped, p.sick) for p in self.battlefield],
            graveyard=list(self.graveyard),
            command_zone=list(self.command_zone),
            turn=self.turn,
            land_played=self.land_played,
            commander_casts=dict(self.commander_casts),  # a dict is mutable: copy it
            commander_cast_turn=self.commander_cast_turn,
            first_commander=self.first_commander,
            log=list(self.log),
        )


# ---------- mana ----------


def available_sources(state: GameState) -> list[Permanent]:
    """Untapped things that make mana right now (dorks only once not sick)."""
    return [
        p
        for p in state.battlefield
        if p.card.amount > 0 and not p.tapped and not p.sick
    ]


def can_pay(state: GameState, mana_value: int, pips: dict[str, int]) -> bool:
    """Enough total mana, and enough of each coloured pip's colour?

    The same approximation as 4d: each colour is checked on its own.
    """
    sources = available_sources(state)
    if sum(p.card.amount for p in sources) < mana_value:
        return False
    for colour, needed in pips.items():
        have = sum(p.card.amount for p in sources if colour in p.card.colours)
        if have < needed:
            return False
    return True


def pay(state: GameState, mana_value: int, pips: dict[str, int]) -> int:
    """Tap whole sources to pay; returns the mana wasted (leftover from a source).

    Call can_pay first. Coloured pips are paid first from the sources with the
    fewest colours, so an any-colour rock is saved for pips nothing else covers.
    """
    free = available_sources(state)
    paid = 0

    def tap(source: Permanent) -> int:
        source.tapped = True
        free.remove(source)
        return source.card.amount

    for colour, needed in pips.items():
        # sorted(key=...): order by a computed value, here "how many colours it makes"
        matching = sorted(
            (p for p in free if colour in p.card.colours),
            key=lambda p: len(p.card.colours),
        )
        covered = 0
        for source in matching:
            if covered >= needed:
                break
            covered += tap(source)
        paid += covered
    # The rest is generic: colourless-only sources first, then the fewest colours.
    rest = sorted(free, key=lambda p: (p.card.colours != "C", len(p.card.colours)))
    for source in rest:
        if paid >= mana_value:
            break
        paid += tap(source)
    return max(0, paid - mana_value)


def commander_cost(state: GameState, card: PlayCard) -> int:
    """Mana value plus {2} for each earlier cast of THIS card from the command zone."""
    return card.mana_value + 2 * state.commander_casts.get(card.name, 0)


# ---------- colour helpers ----------


def _missing_colours(state: GameState) -> set[str]:
    """Colours the commanders in the command zone need that no permanent makes yet."""
    needed = {c for card in state.command_zone for c in card.pips if c in _COLOURS}
    covered = {c for p in state.battlefield for c in p.card.colours}
    return needed - covered


# ---------- the turn ----------


def _play_land(state: GameState) -> PlayCard | None:
    """Choose and play at most one land from the hand."""
    lands = [c for c in state.hand if c.kind in ("land", "fetch")]
    untapped = [c for c in lands if c.kind == "land" and not c.enters_tapped]
    missing = _missing_colours(state)
    # next(..., None): the first match, or None when nothing matches
    choice = next((c for c in untapped if missing & set(c.colours)), None)
    if choice is None and untapped:
        choice = untapped[0]
    if choice is None and lands:
        choice = lands[0]  # only tapped lands and fetches are left
    if choice is None:
        return None
    state.hand.remove(choice)
    state.battlefield.append(Permanent(choice, tapped=choice.enters_tapped))
    state.land_played = True
    return choice


def _take_basic(state: GameState, missing: set[str]) -> PlayCard | None:
    """Remove a basic land from the library, preferring a colour that is missing."""
    basics = [c for c in state.library if c.is_basic and c.kind == "land"]
    choice = next((c for c in basics if missing & set(c.colours)), None)
    if choice is None and basics:
        choice = basics[0]
    if choice is not None:
        state.library.remove(choice)
    return choice


def _resolve_ramp(state: GameState, card: PlayCard) -> str:
    """Fetch basics: some onto the battlefield, some into the hand."""
    notes: list[str] = []
    for _ in range(card.ramp_lands):
        land = _take_basic(state, _missing_colours(state))
        if land is not None:
            # Fetched lands are never summoning sick; only dorks are.
            state.battlefield.append(Permanent(land, tapped=card.ramp_tapped))
            notes.append(f"{land.name}{' tapped' if card.ramp_tapped else ''}")
    for _ in range(card.ramp_to_hand):
        land = _take_basic(state, _missing_colours(state))
        if land is not None:
            state.hand.append(land)
            notes.append(f"{land.name} to hand")
    return f" (fetched {', '.join(notes)})" if notes else " (no basic land to fetch)"


def _resolve(state: GameState, card: PlayCard) -> str:
    """Put a cast non-commander card where it goes; returns a note for the log."""
    if card.kind in ("rock", "dork"):
        state.battlefield.append(Permanent(card, sick=card.kind == "dork"))
        return ""
    state.graveyard.append(card)
    if card.kind == "ramp":
        return _resolve_ramp(state, card)
    if card.kind == "draw":
        drawn = 0
        for _ in range(card.draws):
            if state.library:
                state.hand.append(state.library.pop(0))
                drawn += 1
        return f" (drew {drawn})"
    return ""


def _priority(card: PlayCard) -> tuple[int, int]:
    """Sort key for non-commander spells: lower sorts (and so casts) first."""
    if card.kind in ("rock", "dork", "ramp"):
        return 0, card.mana_value  # cheapest first
    if card.kind == "draw":
        return 1, card.mana_value  # cheapest first
    return 2, -card.mana_value  # generic: most expensive first


def _next_cast(state: GameState) -> tuple[PlayCard, bool] | None:
    """The card to cast now and whether it comes from the command zone, or None."""
    for commander in state.command_zone:
        if can_pay(state, commander_cost(state, commander), commander.pips):
            return commander, True
    spells = [c for c in state.hand if c.kind not in ("land", "fetch")]
    # sorted is stable, so ties keep hand order ("first in hand wins")
    for card in sorted(spells, key=_priority):
        if can_pay(state, card.mana_value, card.pips):
            return card, False
    return None


def play_turn(state: GameState) -> None:
    """One turn: untap, draw, play a land, cast by priority, log one line."""
    state.turn += 1
    state.land_played = False
    for p in state.battlefield:
        p.tapped = False
        p.sick = False
    if not state.library:
        state.log.append(f"Turn {state.turn}: library empty, game over.")
        return
    drawn = state.library.pop(0)  # the top of the library is index 0
    state.hand.append(drawn)
    parts = [f"draw {drawn.name}."]

    played = _play_land(state)
    if played is not None:
        parts.append(f"Play {played.name}.")

    used = 0
    wasted = 0
    if state.first_commander is None and state.command_zone:
        state.first_commander = state.command_zone[0]  # latch before any cast
    # Each pass casts exactly one card or stops, and the hand and command zone
    # only shrink, so this loop always ends.
    while (choice := _next_cast(state)) is not None:
        card, from_command = choice
        cost = commander_cost(state, card) if from_command else card.mana_value
        wasted += pay(state, cost, card.pips)
        used += cost
        if from_command:
            state.command_zone.remove(card)
            state.commander_casts[card.name] = (
                state.commander_casts.get(card.name, 0) + 1
            )
            # Only commanders[0] sets the turn, so the summary's note is true.
            if state.commander_cast_turn is None and card is state.first_commander:
                state.commander_cast_turn = state.turn
            # The commander stays on the battlefield; a mana creature is sick.
            state.battlefield.append(Permanent(card, sick=card.kind == "dork"))
            note = " (commander)"
        else:
            state.hand.remove(card)
            note = _resolve(state, card)
        parts.append(f"Cast {card.name}{note}.")

    unused = wasted + sum(p.card.amount for p in available_sources(state))
    parts.append(f"Mana: {used} used, {unused} unused.")
    state.log.append(f"Turn {state.turn}: " + " ".join(parts))


# ---------- a whole game ----------


def _is_land_like(card: PlayCard) -> bool:
    """Fetch cards count as lands for the keep rule and for bottoming."""
    return card.kind in ("land", "fetch")


def _bottom_one(hand: list[PlayCard]) -> PlayCard:
    """Remove and return the card to bottom: a land if flooded, else the dearest spell."""
    lands = [c for c in hand if _is_land_like(c)]
    if len(lands) > BOTTOM_ABOVE:
        choice = lands[0]
    else:
        spells = [c for c in hand if not _is_land_like(c)]
        # max keeps the first of equal values, so ties go to the first in hand
        choice = max(spells, key=lambda c: c.mana_value) if spells else hand[0]
    hand.remove(choice)
    return choice


def new_game(
    library: list[PlayCard], commanders: list[PlayCard], seed: int
) -> GameState:
    """Shuffle, mulligan until a keep, bottom extras, and log the opening hand."""
    rng = random.Random(seed)  # one generator for the whole game: same seed, same game
    deck = list(library)  # shuffle a copy; the caller's list stays as it was
    sizes = hand_sizes()
    attempt = 0
    for attempt in range(len(sizes)):
        rng.shuffle(deck)  # each mulligan reshuffles the full library
        lands = sum(1 for c in deck[:HAND_SIZE] if _is_land_like(c))
        if keeps(lands) or attempt == len(sizes) - 1:  # the last hand is forced
            break
    size = sizes[attempt]
    hand = deck[:HAND_SIZE]
    del deck[:HAND_SIZE]
    for _ in range(HAND_SIZE - size):
        deck.append(_bottom_one(hand))  # bottomed cards go under the library

    state = GameState(
        library=deck,
        hand=hand,
        battlefield=[],
        graveyard=[],
        command_zone=list(commanders),
        first_commander=commanders[0] if commanders else None,
        log=[],
    )
    state.log.append(f"Mulligans: {attempt} (kept {len(hand)})")
    state.log.append("Opening hand: " + ", ".join(c.name for c in hand))
    return state


def play_game(
    library: list[PlayCard], commanders: list[PlayCard], seed: int, turns: int
) -> GameState:
    """Play up to `turns` turns, then log how the commander did."""
    state = new_game(library, commanders, seed)
    for _ in range(turns):
        # Check here, so an empty library doesn't produce a phantom turn.
        if not state.library:
            state.log.append(f"Library empty after turn {state.turn}; game over.")
            break
        play_turn(state)
    if not commanders:
        state.log.append("No commander.")
    elif state.commander_cast_turn is not None:
        state.log.append(f"Commander cast on turn {state.commander_cast_turn}.")
    else:
        state.log.append(f"Commander not cast in {state.turn} turns.")
    state.log.append("Simplified: no combat, abilities, X costs or cost reducers.")
    return state
