# Goldfish turns design (Stage 6)

Date: 2026-11-06 · Status: design approved in conversation; spec awaiting Ian's review

## Intent

Play a deck's first turns against an empty board, so Ian can see one game turn by turn, and over many games how often he casts his commander by each turn. The gap between that number and the lands-only 4d baseline is what his dorks and ramp are worth.

**Done when:**
- A seeded Goreclaw game's log reads correctly to Ian, turn by turn.
- `fishbowl goldfish tests/decks/goreclaw.txt --games 1000` prints commander-by-turn odds next to the 4d lands-only baseline.
- ROADMAP marks Stage 6 ✅.

## Goals

- Classify every card into one of these kinds: **land**, **fetch**, **rock**, **dork**, **ramp**, **draw** or **generic**. Print the classification so misfires are visible.
- Build a `GameState` that can be copied independently, and a seeded game loop.
- A simple, explainable play priority. No search; that's Stage 7.
- Commander tax, and the 4b mulligan with bottoming by cost.
- A `fishbowl goldfish DECK [--seed N] [--turns N] [--games N]` command.

## Non-goals (stated in the output's footer line)

The simulation leaves out:
- combat, damage and opponents
- triggered and activated abilities (Goreclaw's discount, Krenko's tokens)
- X spells (X = 0)
- cost reducers
- discard effects
- the back faces of double-faced cards
- alternate costs

Goldfish also doesn't join `analyze`. *(My call: keep `analyze` fast; it can join later.)*

## Card kinds (rules verified against the real decks on 2026-11-06)

Remove parenthesised reminder text and double-quoted text before matching, as 4c does for dorks. Check the kinds in this order; the first match wins.

| Kind | Rule | Real matches |
|---|---|---|
| land | `is_land(type_line)`, and not a fetch | basics, utility lands |
| fetch | a land with empty `produced_mana` whose text matches `search your library for a basic land` | Evolving Wilds, Terramorphic Expanse |
| dork | `is_mana_dork(card)` (4c) | Goreclaw: Elvish Mystic, Fanatic of Rhonas, Fyndhorn Elves, Karametra's Acolyte, Llanowar Elves, Selvala, Whisperer of the Wilds |
| rock | the front type line has the word `Artifact` and not `Creature`, and the text matches `\{T\}[^.]*: Add ` | Sol Ring, Arcane Signet, Fire Diamond, Commander's Sphere, The Great Henge |
| ramp | the front type line has `Sorcery` or `Instant`, and the text matches `search your library for [^.]*(land\|plains\|island\|swamp\|mountain\|forest) cards?[^.]*onto the battlefield` (case-insensitive) | Cultivate, Kodama's Reach, Nature's Lore, Rampant Growth, Skyshroud Claim, Three Visits |
| draw | the front type line has `Sorcery` or `Instant`, and the text matches `\bdraw (a\|one\|two\|three\|four\|five) cards?\b` (case-insensitive) | Harmonize, Shamanic Revelation, Faithless Looting, Incinerating Blast |
| generic | everything else | |

## Card details (a `PlayCard` per card)

- `mana_value` = `int(cmc or 0)`. `pips` comes from 4d's `colour_pips(mana_cost)`.
- **Mana produced:**
  - **land:** `produced_mana`, 1 mana.
  - **fetch:** the commander's colour identity (or `"C"` if there's no commander), 1 mana, enters tapped.
  - **rock and dork:** colours from `produced_mana`; the amount is the number of mana symbols between "Add " and the next `.` in the first `{T}…: Add` ability (Sol Ring `{C}{C}` = 2; "one mana of any color" = 1; Selvala's "X mana" = 1). *(My call: count `{…}` symbols; with none, use 1.)*
- **Enters tapped:** a land whose text contains "enters tapped" or "enters the battlefield tapped", and every fetch. *(My call: conditional "unless…" lands count as untapped.)*
- **Ramp:**
  - **Lands to the battlefield:** 2 if the text contains "up to two" and doesn't contain "put one onto the battlefield"; otherwise 1. Skyshroud Claim gives 2; Cultivate and Kodama's Reach give 1.
  - **Lands to hand:** 1 if the text contains "the other into your hand"; otherwise 0.
  - **Tapped:** the lands enter tapped if the clause contains "tapped".
  
  The expected results:
  - Rampant Growth: 1 tapped land
  - Nature's Lore: 1 untapped
  - Three Visits: 1 untapped
  - Skyshroud Claim: 2 untapped
  - Cultivate and Kodama's Reach: 1 tapped + 1 to hand

  The lands fetched are basic lands from the library, preferring a colour the commander needs. If the library has none, the spell gets nothing (that's logged).
- **Draw:** N from the word (a/one = 1 … five = 5).

## Game rules

- **Setup:**
  - The library is the deck minus one copy of each commander. The commanders start in the command zone.
  - Shuffle with `random.Random(seed)`.
  - Opening hand: the 4b keep rule (2–5 land-or-fetch cards in 7, free first mulligan, keep at 5 if forced).
  - Bottoming, one card at a time: with more than 3 lands in hand, bottom a land; otherwise bottom the spell with the highest mana value (ties go to the first in hand). Bottomed cards go to the library's bottom.
- **Each turn:**
  1. Untap everything, and dorks lose summoning sickness.
  2. Draw a card (every turn, including turn 1: multiplayer). If the library is empty, the game ends.
  3. Play at most one land. Prefer an untapped land that produces a colour the commander's pips need and no battlefield source covers yet. Otherwise take any untapped land, otherwise a tapped land or fetch. The first in hand wins ties.
  4. Cast spells until nothing more is castable, picking each time by priority:
     1. the commander (cost + `{2}` × earlier casts)
     2. rock, dork or ramp, cheapest first
     3. draw, cheapest first
     4. generic, most expensive first
     
     Ties go to the first in hand.
- **Paying:** a spell is castable if the total available mana is at least its mana value and, for each pip colour, the available sources producing that colour cover the pips (sources counted by mana amount). To pay:
  1. Pay the coloured pips first, using sources with the fewest colours.
  2. Pay the rest with the remaining sources: colourless-only first, then the fewest colours.
  3. Tap whole sources. Mana left over from a multi-mana source is lost; the log notes it as unused.
  
  *(The same approximation as 4d.)*
- **Permanents:** rocks and dorks go to the battlefield (dorks are sick until the next turn). Ramp, draw and generic spells go to the graveyard after they resolve. The commander goes to the battlefield. `commander_casts += 1`, and the first cast turn is recorded.

## Log format (one game)

```
Goreclaw, Terror of Qal Sisma — seed 42, 6 turns
Mulligans: 0 (kept 7)
Opening hand: Forest, Forest, Llanowar Elves, Cultivate, Beast Whisperer, Sol Ring, Elder Gargaroth
Turn 1: draw Forest. Play Forest. Cast Llanowar Elves. Mana: 1 used, 0 unused.
Turn 2: draw Harmonize. Play Forest. Cast Sol Ring. Cast ... Mana: 4 used, 0 unused.
...
Commander cast on turn 3.
Simplified: no combat, abilities, X costs or cost reducers.
```

The exact wording is the builder's call, but each turn is one line beginning `Turn N:`. The summary `Commander cast on turn N.` (or `Commander not cast in N turns.`) and the footer are required.

Before the log, the command prints the card kinds, one line per non-land kind with its names, like 4c's groups.

## Many games (`--games N`)

- Game i uses seed `seed + i`. Default turns: `max(8, commander mana value + 2)`.
- It prints:
  - for each turn from 1 to the turn limit, `Commander cast by turn t: x.x%`
  - `Average turn (when cast): t.t`
  - `Not cast in N turns: x.x%`
  - **`Lands-only baseline (4d): x.x% by turn M`**, using `curve_odds`' exact lands-and-colours approximation; the simulated colours value is fine
- For two commanders: report the first commander only, and print a note. *(My call.)*

## Testing

- **Classification:** hand-built `Card`s for each rule and the decision examples above. Real decks: the matches listed in the kinds table.
- **Engine:** deterministic tests with hand-built `PlayCard`s and a fixed library order (no shuffle). Check that:
  - a dork can't tap the turn it enters
  - Sol Ring makes 2
  - Cultivate puts a tapped basic onto the battlefield and one into the hand
  - commander tax costs 2 more on a second cast
  - a colour requirement blocks a cast
  - the land choice prefers the missing colour
  - `copy()` independence: changing the copy's hand, library or battlefield leaves the original untouched
- **Seeds:** the same seed gives the same log; a different seed gives a different log.
- **Mulligan:** bottoming removes the highest-mana-value spell.
- **CLI:** single game and `--games 200` on `card_db` decks; the exit code is 0; the summary lines are present.
- **Real:** `goldfish tests/decks/goreclaw.txt --games 1000`. Goreclaw's "by turn 4" must be higher than the 4d baseline (dorks and ramp help). Report the numbers.

## Left to the builder

- The module layout. Suggested: `src/fishbowl/sim/{cards,game,goldfish}.py`, per CLAUDE.md's `sim/`.
- Helper names, and the exact log wording within the rules above.
