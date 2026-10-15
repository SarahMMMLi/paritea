"""The one function paritea uses from scipy.stats: the normal distribution's inverse CDF, ``norm.ppf``."""

from statistics import NormalDist

__all__ = ["norm"]


class _Norm:
    @staticmethod
    def ppf(q: float) -> float:
        return NormalDist().inv_cdf(q)


norm = _Norm()
