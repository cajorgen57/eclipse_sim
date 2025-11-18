/**
 * State Editor - Form-based and JSON editing
 */

class StateEditor {
    constructor() {
        this.state = null;
        this.initialized = false;
        this.collapsed = false;
        this.setupTabs();
        this.setupSaveButton();
        this.setupCollapseToggle();
        this.setupRoundControls();
        this.initialized = true;
        console.log('StateEditor initialized');
    }

    setupTabs() {
        const tabs = document.querySelectorAll('.state-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const targetTab = tab.dataset.tab;
                this.switchTab(targetTab);
            });
        });
    }

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.state-tab').forEach(t => {
            t.classList.remove('active', 'bg-gray-700');
            if (t.dataset.tab === tabName) {
                t.classList.add('active', 'bg-gray-700');
            }
        });

        // Show/hide content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.add('hidden');
        });
        document.getElementById(`tab-${tabName}`)?.classList.remove('hidden');

        // Sync JSON if switching to JSON tab
        if (tabName === 'json' && this.state) {
            this.syncToJSON();
        }
    }

    setupCollapseToggle() {
        const toggleBtn = document.getElementById('toggle-state-editor');
        const stateEditorContent = document.getElementById('state-editor-content');
        const icon = document.getElementById('collapse-icon');
        
        if (!toggleBtn || !stateEditorContent || !icon) {
            console.warn('Collapse toggle elements not found');
            return;
        }
        
        toggleBtn.addEventListener('click', () => {
            this.collapsed = !this.collapsed;
            if (this.collapsed) {
                stateEditorContent.classList.add('hidden');
                icon.textContent = '+';
            } else {
                stateEditorContent.classList.remove('hidden');
                icon.textContent = '−';
            }
        });
    }

    setupRoundControls() {
        const roundInput = document.getElementById('current-round');
        const incrementBtn = document.getElementById('increment-round');
        const decrementBtn = document.getElementById('decrement-round');
        
        if (!roundInput || !incrementBtn || !decrementBtn) {
            console.warn('Round control elements not found');
            return;
        }
        
        incrementBtn.addEventListener('click', () => {
            if (this.state) {
                this.state.round = Math.min(9, (this.state.round || 1) + 1);
                roundInput.value = this.state.round;
                this.syncState();
            }
        });
        
        decrementBtn.addEventListener('click', () => {
            if (this.state) {
                this.state.round = Math.max(1, (this.state.round || 1) - 1);
                roundInput.value = this.state.round;
                this.syncState();
            }
        });
        
        roundInput.addEventListener('change', (e) => {
            if (this.state) {
                this.state.round = parseInt(e.target.value) || 1;
                this.syncState();
            }
        });
    }

    syncState() {
        // Update board renderer if loaded
        if (window.boardRenderer) {
            window.boardRenderer.setState(this.state);
        }
        
        // Update global app state
        if (window.appState) {
            window.appState.currentState = this.state;
        }
        
        showToast('State updated', 'success');
    }

    loadState(state) {
        if (!state) {
            console.error('StateEditor.loadState called with null/undefined state');
            return;
        }
        
        console.log('StateEditor.loadState called with state:', state);
        this.state = state;
        
        // Sync with global app state
        if (window.appState) {
            window.appState.currentState = state;
        }
        
        // Update round input if present
        const roundInput = document.getElementById('current-round');
        if (roundInput && state.round) {
            roundInput.value = state.round;
        }
        
        this.renderPlayersTab();
        this.renderTechTab();
        this.syncToJSON();
        
        // Also update player panel
        if (window.playerPanel) {
            playerPanel.loadState(state);
        }
        
        console.log('StateEditor.loadState completed successfully');
    }

    renderPlayersTab() {
        const container = document.getElementById('players-editor');
        container.innerHTML = '';

        const players = this.state?.players || {};
        
        if (Object.keys(players).length === 0) {
            container.innerHTML = '<p class="text-sm text-gray-400">No players in state</p>';
            return;
        }

        Object.entries(players).forEach(([playerId, player]) => {
            const playerDiv = document.createElement('div');
            playerDiv.className = 'bg-gray-800 rounded p-3';
            
            const header = document.createElement('div');
            header.className = 'font-semibold mb-2 text-sm';
            header.textContent = playerId;
            playerDiv.appendChild(header);

            // Resources
            const resources = player.resources || {};
            const resourcesDiv = document.createElement('div');
            resourcesDiv.className = 'grid grid-cols-3 gap-2 text-xs';
            
            ['money', 'science', 'materials'].forEach(resource => {
                const div = document.createElement('div');
                div.innerHTML = `
                    <label class="block text-gray-400 mb-1">${resource}</label>
                    <input type="number" 
                           data-player="${playerId}" 
                           data-field="resources.${resource}"
                           value="${resources[resource] || 0}"
                           class="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs state-input focus:outline-none focus:ring-1 focus:ring-eclipse-primary">
                `;
                resourcesDiv.appendChild(div);
            });
            
            playerDiv.appendChild(resourcesDiv);

            // Known techs
            const techsDiv = document.createElement('div');
            techsDiv.className = 'mt-2';
            const knownTechs = player.known_techs || [];
            techsDiv.innerHTML = `
                <label class="block text-gray-400 mb-1 text-xs">Known Techs</label>
                <div class="text-xs text-gray-300 bg-gray-700 rounded px-2 py-1 max-h-20 overflow-y-auto">
                    ${knownTechs.length > 0 ? knownTechs.join(', ') : 'None'}
                </div>
            `;
            playerDiv.appendChild(techsDiv);

            container.appendChild(playerDiv);
        });

        // Add event listeners to inputs
        document.querySelectorAll('.state-input').forEach(input => {
            input.addEventListener('change', (e) => this.handleInputChange(e));
        });
    }

    renderTechTab() {
        this.renderTechToContainer('tech-editor');
    }
    
    renderTechToContainer(containerId) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error(`Tech container '${containerId}' not found`);
            return;
        }
        
        container.innerHTML = '';

        const techDisplay = this.state?.tech_display || {};
        const available = techDisplay.available || [];
        const techDefs = this.state?.tech_definitions || {};

        console.log('Tech display data:', { 
            containerId,
            hasTechDisplay: !!techDisplay, 
            availableCount: available.length,
            hasTechDefs: !!techDefs && Object.keys(techDefs).length > 0
        });

        // Show message if no techs available
        if (available.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8">
                    <div class="text-gray-500 mb-2">No technologies available</div>
                    <div class="text-xs text-gray-600">The tech market will populate when a game is loaded or generated</div>
                </div>
            `;
            return;
        }

        // Group by tier for better organization
        const techsByTier = { I: [], II: [], III: [] };
        
        available.forEach(techName => {
            const techDef = Object.values(techDefs).find(t => t.name === techName);
            const cost = techDef?.base_cost || 0;
            const tier = window.UIConstants.getTechTier(cost);
            techsByTier[tier].push({ name: techName, def: techDef });
        });

        // Render each tier section
        Object.entries(techsByTier).forEach(([tier, techs]) => {
            if (techs.length === 0) return;
            
            // Tier header with count
            const tierHeader = document.createElement('div');
            tierHeader.className = 'tier-section flex items-center justify-between mb-3 mt-4 first:mt-0';
            tierHeader.innerHTML = `
                <h3 class="text-sm font-bold text-gray-200 flex items-center gap-2">
                    <span class="w-8 h-8 rounded-full bg-gradient-to-br from-eclipse-primary to-eclipse-accent flex items-center justify-center text-white text-xs font-bold">
                        ${tier}
                    </span>
                    Tier ${tier} Technologies
                </h3>
                <span class="text-xs text-gray-400 bg-gray-800 px-2 py-1 rounded">${techs.length} available</span>
            `;
            container.appendChild(tierHeader);

            // Tech grid for this tier
            const techGrid = document.createElement('div');
            techGrid.className = 'grid grid-cols-2 gap-2 mb-3';

            techs.forEach(({ name, def }) => {
                const techCard = this.createEnhancedTechCard(name, def, tier);
                techGrid.appendChild(techCard);
            });

            container.appendChild(techGrid);
        });
    }

    createEnhancedTechCard(techName, techDef, tier) {
        const category = techDef?.category || 'unknown';
        const cost = techDef?.base_cost || '?';
        const grantsParts = techDef?.grants_parts || [];
        const grantsStructures = techDef?.grants_structures || [];
        
        // Get enhanced category styling from constants
        const style = window.UIConstants.getCategoryStyle(category);

        const card = document.createElement('div');
        card.className = `
            tech-card
            bg-gray-800/40
            border border-gray-700/50
            rounded-lg p-3 
            cursor-pointer 
            transition-all duration-200 
            hover:bg-gray-800/60 hover:border-gray-600/60
            relative overflow-hidden
        `;
        
        card.innerHTML = `
            <!-- Category badge -->
            <div class="absolute top-2 right-2 text-base opacity-40">
                ${style.icon}
            </div>
            
            <!-- Tech name -->
            <div class="text-sm font-medium text-gray-100 mb-2 leading-tight pr-6">
                ${techName}
            </div>
            
            <!-- Cost and tier -->
            <div class="flex items-center gap-2 text-xs mb-2">
                <span class="bg-black/30 px-2 py-0.5 rounded text-gray-300">
                    💎 ${cost}
                </span>
                <span class="text-gray-500 text-[10px] uppercase tracking-wide">
                    Tier ${tier}
                </span>
            </div>
            
            <!-- Grants -->
            ${grantsParts.length > 0 || grantsStructures.length > 0 ? `
                <div class="text-xs text-gray-300 bg-black/20 rounded p-1.5 mt-2 border-t border-gray-700/30">
                    <div class="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1">Unlocks:</div>
                    <div class="space-y-0.5">
                        ${[...grantsParts, ...grantsStructures].map(item => 
                            `<div class="truncate text-gray-400">• ${item.replace(/_/g, ' ')}</div>`
                        ).join('')}
                    </div>
                </div>
            ` : ''}
        `;
        
        return card;
    }

    handleInputChange(event) {
        const input = event.target;
        const playerId = input.dataset.player;
        const field = input.dataset.field;
        const value = parseFloat(input.value) || 0;

        if (!this.state || !playerId) return;

        // Update state
        const fieldParts = field.split('.');
        let target = this.state.players[playerId];
        
        for (let i = 0; i < fieldParts.length - 1; i++) {
            if (!target[fieldParts[i]]) {
                target[fieldParts[i]] = {};
            }
            target = target[fieldParts[i]];
        }
        
        target[fieldParts[fieldParts.length - 1]] = value;

        // Update board renderer if loaded
        if (window.boardRenderer) {
            window.boardRenderer.setState(this.state);
        }

        showToast('State updated', 'success');
    }

    syncToJSON() {
        const textarea = document.getElementById('json-editor');
        if (textarea && this.state) {
            textarea.value = JSON.stringify(this.state, null, 2);
        }
    }

    applyJSON() {
        const textarea = document.getElementById('json-editor');
        try {
            const newState = JSON.parse(textarea.value);
            this.loadState(newState);
            
            // Update board renderer
            if (window.boardRenderer) {
                window.boardRenderer.setState(newState);
            }
            
            showToast('JSON applied successfully', 'success');
        } catch (e) {
            showToast(`Invalid JSON: ${e.message}`, 'error');
        }
    }

    setupSaveButton() {
        const saveBtn = document.getElementById('save-state-btn');
        saveBtn?.addEventListener('click', async () => {
            const filename = document.getElementById('save-filename').value || 'state.json';
            
            if (!this.state) {
                showToast('No state to save', 'error');
                return;
            }

            try {
                showLoading(true);
                const result = await api.saveState(this.state, filename);
                showToast(result.message || 'State saved', 'success');
            } catch (e) {
                showToast(`Failed to save: ${e.message}`, 'error');
            } finally {
                showLoading(false);
            }
        });
    }

    getState() {
        if (!this.state) {
            console.warn('StateEditor.getState called but state is null');
        }
        return this.state;
    }
    
    hasState() {
        return this.state !== null && this.state !== undefined;
    }
}

// Initialize state editor
window.addEventListener('DOMContentLoaded', () => {
    window.stateEditor = new StateEditor();
    
    // Setup apply JSON button
    document.getElementById('apply-json')?.addEventListener('click', () => {
        window.stateEditor.applyJSON();
    });
});

