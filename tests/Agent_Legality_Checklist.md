# Agent Legality Checklist

Goal: never produce illegal tests or illegal recommended actions.

## Required test case schema
- `state` — full game state dict the engine understands
- `player_id` — integer
- `proposed_action` — object with:
  - `action` (or `type`) — string
  - `payload` — dict (IDs, coords, costs, etc.)
- `provenance` — short string: how this test was generated
- `expectations` — optional oracle:
  - `should_be_legal`: true|false
  - `notes`: string

## Hard gate before submit
1. Call `validators.assert_test_case_legal(test)`  
   - If it raises, **do not submit**. Either fix payload or discard.
2. For recommendations you produce, call  
   `validators.assert_plans_legal(output, state, player_id)`  
   - If it raises, regenerate using only actions from `rules_engine.legal_actions(state, player_id)`.

## Generation rules
- Only propose actions present in `rules_engine.legal_actions(state, player_id)`.
- Do not fabricate components you do not own or cannot afford.
- Respect phase constraints:
  - Action allowed only in the current phase.
  - One action per action step unless the rules permit chains.
- Respect costs and limits:
  - Pay resources exactly. No negative banks. No exceeding tracks.
  - Ship part limits and hull slots respected.
  - Influence discs, colony ships, and diplomats must exist in supply.
- Respect map and ownership:
  - Only use explored hexes as required.
  - Only move across valid wormholes and within speed.
  - Only place/build where you have rights per rules.

## What to log on rejection
- `player_id`
- `_fmt_action(proposed_action)`
- Top 10 `legal_actions` at the time
- Diff of missing payload keys vs required keys
- Reason you chose the action (short text)

## Sanity list before finalizing
- Phase consistent
- Resources non-negative post-action
- Component and slot counts valid
- Movement path valid
- Target hex ownership and adjacency valid
- No duplicate steps that would violate “one action” limits

## CI expectations
- Unit: generator emits zero illegal tests across a seeded batch.
- Integration: planner outputs contain zero illegal steps on fixed fixtures.
- Any LegalityError fails CI.
