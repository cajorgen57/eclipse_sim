## Summary

- Use seeded MCTS with progressive widening; evaluator calls simulators.
- Tighten legality checks (discs, market, bag, frontier, phase).
- Add DX/CI; license.

## Validation

- [ ] pytest -q
- [ ] ruff check .
- [ ] ruff format --check .
- [ ] Scenario A/B goldens pass
- [ ] Planner legality invariant holds
