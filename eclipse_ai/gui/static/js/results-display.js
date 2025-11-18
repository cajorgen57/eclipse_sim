/**
 * Results Display - Show prediction results
 */

class ResultsDisplay {
    constructor() {
        this.results = null;
        this.container = document.getElementById('results-container');
        console.log('ResultsDisplay constructor - container:', this.container);
    }

    displayResults(results) {
        console.log('ResultsDisplay.displayResults called with:', results);
        this.results = results;
        this.render();
    }

    render() {
        if (!this.results || !this.results.plans) {
            this.container.innerHTML = '<p class="text-sm text-gray-400 text-center py-4">No results</p>';
            return;
        }

        const plans = this.results.plans || [];
        
        this.container.innerHTML = '';

        // Summary header
        const summary = document.createElement('div');
        summary.className = 'bg-eclipse-dark rounded-lg p-4 mb-4';
        summary.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <h3 class="font-semibold">Round ${this.results.round || '?'}</h3>
                <span class="text-sm text-gray-400">Player: ${this.results.active_player || '?'}</span>
            </div>
            <div class="text-sm text-gray-400">
                Generated ${plans.length} plan${plans.length !== 1 ? 's' : ''}
            </div>
        `;
        this.container.appendChild(summary);

        // Plans list
        plans.forEach((plan, index) => {
            const planCard = this.createPlanCard(plan, index);
            this.container.appendChild(planCard);
        });

        // Features if verbose
        if (this.results.features) {
            const featuresCard = this.createFeaturesCard(this.results.features);
            this.container.appendChild(featuresCard);
        }
    }

    createPlanCard(plan, index) {
        const card = document.createElement('div');
        card.className = 'bg-eclipse-dark rounded-lg p-4 mb-3 hover:bg-gray-800 transition cursor-pointer';
        card.dataset.planIndex = index;

        const steps = plan.steps || [];
        const firstStep = steps[0] || {};
        
        // Header
        const header = document.createElement('div');
        header.className = 'flex items-center justify-between mb-3';
        header.innerHTML = `
            <div class="flex items-center space-x-2">
                <span class="font-semibold text-lg">Plan ${index + 1}</span>
                ${this.getRankBadge(index)}
            </div>
            ${this.getScoreBadge(plan)}
        `;
        card.appendChild(header);

        // Steps
        const stepsDiv = document.createElement('div');
        stepsDiv.className = 'space-y-2';
        
        steps.forEach((step, stepIndex) => {
            const stepDiv = this.createStepDiv(step, stepIndex);
            stepsDiv.appendChild(stepDiv);
        });
        
        card.appendChild(stepsDiv);

        // Click to show overlays
        card.addEventListener('click', () => {
            this.showPlanOverlays(plan, index);
        });

        return card;
    }

    createStepDiv(step, index) {
        const div = document.createElement('div');
        div.className = 'bg-gray-800 rounded p-3 text-sm';
        
        const action = step.action || 'Unknown';
        const payload = step.payload || {};
        
        let details = '';
        
        if (action === 'RESEARCH' || action === 'Research') {
            details = `Tech: ${payload.tech || '?'}`;
        } else if (action === 'BUILD' || action === 'Build') {
            const ships = payload.ships || {};
            const shipList = Object.entries(ships)
                .filter(([_, count]) => count > 0)
                .map(([type, count]) => `${count}× ${type}`)
                .join(', ');
            details = shipList || 'Ships';
        } else if (action === 'EXPLORE' || action === 'Explore') {
            details = `Ring ${payload.ring || '?'}`;
        } else if (action === 'MOVE' || action === 'Move') {
            details = `${payload.from || '?'} → ${payload.to || '?'}`;
        } else if (action === 'INFLUENCE' || action === 'Influence') {
            details = `Hex: ${payload.hex || '?'}`;
        } else if (action === 'UPGRADE' || action === 'Upgrade') {
            details = `Ship: ${payload.ship_type || '?'}`;
        }

        div.innerHTML = `
            <div class="flex items-center justify-between">
                <div>
                    <span class="font-medium">${index + 1}. ${action}</span>
                    ${details ? `<span class="text-gray-400 ml-2">${details}</span>` : ''}
                </div>
                ${step.details?.prior ? `<span class="text-xs text-gray-500">Prior: ${step.details.prior.toFixed(3)}</span>` : ''}
            </div>
        `;
        
        return div;
    }

    getRankBadge(index) {
        const colors = ['bg-yellow-500', 'bg-gray-400', 'bg-orange-600'];
        const color = colors[index] || 'bg-gray-600';
        return `<span class="${color} text-white text-xs px-2 py-1 rounded-full">#${index + 1}</span>`;
    }

    getScoreBadge(plan) {
        if (plan.score != null) {
            return `<span class="text-sm text-gray-400">Score: ${plan.score.toFixed(2)}</span>`;
        }
        return '';
    }

    showPlanOverlays(plan, index) {
        if (window.boardRenderer) {
            const overlays = plan.overlays || [];
            // TODO: Implement overlay rendering in Canvas 2D renderer
            console.log('Plan overlays:', overlays);
            showToast(`Showing overlays for Plan ${index + 1}`, 'info');
        }
    }

    createFeaturesCard(features) {
        const card = document.createElement('div');
        card.className = 'bg-eclipse-dark rounded-lg p-4 mt-4';
        
        const header = document.createElement('h3');
        header.className = 'font-semibold mb-3';
        header.textContent = 'Extracted Features';
        card.appendChild(header);

        if (features.error) {
            card.innerHTML += `<p class="text-sm text-red-400">${features.error}</p>`;
            return card;
        }

        const grid = document.createElement('div');
        grid.className = 'grid grid-cols-2 gap-2 text-xs max-h-64 overflow-y-auto';
        
        const importantFeatures = [
            'money', 'science', 'materials',
            'total_fleet_size', 'controlled_hexes', 'tech_count',
            'fleet_power', 'money_income', 'science_income'
        ];

        const sortedFeatures = Object.entries(features)
            .sort((a, b) => {
                const aIndex = importantFeatures.indexOf(a[0]);
                const bIndex = importantFeatures.indexOf(b[0]);
                if (aIndex !== -1 && bIndex !== -1) return aIndex - bIndex;
                if (aIndex !== -1) return -1;
                if (bIndex !== -1) return 1;
                return a[0].localeCompare(b[0]);
            });

        sortedFeatures.slice(0, 20).forEach(([key, value]) => {
            const featureDiv = document.createElement('div');
            featureDiv.className = 'bg-gray-800 rounded px-2 py-1';
            featureDiv.innerHTML = `
                <span class="text-gray-400">${key}:</span>
                <span class="text-gray-200 font-medium ml-1">${typeof value === 'number' ? value.toFixed(2) : value}</span>
            `;
            grid.appendChild(featureDiv);
        });

        card.appendChild(grid);
        
        if (sortedFeatures.length > 20) {
            const more = document.createElement('p');
            more.className = 'text-xs text-gray-500 mt-2';
            more.textContent = `... and ${sortedFeatures.length - 20} more features`;
            card.appendChild(more);
        }

        return card;
    }
}

// Initialize results display
let resultsDisplay;
window.addEventListener('DOMContentLoaded', () => {
    window.resultsDisplay = new ResultsDisplay();
    resultsDisplay = window.resultsDisplay; // Keep local reference for compatibility
});

