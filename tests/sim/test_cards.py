"""Tests for sorting cards into goldfish kinds (land, rock, dork, ramp, ...)."""

import pytest

from fishbowl.deck.lookup import Card
from fishbowl.sim.cards import classify


def card(
    name: str,
    type_line: str,
    text: str,
    produced: str = "",
    cost: str | None = None,
    cmc: float = 0,
) -> Card:
    """A Card with dummy values for the fields classify doesn't read."""
    return Card("id", name, type_line, text, "", "legal", False, cost, cmc, produced)


def test_basic_land():
    play = classify(card("Forest", "Basic Land — Forest", "({T}: Add {G}.)", "G"))
    assert (play.kind, play.colours, play.amount) == ("land", "G", 1)
    assert play.is_basic
    assert not play.enters_tapped


def test_tapped_land():
    text = "This land enters tapped.\n{T}: Add {G}."
    play = classify(card("Tapped Forest", "Land", text, "G"))
    assert play.kind == "land"
    assert play.enters_tapped
    assert not play.is_basic


def test_fetch_uses_commander_colours():
    text = (
        "This land enters tapped.\n{T}, Sacrifice this land: Search your library "
        "for a basic land card, put it onto the battlefield tapped, then shuffle."
    )
    wilds = card("Evolving Wilds", "Land", text)
    play = classify(wilds, "RG")
    assert (play.kind, play.colours, play.amount) == ("fetch", "RG", 1)
    assert play.enters_tapped
    assert classify(wilds).colours == "C"  # no commander: colourless


def test_llanowar_elves_is_a_dork():
    elves = card(
        "Llanowar Elves",
        "Creature — Elf Druid",
        "{T}: Add {G}.",
        "G",
        "{G}",
        1,
    )
    play = classify(elves)
    assert (play.kind, play.colours, play.amount) == ("dork", "G", 1)
    assert play.pips == {"G": 1}
    assert play.mana_value == 1


def test_sol_ring_makes_two():
    ring = card("Sol Ring", "Artifact", "{T}: Add {C}{C}.", "C", "{1}", 1)
    play = classify(ring)
    assert (play.kind, play.colours, play.amount) == ("rock", "C", 2)


def test_arcane_signet_makes_one():
    text = "{T}: Add one mana of any color in your commander's color identity."
    play = classify(card("Arcane Signet", "Artifact", text, "WUBRG", "{2}", 2))
    assert (play.kind, play.amount) == ("rock", 1)


def test_artifact_creature_is_a_dork_not_a_rock():
    walker = card("Walker", "Artifact Creature — Construct", "{T}: Add {C}.", "C")
    assert classify(walker).kind == "dork"


RAMP_CASES = [
    (
        "Rampant Growth",
        (
            "Search your library for a basic land card, put that card onto the "
            "battlefield tapped, then shuffle."
        ),
        (1, 0, True),
    ),
    (
        "Nature's Lore",
        (
            "Search your library for a Forest card, put that card onto the "
            "battlefield, then shuffle."
        ),
        (1, 0, False),
    ),
    (
        "Skyshroud Claim",
        (
            "Search your library for up to two Forest cards, put them onto the "
            "battlefield, then shuffle."
        ),
        (2, 0, False),
    ),
    (
        "Cultivate",
        (
            "Search your library for up to two basic land cards, reveal those cards, "
            "put one onto the battlefield tapped and the other into your hand, "
            "then shuffle."
        ),
        (1, 1, True),
    ),
]


@pytest.mark.parametrize(("name", "text", "expected"), RAMP_CASES)
def test_ramp_spells(name, text, expected):
    play = classify(card(name, "Sorcery", text, "", "{2}{G}", 3))
    assert play.kind == "ramp"
    assert (play.ramp_lands, play.ramp_to_hand, play.ramp_tapped) == expected


def test_harmonize_draws_three():
    play = classify(
        card("Harmonize", "Sorcery", "Draw three cards.", "", "{2}{G}{G}", 4)
    )
    assert (play.kind, play.draws) == ("draw", 3)


def test_dockside_is_generic():
    text = (
        "When this creature enters, create a Treasure token for each artifact "
        "and/or creature your opponents control."
    )
    play = classify(card("Dockside Extortionist", "Creature — Goblin Pirate", text))
    assert play.kind == "generic"
    assert (play.amount, play.colours) == (0, "")


def test_vanilla_creature_is_generic():
    assert classify(card("Bear", "Creature — Bear", "")).kind == "generic"


def test_quoted_and_reminder_text_is_ignored():
    # The mana ability belongs to the tokens, not to the spell itself.
    text = 'Create a Treasure token. (It has "{T}, Sacrifice: Add one mana".)'
    assert classify(card("Treasure maker", "Artifact", text)).kind == "generic"
