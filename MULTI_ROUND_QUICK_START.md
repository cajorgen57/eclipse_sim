# Multi-Round Simulation - Quick Start Guide

## For Agents Taking on This Work

This is a **5-phase project** to implement multi-round simulation for Eclipse games starting at round > 1.

**Full details:** See `MULTI_ROUND_SIMULATION_PLAN.md`

## Phase Overview

### Phase 1: Enhanced Player State Model (READY TO START)
**Goal:** Add population tracks and influence tracks to PlayerState
**Time:** ~2-4 hours
**Key files:** `game_models.py`, `species_data.py`, `game_setup.py`

### Phase 2: Upkeep & Production Engine
**Goal:** Calculate and apply resource production and upkeep costs
**Time:** ~3-5 hours
**Key files:** NEW `upkeep.py`, `round_flow.py`

### Phase 3: Action Simulation with MCTS
**Goal:** Use AI to simulate player actions until money deficit
**Time:** ~4-6 hours
**Key files:** NEW `round_simulator.py`, existing `mcts_pw.py`

### Phase 4: Combat & Exploration Intelligence
**Goal:** Resolve battles and make smart exploration choices
**Time:** ~3-5 hours
**Key files:** NEW `exploration_intelligence.py`, existing `combat.py`

### Phase 5: Cleanup & Integration
**Goal:** Draw tech tiles, reset state, integrate all phases
**Time:** ~2-4 hours
**Key files:** NEW `cleanup.py`, `multi_round_runner.py`, modify `game_setup.py`

## Critical Rules Reference

### Resource Production (from Upkeep Phase)
- **NOT** 1 per planet or 2 per advanced planet
- Income = **leftmost visible number on each population track**
- Money net = Income - Influence upkeep
- See: User's detailed response about player board mechanics

### Upkeep Costs
- Cost = **leftmost visible number on influence track**
- Discs off the track increase this number
- Ships/cubes don't directly cost upkeep

### Tech Tiles Per Round (Cleanup Phase)
- 2 players: 5 tiles
- 3 players: 6 tiles
- 4 players: 7 tiles
- 5 players: 8 tiles
- 6 players: 9 tiles

### Exploration
- Player CAN choose to discard explored tile
- AI should evaluate: resources, wormholes, ancients
- Place in position with best wormhole connectivity

### Combat
- Ships **pin** each other (can't leave hex with enemies)
- Use existing `combat.py` simulator
- Award reputation tiles to winners

## Key Design Principles

1. **Extend, don't replace** - Work with existing code
2. **Read from tracks** - Production comes from track positions, not planet counts
3. **Use MCTS** - Let the AI make decisions, don't hardcode actions
4. **Test incrementally** - Each phase should have unit tests

## Starting Phase 1

```bash
# 1. Read the full plan
cat MULTI_ROUND_SIMULATION_PLAN.md

# 2. Look at existing models
cat eclipse_ai/game_models.py | grep "class PlayerState"

# 3. Check species data structure
cat eclipse_ai/data/species.json | head -50

# 4. Start coding
# Add PopulationTrack and InfluenceTrack classes to game_models.py
```

## Questions During Implementation?

1. Check `MULTI_ROUND_SIMULATION_PLAN.md` for detailed specifications
2. Check rulebook: `Eclipse - rules.pdf`
3. Reference user's responses in conversation history
4. Ask for clarification if something is ambiguous

## Don't Hallucinate!

If you're unsure about:
- Exact formula for something
- Edge case handling
- Specific rule interpretation

**→ Ask the user rather than guessing**

The user has explicitly requested intellectual honesty and will provide more info if needed.

## Progress Tracking

Update `MULTI_ROUND_SIMULATION_PLAN.md` progress table when you complete a phase.

---

**Ready to start?** Begin with Phase 1!

