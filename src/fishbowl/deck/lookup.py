"""Finding cards in data/cards.db by name, including alternate printed names."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Self

DEFAULT_DB = Path("data") / "cards.db"

_FIELDS = (
    "c.oracle_id, c.name, c.type_line, c.oracle_text, "
    "c.color_identity, c.commander_status, c.is_game_changer"
)
_BY_NAME = f"SELECT {_FIELDS} FROM cards AS c WHERE c.name = ? COLLATE NOCASE"
# The alias column is declared COLLATE NOCASE, so this match ignores case too.
_BY_ALIAS = f"""
SELECT {_FIELDS}
FROM card_aliases AS a JOIN cards AS c ON c.oracle_id = a.oracle_id
WHERE a.alias = ?
"""


@dataclass(frozen=True)
class Card:
    """The card fields the deck code needs."""

    oracle_id: str
    name: str
    type_line: str | None
    oracle_text: str | None
    color_identity: str  # WUBRG letters, "" if colorless
    commander_status: str  # "legal", "banned", "not_legal", ...
    is_game_changer: bool


class CardLookup:
    """Read-only name lookups. Use as:  with CardLookup(path) as lookup: ..."""

    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        # mode=ro: read-only, and fail (instead of creating an empty file) if missing.
        uri = db_path.resolve().as_uri() + "?mode=ro"
        self._connection = sqlite3.connect(uri, uri=True)
        # Databases built before card_aliases existed still work, just without aliases.
        self._has_aliases = (
            self._connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_aliases'"
            ).fetchone()
            is not None
        )

    def find(self, name: str) -> Card | None:
        """The card with this name or alternate name (any case), or None."""
        row = self._connection.execute(_BY_NAME, (name,)).fetchone()
        if row is None and self._has_aliases:
            row = self._connection.execute(_BY_ALIAS, (name,)).fetchone()
        if row is None:
            return None
        *fields, game_changer = row
        return Card(*fields, is_game_changer=bool(game_changer))  # SQLite stores 1/0

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
