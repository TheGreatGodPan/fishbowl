"""Talking to Scryfall: finding and downloading its bulk card data files."""


def find_bulk_download(index: dict, kind: str) -> str:
    """Return the download URL for one bulk file (e.g. "oracle_cards").

    `index` is the parsed JSON from https://api.scryfall.com/bulk-data.
    Raises ValueError if that kind isn't listed, so a Scryfall change
    fails loudly instead of downloading the wrong thing.
    """
    # .get with a default: a malformed index gives [] instead of a KeyError.
    for entry in index.get("data", []):
        if entry.get("type") == kind:
            return entry["download_uri"]

    raise ValueError(f"Scryfall's bulk-data index has no {kind!r} file")
