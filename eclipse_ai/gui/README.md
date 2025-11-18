# Eclipse AI Testing GUI

A web-based visual testing interface for Eclipse Second Dawn AI. Enables rapid iteration and experimentation with board states, configurations, and predictions.

## Features

- **Visual Hex Map**: Interactive SVG-based board visualization with planets, ships, and ownership
- **State Editor**: Edit game state via forms or raw JSON
- **Fixture Management**: Load existing test fixtures and save custom states
- **Configuration Panel**: Adjust planner settings, strategy profiles, and parameters
- **Real-time Predictions**: Generate action recommendations with visual overlays
- **Results Display**: View ranked plans with detailed step-by-step breakdowns
- **Keyboard Shortcuts**: Ctrl+Enter to predict, Ctrl+S to save

## Installation

Install the GUI dependencies:

```bash
pip install -e ".[gui]"
```

This installs:
- FastAPI (web framework)
- Uvicorn (ASGI server)
- Jinja2 (templating)
- python-multipart (file uploads)

## Quick Start

1. **Start the server:**

```bash
python -m eclipse_ai.gui.run
```

2. **Open your browser:**

Navigate to `http://localhost:8000`

3. **Load a fixture:**

Select a test fixture from the dropdown (e.g., "orion_round1")

4. **Generate predictions:**

Click "Generate Predictions" to run the planner

5. **View results:**

Click on plans to show overlays on the hex map

## Usage Guide

### Loading States

**From Fixtures:**
- Use the fixture dropdown to load existing test states
- Fixtures are loaded from `tests/` and `eclipse_ai/eclipse_test/cases/`

**From JSON:**
- Switch to the "JSON" tab
- Paste or edit the state JSON
- Click "Apply JSON Changes"

### Editing States

**Players Tab:**
- Edit resources (money, science, materials) for each player
- View known techs and ship designs
- Changes update the state immediately

**Tech Tab:**
- View available technologies in the tech display

**JSON Tab:**
- Direct JSON editing with full state access
- Use for complex changes or debugging

### Configuration

**Planner Settings:**
- **Simulations**: Number of MCTS simulations (default: 600)
- **Depth**: Search depth for action sequences (default: 3)
- **Strategy Profile**: Choose playstyle (aggressive, economic, tech_rush, etc.)
- **Top K Plans**: Number of plans to generate (default: 5)
- **Verbose**: Show detailed feature extraction

### Hex Map

**Features:**
- Planets shown as colored circles (orange/pink/brown)
- Ships indicated with rocket emoji and count
- Ownership shown by hex border color
- Wormhole connections as dashed lines

**Controls:**
- Zoom: Mouse wheel or +/− buttons
- Reset: Reset view button
- Click hex: View hex details (future: edit modal)

**Overlays:**
- Click a plan to show action overlays
- Arrows for Move actions
- Circles for Explore
- Icons for Build/Influence

### Saving States

1. Edit the state as desired
2. Enter a filename (e.g., `my_test.json`)
3. Click "Save"
4. Files are saved to `eclipse_ai/gui/saved_states/`

## Keyboard Shortcuts

- `Ctrl+Enter` / `Cmd+Enter`: Run prediction
- `Ctrl+S` / `Cmd+S`: Save current state

## Architecture

```
gui/
├── app.py                  # FastAPI application
├── api_routes.py           # REST API endpoints
├── run.py                  # Launch script
├── static/
│   ├── css/
│   │   ├── style.css       # Main styles
│   │   └── hex-map.css     # Hex map styles
│   └── js/
│       ├── main.js         # App initialization
│       ├── api-client.js      # Backend API wrapper
│       ├── board-renderer.js # Canvas 2D board rendering
│       ├── hex-details.js    # Hex details side panel
│       ├── state-editor.js   # Form editing
│       ├── config-panel.js # Planner config
│       └── results-display.js # Results visualization
├── templates/
│   └── index.html          # Single-page app
└── saved_states/           # User-saved states
```

## API Endpoints

The GUI backend provides REST endpoints:

### Fixtures
- `GET /api/fixtures` - List all fixtures
- `GET /api/fixtures/{name}` - Load specific fixture

### State Management
- `POST /api/state/save` - Save state to file

### Prediction
- `POST /api/predict` - Run planner with state and config

### Reference Data
- `GET /api/profiles` - List strategy profiles
- `GET /api/species` - List species
- `GET /api/techs` - List technologies

## Configuration Options

When running predictions, the GUI sends:

```json
{
  "state": { /* GameState JSON */ },
  "config": {
    "planner": {
      "simulations": 600,
      "depth": 3,
      "pw_alpha": 0.65,
      "pw_c": 1.8,
      "prior_scale": 0.6,
      "seed": 0
    },
    "profile": "aggressive",
    "top_k": 5,
    "verbose": false
  }
}
```

## Troubleshooting

**GUI won't start:**
- Ensure GUI dependencies are installed: `pip install -e ".[gui]"`
- Check port 8000 is not already in use

**Fixtures not loading:**
- Verify fixture JSON files exist in `tests/` or `eclipse_ai/eclipse_test/cases/`
- Check console for error messages

**Predictions fail:**
- Verify the state is valid (check JSON tab)
- Ensure required fields are present (players, map, etc.)
- Check browser console for detailed error messages

**Hex map not rendering:**
- Check that state has `map.hexes` with valid hex data
- Verify browser supports SVG

## Development

**Run in development mode:**

```bash
python -m eclipse_ai.gui.run
```

The server runs with auto-reload, so changes to Python files restart automatically.

**Making changes:**

- Backend: Edit `api_routes.py` for new endpoints
- Frontend: Edit JS/CSS files in `static/`
- HTML: Edit `templates/index.html`

**Testing the API:**

You can test endpoints directly:

```bash
# List fixtures
curl http://localhost:8000/api/fixtures

# Load a fixture
curl http://localhost:8000/api/fixtures/orion_round1

# Run prediction
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -d @your_request.json
```

## Future Enhancements

- [ ] Drag-drop ship movement between hexes
- [ ] Multi-step plan simulation with animation
- [ ] Comparison mode (side-by-side configs)
- [ ] Board image upload and parsing
- [ ] Export results as SVG/PDF
- [ ] Undo/redo for state changes
- [ ] Real-time collaboration features
- [ ] Mobile-responsive layout

## License

Part of Eclipse AI Toolkit. See main project LICENSE.

