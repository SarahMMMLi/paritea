# paritea UI

A [Streamlit](https://streamlit.io) web interface for [paritea](https://github.com/paritea/paritea): generate ZX
diagrams, compute their Pauli webs and view them on the diagram.

## Web page

**Live: https://sarahmmmli.github.io/paritea/** — paritea running entirely in the browser (Python and paritea's Rust core
compiled to WebAssembly), nothing to install. To build and serve it locally, see the web page section of
[CLAUDE.md](CLAUDE.md).

## Run it

You need [`uv`](https://docs.astral.sh/uv/) and [Rust](https://rustup.rs) (paritea's core is written in Rust and is
compiled the first time you install it).

```shell
cd app
uv sync
uv run streamlit run streamlit_app.py
```

The app opens at http://localhost:8501 and reloads whenever you save a file.

## Develop

```shell
uv run pytest                                      # tests, including headless runs of every page
uv run ruff check --fix . && uv run ruff format .  # lint and format
```

The app is a separate uv project that installs the library from this repository (`..`) in editable mode, so library
changes show up in the UI without reinstalling. See [CLAUDE.md](CLAUDE.md) for the code layout and conventions.
