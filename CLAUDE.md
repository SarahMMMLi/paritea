# CLAUDE.md

This repository is a personal fork of [paritea/paritea](https://github.com/paritea/paritea) that adds a web user
interface (`app/`) on top of the upstream library.

## Layout

| Path | Owner | What it is |
|---|---|---|
| `src/paritea/`, `rust/`, `tests/`, `benchmarks/`, `demo/` | upstream | The paritea library (Python + Rust bindings built with maturin) |
| `pyproject.toml`, `uv.lock`, `Cargo.*`, `ruff.toml`, `.github/workflows/` (except `app.yml`, `app-pages.yml`) | upstream | Library build, lint and CI config |
| `app/` | this fork | The UI: a static web page (`app/web`) that runs paritea in the browser, plus the Streamlit prototype — a separate uv project that depends on the library in editable mode. See `app/CLAUDE.md` |
| `.github/workflows/app.yml` | this fork | CI for the UI |
| `.github/workflows/app-pages.yml` | this fork | Builds the web page and deploys it to GitHub Pages (https://sarahmmmli.github.io/paritea/) |

**Rule: UI work happens only inside `app/`.** Do not edit upstream-owned files to make the UI work. Keeping them
untouched means `git pull origin main` never conflicts. If the UI genuinely needs a library change, stop and say so:
that change belongs on its own branch off `origin/main` and goes upstream as a pull request (see below).

## Git remotes

- `fork` = `SarahMMMLi/paritea`. `main` tracks `fork/main`, so `git pull`, `git push` and VS Code's Sync button all
  work against the fork. `remote.pushDefault` is also `fork`, so a plain `git push` from any branch goes there.
- `origin` = upstream `paritea/paritea` (no push access). Nothing pulls from it automatically.

Bring in upstream changes deliberately: `git pull origin main`, then `git push` (or VS Code: Pull from… → `origin`).

Contributing a library fix upstream: branch from `origin/main`, change only library files, push the branch to `fork`,
open a PR against `paritea/paritea` with a Conventional Commits title (`feat:`, `fix:`, `docs:`, `refactor:`, …),
which upstream CI enforces.

## Build and test

Requires `uv` and Rust >= 1.91 (`rustup`). uv builds the Rust extension via maturin automatically and rebuilds it
when `rust/**` changes.

```shell
uv sync --all-groups      # library dev environment in ./.venv
uv run pytest             # library tests (~1.5 min)
ruff check && ruff format # lint/format, configured by ruff.toml (applies to app/ too)
```

UI commands live in `app/CLAUDE.md`.

Upstream strips Jupyter notebook outputs (`nbstripout` in pre-commit and CI); commit notebooks without outputs.
