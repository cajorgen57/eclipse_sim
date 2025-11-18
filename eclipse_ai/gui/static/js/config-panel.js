/**
 * Configuration Panel - Planner settings and controls
 */

class ConfigPanel {
    constructor() {
        this.collapsed = false;
        this.loadProfiles();
        this.setupPredictButton();
        this.setupCollapseToggle();
    }

    async loadProfiles() {
        try {
            const profiles = await api.listProfiles();
            const select = document.getElementById('config-profile');
            
            if (select) {
                // Clear existing options except default
                select.innerHTML = '<option value="">Default (Balanced)</option>';
                
                // Add profile options
                profiles.forEach(profile => {
                    const option = document.createElement('option');
                    option.value = profile;
                    option.textContent = profile.charAt(0).toUpperCase() + profile.slice(1).replace('_', ' ');
                    select.appendChild(option);
                });
            }
        } catch (e) {
            console.error('Failed to load profiles:', e);
        }
    }

    setupCollapseToggle() {
        const toggleBtn = document.getElementById('toggle-config-panel');
        const configContent = document.getElementById('config-panel-content');
        const icon = document.getElementById('config-collapse-icon');
        
        if (!toggleBtn || !configContent || !icon) {
            console.warn('Config panel collapse toggle elements not found');
            return;
        }
        
        toggleBtn.addEventListener('click', () => {
            this.collapsed = !this.collapsed;
            if (this.collapsed) {
                configContent.classList.add('hidden');
                icon.textContent = '+';
            } else {
                configContent.classList.remove('hidden');
                icon.textContent = '−';
            }
        });
    }

    getConfig() {
        return {
            planner: {
                simulations: parseInt(document.getElementById('config-sims')?.value || 600),
                depth: parseInt(document.getElementById('config-depth')?.value || 3),
                pw_alpha: 0.65,
                pw_c: 1.8,
                prior_scale: 0.6,
                seed: 0,
            },
            profile: document.getElementById('config-profile')?.value || '',
            top_k: parseInt(document.getElementById('config-topk')?.value || 5),
            verbose: document.getElementById('config-verbose')?.checked || false,
        };
    }

    setupPredictButton() {
        const predictBtn = document.getElementById('predict-btn');
        predictBtn?.addEventListener('click', async () => {
            await this.runPrediction();
        });
    }

    async runPrediction() {
        console.log('runPrediction called');
        console.log('window.stateEditor exists:', !!window.stateEditor);
        console.log('window.stateEditor.initialized:', window.stateEditor?.initialized);
        console.log('window.stateEditor has state:', window.stateEditor?.hasState());
        console.log('window.appState.currentState exists:', !!window.appState?.currentState);
        
        if (!window.stateEditor) {
            console.error('StateEditor not initialized');
            showToast('Error: State editor not initialized. Please refresh the page.', 'error');
            return;
        }
        
        if (!window.stateEditor.hasState()) {
            console.error('No state loaded in StateEditor');
            showToast('No game state loaded. Please load a fixture or generate a new game first.', 'error');
            return;
        }

        const state = window.stateEditor.getState();
        console.log('Retrieved state for prediction:', state);
        const config = this.getConfig();

        try {
            showLoading(true);
            updateStatus('Running planner...', 'running');
            
            const result = await api.predict(state, config);
            
            // Display results
            if (window.resultsDisplay) {
                window.resultsDisplay.displayResults(result);
            } else {
                console.error('window.resultsDisplay not initialized!');
            }
            
            // Update board renderer with overlays from first plan
            if (window.boardRenderer && result.plans && result.plans.length > 0) {
                const overlays = result.plans[0].overlays || [];
                // TODO: Implement overlay rendering in Canvas 2D renderer
                console.log('Plan overlays:', overlays);
            }
            
            updateStatus('Prediction complete', 'success');
            showToast('Predictions generated successfully', 'success');
            
        } catch (e) {
            console.error('Prediction error:', e);
            showToast(`Prediction failed: ${e.message}`, 'error');
            updateStatus('Prediction failed', 'error');
        } finally {
            showLoading(false);
        }
    }
}

// Initialize config panel
window.addEventListener('DOMContentLoaded', () => {
    window.configPanel = new ConfigPanel();
});

