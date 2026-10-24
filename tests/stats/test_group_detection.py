"""Tests for finding mana dorks and tutors from card text."""

import pytest

from fishbowl.deck.lookup import Card, CardLookup
from fishbowl.deck.parser import parse_deck
from fishbowl.stats.groups import find_groups, is_mana_dork, is_tutor


def card(name: str, type_line: str | None, text: str | None) -> Card:
    """A Card with dummy values for the fields the detectors don't read."""
    return Card("id", name, type_line, text, "", "legal", False)


@pytest.fixture
def lookup(card_db):
    with CardLookup(card_db) as opened:
        yield opened


def test_dorks():
    llanowar = card("Llanowar Elves", "Creature — Elf Druid", "{T}: Add {G}.")
    selvala = card(
        "Selvala, Heart of the Wilds",
        "Legendary Creature — Elf Scout",
        "Whenever another creature enters, its controller may draw a card.\n"
        "{G}, {T}: Add X mana in any combination of colors, where X is the greatest "
        "power among creatures you control.",
    )
    assert is_mana_dork(llanowar)
    assert is_mana_dork(selvala)


def test_non_dorks():
    arbor = card("Arbor Elf", "Creature — Elf Druid", "{T}: Untap target Forest.")
    signet = card(
        "Arcane Signet",
        "Artifact",
        "{T}: Add one mana of any color in your commander's color identity.",
    )
    krenko = card(
        "Krenko, Mob Boss",
        "Legendary Creature — Goblin Warrior",
        "{T}: Create X 1/1 red Goblin creature tokens, where X is the number of Goblins you control.",
    )
    assert not is_mana_dork(arbor)
    assert not is_mana_dork(signet)  # an artifact, not a creature
    assert not is_mana_dork(krenko)


def test_tutors():
    matron = card(
        "Goblin Matron",
        "Creature — Goblin",
        "When this creature enters, you may search your library for a Goblin card, "
        "reveal it, put it into your hand, then shuffle.",
    )
    demonic = card(
        "Demonic Tutor",
        "Sorcery",
        "Search your library for a card, put that card into your hand, then shuffle.",
    )
    assert is_tutor(matron)
    assert is_tutor(demonic)


def test_basic_land_searches_are_not_tutors():
    lore = card(
        "Nature's Lore",
        "Sorcery",
        "Search your library for a Forest card, put that card onto the battlefield, then shuffle.",
    )
    cultivate = card(
        "Cultivate",
        "Sorcery",
        "Search your library for up to two basic land cards, put one onto the battlefield tapped and the other into your hand, then shuffle.",
    )
    island = card(
        "Island Fetch",
        "Sorcery",
        "Search your library for an Island card, put it into your hand, then shuffle.",
    )
    assert not is_tutor(lore)
    assert not is_tutor(cultivate)
    assert not is_tutor(island)


def test_no_text_matches_nothing():
    for text in (None, ""):
        blank = card("Blank", "Creature — Elf", text)
        assert not is_mana_dork(blank)
        assert not is_tutor(blank)
    assert not is_mana_dork(card("No Type", None, "{T}: Add {G}."))


def test_find_groups(lookup):
    text = (
        "Commander: Goreclaw, Terror of Qal Sisma\n"
        "1 Goreclaw, Terror of Qal Sisma\n"
        "1 Survival of the Fittest\n1 Sylvan Primordial\n1 Sol Ring\n10 Forest\n"
    )
    dorks, tutors = find_groups(parse_deck(text, lookup), lookup)
    assert (dorks.name, dorks.unit, dorks.units) == ("Mana dorks", "dork", "dorks")
    assert (tutors.name, tutors.unit, tutors.units) == ("Tutors", "tutor", "tutors")
    assert (dorks.count, dorks.names) == (0, [])
    assert (tutors.count, tutors.names) == (1, ["Survival of the Fittest"])


def test_commander_not_counted(lookup):
    text = "1 Survival of the Fittest\n1 Goreclaw, Terror of Qal Sisma\n10 Forest\n"
    deck = parse_deck(text, lookup)
    deck.commanders = [
        entry for entry in deck.cards if entry.name == "Survival of the Fittest"
    ]
    _, tutors = find_groups(deck, lookup)
    assert (tutors.count, tutors.names) == (0, [])
