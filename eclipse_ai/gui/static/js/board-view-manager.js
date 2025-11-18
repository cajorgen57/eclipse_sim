/**
 * Board View Manager - Handles tab switching between Map, Tech Market, and Player Boards
 */

class BoardViewManager {
    constructor() {
        this.currentView = 'map';
        this.state = null;
        this.initialized = false;
        
        // DOM elements
        this.tabs = null;
        this.viewContents = null;
        
        console.log('BoardViewManager constructed');
    }
    
    initialize() {
        if (this.initialized) {
            console.log('BoardViewManager already initialized');
            return;
        }
        
        // Get tab buttons
        this.tabs = document.querySelectorAll('.board-tab');
        this.viewContents = {
            map: document.getElementById('view-map'),
            tech: document.getElementById('view-tech'),
            players: document.getElementById('view-players')
        };
        
        if (!this.tabs || this.tabs.length === 0) {
            console.error('BoardViewManager: No board tabs found');
            return;
        }
        
        // Setup tab click handlers
        this.tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const view = tab.dataset.view;
                this.switchView(view);
            });
        });
        
        this.initialized = true;
        console.log('BoardViewManager initialized successfully');
    }
    
    switchView(viewName) {
        if (!['map', 'tech', 'players'].includes(viewName)) {
            console.error(`Invalid view name: ${viewName}`);
            return;
        }
        
        console.log(`Switching to view: ${viewName}`);
        this.currentView = viewName;
        
        // Update tab buttons
        this.tabs.forEach(tab => {
            if (tab.dataset.view === viewName) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });
        
        // Update view visibility
        Object.entries(this.viewContents).forEach(([view, element]) => {
            if (view === viewName) {
                element.classList.remove('hidden');
                element.classList.add('active');
            } else {
                element.classList.add('hidden');
                element.classList.remove('active');
            }
        });
        
        // Render the appropriate view
        this.renderCurrentView();
    }
    
    loadState(state) {
        if (!state) {
            console.error('BoardViewManager.loadState called with null state');
            return;
        }
        
        this.state = state;
        console.log('BoardViewManager state loaded');
        
        // Ensure StateEditor and PlayerPanel have the state
        if (window.stateEditor) {
            window.stateEditor.state = state;
        }
        if (window.playerPanel) {
            window.playerPanel.state = state;
        }
        
        // Pre-render all views so they're ready when switching tabs
        this.renderAllViews();
    }
    
    renderCurrentView() {
        if (!this.state) {
            console.log('No state loaded, skipping render');
            return;
        }
        
        switch (this.currentView) {
            case 'map':
                this.renderMapView();
                break;
            case 'tech':
                this.renderTechView();
                break;
            case 'players':
                this.renderPlayerView();
                break;
        }
    }
    
    renderMapView() {
        // Map is always rendered by BoardRenderer
        // Just ensure it's updated with current state
        if (window.boardRenderer && this.state) {
            window.boardRenderer.setState(this.state);
        }
        console.log('Map view rendered');
    }
    
    renderTechView() {
        console.log('renderTechView called');
        const container = document.getElementById('tech-market-container');
        if (!container) {
            console.error('Tech market container not found');
            return;
        }
        
        if (!window.stateEditor) {
            console.error('StateEditor not available');
            return;
        }
        
        if (!this.state) {
            console.error('No state available for tech view');
            return;
        }
        
        console.log('Rendering tech to container, state has techs:', this.state.tech_display?.available?.length || 0);
        
        // Use StateEditor's tech rendering to external container
        window.stateEditor.renderTechToContainer('tech-market-container');
        console.log('Tech view rendered');
    }
    
    renderPlayerView() {
        console.log('renderPlayerView called');
        
        if (!window.playerPanel) {
            console.error('PlayerPanel not available');
            return;
        }
        
        if (!this.state) {
            console.error('No state available for player view');
            return;
        }
        
        console.log('Rendering players to container, state has players:', Object.keys(this.state.players || {}).length);
        
        // Use PlayerPanel's rendering to external container
        window.playerPanel.renderToContainer('players-board-container');
        console.log('Player view rendered');
    }
    
    renderAllViews() {
        console.log('Rendering all views with state');
        
        // Render all views so they're ready when switching tabs
        this.renderMapView();
        this.renderTechView();
        this.renderPlayerView();
        
        console.log('All views rendered');
    }
    
    refreshCurrentView() {
        this.renderCurrentView();
    }
    
    refreshAllViews() {
        this.renderAllViews();
    }
    
    getCurrentView() {
        return this.currentView;
    }
}

// Initialize when DOM is ready
window.addEventListener('DOMContentLoaded', () => {
    window.boardViewManager = new BoardViewManager();
    console.log('BoardViewManager created and attached to window');
});

