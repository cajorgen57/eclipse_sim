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

        // Opponent analysis if available
        if (this.results.opponents) {
            const opponentCard = this.createOpponentCard(this.results.opponents, this.results.threat_summary);
            this.container.appendChild(opponentCard);
        }

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
            window.boardRenderer.setOverlays(overlays);

            // Highlight selected plan card
            const cards = this.container.querySelectorAll('[data-plan-index]');
            cards.forEach(c => c.classList.remove('selected', 'plan-card'));
            const selected = this.container.querySelector(`[data-plan-index="${index}"]`);
            if (selected) {
                selected.classList.add('selected', 'plan-card');
            }
        }
    }

    createOpponentCard(opponents, threatSummary) {
        const card = document.createElement('div');
        card.className = 'bg-eclipse-dark rounded-lg p-4 mt-4';

        card.innerHTML = `<h3 class="font-semibold mb-3">Opponent Analysis</h3>`;

        const playerColors = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];

        for (const [pid, data] of Object.entries(opponents)) {
            const color = playerColors[parseInt(pid)] || '#94a3b8';
            const danger = threatSummary ? (threatSummary[pid] || 0) : 0;

            const oppDiv = document.createElement('div');
            oppDiv.className = 'bg-gray-800 rounded p-3 mb-2';

            // Header with style badge
            const styleBadgeColor = {
                'RUSHER': 'bg-red-600', 'BALANCED': 'bg-blue-600',
                'TECHER': 'bg-purple-600', 'TURTLE': 'bg-green-600',
                'BUILDER': 'bg-yellow-600', 'EXPANDER': 'bg-orange-600',
            }[data.style] || 'bg-gray-600';

            oppDiv.innerHTML = `
                <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center space-x-2">
                        <span class="w-3 h-3 rounded-full inline-block" style="background:${color}"></span>
                        <span class="font-medium text-sm">Player ${pid}</span>
                        <span class="${styleBadgeColor} text-white text-xs px-2 py-0.5 rounded-full">${data.style}</span>
                    </div>
                    ${danger > 0 ? `<span class="text-xs ${danger > 0.5 ? 'text-red-400' : 'text-yellow-300'}">Threat: ${(danger * 100).toFixed(0)}%</span>` : ''}
                </div>
                <div class="grid grid-cols-3 gap-1 text-xs">
                    ${this._metricBar('Aggression', data.aggression, '#ef4444')}
                    ${this._metricBar('Fleet Power', data.fleet_power, '#3b82f6')}
                    ${this._metricBar('Tech Pace', data.tech_pace, '#a855f7')}
                    ${this._metricBar('Expansion', data.expansion, '#22c55e')}
                    ${this._metricBar('Mobility', data.mobility, '#eab308')}
                    ${this._metricBar('Border Press.', data.border_pressure, '#f97316')}
                </div>
            `;

            card.appendChild(oppDiv);
        }

        return card;
    }

    _metricBar(label, value, color) {
        const pct = Math.round((value || 0) * 100);
        return `
            <div>
                <div class="flex justify-between text-gray-400 mb-0.5">
                    <span>${label}</span>
                    <span>${pct}%</span>
                </div>
                <div class="w-full bg-gray-700 rounded-full h-1.5">
                    <div class="h-1.5 rounded-full" style="width:${pct}%;background:${color}"></div>
                </div>
            </div>
        `;
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

        // Categorize features for organized display
        const categories = {
            'Resources': ['money', 'science', 'materials', 'money_income', 'science_income', 'materials_income', 'total_income', 'orange_net_income', 'orange_efficiency'],
            'Military': ['total_fleet_size', 'fleet_power', 'fleet_interceptors', 'fleet_cruisers', 'fleet_dreadnoughts', 'fleet_starbases', 'total_firepower_designs', 'total_defense_designs'],
            'Territory': ['controlled_hexes', 'colonized_planets', 'influence_hexes', 'reachable_hexes', 'planet_diversity'],
            'Relative Advantage': ['relative_tech', 'relative_territory', 'relative_fleet', 'relative_economy', 'leader_gap'],
            'Combat Readiness': ['fleet_concentration', 'border_defense_coverage', 'reinforcement_capacity', 'offensive_readiness'],
            'Threats': ['enemy_ships_total', 'contested_hexes', 'threat_ratio', 'danger_max', 'danger_mean'],
            'Tech': ['tech_count', 'military_tech', 'grid_tech', 'nano_tech'],
        };

        // Build a set of categorized keys for quick lookup
        const categorizedKeys = new Set();
        Object.values(categories).forEach(keys => keys.forEach(k => categorizedKeys.add(k)));

        // Render each category as a collapsible section
        for (const [catName, catKeys] of Object.entries(categories)) {
            const catFeatures = catKeys.filter(k => features[k] !== undefined);
            if (catFeatures.length === 0) continue;

            const section = document.createElement('div');
            section.className = 'mb-3';
            section.innerHTML = `<h4 class="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">${catName}</h4>`;

            const grid = document.createElement('div');
            grid.className = 'grid grid-cols-2 gap-1 text-xs';

            catFeatures.forEach(key => {
                const value = features[key];
                const featureDiv = document.createElement('div');
                featureDiv.className = 'bg-gray-800 rounded px-2 py-1 flex justify-between';

                // Color-code relative advantage features
                let valueColor = 'text-gray-200';
                if (catName === 'Relative Advantage' || catName === 'Combat Readiness') {
                    if (typeof value === 'number') {
                        if (value > 0.2) valueColor = 'text-green-400';
                        else if (value < -0.2) valueColor = 'text-red-400';
                        else valueColor = 'text-yellow-300';
                    }
                } else if (catName === 'Threats') {
                    if (typeof value === 'number' && value > 0.5) valueColor = 'text-red-400';
                    else if (typeof value === 'number' && value > 0.2) valueColor = 'text-yellow-300';
                }

                featureDiv.innerHTML = `
                    <span class="text-gray-400 truncate">${key.replace(/_/g, ' ')}</span>
                    <span class="${valueColor} font-medium ml-1">${typeof value === 'number' ? value.toFixed(2) : value}</span>
                `;
                grid.appendChild(featureDiv);
            });

            section.appendChild(grid);
            card.appendChild(section);
        }

        // Remaining uncategorized features
        const remaining = Object.entries(features).filter(([k]) => !categorizedKeys.has(k));
        if (remaining.length > 0) {
            const section = document.createElement('div');
            section.className = 'mb-3';

            const toggleBtn = document.createElement('button');
            toggleBtn.className = 'text-xs text-gray-500 hover:text-gray-300 cursor-pointer';
            toggleBtn.textContent = `+ ${remaining.length} more features`;

            const grid = document.createElement('div');
            grid.className = 'grid grid-cols-2 gap-1 text-xs mt-1 hidden';

            remaining.sort((a, b) => a[0].localeCompare(b[0])).forEach(([key, value]) => {
                const featureDiv = document.createElement('div');
                featureDiv.className = 'bg-gray-800 rounded px-2 py-1 flex justify-between';
                featureDiv.innerHTML = `
                    <span class="text-gray-400 truncate">${key.replace(/_/g, ' ')}</span>
                    <span class="text-gray-200 font-medium ml-1">${typeof value === 'number' ? value.toFixed(2) : value}</span>
                `;
                grid.appendChild(featureDiv);
            });

            toggleBtn.addEventListener('click', () => {
                grid.classList.toggle('hidden');
                toggleBtn.textContent = grid.classList.contains('hidden')
                    ? `+ ${remaining.length} more features`
                    : `- Hide extra features`;
            });

            section.appendChild(toggleBtn);
            section.appendChild(grid);
            card.appendChild(section);
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

