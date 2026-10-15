"""A dataclass stand-in for ``recordclass.RecordClass``: mutable records with positional fields, as paritea uses."""

import dataclasses

__all__ = ["RecordClass"]


class RecordClass:
    """Subclasses become mutable dataclasses built from their annotated fields."""

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        dataclasses.dataclass(cls)
