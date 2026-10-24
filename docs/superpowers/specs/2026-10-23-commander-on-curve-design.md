# Commander on curve design (Stage 4d)

Date: 2026-10-23 · Status: design approved in conversation; spec awaiting Ian's review

## Intent

Answer "will I have the lands to cast my commander on the turn its mana value says?" using **lands only**. That's the honest baseline. The gap between it and how early Ian actually casts his commander is roughly what dorks, rocks and ramp contribute. Stage 6 models those.

**Done when:** for each commander in Ian's three decks, the simulated "enough lands" row is within 0.01 of exact.

Stage 4 is now 4a (lands), 4b (mulligans), 4c (card groups), 4d (this), and 4e (Matplotlib charts, next). Stage 4 is done after 4e.

## Goals

- For each commander: its mana value M, its coloured pips, and two chances by turn M:
  1. **Enough lands:** at least M lands among the cards seen by turn M. Exact and simulated.
  2. **Enough lands and colours:** as above, and for each colour in the cost, at least as many of the seen lands produce that colour as the cost has pips of it. Simulated only.
- A clear label: "lands only; ignores dorks, rocks and cost reducers".

## Non-goals

- Mana dorks, rocks, ramp spells, cost reduction (Ghalta), commander tax, and mulligans. Stage 6 covers the play; mulligans stay in 4b's command.
- An exact formula for the colour row. It needs the multivariate hypergeometric distribution, which isn't worth learning yet.
- Charts (4e).
- Fetch lands (Evolving Wilds and similar, with an empty `produced_mana`) as colour sources.
- Pathway lands (one colour chosen on play) count for both colours, the same approximation as decision 5.

## Decisions

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | New card data | Add `mana_cost: str \| None = None`, `cmc: float \| None = None` and `produced_mana: str = ""` to the end of `Card` in `deck/lookup.py`, with defaults, and select them in `_FIELDS`. | The database already has these columns (`produced_mana` is WUBRGC letters, e.g. "G"). With defaults, existing `Card(...)` calls keep working. |
| 2 | Mana value | M = `int(cmc)`. X counts as 0, following Scryfall's `cmc`. | Scryfall's own number. |
| 3 | Pips | Count the plain single-colour symbols `{W}`, `{U}`, `{B}`, `{R}`, `{G}` in the commander's `mana_cost`. `{C}` pips count against colourless sources (`produced_mana` "C"). Hybrid, Phyrexian and generic symbols add no colour requirement. *(My call; none of Ian's commanders has them.)* | |
| 4 | Turn and cards seen | By turn M, 7 + M cards are seen (multiplayer draws, as in 4a). | Same rule as 4a's land drops. |
| 5 | Colour check | Each colour is checked on its own: sources of that colour among the seen lands ≥ its pips. A dual land counts for both colours. *(My call: exact for mono-colour costs. For multi-colour costs it slightly overstates, because one dual can't pay two pips at once. This is noted on screen as "approximate for multi-colour costs" when the cost has 2 or more colours.)* | |
| 6 | Lands' colours in the simulation | Number the library 0..N−1. Cards 0..L−1 are lands, and each has its `produced_mana` string in a list built from the deck (one entry per copy, commanders excluded as in `library_counts`). | It extends 4a's numbering trick. |
| 7 | Settings | 100,000 trials, seed 42, tolerance 0.01 on the "enough lands" row. | Same as 4a–4c. |
| 8 | Big mana values | If 7 + M is more than the library, that commander gets "Can't be cast on curve from lands in a {N}-card library" instead of rows. Ghalta (M = 12) gets a note: "cost reducers aren't modelled". It's printed whenever M ≥ 8. *(My call.)* | Ghalta's real speed comes from its cost reduction. |
| 9 | Two commanders | One block per commander. | Partners each have their own cost. |
| 11 | What `produced_mana` says | Trust it as stored (checked in the real DB): Command Tower and Exotic Orchard are "WUBRG", Forest is "G", and Bonders' Enclave is "C". 52 lands have "" (mostly fetch lands like Evolving Wilds). They count as lands but are never colour sources. *(My call: a known undercount for fetch-land decks, noted in Out of scope. None of Ian's three decks is affected enough to change the colour row.)* | |
| 12 | Which lands | L and the lands' colour list use `is_land` and the same per-copy, commander-excluded counting as `library_counts`. The test should assert that the colour list has exactly L entries. | |
| 13 | Commander's card | Each commander comes from `deck.commanders` (a `DeckEntry` with a name) and is looked up with `lookup.find`. If the lookup fails, or `cmc` is `None`, or M = 0, the command prints "{name}: no mana cost found; skipped" for that commander. *(My call.)* | |
| 14 | Simulation | A new small loop: `rng.sample(range(N), 7 + M)` per trial, with its own `random.Random(seed)` per commander. It doesn't reuse `land_odds`. | |
| 15 | Too big to cast | `main` checks 7 + M ≤ N itself and prints the decision-8 message. The maths function raises `ValueError` like the others, but `main` never triggers it. The Ghalta M = 12 agreement test is a plain unit test on numbers (39, 99), not a real-DB test. | |
| 10 | No commander | Print "Nothing to cast on curve." and exit 0, after the usual unreadable-lines note. | There's nothing to compute. |

## Command

`uv run python -m fishbowl.stats.curve <decklist>`. It reuses `find_deck_file` and `read_deck` and has the same header style. Example (numbers verified by prototype):

```
Goreclaw, Terror of Qal Sisma: 33 lands in a 99-card library (100,000 simulated hands, seed 42; multiplayer: everyone draws on turn 1)
Lands only; ignores dorks, rocks and cost reducers.

Goreclaw, Terror of Qal Sisma {3}{G}: mana value 4, cast on turn 4
                                exact  simulated
  4+ lands by turn 4            53.3%      53.1%
  ...and 1+ green source                   53.1%
```

The row wording and column widths are the builder's call. Colour names are spelled out (white, blue, black, red, green).

## Testing

- `Card` gains its new fields. Existing tests still pass unchanged, and a lookup returns Sol Ring's `produced_mana == "C"` and `mana_cost == "{1}"`.
- Pips: `"{2}{R}{R}"` → {R: 2}; `"{3}{G}"` → {G: 1}; `"{1}{G/W}"` → {} (hybrid is ignored); `None` → {}.
- Exact row = `exact_at_least(M, L, N, 7 + M)`: 33 of 99 with M = 4 gives 0.533.
- Simulated within 0.01 of exact for M = 4 (33/99) and M = 12 (39/99). The same seed gives the same result.
- The colour row is never higher than the lands row. With every land producing the colour, they're equal. With no sources, the colour row is 0.
- `main`:
  - prints the block
  - gives the no-commander message
  - gives the too-big-to-cast message for a tiny library
  - prints the Ghalta-style note when M ≥ 8
  - prints the multi-colour note
- Real decks: Goreclaw (M 4, G 1), Krenko (M 4, R 2), Ghalta (M 12, G 2).

## Left to the builder

Module layout: suggested `src/fishbowl/stats/curve.py`. Also function names, the return type, and the exact wording of rows.
