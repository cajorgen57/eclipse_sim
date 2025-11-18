/**
 * Main Application Entry Point
 */

// Global state
window.appState = {
    currentFixture: null,
    currentState: null,
    currentResults: null,
};

// Utility functions
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast px-4 py-3 rounded-lg shadow-lg text-sm flex items-center space-x-2 transform transition-all duration-300 translate-x-0`;
    
    const colors = {
        success: 'bg-green-600',
        error: 'bg-red-600',
        info: 'bg-blue-600',
        warning: 'bg-yellow-600',
    };
    
    const icons = {
        success: '✓',
        error: '✗',
        info: 'ℹ',
        warning: '⚠',
    };
    
    toast.classList.add(colors[type] || colors.info);
    toast.innerHTML = `
        <span class="text-lg">${icons[type] || icons.info}</span>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    
    // Animate in
    setTimeout(() => toast.classList.add('opacity-100'), 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-x-full');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        if (show) {
            overlay.classList.remove('hidden');
        } else {
            overlay.classList.add('hidden');
        }
    }
}

function updateStatus(message, status = 'idle') {
    const indicator = document.getElementById('status-indicator');
    if (!indicator) return;
    
    const colors = {
        idle: 'bg-gray-500',
        ready: 'bg-green-500',
        running: 'bg-blue-500',
        success: 'bg-green-500',
        error: 'bg-red-500',
    };
    
    const dot = indicator.querySelector('div');
    const text = indicator.querySelector('span');
    
    if (dot) {
        dot.className = `w-2 h-2 rounded-full ${colors[status] || colors.idle}`;
    }
    if (text) {
        text.textContent = message;
    }
}

// Wait for a component to be ready
function waitForComponent(componentName, maxWaitMs = 5000) {
    return new Promise((resolve, reject) => {
        const startTime = Date.now();
        const checkInterval = setInterval(() => {
            if (window[componentName]) {
                clearInterval(checkInterval);
                console.log(`${componentName} is ready`);
                resolve(window[componentName]);
            } else if (Date.now() - startTime > maxWaitMs) {
                clearInterval(checkInterval);
                reject(new Error(`Timeout waiting for ${componentName}`));
            }
        }, 50);
    });
}

// Initialize application
async function initializeApp() {
    console.log('Initializing Eclipse AI Testing GUI...');
    
    try {
        // Wait for critical components to initialize
        console.log('Waiting for StateEditor to initialize...');
        await waitForComponent('stateEditor');
        console.log('StateEditor ready');
        
        // Wait for BoardViewManager to initialize
        console.log('Waiting for BoardViewManager to initialize...');
        await waitForComponent('boardViewManager');
        console.log('BoardViewManager ready');
        
        // Initialize BoardViewManager
        window.boardViewManager.initialize();
        
        // Load fixtures into dropdown
        await loadFixturesList();
        
        // Setup fixture selector
        setupFixtureSelector();
        
        // Setup game generator
        await setupGameGenerator();
        
        // Auto-generate a default 4-player game if no state loaded
        if (!window.appState.currentState && !window.stateEditor.hasState()) {
            console.log('No state loaded, generating default game...');
            await generateDefaultGame();
        } else {
            console.log('State already loaded, skipping default game generation');
            console.log('Current state has hexes:', window.appState.currentState?.map?.hexes ? Object.keys(window.appState.currentState.map.hexes) : 'none');
        }
        
        updateStatus('Ready', 'ready');
        console.log('Application initialized successfully');
    } catch (error) {
        console.error('Failed to initialize application:', error);
        showToast('Failed to initialize application', 'error');
        updateStatus('Initialization failed', 'error');
    }
}

async function generateDefaultGame() {
    try {
        console.log('Auto-generating default 4-player game...');
        const state = await api.generateGame(4, null, null, false, 1);
        console.log('Generated state:', state);
        console.log('Map hexes:', state.map?.hexes ? Object.keys(state.map.hexes) : 'no hexes');
        
        // Ensure stateEditor exists before loading
        if (!window.stateEditor) {
            console.error('StateEditor not available for default game');
            return;
        }
        
        // Load state into stateEditor (which will sync with appState)
        window.stateEditor.loadState(state);
        
        if (window.boardRenderer) {
            window.boardRenderer.setState(state);
        }
        if (window.playerPanel) {
            window.playerPanel.loadState(state);
        }
        if (window.boardViewManager) {
            window.boardViewManager.loadState(state);
        }
        
        showToast('Default 4-player game loaded', 'info');
        console.log('Default game generated successfully');
    } catch (e) {
        console.error('Failed to generate default game:', e);
        showToast('Failed to load default game', 'error');
    }
}

async function loadFixturesList() {
    try {
        const fixtures = await api.listFixtures();
        const select = document.getElementById('fixture-select');
        
        if (!select) {
            console.error('fixture-select element not found!');
            return;
        }
        
        console.log('Fixtures received:', fixtures);
        
        // Clear existing options
        select.innerHTML = '<option value="">Select a fixture...</option>';
        
        // Add each fixture as a simple option
        fixtures.forEach(fixture => {
            const option = document.createElement('option');
            option.value = fixture.name;
            let label = `${fixture.name}`;
            if (fixture.round) label += ` (Round ${fixture.round})`;
            if (fixture.active_player) label += ` - ${fixture.active_player}`;
            option.textContent = label;
            select.appendChild(option);
            console.log('Added option:', option.value, option.textContent);
        });
        
        console.log(`Loaded ${fixtures.length} fixtures`);
        
        if (fixtures.length === 0) {
            showToast('No fixtures found', 'warning');
        }
        
    } catch (e) {
        console.error('Failed to load fixtures:', e);
        showToast('Failed to load fixtures', 'error');
    }
}

function setupFixtureSelector() {
    const select = document.getElementById('fixture-select');
    if (!select) return;
    
    select.addEventListener('change', async (e) => {
        const fixtureName = e.target.value;
        if (!fixtureName) return;
        
        await loadFixture(fixtureName);
    });
}

async function loadFixture(name) {
    try {
        showLoading(true);
        updateStatus('Loading fixture...', 'running');
        
        const state = await api.loadFixture(name);
        
        // Store fixture name in global state
        window.appState.currentFixture = name;
        
        // Ensure stateEditor exists
        if (!window.stateEditor) {
            console.error('StateEditor not available when loading fixture');
            showToast('Error: State editor not initialized', 'error');
            return;
        }
        
        // Load into state editor (which will sync with appState.currentState)
        window.stateEditor.loadState(state);
        
        // Load into board renderer
        if (window.boardRenderer) {
            window.boardRenderer.setState(state);
        }
        
        // Load into player panel
        if (window.playerPanel) {
            window.playerPanel.loadState(state);
        }
        
        // Load into board view manager
        if (window.boardViewManager) {
            window.boardViewManager.loadState(state);
        }
        
        updateStatus('Fixture loaded', 'success');
        showToast(`Loaded ${name}`, 'success');
        
    } catch (e) {
        console.error('Failed to load fixture:', e);
        showToast(`Failed to load ${name}: ${e.message}`, 'error');
        updateStatus('Load failed', 'error');
    } finally {
        showLoading(false);
    }
}

// Setup game generator
async function setupGameGenerator() {
    try {
        // Load species list
        const species = await api.listSpecies();
        
        // Setup species dropdowns
        const numPlayersSelect = document.getElementById('num-players');
        const speciesSetup = document.getElementById('species-setup');
        
        function updateSpeciesDropdowns() {
            const numPlayers = parseInt(numPlayersSelect.value);
            speciesSetup.innerHTML = '';
            
            for (let i = 1; i <= numPlayers; i++) {
                const playerDiv = document.createElement('div');
                playerDiv.className = 'flex items-center space-x-2';
                
                const label = document.createElement('label');
                label.className = 'text-gray-400';
                label.textContent = `P${i}:`;
                label.style.width = '30px';
                
                const select = document.createElement('select');
                select.className = 'flex-1 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-eclipse-primary';
                select.dataset.playerIndex = i;
                
                // Add default option
                const defaultOption = document.createElement('option');
                defaultOption.value = '';
                defaultOption.textContent = 'Random';
                select.appendChild(defaultOption);
                
                // Add species options
                species.forEach(sp => {
                    const option = document.createElement('option');
                    option.value = sp.id;
                    option.textContent = sp.name;
                    select.appendChild(option);
                });
                
                playerDiv.appendChild(label);
                playerDiv.appendChild(select);
                speciesSetup.appendChild(playerDiv);
            }
        }
        
        // Update dropdowns when player count changes
        numPlayersSelect.addEventListener('change', updateSpeciesDropdowns);
        updateSpeciesDropdowns(); // Initial setup
        
        // Generate game button
        const generateBtn = document.getElementById('generate-game-btn');
        generateBtn.addEventListener('click', async () => {
            const numPlayers = parseInt(numPlayersSelect.value);
            
            // Gather species selections
            const speciesSelects = speciesSetup.querySelectorAll('select');
            const speciesByPlayer = {};
            let hasCustomSpecies = false;
            
            speciesSelects.forEach((select, idx) => {
                if (select.value) {
                    speciesByPlayer[`P${idx + 1}`] = select.value;
                    hasCustomSpecies = true;
                }
            });
            
            // Get ancient homeworlds setting
            const ancientHomeworlds = document.getElementById('ancient-homeworlds').checked;
            
            // Get starting round
            const startingRound = parseInt(document.getElementById('starting-round').value) || 1;
            
            try {
                showLoading(true);
                updateStatus('Generating new game...', 'running');
                
                const state = await api.generateGame(
                    numPlayers,
                    hasCustomSpecies ? speciesByPlayer : null,
                    null, // No seed for now
                    ancientHomeworlds,
                    startingRound
                );
                
                // Ensure stateEditor exists
                if (!window.stateEditor) {
                    console.error('StateEditor not available when generating game');
                    showToast('Error: State editor not initialized', 'error');
                    return;
                }
                
                // Load state into stateEditor (which will sync with appState)
                window.stateEditor.loadState(state);
                
                if (window.boardRenderer) {
                    window.boardRenderer.setState(state);
                }
                
                // Load into player panel
                if (window.playerPanel) {
                    window.playerPanel.loadState(state);
                }
                
                // Load into board view manager
                if (window.boardViewManager) {
                    window.boardViewManager.loadState(state);
                }
                
                updateStatus('Game generated!', 'success');
                showToast(`Generated ${numPlayers}-player game with random setup`, 'success');
                
            } catch (e) {
                console.error('Failed to generate game:', e);
                showToast(`Failed to generate game: ${e.message}`, 'error');
                updateStatus('Generation failed', 'error');
            } finally {
                showLoading(false);
            }
        });
        
    } catch (e) {
        console.error('Failed to setup game generator:', e);
    }
}

// Handle keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + Enter: Run prediction
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        if (window.configPanel) {
            window.configPanel.runPrediction();
        }
    }
    
    // Ctrl/Cmd + S: Save state
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        document.getElementById('save-state-btn')?.click();
    }
});

// Initialize when DOM is ready
window.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing...');
    initializeApp();
});

// Export utility functions to window
window.showToast = showToast;
window.showLoading = showLoading;
window.updateStatus = updateStatus;

