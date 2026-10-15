"""The shelf: every diagram and noise model made in this browser session, so that every tool can reuse them.

Results computed from a diagram refer to its node and edge numbers, and some generators renumber on every call, so
tools always work on the shelved objects themselves rather than rebuilding them.
"""

from dataclasses import dataclass, field
from typing import Any

from paritea.diagram import Diagram
from paritea.noise import NoiseModel

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


@dataclass
class NoiseEntry:
    """A noise model on the shelf. It belongs to one diagram (the same object), as paritea requires."""

    id: str
    name: str
    diagram_id: str
    model: NoiseModel
    settings: dict[str, Any]
    code: str


class Shelf:
    """Diagrams (D1, D2, ...) and noise models (N1, N2, ...) by id.

    Making the same generated diagram or example twice returns the first one.
    """

    def __init__(self) -> None:
        self.entries: dict[str, Entry] = {}
        self.noise: dict[str, NoiseEntry] = {}
        self.keys: dict[str, str] = {}
        self.count = 0
        self.noise_count = 0

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

    def remove(self, entry_id: str) -> list[str]:
        """Remove a diagram and its noise models; returns the ids of the noise models removed with it."""
        self.entries.pop(entry_id, None)
        self.keys = {k: v for k, v in self.keys.items() if v != entry_id}
        children = [n.id for n in self.noise.values() if n.diagram_id == entry_id]
        for noise_id in children:
            del self.noise[noise_id]
        return children

    def add_noise(
        self, model: NoiseModel, *, name: str, diagram_id: str, settings: dict[str, Any], code: str
    ) -> NoiseEntry:
        self.noise_count += 1
        entry = NoiseEntry(f"N{self.noise_count}", name, diagram_id, model, settings, code)
        self.noise[entry.id] = entry
        return entry

    def get_noise(self, noise_id: str) -> NoiseEntry:
        if noise_id not in self.noise:
            raise UserError(f"Noise model {noise_id} is not on the shelf any more. Build it again.")
        return self.noise[noise_id]

    def remove_noise(self, noise_id: str) -> None:
        self.noise.pop(noise_id, None)


SHELF = Shelf()
