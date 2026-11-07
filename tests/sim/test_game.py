"""Tests for the goldfish game state and turn engine, with hand-built states."""

from typing import ClassVar

from fishbowl.sim.cards import Kind, PlayCard
from fishbowl.sim.game import (
    GameState,
    Permanent,
    available_sources,
    can_pay,
    commander_cost,
    new_game,
    pay,
    play_game,
    play_turn,
)


def pc(
    name: str,
    kind: Kind = "generic",
    mv: int = 0,
    pips: dict[str, int] | None = None,
    colours: str = "",
    amount: int = 0,
    tapped: bool = False,
    ramp: tuple[int, int, bool] = (0, 0, False),
    draws: int = 0,
    basic: bool = False,
) -> PlayCard:
    """A PlayCard with dummy values for whatever a test doesn't care about."""
    return PlayCard(
        name, kind, mv, pips or {}, colours, amount, tapped, *ramp, draws, basic
    )


def land(colour: str, tapped: bool = False) -> PlayCard:
    return pc(f"{colour}-land", "land", colours=colour, amount=1, tapped=tapped)


def basic(colour: str) -> PlayCard:
    return pc(f"Basic {colour}", "land", colours=colour, amount=1, basic=True)


def state(**kwargs: list) -> GameState:
    return GameState(
        library=kwargs.get("library", []),
        hand=kwargs.get("hand", []),
        battlefield=kwargs.get("battlefield", []),
        graveyard=[],
        command_zone=kwargs.get("command_zone", []),
        log=[],
    )


ELVES = pc("Elves", "dork", 1, {"G": 1}, "G", 1)
SOL_RING = pc("Sol Ring", "rock", 1, {}, "C", 2)
SPELL = pc("Spell", "generic", 9)  # too dear to cast: just something to draw
FILLER = [SPELL] * 5


def test_dork_sick_on_entry():
    s = state(hand=[land("G"), ELVES], library=list(FILLER))
    # Turn 1: Forest then Elves is cast; the Elves must not tap yet.
    play_turn(s)
    elves = next(p for p in s.battlefield if p.card.name == "Elves")
    assert elves.sick
    assert elves not in available_sources(s)
    play_turn(s)  # next turn the sickness wears off
    assert elves.sick is False
    assert elves in available_sources(s)


def test_sol_ring_makes_two():
    s = state(battlefield=[Permanent(SOL_RING), Permanent(land("G"))])
    assert can_pay(s, 3, {})
    assert not can_pay(s, 4, {})


def test_cultivate_fetches():
    cultivate = pc("Cultivate", "ramp", 3, {"G": 1}, ramp=(1, 1, True))
    s = state(
        hand=[cultivate],
        library=[SPELL, basic("G"), basic("G")],
        battlefield=[Permanent(land("G")) for _ in range(3)],
    )
    play_turn(s)
    fetched = s.battlefield[-1]
    assert fetched.card.is_basic and fetched.tapped and not fetched.sick
    # Drew the Spell, then fetched two basics: one to the battlefield, one to the hand.
    assert [c.name for c in s.hand] == ["Spell", "Basic G"]
    assert s.library == []
    assert cultivate in s.graveyard


def test_ramp_no_basics():
    rampant = pc("Rampant Growth", "ramp", 2, {"G": 1}, ramp=(1, 0, True))
    s = state(
        hand=[rampant],
        library=[SPELL],
        battlefield=[Permanent(land("G")), Permanent(land("G"))],
    )
    play_turn(s)
    assert len(s.battlefield) == 2
    assert rampant in s.graveyard
    assert "no basic" in s.log[0]


def test_colour_blocks_cast():
    gg = pc("Needs GG", "generic", 2, {"G": 2})
    s = state(battlefield=[Permanent(land("G")), Permanent(land("R"))])
    assert not can_pay(s, gg.mana_value, gg.pips)  # 2 mana, but only 1 green
    s2 = state(battlefield=[Permanent(land("G")), Permanent(land("G"))])
    assert can_pay(s2, gg.mana_value, gg.pips)


def test_pay_taps_fewest_colours_first():
    any_rock = pc("Signet", "rock", 2, {}, "WUBRG", 1)
    s = state(battlefield=[Permanent(any_rock), Permanent(land("G"))])
    unused = pay(s, 1, {"G": 1})
    assert unused == 0
    assert [p.tapped for p in s.battlefield] == [False, True]


def test_pay_reports_unused_mana():
    s = state(battlefield=[Permanent(SOL_RING)])
    assert pay(s, 1, {}) == 1  # Sol Ring makes 2, only 1 needed
    assert s.battlefield[0].tapped


def test_land_prefers_missing_colour():
    commander = pc("Cmdr", "generic", 9, {"G": 1, "R": 1})
    s = state(
        hand=[land("G"), land("R")],
        library=[SPELL],
        battlefield=[Permanent(land("G"))],
        command_zone=[commander],
    )
    play_turn(s)
    assert s.battlefield[-1].card.name == "R-land"  # green was already covered


def test_land_untapped_before_tapped():
    s = state(
        hand=[land("G", tapped=True), land("G")],
        library=[SPELL],
    )
    play_turn(s)
    assert not s.battlefield[0].tapped
    assert s.hand[0].enters_tapped  # the tapped one is still waiting


def test_priority_order():
    commander = pc("Cmdr", "generic", 2, {"G": 1})
    ramp = pc("Ramp", "ramp", 2, {"G": 1}, ramp=(1, 0, False))
    draw = pc("Draw", "draw", 1, {"G": 1}, draws=1)
    cheap = pc("Cheap", "generic", 1, {"G": 1})
    dear = pc("Dear", "generic", 2, {"G": 1})
    s = state(
        hand=[cheap, dear, draw, ramp],
        library=[pc("Top", mv=99), pc("Next", mv=99)],
        battlefield=[Permanent(land("G")) for _ in range(20)],
        command_zone=[commander],
    )
    play_turn(s)
    assert [c.name for c in s.graveyard] == ["Ramp", "Draw", "Dear", "Cheap"]
    assert any(p.card.name == "Cmdr" for p in s.battlefield)
    cast_order = s.log[0].split("Cast ")[1:]
    assert cast_order[0].startswith("Cmdr")


def test_commander_tax():
    commander = pc("Cmdr", "generic", 4, {"G": 1})
    s = state(command_zone=[commander])
    assert commander_cost(s, commander) == 4
    s.commander_casts = {"Cmdr": 1}
    assert commander_cost(s, commander) == 6
    # Five sources are enough for the first cast but not the second.
    s.battlefield = [Permanent(land("G")) for _ in range(5)]
    s.library = [SPELL, SPELL]
    s.commander_casts = {"Cmdr": 1}
    play_turn(s)
    assert s.command_zone == [commander]


def test_commander_cast_recorded():
    commander = pc("Cmdr", "generic", 2, {"G": 1})
    s = state(
        command_zone=[commander],
        library=[SPELL],
        battlefield=[Permanent(land("G")), Permanent(land("G"))],
    )
    play_turn(s)
    assert (s.commander_casts, s.commander_cast_turn) == ({"Cmdr": 1}, 1)
    assert s.command_zone == []
    assert any(p.card is commander for p in s.battlefield)


def test_nothing_castable():
    s = state(hand=[pc("Big", "generic", 5)], library=[SPELL])
    play_turn(s)
    assert "Cast" not in s.log[0]
    assert len(s.hand) == 2


def test_copy_is_independent():
    s = state(
        hand=[land("G")],
        library=[SPELL],
        battlefield=[Permanent(land("G"))],
    )
    twin = s.copy()
    twin.hand.append(pc("New"))
    twin.library.clear()
    twin.battlefield[0].tapped = True
    twin.log.append("x")
    assert len(s.hand) == 1 and len(s.library) == 1
    assert s.battlefield[0].tapped is False
    assert s.log == []


def test_turn_log_line():
    s = state(hand=[land("G")], library=[SPELL])
    play_turn(s)
    assert len(s.log) == 1
    assert s.log[0].startswith("Turn 1: draw ")


# ---------- whole games ----------

FOOTER = "Simplified: no combat, abilities, X costs or cost reducers."


def mixed_library() -> list[PlayCard]:
    """30 distinct cards, so different shuffles give visibly different games."""
    lands = [pc(f"Forest {i}", "land", colours="G", amount=1) for i in range(12)]
    spells = [pc(f"Spell {i}", "generic", 3 + i % 4) for i in range(18)]
    return lands + spells


def test_same_seed_same_game():
    a = play_game(mixed_library(), [], seed=7, turns=6)
    b = play_game(mixed_library(), [], seed=7, turns=6)
    assert a.log == b.log


def test_different_seed_differs():
    a = play_game(mixed_library(), [], seed=1, turns=6)
    b = play_game(mixed_library(), [], seed=2, turns=6)
    assert a.log != b.log


def test_bottoms_most_expensive():
    # No lands at all: every hand is rejected until the forced keep at 5,
    # so two cards are bottomed, and they must be the two dearest of the seven.
    library = [pc(f"Spell {mv}", "generic", mv) for mv in range(1, 21)]
    s = new_game(library, [], seed=3)
    assert len(s.hand) == 5
    assert len(s.library) == 15
    bottomed = s.library[-2:]
    assert bottomed[0].mana_value > bottomed[1].mana_value  # dearest went first
    assert all(c.mana_value < bottomed[1].mana_value for c in s.hand)
    assert s.log[0] == "Mulligans: 3 (kept 5)"
    assert s.log[1].startswith("Opening hand: ")


def test_bottoms_a_land_when_flooded():
    # All lands except one spell: with more than 3 lands in hand, a land goes.
    library = [land("G") for _ in range(30)] + [pc("Spell", "generic", 9)]
    s = new_game(library, [], seed=5)
    # 7 lands (or 6 + the spell) is not a keep, so mulligans happen; the end
    # hand holds only lands or the spell, and bottomed cards are lands.
    assert all(c.name == "G-land" for c in s.library[-(7 - len(s.hand)) :])


def test_library_runs_out():
    library = [pc(f"Spell {mv}", "generic", mv + 5) for mv in range(10)]
    s = play_game(library, [], seed=1, turns=20)
    # Forced keep at 5 leaves 5 to draw: turns 1-5 happen, then it stops.
    assert s.turn == 5
    assert "Library empty after turn 5; game over." in s.log
    assert not any(line.startswith("Turn 6") for line in s.log)
    assert s.log[-2] == "No commander."
    assert s.log[-1] == FOOTER


def test_commander_cast_turn_recorded():
    commander = pc("Boss", "generic", 1, {"G": 1})
    library = [land("G") for _ in range(40)]
    s = play_game(library, [commander], seed=1, turns=4)
    assert s.commander_cast_turn == 1
    assert "Commander cast on turn 1." in s.log
    assert s.log[-1] == FOOTER


def test_commander_not_cast():
    commander = pc("Boss", "generic", 9, {"G": 1})
    s = play_game([land("G") for _ in range(40)], [commander], seed=1, turns=3)
    assert s.commander_cast_turn is None
    assert "Commander not cast in 3 turns." in s.log


# ---------- tax per commander ----------


def test_partner_tax_is_separate():
    a = pc("Partner A", "generic", 2, {"G": 1})
    b = pc("Partner B", "generic", 3, {"G": 1})
    s = state(
        command_zone=[a, b],
        library=[SPELL, SPELL, SPELL],
        battlefield=[Permanent(land("G")) for _ in range(2)],
    )
    play_turn(s)  # only A is affordable (2 mana)
    assert s.commander_casts == {"Partner A": 1}
    assert commander_cost(s, b) == 3  # A's cast adds nothing to B's cost
    assert commander_cost(s, a) == 4
    assert s.commander_cast_turn == 1  # commanders[0] was cast


def test_cast_turn_tracks_first_commander_only():
    a = pc("Partner A", "generic", 5, {"G": 1})
    b = pc("Partner B", "generic", 1, {"G": 1})
    s = state(
        command_zone=[a, b],
        library=[SPELL],
        battlefield=[Permanent(land("G"))],
    )
    play_turn(s)  # B is cast, A is not
    assert s.commander_casts == {"Partner B": 1}
    assert s.commander_cast_turn is None


def test_copy_copies_cast_dict():
    s = state(library=[SPELL])
    s.commander_casts = {"X": 1}
    twin = s.copy()
    twin.commander_casts["X"] = 5
    assert s.commander_casts == {"X": 1}


# ---------- untap, land drop, opening hands ----------


def test_untap_next_turn():
    s = state(
        hand=[ELVES],
        library=[SPELL, SPELL],
        battlefield=[Permanent(land("G"))],
    )
    play_turn(s)
    assert s.battlefield[0].tapped  # the land paid for Elves
    play_turn(s)
    assert not s.battlefield[0].tapped
    elves = next(p for p in s.battlefield if p.card is ELVES)
    assert not elves.sick  # no longer sick on turn 2
    assert len(available_sources(s)) == 2


def test_dork_taps_the_turn_after_it_enters():
    two_drop = pc("Two-drop", "generic", 2, {"G": 1})
    s = state(
        hand=[ELVES, two_drop],
        library=[SPELL, SPELL],
        battlefield=[Permanent(land("G"))],
    )
    play_turn(s)  # the land pays for Elves; the dork is sick
    assert two_drop in s.hand
    play_turn(s)  # land + Elves now pay for the two-drop
    assert two_drop in s.graveyard


def test_one_land_per_turn():
    s = state(hand=[land("G"), land("G")], library=[SPELL])
    play_turn(s)
    assert len(s.battlefield) == 1
    assert sum(1 for c in s.hand if c.kind == "land") == 1


class _RiggedRandom:
    """Stands in for random.Random: each shuffle applies the next prepared order."""

    orders: ClassVar[list] = []
    calls: ClassVar[int] = 0

    def __init__(self, seed: int) -> None:
        type(self).calls = 0

    def shuffle(self, deck: list) -> None:
        order = type(self).orders[min(type(self).calls, len(type(self).orders) - 1)]
        type(self).calls += 1
        deck.sort(key=order)


def _rig(monkeypatch, *orders) -> None:
    # Why rig it: a real shuffle needs a lucky seed; a fixed order makes the
    # opening hand certain, so the test checks the rule, not the luck.
    from fishbowl.sim import game

    _RiggedRandom.orders = list(orders)
    monkeypatch.setattr(game.random, "Random", _RiggedRandom)


def _deck_10_lands() -> list[PlayCard]:
    return [pc(f"L{i}", "land", colours="G", amount=1) for i in range(10)] + [
        pc(f"S{i}", "generic", 3) for i in range(20)
    ]


def _three_lands_first(c: PlayCard) -> tuple[int, bool, str]:
    # The chosen lands first, then spells, then the other lands (False < True).
    picked = c.name in ("L0", "L1", "L2")
    return (0 if picked else 1, c.kind in ("land", "fetch"), c.name)


def _no_lands_first(c: PlayCard) -> tuple[bool, str]:
    return (c.kind in ("land", "fetch"), c.name)  # spells first: 0 lands in the top 7


def test_keep_logs_zero_mulligans(monkeypatch):
    _rig(monkeypatch, _three_lands_first)
    s = new_game(_deck_10_lands(), [], seed=1)
    assert s.log[0] == "Mulligans: 0 (kept 7)"


def test_free_mulligan_logs_one(monkeypatch):
    _rig(monkeypatch, _no_lands_first, _three_lands_first)
    s = new_game(_deck_10_lands(), [], seed=1)
    assert s.log[0] == "Mulligans: 1 (kept 7)"  # the first mulligan is free


def test_fetch_counts_as_land_for_keep(monkeypatch):
    fetch = pc("Fetch", "fetch", 2)

    def one_land_one_fetch_first(c: PlayCard) -> tuple[int, bool, str]:
        picked = c.name in ("L0", "Fetch")
        return (0 if picked else 1, c.kind in ("land", "fetch"), c.name)

    _rig(monkeypatch, one_land_one_fetch_first)
    # 1 land + 1 fetch = 2 land-likes, a keep; without the fetch it would be 1.
    s = new_game(_deck_10_lands() + [fetch], [], seed=1)
    assert s.log[0] == "Mulligans: 0 (kept 7)"
