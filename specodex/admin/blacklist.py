"""Manufacturer blacklist — manufacturers banned from promotion to prod.

The blacklist is a JSON file at repo root (``admin/blacklist.json``).
It is checked into git so changes go through code review.

Comparison is case-insensitive: "ABB", "abb", and "Abb" all refer to the
same entry, and the first-added casing is preserved for display. This
prevents trivial bypass and matches the TypeScript implementation in
``app/backend/src/services/blacklist.ts``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

DEFAULT_BLACKLIST_PATH = (
    Path(__file__).resolve().parents[2] / "admin" / "blacklist.json"
)


class Blacklist:
    """A set of manufacturer names banned from promotion to prod."""

    def __init__(self, path: Path = DEFAULT_BLACKLIST_PATH) -> None:
        self.path = path
        # Map from lowercased key → original casing. First-added wins.
        self._banned: Dict[str, str] = {}
        if path.exists():
            self.load()

    def load(self) -> None:
        data = json.loads(self.path.read_text())
        banned = data.get("banned_manufacturers", [])
        if not isinstance(banned, list):
            raise ValueError(
                f"{self.path}: 'banned_manufacturers' must be a list of strings"
            )
        self._banned = {}
        for raw in banned:
            name = str(raw)
            key = name.lower()
            # Preserve the first occurrence's casing if the file has duplicates.
            if key not in self._banned:
                self._banned[key] = name

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"banned_manufacturers": self.names()}
        self.path.write_text(json.dumps(payload, indent=2) + "\n")

    def add(self, name: str) -> bool:
        """Add a manufacturer. Returns True if newly added, False if already present (case-insensitive)."""
        key = name.lower()
        if key in self._banned:
            return False
        self._banned[key] = name
        return True

    def remove(self, name: str) -> bool:
        """Remove a manufacturer. Returns True if removed, False if not present (case-insensitive)."""
        key = name.lower()
        if key not in self._banned:
            return False
        del self._banned[key]
        return True

    def contains(self, name: str) -> bool:
        """Case-insensitive membership check."""
        return name.lower() in self._banned

    def names(self) -> List[str]:
        """Stored (display) names, sorted case-insensitively."""
        return sorted(self._banned.values(), key=str.lower)

    def __len__(self) -> int:
        return len(self._banned)
