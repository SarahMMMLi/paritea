"""Stand-in for sinter (needs stim and multiprocessing, neither of which runs here); see the stim stand-in."""

__all__ = ["Task", "TaskStats", "collect"]


class Task:
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise ImportError("sinter is not available in this browser engine.")


class TaskStats(Task): ...


def collect(*args: object, **kwargs: object) -> None:
    raise ImportError("sinter.collect needs several processes, which a browser cannot start.")
