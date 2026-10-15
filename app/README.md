# paritea in your browser

**https://sarahmmmli.github.io/paritea/**: a web page for [paritea](https://github.com/paritea/paritea) that runs
entirely in the browser. Python and paritea's Rust core are compiled to WebAssembly, so there is nothing to install
and nothing is uploaded.

| Tool | You provide | You get |
|---|---|---|
| Diagrams | A generator, an example, or a PyZX / QASM file | The drawing, its size and boundaries; PyZX JSON, TikZ and SVG downloads |
| Pauli webs | A diagram | Its stabilising webs and detecting regions, drawn on the diagram |
| Noise model | A diagram, X/Y/Z weights, noise-free wires | Every fault with its weight |
| Fault propagation | A noise model | What each fault does at the boundary and which detecting regions it flips |
| Semantic equivalence | Two diagrams | Whether they are the same map, with both stabiliser tableaux |
| Fault equivalence | Two noisy diagrams, how far to check | Yes or no, and the smallest fault weight where they differ |
| stim → detector error model | A stim circuit | paritea's detector error model, checked against stim's own |
| Python console | Python code | Anything paritea can do, with the diagrams made in the other tools |

Every result comes with the Python that reproduces it, and results built from a generator, an example or stim's
preset have a link that recreates them in anyone's browser.

## Run it locally

You need [`uv`](https://docs.astral.sh/uv/) and [Rust](https://rustup.rs). From `app/`:

```shell
uv sync                                         # the Python the page runs, with paritea built natively
./build/build_wheels.sh                         # paritea and stim compiled to WebAssembly (slow the first time)
uv run python build/precompute.py
uv run python build/build_site.py
python3 -m http.server 8000 --directory web     # then open http://localhost:8000
```

In VS Code, **Run → paritea web page** does the last two steps and opens the page.

## Develop

```shell
uv run pytest                                      # tests
uv run ruff check --fix . && uv run ruff format .  # lint and format
```

The page is a separate uv project that installs the library from this repository (`..`) in editable mode. Every push
to `main` rebuilds the page, checks it in a headless browser and publishes it. See [CLAUDE.md](CLAUDE.md) for the code
layout and conventions.
