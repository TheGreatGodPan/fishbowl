# Card groups design (Stage 4c)

Date: 2026-10-23 · Status: draft for Ian's review

## Intent

When Ian judges an opening hand, he looks for specific cards more than lands. For Goreclaw that's mana dorks; for Krenko it's goblin tutors (Goblin Matron, Goblin Recruiter). A single probability ("41% to have a dork in the opening hand") doesn't lead to a decision. A **comparison** does: "how would that change with 2 more dorks?" So 4c answers a deck-tuning question:

> For each card group: how likely am I to have at least one by turn t, and how would that change if I ran a few more or a few fewer?

Ian doesn't tag cards in Moxfield, so Fishbowl detects the groups itself from Scryfall card text. It prints which cards matched so Ian can spot misfires.

**Done when:** for each of Ian's three decks the matched-card lists look right to Ian, and for each group the simulated "current count" row is within 0.01 of exact.

## Goals

- Detect two groups from card data: **mana dorks** and **tutors**.
- For each group, show a what-if table: the chance of at least one card from the group by each checkpoint, for the current count and for counts around it.
- Exact (hypergeometric) for every row; simulated as well for the current-count row, as in 4a/4b.

## Non-goals

- Charts (Matplotlib) and the lands-only "commander on curve" baseline. These move to a new Stage 4d.
- Combo pieces or any user-named group. This needs a list Ian writes, so it's for a later slice.
- Playing the cards out (a dork on turn 1 → commander on turn 3). That's Stage 6.
- Mulligans in the group odds. The odds are for the hands you're dealt, before any mulligan.
- Other groups (non-creature ramp, card draw, removal).

## Anti-goals

- **Silent misdetection.** A group count Ian can't check is worse than none. The matched cards are always printed.
- **Counting land searches as tutors.** Nature's Lore, Three Visits and Skyshroud Claim fetch Forests; they are ramp, not tutors.

## Decisions

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | Groups | Mana dorks and tutors, every deck, always both. Picked by Claude; Ian delegated the choice. | Dorks fit Goreclaw and tutors fit Krenko. Showing both everywhere keeps the code simple, and a group with 0 cards still has a useful what-if ("what if I added 2?"). |
| 2 | What's a mana dork | The front face's type line contains the word `Creature`, and its rules text has a tap ability that adds mana: the pattern `{T}`, then anything up to the next `.` (or none), then `: Add `. *(My call: oracle text, not the `produced_mana` column, because the prototype got the right 7 for Goreclaw.)* | A trial on Goreclaw found exactly: Elvish Mystic, Fanatic of Rhonas, Fyndhorn Elves, Karametra's Acolyte, Llanowar Elves, Selvala, Heart of the Wilds, and Whisperer of the Wilds. Arbor Elf (untaps a Forest) is correctly left out. |
| 3 | What's a tutor | Rules text contains "search your library for" (any capitalisation), and the text after it, up to the next `.`, doesn't mention `land` or any basic land type (`Plains`, `Island`, `Swamp`, `Mountain`, `Forest`). | The trial found Goblin Matron and Goblin Recruiter (Krenko), and Defense of the Heart and Fierce Empath (Goreclaw). It also showed that without the basic-type rule, Forest fetches sneak in. |
| 4 | Where detection rules live | In code, in the new module, as named patterns with a short comment each. | These are Fishbowl's heuristics, not format rules, so the "format rules are data" rule doesn't apply. |
| 5 | Commanders | Commanders are in the command zone, not the library. They're never counted in a group, and the library size is the same as in `library_counts`. | Same as 4a. |
| 6 | Checkpoints | Opening hand (7 cards), by turn 1 (8), turn 2 (9), turn 3 (10). Multiplayer draws, as in 4a. *(My call: stops at turn 3, because dorks and tutors matter early.)* | |
| 7 | What-if counts | Current count −4, −2, current, +2, +4, dropping any below 0 or above the library size. *(My call.)* | Steps of 2 show the trend without a long table. The current row is marked. |
| 8 | Exact vs simulated | Every row is exact (`exact_at_least(1, count, library, cards)`). The current-count row is also simulated (100,000 hands, seed 42) and shown in a "simulated" column; other rows leave it blank. | It keeps the 4a/4b exact-vs-simulated check without simulating every what-if row. |
| 10 | Double-faced and split cards | Detection reads the card's top-level `oracle_text` and the front of `type_line`, as 4a does. When `oracle_text` is empty (Scryfall leaves it empty for many multi-face cards), the card matches no group. *(My call: no change to `Card` or `CardLookup`. Same simplification as 4a's MDFC lands, and tracked as the same open item.)* | |
| 11 | How literal the rules are | Implement decisions 2 and 3 literally. The dork regex is `\{T\}[^.]*: Add ` (so Selvala's "{G}, {T}: Add" matches). No extra tutor tuning beyond the land rule. *(My call: Ian checks the printed lists, and misfires get fixed with a test then.)* | |
| 12 | Commander in a group | Handled like `library_counts`: one copy of each commander is left out of both the count and the printed names. | |
| 9 | Libraries | Standard library only. | No new dependencies; Matplotlib waits for 4d. |

## Command

`uv run python -m fishbowl.stats.groups <decklist>`. It has the same shape as the 4a/4b commands: it reuses `find_deck_file` and `read_deck`, gives the same no-commander, unreadable-lines and tiny-deck (fewer than 10 cards) messages, and uses a header line like 4a's.

Then, for each group:

```
Mana dorks: 7 in the library
  Elvish Mystic, Fanatic of Rhonas, Fyndhorn Elves, Karametra's Acolyte,
  Llanowar Elves, Selvala, Heart of the Wilds, Whisperer of the Wilds

At least one          opening   turn 1   turn 2   turn 3   simulated (opening)
  3 dorks               ...
  5 dorks               31%      35%      39%      ...
  7 dorks (yours)       41%      46%      50%      ...      41.0%
  9 dorks               50%      55%      59%      ...
  11 dorks              57%      62%      67%      ...
```

A group with no matches prints "Tutors: none found" and still shows its what-if rows (0, 2, 4). Percentages are whole numbers in the what-if columns (they're for comparing) and 1 decimal in the simulated column. The exact layout and column widths are the builder's call.

## What's left to the builder

- Function names and module layout inside `src/fishbowl/stats/`. Suggested: `groups.py` with `is_mana_dork(card)`, `is_tutor(card)`, `find_groups(deck, lookup)`, `what_if(count, library, ...)`, `main`.
- How the matched names wrap on screen.
- Whether the simulation reuses `land_odds`-style sampling or a small helper. It should follow 4a's numbering trick: cards numbered below `count` are in the group.

## Testing

- Detection, on hand-written `Card` values: a dork (Llanowar Elves text) → yes. Arbor Elf text → no. A non-creature mana rock (Arcane Signet) → not a dork. Goblin Matron → tutor. Nature's Lore ("a Forest card") → not a tutor. Cultivate ("basic land cards") → not a tutor. Demonic Tutor ("a card") → tutor.
- Real decks (`data/cards.db`, in `tests/deck/test_real_decks.py` style):
  - Goreclaw dorks are exactly the 7 names above.
  - Krenko tutors include Goblin Matron and Goblin Recruiter.
  - Goreclaw tutors don't include Nature's Lore, Three Visits or Skyshroud Claim.
- What-if: the rows are current −4..+4 by 2, clipped at 0 and at the library size. 7 dorks of 99 in the opening hand = 41% (40.6%). Larger counts never give a lower chance.
- Simulated within 0.01 of exact for the current row. The same seed gives the same result.
- `main`: prints both groups, the matched names, and the "(yours)" marker; the tiny-deck message; the notes.

## Roadmap change

Stage 4 is split: 4c = card groups (this), 4d = commander on curve (lands-only baseline) + Matplotlib charts. Stage 4 stays 🔄 until 4d.
