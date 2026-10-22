# Mulligans design (Stage 4b)

Date: 2026-10-21 · Status: approved in conversation (2026-10-18 design, confirmed 2026-10-21)

## Goal

Answer two questions about a deck once mulligans are allowed:

1. How often do you keep on the 1st, 2nd, 3rd... hand, and what hand size do you usually end up with?
2. How much do mulligans improve your chance of never missing a land drop through turns 1–5?

Keep rates are computed two ways, exactly and by simulation, and shown side by side, as in Stage 4a. Land drops after mulligans are simulated only. They are shown next to the 4a exact no-mulligan numbers so the gain is visible.

**Done when:** every simulated keep-rate row (and the average kept hand size) is within 0.01 of its exact value, for 33/99 and 39/99, with the free mulligan on and off.

Stage 4 is split into 4a (land odds, done), 4b (this: mulligans) and 4c (commander on curve + charts).

## Decisions

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | Keep rule | Keep if the 7 cards drawn contain 2–5 lands (the same range as the 4a "2-5 lands" row). Otherwise mulligan. | Simple, common rule of thumb. It reuses the 4a number as *p*. |
| 2 | Mulligan type | London mulligan: always draw 7, then put 1 card on the bottom of the library for each non-free mulligan taken so far. The keep decision is made on the 7 drawn, before bottoming. | Current Commander rule. |
| 3 | Free first mulligan | On by default (`free_first=True`): hand sizes go 7 → 7 → 6 → 5. With `free_first=False`: 7 → 6 → 5. | Multiplayer Commander gives one free mulligan. The option covers other tables. |
| 4 | Floor | Always keep at 5 cards, whatever the 7 drawn look like ("forced keep"). | Going below 5 is rarely right. It also bounds the loop. |
| 5 | Bottoming | One card at a time: if the hand holds **more than 3** lands, bottom a land; otherwise bottom a spell. | Aims for 3 lands, the usual sweet spot. When the hand has 3 or fewer lands it has at least 4 spells, so a spell is always available. |
| 6 | Draws | Multiplayer: everyone draws on turn 1, so by turn t you've drawn t cards after the kept hand. No `skip_first_draw` option in 4b. | Matches the 4a default. *(Builder's-call note: dropped to keep 4b small. It's easy to add later.)* |
| 7 | Land drop through turn t | Lands left in the kept hand after bottoming, plus lands in the next t cards drawn, is at least t. | Same idea as 4a: lands can be held. |
| 8 | Agreement | 100,000 trials, seed 42, tolerance 0.01 absolute. | Same as 4a. The standard error is about 0.0016. |
| 9 | Libraries | Standard library only (`math`, `random`). | No new dependencies. |
| 10 | Command options | `free_first` is a function parameter only. The command always uses the default (free mulligan on) and says so in its header. | Command-line flags arrive with `typer` in Stage 5. |

## Exact keep rates (the geometric pattern)

Let *p* = P(2–5 lands in 7) = Σ `exact_exactly(k, lands, library, 7)` for k = 2..5. Each attempt is a fresh shuffle, so attempts are independent.

With the free mulligan (4 attempts):

| Row | Hand size | Exact |
|---|---|---|
| Keep 7 (first hand) | 7 | p |
| Keep 7 (free mulligan) | 7 | (1−p)·p |
| Keep 6 | 6 | (1−p)²·p |
| Keep 5 (forced) | 5 | (1−p)³ |

Without it (3 attempts): Keep 7 = p, Keep 6 = (1−p)·p, Keep 5 (forced) = (1−p)².

The rows always sum to 1. **Average kept hand size** (exact) = Σ size × rate.

The general form: P(keep on attempt i) = (1−p)^(i−1)·p, and the last attempt is (1−p)^(attempts−1).

## Simulation

Number the library 0..N−1. Cards numbered below L (the land count) are lands, as in 4a.

Each trial:
1. For each attempt in order: draw `rng.sample(range(N), 12)` (the top 12 of a fresh shuffle; 7 for the hand plus 5 draws). Count the lands in the first 7. If `keeps(...)` is true, or this is the last attempt, keep this attempt.
2. Record which attempt was kept (for the keep-rate rows and average hand size).
3. Bottom cards with `lands_after_bottoming` to get the lands left in hand. The bottomed cards go under the library and can't be drawn in 5 turns, so the next draws are positions 7..11 of the same sample.
4. For each turn t = 1..5: count a hit if the hand's lands plus lands in positions 7..7+t−1 is at least t.

## Functions (in `src/fishbowl/stats/mulligan.py`)

- `keeps(lands_in_seven: int) -> bool`: true for 2–5.
- `lands_after_bottoming(lands_in_seven: int, to_bottom: int) -> int`: applies decision 5. For example (7, 2) → 5; (6, 2) → 4; (4, 2) → 3; (2, 2) → 2; (5, 0) → 5.
- `keep_rates(p: float, free_first: bool = True) -> list[float]`: the exact rows above, in order.
- `mulligan_odds(lands, library, trials=TRIALS, seed=SEED, free_first=True)`: returns the keep-rate rows (exact + simulated), the average hand size row (exact + simulated), and the land-drop rows (no-mulligan exact from `exact_at_least`, with-mulligan simulated). It raises `ValueError` for the same bad inputs as `land_odds` (library too small to see 12 cards, lands out of range, trials < 1). The return shape is the builder's call. Reusing `OddsRow` for the keep rows is suggested; the land-drop rows can reuse it too, reading the two columns as "no mulligan" and "with mulligans".
- `main(...)`: same shape and parameters as `lands.main`. It reuses `find_deck_file`, `read_deck` and `library_counts`, and gives the same "Only N cards in the library…" message and exit code 1 for tiny decks.

Constants such as `HAND_SIZE`, `TRIALS`, `SEED` and `LAND_DROP_TURNS` are imported from `lands.py`, not redefined.

## Command

`uv run python -m fishbowl.stats.mulligan <decklist>`

Prints:
1. A header like 4a's. Add: "free first mulligan; keep 2-5 lands; always keep at 5".
2. The unreadable-lines note, if any (as in 4a).
3. **Keep rates** table: columns label, exact, simulated (percentages, 1 decimal). Then an "Average hand size" row with 2 decimals (not a percentage).
4. **Land drops** table: columns label, no mulligan, with mulligans (percentages, 1 decimal).

## Testing

- `keeps`: 1 → False, 2 → True, 5 → True, 6 → False, 0 and 7 → False.
- `lands_after_bottoming`: the examples above. The result never exceeds the hand size (7 − to_bottom).
- `keep_rates`: sums to 1 for several p, both modes. p = 1 gives [1, 0, 0, 0]. p = 0 gives everything on the forced row. Hand-checkable: p = 0.5 with the free mulligan gives [0.5, 0.25, 0.125, 0.125].
- `mulligan_odds`: same seed gives identical results; a different seed gives different ones. Every keep row and the average hand size are within 0.01 of exact for 33/99 and 39/99, `free_first` on and off. Bad inputs raise `ValueError`.
- Sanity: for 33/99, "with mulligans" is higher than "no mulligan" for the turn 2 land drop.
- `main`: runs on a test decklist and prints both tables. A tiny deck prints the "Only N cards" message and returns 1.

## Out of scope

Smarter keep rules (looking at spells, curve or the commander), bottoming by card quality, the 2-player draw option, command-line flags (Stage 5), the commander on curve and charts (4c), and double-faced cards with a land on the back.
