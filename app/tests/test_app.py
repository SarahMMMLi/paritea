"""Smoke tests that run the real Streamlit app headlessly."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from paritea_ui.core import GENERATORS

APP = Path(__file__).parents[1] / "streamlit_app.py"
PAULI_WEBS_PAGE = "paritea_ui/pages/pauli_webs.py"


def _app() -> AppTest:
    # The first paritea import compiles numba code, which can take a while.
    return AppTest.from_file(APP, default_timeout=120)


def test_home_page_renders() -> None:
    at = _app().run()

    assert not at.exception
    assert at.title[0].value == "paritea"


@pytest.mark.parametrize("generator", list(GENERATORS))
def test_pauli_webs_page_renders_every_generator(generator: str) -> None:
    at = _app()
    at.switch_page(PAULI_WEBS_PAGE).run()
    at.sidebar.selectbox[0].select(generator).run()

    assert not at.exception
    assert not at.error
    assert at.metric[0].label == "Nodes"


def test_pauli_webs_page_shows_detecting_regions() -> None:
    at = _app()
    at.switch_page(PAULI_WEBS_PAGE).run()
    regions_option = next(o for o in at.radio[0].options if o.startswith("Detecting regions"))
    at.radio[0].set_value(regions_option).run()

    assert not at.exception
    assert not at.error
