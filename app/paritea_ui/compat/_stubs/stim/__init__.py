"""Stand-in for stim, which this browser engine does not have yet.

paritea imports stim as soon as ``paritea.equivalence`` is imported, even for checks that never use it. Importing this
module works; using any of its classes says that stim is unavailable.
"""

__all__ = ["Circuit", "CircuitInstruction", "CompiledDemSampler", "DemTarget", "DetectorErrorModel", "GateTarget"]


class _Unavailable:
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise ImportError("stim is not available in this browser engine yet.")


class Circuit(_Unavailable): ...


class CircuitInstruction(_Unavailable): ...


class CompiledDemSampler(_Unavailable): ...


class DemTarget(_Unavailable): ...


class DetectorErrorModel(_Unavailable): ...


class GateTarget(_Unavailable): ...
