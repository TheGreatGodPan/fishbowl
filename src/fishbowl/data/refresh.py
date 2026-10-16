"""One command to refresh card data: download Scryfall's file, then rebuild cards.db.

Run it with:  uv run python -m fishbowl.data.refresh
"""

import sys
from collections.abc import Callable

from fishbowl.data import database, scryfall


def refresh(
    download: Callable[[], object] = scryfall.main,
    build: Callable[[], int] = database.main,
) -> int:
    """Download, then build. Returns an exit code (0 = success).

    download and build are parameters so tests can pass in fakes
    instead of touching the internet or data/.
    """
    try:
        download()
    except (OSError, ValueError) as error:
        # OSError covers no network, timeouts and HTTP errors; ValueError covers
        # an index or link from Scryfall that fails our checks.
        print(f"Download failed: {error}")
        print("cards.db was not rebuilt.")
        return 1
    return build()


if __name__ == "__main__":
    sys.exit(refresh())
