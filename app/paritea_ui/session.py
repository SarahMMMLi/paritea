"""The shelf: every diagram made in this browser session, so that every tool can reuse it.

Results computed from a diagram refer to its node and edge numbers, and some generators renumber on every call, so
tools always work on the shelved diagram itself rather than rebuilding it.
"""

from dataclasses import dataclass, field
from typing import Any

from paritea.diagram import Diagram

from paritea_ui.validate import UserError


@dataclass
class Entry:
    """A diagram on the shelf, with how it was made and the Python that makes it again."""

    id: str
    name: str
    diagram: Diagram
    source: dict[str, Any]
    code: str
    notes: list[str] = field(default_factory=list)


class Shelf:
    """Diagrams by id (D1, D2, ...). Making the same generated diagram or example twice returns the first one."""

    def __init__(self) -> None:
        self.entries: dict[str, Entry] = {}
        self.keys: dict[str, str] = {}
        self.count = 0

    def find(self, key: str) -> Entry | None:
        entry_id = self.keys.get(key)
        return self.entries.get(entry_id) if entry_id else None

    def add(
        self,
        diagram: Diagram,
        *,
        name: str,
        source: dict[str, Any],
        code: str,
        key: str | None = None,
        notes: list[str] | None = None,
    ) -> Entry:
        self.count += 1
        entry = Entry(f"D{self.count}", name, diagram, source, code, notes or [])
        self.entries[entry.id] = entry
        if key:
            self.keys[key] = entry.id
        return entry

    def get(self, entry_id: str) -> Entry:
        if entry_id not in self.entries:
            raise UserError(f"Diagram {entry_id} is not on the shelf any more. Build or import it again.")
        return self.entries[entry_id]

    def remove(self, entry_id: str) -> None:
        self.entries.pop(entry_id, None)
        self.keys = {k: v for k, v in self.keys.items() if v != entry_id}


SHELF = Shelf()
