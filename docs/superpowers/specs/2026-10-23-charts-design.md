# Charts design (Stage 4e)

Date: 2026-10-23 · Status: design approved in conversation (proposed with 4d); spec awaiting Ian's review

## Intent

Turn the 4b and 4c tables into pictures Ian can glance at while tuning a deck: how mulligans lift land drops, and how adding or cutting dorks or tutors moves the odds. Stage 4 is done after this.

**Done when:** `uv run python -m fishbowl.stats.charts tests/decks/goreclaw.txt` writes two PNGs that Ian opens and finds readable, and the Stage 4 roadmap entry is ✅.

## Goals

- **Chart 1: Land drops.** Turns 1–5, the chance of no missed land drop: no mulligan (exact, 4a) vs with mulligans (simulated, 4b).
- **Chart 2: Card groups.** Two side-by-side panels, Mana dorks and Tutors. Each shows the chance of at least one by the opening hand and turns 1–3, with one line per what-if count (4c). Your current count is emphasised.
- A command that writes both into `charts/` and prints the paths.

## Non-goals

- A chart for commander on curve. It's two numbers, so the 4d text table is the better form.
- Interactive charts, dark-mode images, or showing a window. That's for Stage 7.5 (Streamlit).
- Testing pixels. Tests check the chart's structure (lines, labels, axes); Ian checks the look.

## Decisions

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | Library | **Matplotlib**, added with `uv add matplotlib`. It's the first new runtime dependency since the project began. | It's the standard Python plotting library, works on Windows, macOS and Linux, and the roadmap names it. |
| 2 | No window | Call `matplotlib.use("Agg")` before importing `pyplot`. | "Agg" draws straight to an image file. Tests and terminals never pop up a window. |
| 3 | Output | `charts/<deck file stem>-land-drops.png` and `charts/<stem>-card-groups.png`, relative to the working directory like `data/`. `main` takes an `out_dir: Path = Path("charts")` parameter for tests. Add `/charts/` to `.gitignore`. | They're generated files, like the card database. |
| 4 | Image | 8 × 4.5 inches at 150 dpi, light background `#fcfcfb`. | Readable on screen and in a README. |
| 5 | Chart 1 form | A line chart. x = turn 1..5, y = 0–100%. Two series: "No mulligan" in blue `#2a78d6` and "With mulligans" in orange `#eb6834`. 2-pt lines with round markers. Each line is labelled with its name at the right end, plus a legend. | Change over turns calls for a line chart. These two colours passed the colour-blind and contrast validator (worst adjacent CVD ΔE 24.7). |
| 6 | Chart 2 form | Two panels (subplots) side by side with the same 0–100% y-axis. x = Opening, Turn 1, Turn 2, Turn 3. One line per what-if row. | Small multiples, one per group, with no second y-axis. |
| 7 | Chart 2 colours | One blue ramp, light → dark as the count rises. The colour follows the row's **offset from your count**, not its rank: −4 `#86b6ef`, −2 `#5598e7`, yours `#2a78d6`, +2 `#1c5cab`, +4 `#104281`. Your row is thicker (3 pt), and its end label reads "7 dorks (yours)". | It's an ordered quantity, so one hue is right. The ramp passed the ordinal validator. Keying colour by offset means "yours" is always the same blue even when rows are dropped (0 dorks gives yours, +2, +4). |
| 8 | Chrome | Horizontal gridlines only, hairline `#e1e0d9`. Axis lines and ticks in `#898781`. Titles in `#0b0b0b`, other text in `#52514e`. No top or right frame lines. Y ticks as percentages. | Recessive axes keep the eye on the data. |
| 9 | Titles | Chart 1: "{commander}: land drops, with and without mulligans". Chart 2: "{commander}: at least one card from each group". Panel titles: "Mana dorks (7)" and "Tutors (2)", or "Mana dorks (none found)". | The title names the chart, and the count shows in the panel. |
| 10 | Data source | Reuse `mulligan_odds` (4b) and `find_groups` + `what_if` (4c). No new maths. | |
| 11 | Command | `uv run python -m fishbowl.stats.charts <decklist>`. Same shape as the other commands: the notes, the tiny-deck check (fewer than 12 cards in the library, as 4b), the no-commander behaviour (titles use "Deck"). It prints `Saved charts/goreclaw-land-drops.png` and so on, one line per file. | |

## Testing

- The chart functions return a Matplotlib `Figure` and don't save it themselves, so the tests can inspect them:
  - Chart 1 has 2 lines with 5 points each, a legend with both names, y limits 0–1, and the line colours given above.
  - Chart 2 has 2 panels. A group with 7 has 5 lines, one of them labelled "(yours)" and 3 pt wide. A group with 0 has 3 lines. Colours are keyed by offset.
- `main` writes both files to `tmp_path`, each starting with the PNG signature bytes `\x89PNG`, and prints their paths. Tiny deck, no commander, unreadable lines and usage behave as in the other commands.
- Each test closes its figures with `plt.close(fig)` to avoid memory warnings.
- Final step: render Goreclaw and Krenko and **look at the PNGs** for label collisions before calling it done.

## Left to the builder

- Module layout. Suggested: `src/fishbowl/stats/charts.py` with `land_drop_chart(odds, title)`, `card_group_chart(groups, library, title)` and `main`.
- Exact label placement, and the right-hand margin needed for the end labels.
