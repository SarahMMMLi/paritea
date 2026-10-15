"""A NumPy stand-in for ``galois.GF2``, covering exactly what paritea uses.

paritea needs arrays over GF(2): construction from 0/1 data, ``GF2.Zeros``, item assignment, ``+`` (XOR), ``@``
(matrix product mod 2), indexing, ``tolist`` and ``row_reduce``. The row reduction follows galois' algorithm, so the
reduced echelon form (which is unique) and the shape of the result match it.
"""

import numpy as np

__all__ = ["GF2"]


class GF2(np.ndarray):
    """An array over GF(2), stored as uint8 zeros and ones."""

    def __new__(cls, array):
        values = np.asarray(array) if isinstance(array, np.ndarray) else np.array(array, dtype=np.int64)
        if values.size and (values.min() < 0 or values.max() > 1):
            raise ValueError("GF(2) arrays may only contain 0 and 1.")
        return values.astype(np.uint8).view(cls)

    @classmethod
    def Zeros(cls, shape) -> "GF2":
        return np.zeros(shape, dtype=np.uint8).view(cls)

    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        plain = [np.asarray(x).view(np.ndarray) if isinstance(x, np.ndarray) else x for x in inputs]
        if method == "__call__" and not kwargs:
            if ufunc in (np.add, np.subtract):
                return np.bitwise_xor(*(np.asarray(x, dtype=np.uint8) for x in plain)).view(GF2)
            if ufunc is np.multiply:
                return np.bitwise_and(*(np.asarray(x, dtype=np.uint8) for x in plain)).view(GF2)
            if ufunc is np.matmul:
                a, b = (np.asarray(x, dtype=np.int64) for x in plain)
                return (np.matmul(a, b) & 1).astype(np.uint8).view(GF2)
        return getattr(ufunc, method)(*plain, **kwargs)

    def row_reduce(self, ncols: int | None = None, eye: str = "left") -> "GF2":
        """Reduced row echelon form; ``eye="right"`` reduces from the bottom-right corner instead."""
        if eye == "right":
            return self[::-1, ::-1].row_reduce(ncols, eye="left")[::-1, ::-1]
        a = np.array(self, dtype=np.uint8)
        rows, cols = a.shape
        pivot_row = 0
        for j in range(cols if ncols is None else ncols):
            if pivot_row == rows:
                break
            candidates = np.flatnonzero(a[pivot_row:, j])
            if candidates.size == 0:
                continue
            i = pivot_row + candidates[0]
            a[[pivot_row, i]] = a[[i, pivot_row]]
            others = a[:, j].astype(bool)
            others[pivot_row] = False
            a[others] ^= a[pivot_row]
            pivot_row += 1
        return a.view(GF2)
