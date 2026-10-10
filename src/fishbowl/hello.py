"""Stage 0 warm-up: count the cards in a plain-text decklist.

Run it with:  uv run python -m fishbowl.hello examples/sample_deck.txt
"""

import sys
from pathlib import Path


def count_cards(text: str) -> int:
    """Add up the quantities in a decklist like "1 Sol Ring" / "36 Forest"."""
    total = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue  # blank line: nothing to count

        first_word = line.split()[0]
        # isdecimal, not isdigit: isdigit says yes to "²", which int() can't convert.
        if first_word.isdecimal():
            total += int(first_word)
        else:
            total += 1  # no quantity given, so assume one copy
    return total


def main() -> None:
    # sys.argv: the words typed on the command line; [0] is the script itself.
    if len(sys.argv) != 2:
        print("Usage: uv run python -m fishbowl.hello <decklist.txt>")
        sys.exit(1)

    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    print(count_cards(text))


# Only runs main() when this file is run directly, not when a test imports it.
if __name__ == "__main__":
    main()
