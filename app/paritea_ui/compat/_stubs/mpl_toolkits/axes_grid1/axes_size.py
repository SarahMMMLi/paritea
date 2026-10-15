"""paritea's Shor-extraction generator imports ``Fraction`` from here by mistake; it means ``fractions.Fraction``."""

from fractions import Fraction

__all__ = ["Fraction"]
