# Deck validator design (Stage 3)

Date: 2026-10-18 · Status: approved in conversation

## Goal

Check a `ParsedDeck` (from Stage 2) against Commander's deck-building rules. Report **errors**, which are rule breaks, and **notes**, which are useful facts that aren't rule breaks. Never give a bracket verdict.

**Done when:** Ian's three decks (Goreclaw, Ghalta, Krenko) are reported legal with 0 Game Changers, and a deliberately broken deck fails with a clear message for every error type.

## Evidence (real data, 2026-10-18)

- All three of Ian's decks are on-color, have multiples only of basic lands, contain no banned cards and have 0 Game Changers. This was an informal check before the design.
- Basic lands: `type_line` starts with `Basic` (Forest, Snow-Covered Forest, Wastes, …).
- "A deck can have any number of cards named …": 14 cards, e.g. Relentless Rats. "A deck can have up to seven cards named Seven Dwarves", and "up to nine" for Nazgûl.
- Banned in Commander: 83 cards. `not_legal` game cards: e.g. Alchemy cards like Absorb Energy. Game Changers: 53.

## Decisions

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | What to report | Errors (rule breaks) + notes (Game Changers count and names, unchecked things). No bracket verdict. | Bracket guidance is Wizards' and still changing. It depends on combos and extra turns we can't judge yet. The Game Changer count is the key fact. |
| 2 | Two commanders | Pairing (Partner/Background/Doctor) is not checked yet. A note says so. All other checks run, and color identity uses both commanders combined. | Follows the roadmap ("pairings later") without passing silently. None of Ian's decks has two commanders. |
| 3 | Unreadable lines | If the parser reported problems, the deck can't be legal (error). | Fail closed. Unknown cards could break any rule. |

## Errors

| Code | Check | Message (example) |
|---|---|---|
| `unreadable_lines` | `deck.problems` not empty | `2 lines couldn't be read, so the deck can't be fully checked.` (`1 line couldn't …` for one) |
| `deck_size` | `deck.total != 100` | `Deck has 99 cards; a Commander deck needs exactly 100.` |
| `no_commander` | no commanders | `No commander identified.` |
| `ineligible_commander` | commander is not a legendary creature and its text doesn't say "can be your commander" | `Sol Ring can't be a commander (it isn't a legendary creature).` |
| `too_many_copies` | quantity above the card's copy limit | `2 copies of Sol Ring; only 1 allowed.` / `8 copies of Seven Dwarves; up to 7 allowed.` |
| `off_color` | card's color identity not inside the commanders' combined identity (skipped when there are no commanders) | `Witch Enchanter // Witch-Blessed Meadow (W) is outside the commander's color identity (G).` A colorless identity prints as `colorless`. |
| `banned` | `commander_status == "banned"` | `Sylvan Primordial is banned in Commander.` |
| `not_legal` | `commander_status` anything else but `legal` | `Absorb Energy is not legal in Commander (not_legal).` |

Copy limit:
- `None` (any number) for basic lands and for "any number of cards named".
- N for "can have up to N cards named", where N is a number word one–ten. An unrecognized word gives 1.
- Otherwise 1.

## Notes

| Code | When | Message |
|---|---|---|
| `game_changers` | always | `Game Changers: 0`, or `Game Changers: 2 (Rhystic Study, Smothering Tithe)` in deck order |
| `pairing_unchecked` | two commanders | `Commander pairing not checked yet (Partner/Background rules come later).` |
| `left_out` | `deck.left_out` not empty | `3 left-out cards (sideboard, maybeboard, companion) weren't checked.` (singular: `1 left-out card (sideboard, maybeboard, companion) wasn't checked.`) |

## Code

- `Card` (in `lookup.py`) gains `color_identity: str`, `commander_status: str` and `is_game_changer: bool`. `CardLookup.find` selects them.
- New `src/fishbowl/deck/validator.py`:
  - `Issue(code, message)` and `ValidationReport(errors, notes)`, plus the property `is_legal` (no errors).
  - `copy_limit(card) -> int | None`
  - One function per check: `check_x(deck, cards) -> list[Issue]`, where `cards` maps oracle_id → `Card`.
  - `validate(deck, lookup) -> ValidationReport` runs them in the order of the table above, then the notes.
  - It reuses `can_be_commander` from `commander.py`.
- The deck command (`uv run python -m fishbowl.deck.parser <file>`) prints `Legal: yes`, or `Legal: no (N errors)` (`Legal: no (1 error)` for exactly one), then `Errors:` and `Notes:` sections, after the parse summary. It exits 0 only when the deck is legal. Problems already make it not legal.

## Testing

- Real-card fixtures added to `tests/conftest.py` and `card_db`: Forest, Relentless Rats, Seven Dwarves, Sylvan Primordial (banned), Absorb Energy (not_legal), Survival of the Fittest (Game Changer). All are copied from `data/oracle-cards.jsonl.gz`.
- Unit tests for `copy_limit` and for every check, passing and failing.
- `validate` on a legal 100-card deck (Goreclaw + 99 Forest), and on one broken deck that triggers every error code.
- Real decks: all three report `is_legal` with Game Changers 0.
- Command output tests updated: small test decks are no longer "legal".

## Out of scope

- Partner, Background and Doctor pairing rules (a later slice).
- Bracket estimation.
- Companion legality, and rules for cards in the sideboard.
