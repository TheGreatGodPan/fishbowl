![Fishbowl banner: a goldfish swimming among blank cards and probability charts](docs/images/fishbowl_banner.png)

# Fishbowl

Fishbowl is an open-source deck-tuning and goldfish-coaching tool for Magic: The Gathering's Commander (EDH) format. Paste in a decklist and Fishbowl checks that it's legal, shows mana and curve statistics, and works out the best way to play your first few turns against an empty board ("goldfishing"). A later phase will add games against opponent decks using the [Argentum Engine](https://github.com/wingedsheep/argentum-engine).

**Status:** early development. See [docs/ROADMAP.md](docs/ROADMAP.md) for the plan and progress.

## Install and run

The commands below are identical on Windows (PowerShell), macOS and Linux.

**You need two things first:**

- [Git](https://git-scm.com/downloads), to download the project.
- [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs the right Python version and Fishbowl's libraries for you. You don't need to install Python yourself.

**1. Download the project.**

```
git clone https://github.com/TheGreatGodPan/fishbowl.git
```

**2. Go into the project folder.**

```
cd fishbowl
```

**3. Install Fishbowl's libraries.**

```
uv sync
```

**4. Download the card data.** This fetches about 100 MB of card data from Scryfall and builds a local database from it, so it takes a few minutes. Run it again later to pick up newly released cards.

```
uv run fishbowl refresh
```

**5. Analyze a deck.** This runs every report on the included sample deck.

```
uv run fishbowl analyze examples/sample_deck.txt
```

The sample deck has no `Commander:` line, so Fishbowl asks "Which card is your commander?" and shows a numbered list. Type `2` (Goreclaw) and press Enter. **Tip:** add `Commander: <card name>` as the first line of your own decklist to skip the question.

To analyze your own deck, save it as a text file (one card per line, like `1 Sol Ring`) and use its path in place of `examples/sample_deck.txt`. Run the commands from inside the `fishbowl` folder; if your deck is saved somewhere else, give its full path, for example `C:\Users\me\Documents\mydeck.txt`.

### Other commands

`uv run fishbowl --help` lists everything. Each command below takes a decklist file, for example `uv run fishbowl lands mydeck.txt`.

| Command | What it does |
| --- | --- |
| `refresh` | Downloads the card data and rebuilds the local database (no deck needed). |
| `check DECK` | Checks that the deck is a legal Commander deck. |
| `lands DECK` | Shows the odds of opening hands with 2 to 5 lands, and of making each land drop. |
| `mulligan DECK` | Shows how often you would mulligan, and what hands you end up with. |
| `groups DECK` | Shows the odds of seeing a mana dork or a tutor in your first few turns, and how adding or cutting a few would change them. |
| `curve DECK` | Shows the odds of casting your commander on curve. |
| `charts DECK` | Saves charts as PNG images in a `charts/` folder inside the folder you run it from. |
| `analyze DECK` | Runs check, lands, mulligan, groups and curve in one go. Add `--charts` to save the charts too. |
| `goldfish DECK` | Plays your first turns against an empty board and prints a turn-by-turn log. Add `--games 1000` to play many games and see how often your commander is cast by each turn, next to two lands-only baselines. |

## License

Fishbowl's code is licensed under the [Apache License 2.0](LICENSE).

## Fan Content notice

> Fishbowl is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards. Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC.
