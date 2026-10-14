from pathlib import Path

import pytest

APP_DIR = Path(__file__).parent


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    # The library's test run (pytest from the repository root, in the library's environment) walks into app/ as well.
    # The app's tests need the app's own environment, so they only run when pytest is started from app/.
    if config.rootpath != APP_DIR:
        return True
    return None
