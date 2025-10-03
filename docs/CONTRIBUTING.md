# Contributing

Thank you for helping improve Eclipse AI! This guide summarizes the workflow we use for
changes and the checks that keep the project healthy.

## Getting started

1. Create and activate a virtual environment.
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies, including development tools.
   ```bash
   pip install -e ".[dev]"
   ```
3. Install the Git hooks so formatting and linting run automatically.
   ```bash
   pre-commit install
   ```

## Development workflow

* Follow the architecture described in `Agents.md`: models → rules → simulators → planner.
* Keep notebooks and data paths stable; add new helpers instead of moving existing files.
* Organize work into focused branches (for example `chore/dx-ci-license`).
* Write tests alongside changes. Prefer deterministic seeds so results are reproducible.

## Checks before opening a pull request

Run these commands locally and ensure they succeed:

```bash
ruff check .
ruff format --check .
pytest -q
```

If you add slow-running simulations, mark the tests with `@pytest.mark.slow` so the default
CI matrix stays fast.

## Pull requests

* Keep diffs narrow and reference the relevant milestone from the roadmap.
* Include a summary of the change, impacted modules, and how it was validated.
* Ensure GitHub Actions is green before requesting review.
* By submitting a contribution you agree that your work is licensed under the project
  license (MIT).

We appreciate your contributions—thank you for helping us ship a stronger Eclipse AI agent!
