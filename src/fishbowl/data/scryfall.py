"""Talking to Scryfall: finding and downloading its bulk card data files.

Download the oracle_cards file with:  uv run python -m fishbowl.data.scryfall
"""

import json
import shutil
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

INDEX_URL = "https://api.scryfall.com/bulk-data"
# Kept compressed: Pandas reads .jsonl.gz directly, so there's no need to unzip.
DEFAULT_DEST = Path("data") / "oracle-cards.jsonl.gz"
# Scryfall asks every client to identify itself, like a polite scanner.
USER_AGENT = "Fishbowl/0.1 (+https://github.com/TheGreatGodPan/fishbowl)"
TIMEOUT_SECONDS = 60


def build_request(url: str) -> Request:
    """A request carrying the headers Scryfall asks for."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    return Request(url, headers=headers)


def check_download_url(url: str) -> None:
    """Raise ValueError unless url is https:// on scryfall.io or a subdomain of it.

    The download link arrives over the network, so we check it before using it.
    """
    parts = urlparse(url)
    # .hostname is the real host: it drops any "user@" prefix and lowercases it.
    host = parts.hostname or ""
    if parts.scheme != "https":
        raise ValueError(f"Refusing non-https download URL: {url!r}")
    # Exact match or a true subdomain; a plain endswith("scryfall.io") would let
    # "notscryfall.io" through.
    if host != "scryfall.io" and not host.endswith(".scryfall.io"):
        raise ValueError(f"Refusing download from outside scryfall.io: {url!r}")


def find_bulk_download(index: dict, kind: str) -> str:
    """Return the download URL for one bulk file (e.g. "oracle_cards").

    `index` is the parsed JSON from https://api.scryfall.com/bulk-data.
    Raises ValueError if that kind isn't listed, so a Scryfall change
    fails loudly instead of downloading the wrong thing.
    """
    # .get with a default: a malformed index gives [] instead of a KeyError.
    for entry in index.get("data", []):
        if entry.get("type") == kind:
            # Scryfall serves bulk files as gzipped JSON Lines (one card per line).
            url = entry.get("jsonl_download_uri")
            if not url:
                raise ValueError(f"Scryfall's {kind!r} entry has no download link")
            return url

    raise ValueError(f"Scryfall's bulk-data index has no {kind!r} file")


def fetch_json(url: str) -> dict:
    """Fetch a small JSON document (like the bulk-data index)."""
    # with: closes the connection when the block ends, even after an error.
    with urlopen(build_request(url), timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def download_file(url: str, dest: Path) -> None:
    """Stream url to dest without holding the whole file in memory."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Write to a .part file first; only a finished download gets the real name.
    partial = dest.with_name(dest.name + ".part")
    # One with, two resources: the connection and the file ("wb" = write bytes).
    with (
        urlopen(build_request(url), timeout=TIMEOUT_SECONDS) as response,
        partial.open("wb") as out,
    ):
        shutil.copyfileobj(response, out)  # copies in chunks
    partial.replace(dest)  # rename: all or nothing


def main() -> None:
    print(f"Fetching bulk-data index from {INDEX_URL}")
    url = find_bulk_download(fetch_json(INDEX_URL), "oracle_cards")
    check_download_url(url)

    print(f"Downloading {url}")
    download_file(url, DEFAULT_DEST)
    size_mb = DEFAULT_DEST.stat().st_size / 1_000_000
    print(f"Saved {DEFAULT_DEST} ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
