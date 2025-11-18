/**
 * Hex Details Panel - Displays detailed information about selected hex
 */

class HexDetailsPanel {
    constructor() {
        this.panel = document.getElementById('hex-details-panel');
        this.title = document.getElementById('hex-details-title');
        this.infoDiv = document.getElementById('hex-info');
        this.planetsDiv = document.getElementById('hex-planets');
        this.shipsDiv = document.getElementById('hex-ships');
        this.techDiv = document.getElementById('hex-tech');
        this.closeBtn = document.getElementById('hex-details-close');
        
        this.currentHexId = null;
        this.currentHexData = null;
        
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // Listen for hex selection from board renderer
        window.addEventListener('hexSelected', (e) => {
            this.showHexDetails(e.detail.hexId, e.detail.hexData);
        });
        
        // Close button
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => {
                this.hide();
            });
        }
    }
    
    showHexDetails(hexId, hexData) {
        if (!hexId || !hexData) {
            this.hide();
            return;
        }
        
        this.currentHexId = hexId;
        this.currentHexData = hexData;
        
        // Update title
        if (this.title) {
            this.title.textContent = `Hex ${hexId} Details`;
        }
        
        // Populate sections
        this.renderInfo();
        this.renderPlanets();
        this.renderShips();
        this.renderTech();
        
        // Show panel
        if (this.panel) {
            this.panel.classList.remove('hidden');
        }
    }
    
    hide() {
        if (this.panel) {
            this.panel.classList.add('hidden');
        }
        this.currentHexId = null;
        this.currentHexData = null;
    }
    
    renderInfo() {
        if (!this.infoDiv) return;
        
        const data = this.currentHexData;
        const info = [];
        
        // Hex ID
        info.push(`<div class="flex justify-between">
            <span class="text-gray-400">Hex ID:</span>
            <span class="font-mono">${this.currentHexId}</span>
        </div>`);
        
        // Tile type
        if (data.tile_type && data.tile_type !== 'empty') {
            info.push(`<div class="flex justify-between">
                <span class="text-gray-400">Tile Type:</span>
                <span class="capitalize">${data.tile_type}</span>
            </div>`);
        }
        
        // Owner
        if (data.controlled_by !== undefined && data.controlled_by !== null) {
            info.push(`<div class="flex justify-between">
                <span class="text-gray-400">Controlled By:</span>
                <span>Player ${data.controlled_by}</span>
            </div>`);
        }
        
        // Warp Portal
        if (data.is_warp_portal || data.warp_portal) {
            info.push(`<div class="flex items-center space-x-2 text-purple-400">
                <span>⚯</span>
                <span>Warp Portal</span>
            </div>`);
        }
        
        // Anomaly
        if (data.anomaly) {
            const anomalyInfo = typeof data.anomaly === 'object' ? data.anomaly : {};
            info.push(`<div class="flex items-center space-x-2 text-orange-400">
                <span>⚠</span>
                <span>Anomaly Present</span>
                ${anomalyInfo.threat ? `<span class="text-xs">(Threat: ${anomalyInfo.threat})</span>` : ''}
            </div>`);
        }
        
        // Discovery
        if (data.discovery) {
            const disc = data.discovery;
            info.push(`<div class="flex justify-between">
                <span class="text-gray-400">Discovery:</span>
                <span class="text-yellow-400">${disc.type || 'Unknown'}</span>
            </div>`);
            if (disc.value) {
                info.push(`<div class="flex justify-between ml-4">
                    <span class="text-gray-500">Value:</span>
                    <span>${disc.value}</span>
                </div>`);
            }
        }
        
        // Influence discs
        if (data.influence_discs || data.population_cubes) {
            const count = data.influence_discs || data.population_cubes;
            info.push(`<div class="flex justify-between">
                <span class="text-gray-400">Influence Discs:</span>
                <span>${count}</span>
            </div>`);
        }
        
        // Ancients
        if (data.ancients || data.guardians) {
            const ancients = data.ancients || data.guardians;
            const count = typeof ancients === 'number' ? ancients : ancients.count || 1;
            info.push(`<div class="flex items-center space-x-2 text-red-400">
                <span>☠</span>
                <span>Ancients: ${count}</span>
            </div>`);
        }
        
        this.infoDiv.innerHTML = info.length > 0 
            ? info.join('') 
            : '<div class="text-gray-500">No hex information</div>';
    }
    
    renderPlanets() {
        if (!this.planetsDiv) return;
        
        const data = this.currentHexData;
        
        if (!data.planets || data.planets.length === 0) {
            this.planetsDiv.innerHTML = '';
            return;
        }
        
        const planets = data.planets.map((planet, i) => {
            const typeColor = {
                money: 'text-yellow-400',
                science: 'text-blue-400',
                materials: 'text-red-400',
                advanced: 'text-purple-400'
            }[planet.type] || 'text-green-400';
            
            const prodIcons = [];
            if (planet.production) {
                if (planet.production.money) prodIcons.push(`💰${planet.production.money}`);
                if (planet.production.science) prodIcons.push(`🔬${planet.production.science}`);
                if (planet.production.materials) prodIcons.push(`⚙️${planet.production.materials}`);
            }
            
            const status = planet.colonized || planet.population ? '(Colonized)' : '';
            
            return `<div class="border border-gray-700 rounded p-2 space-y-1">
                <div class="flex justify-between items-center">
                    <span class="font-semibold ${typeColor}">Planet ${i + 1}</span>
                    <span class="text-gray-500 text-xs">${status}</span>
                </div>
                ${planet.type ? `<div class="text-xs"><span class="text-gray-400">Type:</span> ${planet.type}</div>` : ''}
                ${prodIcons.length > 0 ? `<div class="text-xs flex space-x-2">${prodIcons.join(' ')}</div>` : ''}
                ${planet.advanced ? '<div class="text-xs text-purple-300">⭐ Advanced</div>' : ''}
            </div>`;
        }).join('');
        
        this.planetsDiv.innerHTML = `
            <div class="font-semibold text-gray-300 mb-2">Planets (${data.planets.length})</div>
            <div class="space-y-2">${planets}</div>
        `;
    }
    
    renderShips() {
        if (!this.shipsDiv) return;
        
        const data = this.currentHexData;
        
        if (!data.ships || (Array.isArray(data.ships) && data.ships.length === 0)) {
            this.shipsDiv.innerHTML = '';
            return;
        }
        
        const ships = this.countShips(data.ships);
        const shipTypes = Object.entries(ships).filter(([_, count]) => count > 0);
        
        if (shipTypes.length === 0) {
            this.shipsDiv.innerHTML = '';
            return;
        }
        
        const shipIcons = {
            interceptor: '▲',
            cruiser: '◆',
            dreadnought: '■',
            starbase: '⬡'
        };
        
        const shipsList = shipTypes.map(([type, count]) => {
            return `<div class="flex justify-between items-center bg-gray-800 rounded px-2 py-1">
                <span class="flex items-center space-x-2">
                    <span class="text-lg">${shipIcons[type] || '●'}</span>
                    <span class="capitalize">${type}</span>
                </span>
                <span class="font-mono">×${count}</span>
            </div>`;
        }).join('');
        
        this.shipsDiv.innerHTML = `
            <div class="font-semibold text-gray-300 mb-2">Ships</div>
            <div class="space-y-1">${shipsList}</div>
        `;
    }
    
    renderTech() {
        if (!this.techDiv) return;
        
        const data = this.currentHexData;
        const techs = data.technologies || data.tech;
        
        if (!techs || techs.length === 0) {
            this.techDiv.innerHTML = '';
            return;
        }
        
        const techList = techs.map((tech, i) => {
            // Get category from tech or detect it
            const category = tech.category || tech.type || window.UIConstants.detectTechCategory(tech.name || '');
            const style = window.UIConstants.getCategoryStyle(category);
            
            return `<div class="border border-gray-700/50 rounded p-2 bg-black/20 hover:bg-black/30 transition-colors">
                <div class="font-medium text-sm flex items-center gap-2">
                    <span class="opacity-70">${style.icon}</span>
                    <span class="text-gray-200">${tech.name || `Tech ${i + 1}`}</span>
                </div>
                ${tech.category ? `<div class="text-[10px] text-gray-500 uppercase tracking-wide mt-1 ml-6">${tech.category}</div>` : ''}
                ${tech.cost ? `<div class="text-xs text-gray-400 ml-6">Cost: ${tech.cost}</div>` : ''}
            </div>`;
        }).join('');
        
        this.techDiv.innerHTML = `
            <div class="font-semibold text-gray-300 mb-2">Technologies (${techs.length})</div>
            <div class="space-y-1">${techList}</div>
        `;
    }
    
    countShips(shipsData) {
        const counts = {
            interceptor: 0,
            cruiser: 0,
            dreadnought: 0,
            starbase: 0
        };
        
        if (Array.isArray(shipsData)) {
            shipsData.forEach(ship => {
                const type = ship.type || ship.ship_type;
                if (counts.hasOwnProperty(type)) {
                    counts[type]++;
                }
            });
        } else if (typeof shipsData === 'object') {
            Object.assign(counts, shipsData);
        }
        
        return counts;
    }
}

// Initialize when DOM is ready
window.addEventListener('DOMContentLoaded', () => {
    window.hexDetailsPanel = new HexDetailsPanel();
    console.log('Hex Details Panel initialized');
});

