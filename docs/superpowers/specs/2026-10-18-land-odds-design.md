# Land odds design (Stage 4a)

Date: 2026-10-18 · Status: approved in conversation

## Goal

For a parsed deck, compute land odds two ways: exactly, with the hypergeometric formula, and by simulating shuffled hands. Show both side by side.

**Done when:** for every row, the simulated value is within 1 percentage point of the exact value, for each of Ian's three decks (Goreclaw 33 lands, Ghalta 39, Krenko 33, each in a 99-card library).

Stage 4 is split into 4a (this: land odds), 4b (mulligans) and 4c (commander on curve + charts).

## Decisions

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | Libraries | Standard library only: `math.comb` for the exact formula, `random.Random(seed)` for simulation. No scipy/numpy. | Ian learns the formula; no new dependencies (CLAUDE.md). ~1 s per 100,000 hands is fine. numpy may come with Stage 6–7. The roadmap line mentioning `scipy.stats.hypergeom` is updated. |
| 2 | Library size | Deck minus commanders: 99 (98 with two). With no commander identified, all cards are the library, and a note says so. | Commanders start in the command zone. |
| 3 | What's a land | Front face's type line contains the word `Land`. Cards with a land only on the back count as non-lands for now. | Same front-face rule as the commander check. None of Ian's decks has such cards. |
| 4 | Draws | Multiplayer default: every player draws on turn 1, so 7 + t cards are seen by turn t. Option `skip_first_draw=True` gives 7 + t − 1. | Multiplayer Commander rule; the option covers 2-player games. |
| 5 | Land drop through turn t | At least t lands among the cards seen by turn t. | Lands can be held, so this is the exact condition for never missing a drop through turn t. |
| 6 | Agreement | 100,000 trials, seed 42, tolerance 0.01 absolute (1 percentage point). | Standard error at 100,000 trials is about 0.0016, so 0.01 is a safe margin. |

## Rows

1. `Opening hand: 2 lands`, `3 lands`, `4 lands`, `5 lands`: exactly k lands in 7 cards.
2. `Opening hand: 2-5 lands`: their sum.
3. `Land drop through turn 1` … `turn 5`: at least t lands in 7 + t cards (or 7 + t − 1 with `skip_first_draw`).

## Formulas

- `P(exactly k) = C(L, k) · C(N − L, n − k) / C(N, n)`, where L = lands, N = library, n = cards drawn.
- `P(at least k) = Σ P(exactly i)` for i = k … n.
- Invalid inputs raise `ValueError`: lands outside 0..N, or n outside 0..N.

## Simulation

Number the library 0..N−1, with cards 0..L−1 being the lands. Each trial does `rng.sample(range(N), m)`, where m is the most cards seen in any row (12 by default). That is the top m cards of a shuffled library. Positions below L are lands. Count the hits for each row.

## Command

`uv run python -m fishbowl.stats.lands <decklist>` reads and parses the file and asks for the commander if needed. This uses a new shared `read_deck` helper extracted from the deck command. It then prints a header line and an aligned table with columns: label, exact (percentage with 1 decimal), simulated.

## Testing

- The formula on hand-checkable cases: 2 lands of 4, draw 1 → exactly 1 land = 0.5. 2 of 4, draw 2 → 0 lands = 1/6.
- `exact_exactly` over k = 0..n sums to 1. `exact_at_least(0, …) = 1`. Invalid inputs raise `ValueError`.
- The simulation gives identical results for the same seed and different results for another seed.
- Agreement within 0.01 for 33/99 and 39/99, both draw modes.
- Real decks (`data/cards.db`): library counts are (33, 99), (39, 99) and (33, 99).

## Out of scope

Mulligans (4b), the commander on curve and charts (4c), mana rocks and dorks (Stage 6), and double-faced cards with a land on the back.
