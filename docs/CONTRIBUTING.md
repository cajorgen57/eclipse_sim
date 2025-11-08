# Contributing to Eclipse AI

Thanks for helping improve the Eclipse AI planner! This guide summarizes the recommended
workflow so that every pull request stays consistent and easy to review.

## Quickstart

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
2. Enable the pre-commit hooks to format and lint on save:
   ```bash
   pre-commit install
   ```
3. Run the checks locally before pushing:
   ```bash
   ruff check .
   ruff format --check .
   pytest -q
   ```

## Development workflow

- Follow the architecture documented in `Agents.md`; update existing modules in place instead of
  duplicating logic.
- Keep pull requests focused. The preferred flow is one branch per milestone as outlined in the
  project plan.
- Add or update tests whenever you change gameplay logic. Mark expensive simulations with
  `@pytest.mark.slow` so they can be skipped in the default CI matrix.
- When in doubt, open a draft PR early to discuss the approach.

## Pull request checklist

Before requesting review:

- [ ] Format and lint cleanly (`ruff format --check .`, `ruff check .`).
- [ ] All tests pass locally (`pytest -q`).
- [ ] Update documentation, comments, or changelog entries when behavior changes.
- [ ] Ensure new files include appropriate licensing headers if required.

CI runs the same commands across Python 3.10–3.12, so a green pipeline locally should map to a
passing PR.
