# Multi-Round Simulation Implementation Plan

## Overview

This document outlines the phased implementation for simulating multiple rounds when a game starts at round > 1. Each phase is designed to be independently implementable and can be passed to different agents.

## Dependencies

```
Phase 1 (Foundation)
    ↓
Phase 2 (Upkeep & Production)
    ↓
Phase 3 (Action Simulation)
    ↓
Phase 4 (Combat & Exploration)
    ↓
Phase 5 (Integration & Testing)
```

---

## Phase 1: Enhanced Player State Model

**Goal:** Extend the existing `PlayerState` model to track population and influence tracks.

**Status:** NOT STARTED

### Tasks

1. **Add Population Track Model**
   - Add `population_tracks` field to `PlayerState` in `game_models.py`
   - Track positions: which squares have cubes (List[bool] for each track)
   - Track values: the production numbers on each square (List[int])
   - Implement `get_production(resource_type)` method that returns leftmost visible number

2. **Add Influence Track Model**
   - Add `influence_track` field to `PlayerState`
   - Track positions: which circles have discs (List[bool])
   - Track values: upkeep cost numbers (List[int])
   - Implement `get_upkeep_cost()` method that returns leftmost visible number

3. **Track Disc and Cube Positions**
   - Add `discs_on_hexes` (List[str]) - hex IDs where player has influence discs
   - Add `discs_on_actions` (Dict[str, bool]) - which action spaces have discs this round
   - Add `cubes_on_hexes` (Dict[str, Dict[str, int]]) - hex_id -> {resource_type -> count}

4. **Update Species Starting Data**
   - Extend `species.json` or create `species_tracks.json` with:
     - Default population track layouts (cube positions and production values)
     - Default influence track layouts (disc positions and upkeep values)
   - Add loader function in `species_data.py`

### Files to Modify

- `eclipse_ai/game_models.py` - Add new fields to `PlayerState`
- `eclipse_ai/data/species.json` or new `species_tracks.json`
- `eclipse_ai/species_data.py` - Add track data loading
- `eclipse_ai/game_setup.py` - Initialize tracks in `_setup_players()`

### Acceptance Criteria

- [ ] `PlayerState` has all track fields
- [ ] `get_production()` correctly returns leftmost visible number for each resource
- [ ] `get_upkeep_cost()` correctly returns leftmost visible number on influence track
- [ ] Species data includes track configurations
- [ ] Unit tests pass for track production/upkeep calculations

### Example Code Structure

```python
@dataclass
class PopulationTrack:
    """Represents one resource's population track."""
    track_values: List[int]  # Production numbers on each square
    cube_positions: List[bool]  # True if cube is on this square
    
    def get_production(self) -> int:
        """Returns leftmost visible (no cube) production value."""
        for value, has_cube in zip(self.track_values, self.cube_positions):
            if not has_cube:
                return value
        return 0

@dataclass
class InfluenceTrack:
    """Represents the influence track."""
    upkeep_values: List[int]  # Upkeep costs
    disc_positions: List[bool]  # True if disc is on this circle
    
    def get_upkeep(self) -> int:
        """Returns leftmost visible upkeep cost."""
        for cost, has_disc in zip(self.upkeep_values, self.disc_positions):
            if not has_disc:
                return cost
        return 0

# Add to PlayerState:
class PlayerState:
    # ... existing fields ...
    population_tracks: Dict[str, PopulationTrack]  # "money", "science", "materials"
    influence_track: InfluenceTrack
    discs_on_hexes: List[str]
    discs_on_actions: Dict[str, bool]
    cubes_on_hexes: Dict[str, Dict[str, int]]
```

---

## Phase 2: Upkeep & Production Engine

**Goal:** Implement the Upkeep Phase mechanics (resource production and upkeep payment).

**Status:** NOT STARTED

**Dependencies:** Phase 1 complete

### Tasks

1. **Create Upkeep Module**
   - Create `eclipse_ai/upkeep.py`
   - Implement `calculate_production(player: PlayerState) -> Dict[str, int]`
   - Implement `calculate_upkeep_cost(player: PlayerState) -> int`
   - Implement `apply_upkeep(state: GameState, player_id: str) -> None`

2. **Handle Bankruptcy**
   - Implement `can_afford_upkeep(player: PlayerState) -> bool`
   - Implement logic to trade Science/Materials to Money (3:1 ratio)
   - Implement logic to remove influence discs if still can't pay
   - Return cubes to tracks when discs removed from hexes

3. **Resource Production**
   - Read production from each track's leftmost visible square
   - Add to player's stored resources (money, science, materials)
   - Update `Resources` object in `PlayerState`

4. **Integration with Round Flow**
   - Add upkeep phase to existing `round_flow.py` if it exists
   - Or create new round structure module

### Files to Create/Modify

- NEW: `eclipse_ai/upkeep.py`
- MODIFY: `eclipse_ai/game_models.py` - Add upkeep-related helper methods
- MODIFY: `eclipse_ai/round_flow.py` (or create if doesn't exist)

### Acceptance Criteria

- [ ] Production calculated correctly from tracks
- [ ] Upkeep cost calculated correctly from influence track
- [ ] Net money change applied correctly
- [ ] Science and materials production applied
- [ ] Bankruptcy handling works (trade resources, remove discs)
- [ ] Unit tests for all upkeep scenarios

### Example Code Structure

```python
# eclipse_ai/upkeep.py

def calculate_production(player: PlayerState) -> Dict[str, int]:
    """Calculate resource production from population tracks."""
    return {
        "money": player.population_tracks["money"].get_production(),
        "science": player.population_tracks["science"].get_production(),
        "materials": player.population_tracks["materials"].get_production(),
    }

def calculate_upkeep_cost(player: PlayerState) -> int:
    """Calculate influence upkeep cost."""
    return player.influence_track.get_upkeep()

def apply_upkeep(state: GameState, player_id: str) -> None:
    """
    Apply upkeep phase for one player.
    1. Calculate production
    2. Calculate upkeep
    3. Apply net money change
    4. Add science and materials
    5. Handle bankruptcy if needed
    """
    player = state.players[player_id]
    
    # Step 1: Calculate income
    production = calculate_production(player)
    upkeep = calculate_upkeep_cost(player)
    
    # Step 2: Net money
    net_money = production["money"] - upkeep
    
    # Step 3: Apply (handle bankruptcy if needed)
    if player.resources.money + net_money < 0:
        handle_bankruptcy(state, player_id, needed=-net_money)
    
    player.resources.money = max(0, player.resources.money + net_money)
    player.resources.science += production["science"]
    player.resources.materials += production["materials"]
```

---

## Phase 3: Action Simulation with MCTS

**Goal:** Simulate players taking actions using the MCTS planner until they would go into money deficit.

**Status:** NOT STARTED

**Dependencies:** Phase 1 and Phase 2 complete

### Tasks

1. **Create Action Simulator**
   - Create `eclipse_ai/round_simulator.py`
   - Implement `simulate_action_phase(state: GameState, round_num: int) -> GameState`
   - Use existing MCTS planner to decide actions
   - Implement money deficit prediction

2. **Money Deficit Detection**
   - Implement `predict_money_after_upkeep(player: PlayerState, potential_action: Action) -> int`
   - Check if action would lead to negative money after upkeep
   - Consider: action cost + predicted upkeep - predicted income

3. **Action Phase Loop**
   - Players take turns in order
   - Each player uses MCTS to pick best action
   - If action would cause deficit, player passes instead
   - Continue until all players passed
   - Mark actions taken (place discs on action spaces)

4. **Integrate with Existing Planner**
   - Use `PW_MCTSPlanner` from `eclipse_ai/planners/mcts_pw.py`
   - Configure with appropriate simulation budget (lower for simulation rounds)
   - Handle action execution and state updates

### Files to Create/Modify

- NEW: `eclipse_ai/round_simulator.py`
- MODIFY: `eclipse_ai/planners/mcts_pw.py` - May need quick-mode flag
- MODIFY: `eclipse_ai/forward_model.py` - Ensure it handles all actions

### Acceptance Criteria

- [ ] Players use MCTS to decide actions
- [ ] Money deficit prediction prevents bankruptcy
- [ ] All players take turns until all pass
- [ ] Action discs placed correctly
- [ ] State properly updated after each action
- [ ] Unit tests with mock MCTS decisions

### Example Code Structure

```python
# eclipse_ai/round_simulator.py

def simulate_action_phase(state: GameState, round_num: int) -> GameState:
    """Simulate one round's action phase using MCTS."""
    from eclipse_ai.planners.mcts_pw import PW_MCTSPlanner
    
    planner = PW_MCTSPlanner(simulations=100)  # Fewer sims for speed
    players_passed = {pid: False for pid in state.players}
    
    while not all(players_passed.values()):
        for player_id in state.turn_order:
            if players_passed[player_id]:
                continue
            
            # Use MCTS to decide action
            actions = planner.plan(state, player_id, top_k=1)
            
            if not actions:
                players_passed[player_id] = True
                continue
            
            best_action = actions[0]
            
            # Check if action would cause money deficit
            if would_cause_deficit(state, player_id, best_action):
                players_passed[player_id] = True
                continue
            
            # Execute action
            state = execute_action(state, player_id, best_action)
    
    return state

def would_cause_deficit(state: GameState, player_id: str, action: Action) -> bool:
    """Check if action would lead to negative money after upkeep."""
    player = state.players[player_id]
    
    # Estimate money after this action and upkeep
    action_cost = estimate_action_cost(action)
    current_money = player.resources.money
    predicted_income = player.population_tracks["money"].get_production()
    predicted_upkeep = player.influence_track.get_upkeep()
    
    money_after = current_money - action_cost + predicted_income - predicted_upkeep
    
    return money_after < 0
```

---

## Phase 4: Combat & Exploration Intelligence

**Goal:** Resolve combat phase and make intelligent exploration decisions.

**Status:** NOT STARTED

**Dependencies:** Phase 3 complete

### Tasks

1. **Combat Resolution**
   - Integrate existing `eclipse_ai/simulators/combat.py`
   - Detect hexes with multiple players' ships
   - Resolve battles using combat simulator
   - Handle ship pinning (ships in same hex pin each other)
   - Award reputation tiles to winners

2. **Exploration Intelligence**
   - Create `eclipse_ai/exploration_intelligence.py`
   - Implement `should_keep_tile(player: PlayerState, tile: Hex) -> bool`
   - Heuristics:
     - Keep if has good resources (multiple planets)
     - Keep if wormholes connect well to existing sectors
     - Discard if too many ancients
     - Discard if no resources and bad wormholes
   - Implement `choose_placement_position(state: GameState, player_id: str, tile: Hex) -> (int, int)`
   - Choose position that maximizes wormhole connectivity

3. **Tile Placement Logic**
   - Find all legal positions for explored tile
   - Score each position based on:
     - Wormhole connections to existing sectors
     - Distance from home sector
     - Resource value of the tile
   - Place in highest-scoring position

4. **Combat Pinning Rules**
   - Ships cannot move out of a hex if enemy ships present (pinning)
   - Implement in movement validation
   - Document in code comments with rulebook reference

### Files to Create/Modify

- NEW: `eclipse_ai/exploration_intelligence.py`
- MODIFY: `eclipse_ai/simulators/combat.py` - Ensure it handles pinning
- MODIFY: `eclipse_ai/movement.py` - Add pinning validation
- MODIFY: `eclipse_ai/round_simulator.py` - Add combat phase

### Acceptance Criteria

- [ ] Combat resolves correctly using existing simulator
- [ ] Pinning prevents illegal moves
- [ ] Reputation tiles awarded to winners
- [ ] Exploration tiles kept/discarded intelligently
- [ ] Tiles placed in good positions
- [ ] Unit tests for exploration heuristics

### Example Code Structure

```python
# eclipse_ai/exploration_intelligence.py

def should_keep_tile(player: PlayerState, tile: Hex) -> bool:
    """Decide whether to keep an explored tile."""
    # Count valuable resources
    good_planets = sum(1 for p in tile.planets if p.type in ["orange", "pink", "brown"])
    
    # Too many ancients?
    if tile.ancients >= 4:
        return False
    
    # No resources and few wormholes?
    if good_planets == 0 and len(tile.wormholes) <= 1:
        return False
    
    # Otherwise keep it
    return True

def choose_placement_position(
    state: GameState,
    player_id: str,
    tile: Hex,
    source_hex_id: str
) -> Tuple[int, int]:
    """Choose best position to place explored tile."""
    from eclipse_ai.map.placement import find_legal_placements
    
    legal_positions = find_legal_placements(state.map, source_hex_id, tile)
    
    if not legal_positions:
        return None
    
    # Score each position
    scored = []
    for pos, rotation in legal_positions:
        score = score_placement(state, player_id, pos, tile, rotation)
        scored.append((score, pos, rotation))
    
    # Return highest scoring position
    scored.sort(reverse=True)
    return scored[0][1], scored[0][2]  # (position, rotation)

def score_placement(
    state: GameState,
    player_id: str,
    pos: Tuple[int, int],
    tile: Hex,
    rotation: int
) -> float:
    """Score a potential tile placement."""
    score = 0.0
    
    # Prefer positions with wormhole connections to owned sectors
    # Prefer positions closer to home
    # Prefer positions with good resources
    
    # TODO: Implement detailed scoring
    
    return score
```

---

## Phase 5: Cleanup Phase & Integration

**Goal:** Implement cleanup phase (tech tile drawing, disc/cube reset) and integrate all phases.

**Status:** NOT STARTED

**Dependencies:** Phases 1-4 complete

### Tasks

1. **Cleanup Phase Implementation**
   - Create `eclipse_ai/cleanup.py`
   - Draw new tech tiles based on player count (5/6/7/8/9)
   - Return action discs to influence track
   - Refresh colony ships (mark all as available)
   - Return destroyed ships to player supply
   - Flip summary cards back

2. **Full Round Simulation**
   - Create `run_full_round(state: GameState, round_num: int) -> GameState`
   - Call action phase simulator
   - Call combat resolution
   - Call upkeep application
   - Call cleanup phase
   - Return updated state

3. **Multi-Round Runner**
   - Implement `simulate_rounds(state: GameState, start_round: int, end_round: int) -> GameState`
   - Loop through rounds from start to end
   - Run full round for each
   - Log progress for debugging

4. **Integration with game_setup.py**
   - Modify `new_game()` to check if `starting_round > 1`
   - If yes, call `simulate_rounds(state, 1, starting_round - 1)`
   - Return the resulting state

5. **Testing & Validation**
   - Create integration tests
   - Test 2-player game starting at round 3
   - Verify resources, discs, cubes are correct
   - Verify tech tiles drawn correctly
   - Verify exploration happened and tiles placed

### Files to Create/Modify

- NEW: `eclipse_ai/cleanup.py`
- NEW: `eclipse_ai/multi_round_runner.py`
- MODIFY: `eclipse_ai/game_setup.py` - Add multi-round simulation call
- NEW: `tests/test_multi_round_simulation.py`

### Acceptance Criteria

- [ ] Cleanup phase draws correct number of tech tiles
- [ ] Action discs reset properly
- [ ] Colony ships refresh
- [ ] Full round simulation runs all phases in order
- [ ] Multi-round runner correctly simulates N rounds
- [ ] Integration test: 4-player game starting at round 5 has realistic state
- [ ] All unit tests pass
- [ ] Integration tests pass

### Example Code Structure

```python
# eclipse_ai/cleanup.py

TECH_TILES_PER_ROUND = {
    2: 5,
    3: 6,
    4: 7,
    5: 8,
    6: 9,
}

def cleanup_phase(state: GameState) -> GameState:
    """Execute cleanup phase."""
    num_players = len(state.players)
    
    # Draw new tech tiles
    num_to_draw = TECH_TILES_PER_ROUND.get(num_players, 7)
    draw_new_tech_tiles(state, num_to_draw)
    
    # Reset action discs
    for player_id, player in state.players.items():
        player.discs_on_actions = {}
        # Discs return to influence track
    
    # Refresh colony ships
    for player in state.players.values():
        player.colony_ships.used_this_round = 0
    
    return state

# eclipse_ai/multi_round_runner.py

def run_full_round(state: GameState, round_num: int) -> GameState:
    """Run one complete round."""
    print(f"[SIMULATION] Running round {round_num}")
    
    # 1. Action Phase
    state = simulate_action_phase(state, round_num)
    
    # 2. Combat Phase
    state = resolve_combat_phase(state)
    
    # 3. Upkeep Phase
    for player_id in state.players:
        apply_upkeep(state, player_id)
    
    # 4. Cleanup Phase
    state = cleanup_phase(state)
    
    return state

def simulate_rounds(state: GameState, start_round: int, end_round: int) -> GameState:
    """Simulate multiple rounds from start to end."""
    for round_num in range(start_round, end_round + 1):
        state = run_full_round(state, round_num)
        state.round = round_num + 1
    
    return state
```

### Integration Example

```python
# In eclipse_ai/game_setup.py

def new_game(
    num_players: int = 4,
    species_by_player: Optional[Mapping[str, str]] = None,
    seed: Optional[int] = None,
    ancient_homeworlds: bool = False,
    starting_round: int = 1,
) -> GameState:
    # ... existing setup code ...
    
    state = GameState(
        round=1,  # Always start at round 1 for simulation
        # ... other fields ...
    )
    
    # ... existing setup code ...
    
    # If starting beyond round 1, simulate previous rounds
    if starting_round > 1:
        from eclipse_ai.multi_round_runner import simulate_rounds
        print(f"[SETUP] Simulating rounds 1-{starting_round - 1}")
        state = simulate_rounds(state, 1, starting_round - 1)
        state.round = starting_round
    
    return state
```

---

## Testing Strategy

### Unit Tests (Per Phase)

- Phase 1: Test track calculations, production/upkeep formulas
- Phase 2: Test upkeep application, bankruptcy handling
- Phase 3: Test action simulation, deficit detection
- Phase 4: Test combat resolution, exploration decisions
- Phase 5: Test cleanup phase, tech tile drawing

### Integration Tests

- **Test 1:** 2-player game starting at round 3
  - Verify both players have taken actions
  - Verify resources accumulated
  - Verify tech tiles drawn (5 per round × 2 rounds = 10 total)
  
- **Test 2:** 4-player game starting at round 5
  - Verify all players have explored sectors
  - Verify realistic resource counts
  - Verify tech tiles drawn (7 per round × 4 rounds = 28 total)

- **Test 3:** Combat scenario
  - Set up state where players will fight
  - Run simulation
  - Verify combat resolved and reputation awarded

### Performance Tests

- Measure time to simulate 1 round (target: < 5 seconds)
- Measure time to simulate 5 rounds (target: < 30 seconds)
- Profile MCTS calls to identify bottlenecks

---

## Implementation Notes

### For Future Agents

1. **Read the rulebook sections provided** - All mechanics are documented in the user's responses
2. **Preserve existing code** - Extend, don't replace
3. **Add comprehensive logging** - Use `print(f"[MODULE] message")` format
4. **Write tests first** - TDD approach recommended
5. **Reference existing code** - Look at `combat.py`, `exploration.py` for patterns

### Key Files to Reference

- `eclipse_ai/game_models.py` - Core data structures
- `eclipse_ai/planners/mcts_pw.py` - AI decision making
- `eclipse_ai/simulators/combat.py` - Combat resolution
- `eclipse_ai/map/placement.py` - Tile placement logic
- `eclipse_ai/technology.py` - Tech tile handling

### Common Pitfalls to Avoid

1. **Don't count planets for production** - Use track positions only
2. **Don't forget pinning rules** - Ships can't leave hexes with enemies
3. **Don't skip bankruptcy checks** - Must handle negative money
4. **Don't use wrong tech tile counts** - Cleanup uses different numbers than setup

---

## Progress Tracking

| Phase | Status | Assigned To | Completed Date |
|-------|--------|-------------|----------------|
| 1: Player State Model | ✅ COMPLETED | AI Agent | 2025-01-14 |
| 2: Upkeep & Production | ✅ COMPLETED | AI Agent | 2025-01-14 |
| 3: Action Simulation | ✅ COMPLETED | AI Agent | 2025-01-14 |
| 4: Combat & Exploration | ✅ COMPLETED | AI Agent | 2025-01-14 |
| 5: Cleanup & Integration | ✅ COMPLETED | AI Agent | 2025-01-14 |

---

## Questions for User (if any arise during implementation)

- [ ] TBD

---

## Document Version

- **Created:** 2025-01-14
- **Last Updated:** 2025-01-14
- **Status:** Phase 1 ready to start

