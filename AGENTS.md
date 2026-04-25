# Repository Guidelines

## Project Structure & Module Organization

Core code lives in `src/rapmap/`. Keep CLI wiring in `src/rapmap/cli.py`, shared config logic in `src/rapmap/config.py`, and domain code grouped by area such as `audio/`, `lyrics/`, `align/`, `timing/`, `edit/`, `guide/`, and `audacity/`. Tests live in `tests/` and generally mirror module scope, for example `tests/test_cli.py` and `tests/test_audio_normalize.py`. Default YAMLs belong in `configs/`; sample inputs go in `inputs/`. Repository-level research and agent notes (`CLAUDE.md`, `.agents/`) support workflow, but production code should stay under `src/`.

## Build, Test, and Development Commands

Use `uv` for local development.

- `uv sync --extra dev` installs runtime and dev dependencies.
- `uv run rapmap --help` verifies the CLI entry point.
- `uv run pytest tests/` runs the full test suite.
- `uv run pytest tests/test_cli.py -v` runs a focused test file.
- `uv run ruff check src/ tests/` runs lint checks.
- `uv run ruff format src/ tests/` formats Python files.

Run lint and tests before opening a PR.

## Coding Style & Naming Conventions

Target Python 3.11+ and follow Ruff settings in `pyproject.toml`: 100-character lines, import sorting enabled, and standard `E/F/I/W` rule sets. Use 4-space indentation, `snake_case` for functions and modules, `PascalCase` for classes, and descriptive test names like `test_load_defaults`. Prefer small, typed functions and explicit assertions when validating timing or alignment invariants. Internal timing data should use integer sample indices, not float seconds.

## Testing Guidelines

Pytest is the test framework. Add tests alongside every behavior change, especially for CLI flows, config loading, lyrics parsing, and audio normalization. Name files `test_<feature>.py` and keep fixtures local unless reused broadly. Use targeted runs while iterating, then finish with `uv run pytest tests/`.

## Commit & Pull Request Guidelines

Recent history uses bracketed prefixes such as `[infra] initial commit`. Follow that pattern with concise imperative subjects, for example `[align] add guide role validation`. PRs should include a short problem statement, the approach taken, and the exact validation commands run. Include sample CLI output or screenshots only when user-facing behavior changes.

## Configuration & Safety Notes

Never commit secrets; keep real values in `.env` and update `.env.example` when configuration changes. If you modify packaged defaults in `configs/`, verify the corresponding `pyproject.toml` wheel includes still match.
