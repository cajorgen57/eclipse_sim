# Eclipse AI GUI Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        USER (Browser)                        │
│                      http://localhost:8000                   │
└────────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │   HTTP/JSON     │
                    └────────┬────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                     FRONTEND (Browser)                       │
├──────────────────────────────────────────────────────────────┤
│  index.html (Single Page App)                               │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │board-renderer│  │state-editor  │  │config-panel  │     │
│  │    .js       │  │    .js       │  │    .js       │     │
│  │Canvas 2D rend│  │ Form editing │  │ Planner cfg  │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │             │
│  ┌──────▼──────────────────▼──────────────────▼────────┐   │
│  │           api-client.js (API wrapper)              │   │
│  └────────────────────────┬───────────────────────────┘   │
│                            │                               │
│  ┌─────────────────────────▼──────────────────────────┐   │
│  │         results-display.js (Results UI)            │   │
│  └────────────────────────────────────────────────────┘   │
│                                                              │
│  CSS: style.css + hex-map.css (Tailwind + custom)          │
└────────────────────────────┬─────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │   REST API      │
                    └────────┬────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                  BACKEND (FastAPI/Python)                    │
├──────────────────────────────────────────────────────────────┤
│  app.py (FastAPI app, static serving, CORS)                 │
│                                                              │
│  api_routes.py (REST endpoints):                            │
│  ┌────────────────────────────────────────────────────┐     │
│  │ GET  /api/fixtures          → List fixtures        │     │
│  │ GET  /api/fixtures/{name}   → Load fixture         │     │
│  │ POST /api/state/save        → Save state           │     │
│  │ POST /api/predict           → Run planner          │     │
│  │ GET  /api/profiles          → List profiles        │     │
│  │ GET  /api/species           → List species         │     │
│  │ GET  /api/techs             → List techs           │     │
│  └────────────────────────────────────────────────────┘     │
└────────────────────────────┬─────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │  Function Calls  │
                    └────────┬────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                  ECLIPSE AI CORE (Python)                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  recommend()               Main planner entry point          │
│  state_assembler           Load/save/transform states        │
│  game_models.GameState     Core data structures             │
│  planners.mcts_pw          PW-MCTS planner                  │
│  rules_engine              Legal action generation          │
│  evaluator                 State evaluation                 │
│  overlay.plan_overlays()   Generate visual overlays         │
│  value.profiles            Strategy profiles                │
│  simulators.combat         Combat resolution                │
│  simulators.exploration    Exploration sampling             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Load Fixture

```
User clicks dropdown
    ↓
Frontend: api.loadFixture(name)
    ↓
Backend: GET /api/fixtures/{name}
    ↓
Read JSON from tests/ or eclipse_test/cases/
    ↓
Return GameState JSON
    ↓
Frontend: stateEditor.loadState(state)
    ↓
Frontend: boardRenderer.setState(state)
    ↓
Display on screen
```

### 2. Generate Prediction

```
User clicks "Generate Predictions"
    ↓
Frontend: Gather config (sims, depth, profile)
    ↓
Frontend: api.predict(state, config)
    ↓
Backend: POST /api/predict
    ↓
Parse request.state into GameState
    ↓
Build manual_inputs from request.config
    ↓
Call: recommend(None, None, prior_state, manual_inputs)
    ↓
Eclipse AI Core:
  - state_assembler.from_dict()
  - PW_MCTSPlanner.plan()
  - rules_engine.legal_actions()
  - evaluator.evaluate_action()
  - simulators.combat.resolve()
  - overlay.plan_overlays()
    ↓
Return: { plans: [...], belief: {...}, features: {...} }
    ↓
Backend: Send JSON response
    ↓
Frontend: resultsDisplay.displayResults(result)
    ↓
Frontend: boardRenderer.setState(state) + overlays (TODO)
    ↓
Display on screen
```

### 3. Edit State

```
User edits resource input
    ↓
Frontend: stateEditor.handleInputChange()
    ↓
Update in-memory state object
    ↓
Frontend: boardRenderer.setState(state)
    ↓
Frontend: stateEditor.syncToJSON()
    ↓
Display updates
```

### 4. Save State

```
User enters filename, clicks Save
    ↓
Frontend: api.saveState(state, filename)
    ↓
Backend: POST /api/state/save
    ↓
Write JSON to eclipse_ai/gui/saved_states/
    ↓
Return success message
    ↓
Frontend: Show toast notification
```

## File Organization

### Backend Structure

```
eclipse_ai/gui/
├── __init__.py              # Package initialization
├── app.py                   # FastAPI app setup
│   - CORS middleware
│   - Static file serving
│   - Template rendering
│   - Router mounting
│
├── api_routes.py            # API endpoint handlers
│   - Fixture management
│   - State operations
│   - Prediction execution
│   - Reference data
│
└── run.py                   # Launch script
    - CLI entry point
    - Uvicorn configuration
```

### Frontend Structure

```
static/
├── css/
│   ├── style.css            # Main application styles
│   │   - Layout
│   │   - Components
│   │   - Utilities
│   │   - Animations
│   │
│   └── hex-map.css          # Hex map specific styles
│       - SVG elements
│       - Overlays
│       - Interactions
│
└── js/
    ├── main.js              # Application bootstrap
    │   - Initialization
    │   - Fixture loading
    │   - Global utilities
    │   - Event handlers
    │
    ├── api-client.js        # Backend API wrapper
    │   - HTTP requests
    │   - Error handling
    │   - Response parsing
    │
    ├── board-renderer.js    # Board visualization
    │   - Canvas 2D rendering
    │   - Hex map with interactive tooltips
    │   - Click selection and hover effects
    │   - Coordinate math
    │   - Zoom/pan
    │   - Overlays
    │
    ├── state-editor.js      # State editing
    │   - Tab management
    │   - Form rendering
    │   - JSON sync
    │   - Validation
    │
    ├── config-panel.js      # Configuration UI
    │   - Settings form
    │   - Profile loading
    │   - Prediction trigger
    │
    └── results-display.js   # Results visualization
        - Plan cards
        - Step formatting
        - Feature display
        - Overlay control

templates/
└── index.html               # Single-page app
    - HTML structure
    - Tailwind CSS
    - Script includes
```

## Component Interaction

### State Management

```
┌─────────────────────────────────────────────────────┐
│  Global State (window.appState)                     │
│  ┌────────────────────────────────────────────┐     │
│  │  currentFixture: string                    │     │
│  │  currentState: GameState                   │     │
│  │  currentResults: PredictionResults         │     │
│  └────────────────────────────────────────────┘     │
│                       │                             │
│       ┌───────────────┼───────────────┐             │
│       ▼               ▼               ▼             │
│  stateEditor    boardRenderer  resultsDisplay       │
│       │               │               │             │
│       └───────────────┴───────────────┘             │
│                       │                             │
│                   api-client                        │
└───────────────────────┬─────────────────────────────┘
                        │
                    Backend API
```

### Event Flow

```
User Action
    ↓
Event Handler (main.js, *-panel.js)
    ↓
Update Component State
    ↓
API Call (if needed)
    ↓
Update Global State
    ↓
Notify Other Components
    ↓
Re-render UI
    ↓
Show Feedback (toast, status)
```

## Technology Stack

### Backend
- **FastAPI**: Web framework (async, OpenAPI docs)
- **Uvicorn**: ASGI server (high performance)
- **Jinja2**: Template rendering
- **python-multipart**: File upload support

### Frontend
- **HTML5**: Semantic markup
- **Tailwind CSS**: Utility-first styling
- **Vanilla JavaScript**: No framework dependencies
- **SVG**: Vector graphics for hex map

### Integration
- **Eclipse AI Core**: Existing Python codebase
- **REST API**: JSON over HTTP
- **File System**: Fixture loading, state saving

## Design Patterns

### Backend
- **Router Pattern**: Modular endpoint organization
- **Dependency Injection**: FastAPI automatic
- **Error Handling**: HTTP status codes + JSON errors

### Frontend
- **Class-based Components**: BoardRenderer, StateEditor, etc.
- **Event-Driven**: User actions trigger state updates
- **Singleton Pattern**: Global instances (api, boardRenderer, etc.)
- **Observer Pattern**: Components watch state changes

## Security Considerations

- **CORS**: Enabled for localhost development
- **Input Validation**: Server-side JSON validation
- **Path Sanitization**: Fixture loading, state saving
- **No Authentication**: Local development tool

## Performance Optimizations

- **Async API**: FastAPI async endpoints
- **Lazy Loading**: Load fixtures on demand
- **Debouncing**: Input change handlers
- **SVG Caching**: Reuse rendered elements
- **Progressive Rendering**: Stream large results

## Extensibility

### Adding New API Endpoints

1. Add route to `api_routes.py`:
```python
@router.get("/api/new-endpoint")
async def new_endpoint():
    return {"data": "value"}
```

2. Add client method to `api-client.js`:
```javascript
async newEndpoint() {
    return this.get('/new-endpoint');
}
```

3. Use in frontend:
```javascript
const result = await api.newEndpoint();
```

### Adding New UI Components

1. Create JS module in `static/js/`
2. Import in `index.html`
3. Initialize in `main.js`
4. Add styles in `static/css/`

### Adding New State Features

1. Extend `GameState` in `game_models.py`
2. Update `state_assembler.py` parsing
3. Add UI fields in `state-editor.js`
4. Update hex map rendering if visual

## Deployment Notes

### Development
```bash
python -m eclipse_ai.gui.run
# Runs with hot-reload
```

### Production (if needed)
```bash
gunicorn eclipse_ai.gui.app:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

### Docker (future)
```dockerfile
FROM python:3.10
COPY . /app
WORKDIR /app
RUN pip install -e ".[gui]"
CMD ["python", "-m", "eclipse_ai.gui.run"]
```

## Testing

### Manual Testing
- Load fixtures → verify rendering
- Edit state → verify updates
- Run predictions → verify results
- Save state → verify file creation

### Automated Testing (future)
- Playwright for E2E tests
- Jest for JS unit tests
- Pytest for API tests

## Monitoring

### Logs
- Terminal: Python exceptions, HTTP requests
- Browser Console: JS errors, API responses
- Network Tab: Request/response inspection

### Debugging
- Backend: Add print() or logging
- Frontend: console.log() or debugger
- API: Check FastAPI docs at /docs

---

This architecture provides a clean separation between frontend (presentation), backend (API), and core (business logic), making the system maintainable and extensible.

