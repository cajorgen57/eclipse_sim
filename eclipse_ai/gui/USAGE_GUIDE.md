# Eclipse AI GUI - Quick Usage Guide

## Installation & Startup

```bash
# 1. Install GUI dependencies
pip install -e ".[gui]"

# 2. Start the server
python -m eclipse_ai.gui.run

# 3. Open browser to http://localhost:8000
```

## Workflow: Testing a Strategy

### Step 1: Create a Game State

**Option A: Generate New Game (Recommended)** 🆕
1. Select player count (2-6 players)
2. *(Optional)* Expand "Species Setup" to choose specific species per player
3. Click "New Game" button
4. Fresh game state generated with:
   - Proper starting sectors for each species
   - Random tech market (scaled to player count)
   - Random exploration tiles (scaled to player count)
   - Species-specific starting resources, ships, and colonies

**Option B: Load Saved Fixture**
1. Expand "Load Saved Fixture"
2. Select a test case (e.g., "orion_round1_state")
3. State loads automatically into editor and hex map

**Option C: Edit Existing State**
1. Start with generated or loaded state
2. Edit in the "Players" or "JSON" tabs
3. Save with a custom filename

### Step 2: Configure Planner

**Basic Settings:**
- **Simulations**: 600 (faster) to 2000 (better quality)
- **Depth**: 2-4 action lookahead
- **Top K Plans**: How many alternatives to generate

**Strategy Profiles:**
- **Balanced**: Default all-around play
- **Aggressive**: Favor combat and expansion
- **Economic**: Prioritize resource generation
- **Tech Rush**: Research-focused
- **Defensive**: Territory protection
- **Expansion**: Territory acquisition
- **Late Game**: VP optimization
- **Turtle**: Defensive buildup

### Step 3: Generate Predictions

1. Click the big "Generate Predictions" button
2. Wait for planner to complete (10-60 seconds)
3. Results appear in the bottom panel

### Step 4: Analyze Results

**Plan Cards:**
- Ranked by estimated value
- Shows action sequence
- Click card to show overlays on map

**Hex Map Overlays:**
- **Arrows**: Movement actions
- **Circles**: Exploration targets
- **Icons**: Build/Influence locations

**Features Panel (if verbose enabled):**
- Shows 75+ extracted game features
- See what the AI considers important

### Step 5: Iterate

**Compare Strategies:**
1. Note results for current config
2. Change strategy profile
3. Rerun prediction
4. Compare plan quality

**Test Edge Cases:**
1. Edit state (e.g., remove ships, change resources)
2. See how AI adapts
3. Validate decisions make sense

**Save Interesting States:**
1. Edit filename field
2. Click "Save"
3. Reload later for regression testing

## Common Testing Scenarios

### Test 1: Opening Turn Strategy (Dynamic)

```
Setup: Generate 4-player game with random species
Config: Simulations=600, Depth=3, Profile=Balanced
Question: What's the optimal opening move for different species?
```

**Workflow**:
1. Click "New Game" (default 4 players)
2. Run prediction
3. Note recommended action
4. Generate new game and repeat
5. Compare patterns across different species and tech markets

**Expected**: 
- Species with mobility techs (Fusion Drive) → Explore
- Species with early military advantage → Aggressive expansion
- Species with resource bonuses → Research or Build

### Test 2: Species-Specific Opening

```
Setup: Generate 2-player game
       P1: Orion Hegemony
       P2: Terrans
Config: Simulations=1000, Depth=4, Profile=Aggressive
Question: How does starting species affect early strategy?
```

**Workflow**:
1. Expand "Species Setup (optional)"
2. Select "Orion Hegemony" for P1, "Terrans" for P2
3. Click "New Game"
4. Run prediction for each player
5. Compare recommended actions

**Expected**: Orion (combat bonus) may favor aggression; Terrans (balanced) may explore

### Test 3: Combat vs. Economy

```
Fixture: mid_game_conflict
Config A: Profile=Aggressive, Depth=3
Config B: Profile=Economic, Depth=3
Question: How does strategy profile affect decisions?
```

**Compare**: Aggressive should favor Move/Attack, Economic favors Influence/Research

### Test 3: Resource Constraints

```
Fixture: low_resources
Edit: Set money=1, science=0, materials=2
Config: Simulations=1000, Depth=4
Question: Does AI correctly prioritize resource generation?
```

**Expected**: Should recommend Influence (for income) over expensive Research

### Test 4: Tech Tree Progression

```
Fixture: early_tech_state
Config: Profile=Tech_Rush, Top_K=10
Question: What tech order does AI prefer?
```

**Analyze**: Check if recommendations follow logical tech dependencies

### Test 5: End Game VP Optimization

```
Fixture: round_8_state
Config: Profile=Late_Game, Depth=5, Simulations=2000
Question: Does AI maximize final VP?
```

**Expected**: Should prioritize discovery tiles, tech VPs, hex control

## Keyboard Shortcuts

- **Ctrl+Enter** (Cmd+Enter on Mac): Run prediction
- **Ctrl+S** (Cmd+S on Mac): Save current state

## Tips & Tricks

### 1. Use Verbose Mode for Understanding

Enable "Show detailed features" to see what the AI values:
- High `fleet_power` = military strength
- High `science_income` = research capacity
- High `threat_exposure` = danger from opponents

### 2. Compare Multiple Profiles

Run same state with different profiles to understand strategic differences:
```
1. Load fixture
2. Run with Aggressive → note top plan
3. Run with Economic → compare
4. Run with Tech_Rush → compare
```

### 3. Test Edge Cases

Artificially create interesting scenarios:
- Zero resources → AI must adapt
- Enemy fleet adjacent → AI should respond
- No techs researched → AI priorities shift

### 4. Validate Against Real Games

Load a real game position and see if AI suggestions match intuition:
- If AI suggests unexpected move, investigate why
- Check feature values to understand reasoning
- Adjust weights if consistently disagree

### 5. Save Test Suites

Create named fixtures for different phases:
- `opening_strong.json` - ideal start
- `opening_weak.json` - poor start
- `midgame_conflict.json` - combat scenario
- `endgame_race.json` - VP optimization

### 6. Use Hex Map for Verification

Click plans to see overlays:
- Verify Movement paths make sense
- Check Exploration targets are logical
- Ensure Build locations are strategic

### 7. Iterate on Configuration

For difficult positions, increase quality:
```
Simulations: 600 → 1000 → 2000
Depth: 3 → 4 → 5
```

Watch how plan quality improves.

## Troubleshooting

**"No predictions yet"**
→ Load a fixture first

**"Prediction failed"**
→ Check JSON tab for valid state structure
→ Look at browser console for errors

**Hex map doesn't show anything**
→ Ensure state has `map.hexes` with hex data
→ Try resetting view

**Plans look strange**
→ Increase simulations for better quality
→ Check if state is realistic
→ Try different strategy profile

**Slow predictions**
→ Reduce simulations or depth
→ Check CPU usage

## Advanced: Manual JSON Editing

The JSON tab gives full control. Common edits:

**Change Resources:**
```json
"players": {
  "orion": {
    "resources": {
      "money": 10,   ← change this
      "science": 5,  ← or this
      "materials": 8 ← or this
    }
  }
}
```

**Add/Remove Ships:**
```json
"hexes": {
  "230": {
    "pieces": {
      "orion": {
        "ships": {
          "interceptor": 3,  ← change counts
          "cruiser": 1
        }
      }
    }
  }
}
```

**Change Available Techs:**
```json
"tech_display": {
  "available": [
    "Plasma Cannon",
    "Fusion Drive",    ← add/remove techs
    "Gauss Shield"
  ]
}
```

After editing, click "Apply JSON Changes".

## Getting Help

- Check browser console (F12) for JavaScript errors
- Check terminal for Python errors
- Validate JSON at jsonlint.com
- Review `eclipse_ai/gui/README.md` for details

## Next Steps

Once comfortable with the GUI:
1. Test multiple game positions systematically
2. Compare AI decisions to human intuition
3. Identify areas where AI needs improvement
4. Adjust evaluation weights in `value/weights.yaml`
5. Create custom strategy profiles in `value/profiles.yaml`

Happy testing! 🚀

