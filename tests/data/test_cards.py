"""Tests for flattening Scryfall card fields into simple database values."""

import json

import pytest

from fishbowl.data.cards import (
    card_to_row,
    color_letters,
    commander_status,
    is_game_card,
    legal_in_commander,
    token_links,
)


def test_legal_card_is_true():
    assert legal_in_commander({"commander": "legal", "vintage": "restricted"}) is True


@pytest.mark.parametrize("status", ["not_legal", "banned", "restricted", ""])
def test_anything_but_legal_is_false(status):
    assert legal_in_commander({"commander": status}) is False


@pytest.mark.parametrize("legalities", [{}, {"modern": "legal"}, None, "legal", 42])
def test_missing_or_malformed_legalities_is_false(legalities):
    # Safe default: if we can't confirm it's legal, treat it as not legal.
    assert legal_in_commander(legalities) is False


@pytest.mark.parametrize("status", ["legal", "banned", "restricted"])
def test_card_legal_banned_or_restricted_anywhere_is_a_game_card(status):
    assert is_game_card({"commander": "not_legal", "vintage": status}) is True


@pytest.mark.parametrize(
    "legalities",
    [
        {"commander": "not_legal", "vintage": "not_legal"},
        {},
        None,
        "legal",
        {"vintage": ["legal"]},
        {"vintage": {"a": 1}},
    ],
)
def test_card_legal_nowhere_is_not_a_game_card(legalities):
    assert is_game_card(legalities) is False


def test_commander_status_passes_scryfall_value_through():
    assert commander_status({"commander": "banned"}) == "banned"


@pytest.mark.parametrize("legalities", [{}, None, {"commander": 7}])
def test_commander_status_missing_or_malformed_is_missing(legalities):
    assert commander_status(legalities) == "missing"


@pytest.mark.parametrize(
    ("symbols", "expected"),
    [
        ([], ""),
        (["R"], "R"),
        (["G", "W"], "WG"),  # always WUBRG order, whatever order Scryfall uses
        (["C"], "C"),
        (["U", "C", "B"], "UBC"),
    ],
)
def test_color_letters_in_wubrg_order(symbols, expected):
    assert color_letters(symbols) == expected


@pytest.mark.parametrize("symbols", [None, "WG", ["X", 3, None], 42])
def test_color_letters_ignores_bad_input(symbols):
    assert color_letters(symbols) == ""


def test_token_links_keeps_only_tokens():
    all_parts = [
        {
            "id": "70f8a1de-cd4c-4afa-bf03-0245d375d42e",
            "component": "token",
            "name": "Goblin",
        },
        {
            "id": "824b2d73-2151-4e5e-9f05-8f63e2bdcaa9",
            "component": "combo_piece",
            "name": "Krenko, Mob Boss",
        },
    ]
    assert token_links(all_parts) == [
        {"id": "70f8a1de-cd4c-4afa-bf03-0245d375d42e", "name": "Goblin"}
    ]


@pytest.mark.parametrize(
    "all_parts",
    [
        None,
        "Goblin",
        [None, "x", {"component": "token"}, {"component": "token", "name": "Goblin"}],
    ],
)
def test_token_links_ignores_bad_input(all_parts):
    assert token_links(all_parts) == []


def test_sol_ring_row(sol_ring):
    assert card_to_row(sol_ring) == {
        "oracle_id": "6ad8011d-3471-4369-9d68-b264cc027487",
        "name": "Sol Ring",
        "layout": "normal",
        "mana_cost": "{1}",
        "cmc": 1.0,
        "type_line": "Artifact",
        "oracle_text": "{T}: Add {C}{C}.",
        "colors": "",
        "color_identity": "",
        "produced_mana": "C",
        "keywords": "[]",
        "legal_commander": 1,
        "commander_status": "legal",
        "is_game_changer": 0,
        "card_faces": None,
        "tokens": "[]",
    }


def test_row_keys_match_table_columns_in_order(sol_ring):
    row = card_to_row(sol_ring)
    assert row is not None
    assert list(row) == [
        "oracle_id",
        "name",
        "layout",
        "mana_cost",
        "cmc",
        "type_line",
        "oracle_text",
        "colors",
        "color_identity",
        "produced_mana",
        "keywords",
        "legal_commander",
        "commander_status",
        "is_game_changer",
        "card_faces",
        "tokens",
    ]


def test_krenko_row_links_goblin_token(krenko):
    row = card_to_row(krenko)
    assert row is not None
    assert row["color_identity"] == "R"
    assert row["produced_mana"] == ""  # Krenko has no produced_mana field at all
    assert isinstance(row["tokens"], str)
    assert json.loads(row["tokens"]) == [
        {"id": "70f8a1de-cd4c-4afa-bf03-0245d375d42e", "name": "Goblin"}
    ]


def test_double_faced_row_keeps_faces_and_null_top_level(witch_enchanter):
    row = card_to_row(witch_enchanter)
    assert row is not None
    assert row["mana_cost"] is None
    assert row["oracle_text"] is None
    assert row["colors"] == ""
    assert row["type_line"] == "Creature — Human Warlock // Land"
    assert isinstance(row["card_faces"], str)
    faces = json.loads(row["card_faces"])
    assert [face["mana_cost"] for face in faces] == ["{3}{W}", ""]


def test_game_changer_is_1(sol_ring):
    sol_ring["game_changer"] = True
    row = card_to_row(sol_ring)
    assert row is not None
    assert row["is_game_changer"] == 1


@pytest.mark.parametrize("missing", ["oracle_id", "name"])
def test_card_without_id_or_name_gives_none(sol_ring, missing):
    del sol_ring[missing]
    assert card_to_row(sol_ring) is None


@pytest.mark.parametrize("card", [None, "Sol Ring", [], 42])
def test_non_dict_card_gives_none(card):
    assert card_to_row(card) is None


def test_wrong_types_get_defaults(sol_ring):
    sol_ring.update(
        colors="R", keywords="Flying", legalities=None, all_parts=[None], layout=None
    )
    row = card_to_row(sol_ring)
    assert row is not None
    assert row["colors"] == ""
    assert row["keywords"] == "[]"
    assert row["legal_commander"] == 0
    assert row["commander_status"] == "missing"
    assert row["tokens"] == "[]"
    assert row["layout"] == "unknown"


def test_wrong_typed_pass_through_fields_become_none(sol_ring):
    sol_ring.update(cmc={"x": 1}, mana_cost=5, type_line=["Artifact"], oracle_text=None)
    row = card_to_row(sol_ring)
    assert row is not None
    assert row["cmc"] is None
    assert row["mana_cost"] is None
    assert row["type_line"] is None
    assert row["oracle_text"] is None


def test_bool_cmc_becomes_none(sol_ring):
    # bool is a subclass of int in Python, so it needs its own check
    sol_ring["cmc"] = True
    row = card_to_row(sol_ring)
    assert row is not None
    assert row["cmc"] is None


def test_int_cmc_becomes_float(sol_ring):
    sol_ring["cmc"] = 3
    row = card_to_row(sol_ring)
    assert row is not None
    cmc = row["cmc"]
    assert cmc == 3.0
    assert isinstance(cmc, float)
