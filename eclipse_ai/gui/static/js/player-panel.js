/**
 * Player Information Panel
 * Displays ship blueprints, technologies, and resources
 */

class PlayerPanel {
    constructor() {
        this.currentPlayer = null;
        this.state = null;
        this.collapsed = false;
        
        this.setupToggle();
    }
    
    setupToggle() {
        const toggle = document.getElementById('player-info-toggle');
        if (toggle) {
            toggle.addEventListener('click', () => {
                this.collapsed = !this.collapsed;
                const content = document.getElementById('player-info-content');
                const arrow = toggle.querySelector('span');
                if (this.collapsed) {
                    content.style.display = 'none';
                    arrow.textContent = '▶';
                } else {
                    content.style.display = 'block';
                    arrow.textContent = '▼';
                }
            });
        }
    }
    
    loadState(state) {
        this.state = state;
        this.currentPlayer = state.active_player || Object.keys(state.players || {})[0];
        this.render();
    }
    
    render() {
        if (!this.state || !this.state.players) return;
        
        this.renderPlayerTabs();
        this.renderPlayerDetails();
    }
    
    renderToContainer(containerBaseId) {
        if (!this.state || !this.state.players) {
            console.error('PlayerPanel: No state available for rendering');
            return;
        }
        
        console.log(`PlayerPanel rendering to container: ${containerBaseId}`);
        
        // Render player tabs to external container
        const tabsContainer = document.getElementById('player-tabs-board');
        const detailsContainer = document.getElementById('player-details-board');
        
        if (!tabsContainer || !detailsContainer) {
            console.error('PlayerPanel: External containers not found', { tabsContainer, detailsContainer });
            return;
        }
        
        // Clear containers
        tabsContainer.innerHTML = '';
        detailsContainer.innerHTML = '';
        
        // Render tabs
        Object.entries(this.state.players).forEach(([playerId, player]) => {
            const button = document.createElement('button');
            button.className = `px-3 py-1 rounded text-xs font-medium transition ${
                playerId === this.currentPlayer 
                    ? 'bg-eclipse-primary text-white' 
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`;
            button.textContent = this.getPlayerName(playerId, player);
            button.addEventListener('click', () => {
                this.currentPlayer = playerId;
                this.renderToContainer(containerBaseId);
            });
            tabsContainer.appendChild(button);
        });
        
        // Render player details
        const player = this.state.players[this.currentPlayer];
        if (!player) return;
        
        detailsContainer.className = 'space-y-3';
        
        // Enhanced resource display with visual bars
        const resourceCard = this.createResourceCard(player);
        detailsContainer.appendChild(resourceCard);
        
        // Ship blueprints
        const shipCard = this.createShipCard(player);
        detailsContainer.appendChild(shipCard);
        
        // Tech tree visualization
        const techSection = this.createSection('Technologies');
        techSection.appendChild(this.renderTechnologies(player));
        detailsContainer.appendChild(techSection);
        
        // Diplomacy and Combat tiles
        const diplomacyCard = this.createDiplomacyCard(player);
        detailsContainer.appendChild(diplomacyCard);
        
        console.log('PlayerPanel rendered to external container');
    }
    
    renderPlayerTabs() {
        const container = document.getElementById('player-tabs');
        if (!container) return;
        
        container.innerHTML = '';
        
        Object.entries(this.state.players).forEach(([playerId, player]) => {
            const button = document.createElement('button');
            button.className = `px-3 py-1 rounded text-xs font-medium transition ${
                playerId === this.currentPlayer 
                    ? 'bg-eclipse-primary text-white' 
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`;
            button.textContent = this.getPlayerName(playerId, player);
            button.addEventListener('click', () => {
                this.currentPlayer = playerId;
                this.render();
            });
            container.appendChild(button);
        });
    }
    
    renderPlayerDetails() {
        const container = document.getElementById('player-details');
        if (!container || !this.currentPlayer) return;
        
        const player = this.state.players[this.currentPlayer];
        if (!player) return;
        
        container.innerHTML = '';
        container.className = 'space-y-3';
        
        // Enhanced resource display with visual bars
        const resourceCard = this.createResourceCard(player);
        container.appendChild(resourceCard);
        
        // Ship blueprints in expandable sections
        const shipCard = this.createShipCard(player);
        container.appendChild(shipCard);
        
        // Tech tree visualization
        const techSection = this.createSection('Technologies');
        techSection.appendChild(this.renderTechnologies(player));
        container.appendChild(techSection);
        
        // Diplomacy and Combat tiles
        const diplomacyCard = this.createDiplomacyCard(player);
        container.appendChild(diplomacyCard);
    }
    
    createSection(title) {
        const section = document.createElement('div');
        section.className = 'bg-gray-800 rounded p-2';
        
        const header = document.createElement('h4');
        header.className = 'text-xs font-semibold text-gray-300 mb-2';
        header.textContent = title;
        section.appendChild(header);
        
        return section;
    }
    
    createResourceCard(player) {
        const card = document.createElement('div');
        card.className = 'player-card bg-gradient-to-br from-gray-800 to-gray-900 rounded-lg p-4 border border-gray-700 shadow-lg';
        
        const resources = player.resources || { money: 0, science: 0, materials: 0 };
        const income = player.income || { money: 0, science: 0, materials: 0 };
        
        card.innerHTML = `
            <div class="flex items-center justify-between mb-3">
                <h4 class="text-sm font-bold text-white">Resources & Economy</h4>
                <span class="text-xs text-gray-400">Round ${this.state.round || 1}</span>
            </div>
            
            <div class="space-y-3">
                ${Object.entries(resources).map(([type, value]) => {
                    const config = window.UIConstants.getResourceConfig(type);
                    const inc = income[type] || 0;
                    const nextValue = value + inc;
                    const percentage = inc > 0 ? Math.min(100, (value / Math.max(1, nextValue)) * 100) : 0;
                    
                    return `
                        <div class="bg-black/30 rounded-lg p-3">
                            <!-- Resource header -->
                            <div class="flex items-center justify-between mb-2">
                                <div class="flex items-center gap-2">
                                    <span class="text-xl">${config.icon}</span>
                                    <span class="text-xs font-semibold text-gray-300">${config.label}</span>
                                </div>
                                <div class="flex items-center gap-2">
                                    <span class="text-lg font-bold text-white">${value}</span>
                                    ${inc > 0 ? `
                                        <span class="text-xs text-green-400 font-semibold">
                                            +${inc} → ${nextValue}
                                        </span>
                                    ` : ''}
                                </div>
                            </div>
                            
                            <!-- Visual progress bar -->
                            ${inc > 0 ? `
                                <div class="w-full bg-gray-700 rounded-full h-2 overflow-hidden">
                                    <div class="resource-bar h-full bg-gradient-to-r ${config.gradient} transition-all duration-500" 
                                         style="--fill-width: ${percentage}%; width: ${percentage}%">
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    `;
                }).join('')}
            </div>
        `;
        
        return card;
    }
    
    renderResources(player) {
        const container = document.createElement('div');
        container.className = 'grid grid-cols-3 gap-2 text-xs';
        
        const resources = player.resources || { money: 0, science: 0, materials: 0 };
        const income = player.income || { money: 0, science: 0, materials: 0 };
        
        const resourceIcons = {
            money: '💰',
            science: '🔬',
            materials: '🔩'
        };
        
        Object.entries(resources).forEach(([type, value]) => {
            const div = document.createElement('div');
            div.className = 'flex items-center space-x-1';
            
            const icon = document.createElement('span');
            icon.textContent = resourceIcons[type] || '•';
            
            const text = document.createElement('span');
            text.className = 'text-gray-300';
            text.textContent = `${value}`;
            
            const incomeText = document.createElement('span');
            incomeText.className = 'text-green-400 text-xs';
            incomeText.textContent = income[type] > 0 ? `+${income[type]}` : '';
            
            div.appendChild(icon);
            div.appendChild(text);
            if (income[type] > 0) div.appendChild(incomeText);
            
            container.appendChild(div);
        });
        
        return container;
    }
    
    createShipCard(player) {
        const card = document.createElement('div');
        card.className = 'player-card bg-gradient-to-br from-gray-800 to-gray-900 rounded-lg p-4 border border-gray-700 shadow-lg';
        
        const shipDesigns = player.ship_designs || {};
        const shipTypes = ['interceptor', 'cruiser', 'dreadnought', 'starbase'];
        
        card.innerHTML = `
            <div class="flex items-center justify-between mb-3">
                <h4 class="text-sm font-bold text-white flex items-center gap-2">
                    <span>🛸</span>
                    Ship Blueprints
                </h4>
                <span class="text-xs text-gray-400 bg-gray-800 px-2 py-1 rounded">
                    ${Object.keys(shipDesigns).length} designs
                </span>
            </div>
        `;
        
        const shipsContainer = document.createElement('div');
        shipsContainer.className = 'space-y-2';
        
        shipTypes.forEach(shipType => {
            if (shipDesigns[shipType]) {
                const blueprint = this.createEnhancedShipBlueprint(shipType, shipDesigns[shipType]);
                shipsContainer.appendChild(blueprint);
            }
        });
        
        card.appendChild(shipsContainer);
        return card;
    }
    
    createDiplomacyCard(player) {
        const card = document.createElement('div');
        card.className = 'player-card bg-gradient-to-br from-gray-800 to-gray-900 rounded-lg p-4 border border-gray-700 shadow-lg';
        
        const diplomacy = player.diplomacy || {};
        const ambassadors = player.ambassadors || {};
        const hasTraitor = player.has_traitor || false;
        const allianceId = player.alliance_id || null;
        const allianceTile = player.alliance_tile || null;
        const reputation = player.reputation || [];
        
        card.innerHTML = `
            <div class="flex items-center justify-between mb-3">
                <h4 class="text-sm font-bold text-white flex items-center gap-2">
                    <span>🤝</span>
                    Diplomacy & Combat
                </h4>
                <span class="text-xs text-gray-400 bg-gray-800 px-2 py-1 rounded">
                    ${Object.keys(diplomacy).length} relations
                </span>
            </div>
        `;
        
        const diplomacyContainer = document.createElement('div');
        diplomacyContainer.className = 'space-y-2';
        
        // Reputation tiles
        if (reputation && reputation.length > 0) {
            const repSection = document.createElement('div');
            repSection.className = 'bg-black/30 rounded-lg p-2';
            repSection.innerHTML = `
                <div class="flex items-center justify-between mb-1">
                    <span class="text-xs font-semibold text-gray-300">🏆 Reputation</span>
                    <span class="text-xs text-yellow-400">${reputation.reduce((a, b) => a + b, 0)} VP</span>
                </div>
                <div class="flex flex-wrap gap-1">
                    ${reputation.map(vp => `
                        <span class="bg-yellow-500/30 text-yellow-200 px-2 py-1 rounded text-xs font-bold">
                            +${vp}
                        </span>
                    `).join('')}
                </div>
            `;
            diplomacyContainer.appendChild(repSection);
        }
        
        // Alliance status
        if (allianceId || allianceTile) {
            const allianceSection = document.createElement('div');
            allianceSection.className = 'bg-black/30 rounded-lg p-2';
            allianceSection.innerHTML = `
                <div class="flex items-center justify-between">
                    <span class="text-xs font-semibold text-gray-300">🤝 Alliance</span>
                    ${allianceTile ? `
                        <span class="text-xs font-bold ${allianceTile === '+2' ? 'text-green-400' : 'text-red-400'}">
                            ${allianceTile} VP
                        </span>
                    ` : ''}
                </div>
                ${allianceId ? `
                    <div class="text-xs text-gray-400 mt-1">
                        With: ${allianceId}
                    </div>
                ` : ''}
            `;
            diplomacyContainer.appendChild(allianceSection);
        }
        
        // Diplomatic relations
        if (Object.keys(diplomacy).length > 0) {
            const relationsSection = document.createElement('div');
            relationsSection.className = 'bg-black/30 rounded-lg p-2';
            
            const relationsHeader = document.createElement('div');
            relationsHeader.className = 'text-xs font-semibold text-gray-300 mb-2';
            relationsHeader.textContent = '📜 Diplomatic Relations';
            relationsSection.appendChild(relationsHeader);
            
            const relationsList = document.createElement('div');
            relationsList.className = 'space-y-1';
            
            Object.entries(diplomacy).forEach(([playerId, status]) => {
                const relationDiv = document.createElement('div');
                relationDiv.className = 'flex items-center justify-between text-xs';
                
                const relationIcon = this.getDiplomacyIcon(status);
                const relationColor = this.getDiplomacyColor(status);
                
                relationDiv.innerHTML = `
                    <span class="text-gray-300">${playerId}</span>
                    <span class="${relationColor} font-semibold">
                        ${relationIcon} ${status}
                    </span>
                `;
                relationsList.appendChild(relationDiv);
            });
            
            relationsSection.appendChild(relationsList);
            diplomacyContainer.appendChild(relationsSection);
        }
        
        // Ambassadors
        if (Object.keys(ambassadors).length > 0) {
            const ambassadorSection = document.createElement('div');
            ambassadorSection.className = 'bg-black/30 rounded-lg p-2';
            ambassadorSection.innerHTML = `
                <div class="text-xs font-semibold text-gray-300 mb-1">👔 Ambassadors</div>
                <div class="flex flex-wrap gap-1">
                    ${Object.entries(ambassadors).map(([playerId, active]) => `
                        <span class="bg-blue-500/30 text-blue-200 px-2 py-1 rounded text-xs ${active ? '' : 'opacity-50'}">
                            ${playerId}
                        </span>
                    `).join('')}
                </div>
            `;
            diplomacyContainer.appendChild(ambassadorSection);
        }
        
        // Traitor card
        if (hasTraitor) {
            const traitorSection = document.createElement('div');
            traitorSection.className = 'bg-red-900/30 border border-red-500/50 rounded-lg p-2';
            traitorSection.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="text-lg">🗡️</span>
                    <span class="text-xs font-semibold text-red-300">Traitor Card</span>
                </div>
            `;
            diplomacyContainer.appendChild(traitorSection);
        }
        
        // Empty state
        if (Object.keys(diplomacy).length === 0 && !allianceId && !hasTraitor && reputation.length === 0) {
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'text-xs text-gray-500 italic text-center py-4';
            emptyDiv.textContent = 'No diplomatic relations or reputation tiles';
            diplomacyContainer.appendChild(emptyDiv);
        }
        
        card.appendChild(diplomacyContainer);
        return card;
    }
    
    getDiplomacyIcon(status) {
        const icons = {
            'peace': '🕊️',
            'war': '⚔️',
            'alliance': '🤝',
            'neutral': '⚖️'
        };
        return icons[status.toLowerCase()] || '📋';
    }
    
    getDiplomacyColor(status) {
        const colors = {
            'peace': 'text-green-400',
            'war': 'text-red-400',
            'alliance': 'text-blue-400',
            'neutral': 'text-gray-400'
        };
        return colors[status.toLowerCase()] || 'text-gray-400';
    }
    
    renderShipBlueprints(player) {
        const container = document.createElement('div');
        container.className = 'space-y-2';
        
        const shipDesigns = player.ship_designs || {};
        const shipTypes = ['interceptor', 'cruiser', 'dreadnought', 'starbase'];
        
        if (Object.keys(shipDesigns).length === 0) {
            const empty = document.createElement('div');
            empty.className = 'text-xs text-gray-500 italic';
            empty.textContent = 'No ship designs';
            container.appendChild(empty);
            return container;
        }
        
        shipTypes.forEach(shipType => {
            if (shipDesigns[shipType]) {
                const blueprint = this.renderShipBlueprint(shipType, shipDesigns[shipType]);
                container.appendChild(blueprint);
            }
        });
        
        return container;
    }
    
    renderShipBlueprint(shipType, design) {
        const div = document.createElement('div');
        div.className = 'bg-gray-900 rounded p-2 border border-gray-700';
        
        // Ship header
        const header = document.createElement('div');
        header.className = 'flex items-center justify-between mb-1';
        
        const name = document.createElement('span');
        name.className = 'text-xs font-semibold text-white capitalize';
        const shipIcons = {
            interceptor: '🛸',
            cruiser: '🚀',
            dreadnought: '🛡️',
            starbase: '🏭'
        };
        name.textContent = `${shipIcons[shipType] || ''} ${shipType}`;
        
        header.appendChild(name);
        div.appendChild(header);
        
        // Ship stats
        const stats = document.createElement('div');
        stats.className = 'grid grid-cols-4 gap-1 text-xs';
        
        const statsList = [
            { key: 'initiative', label: 'Init', icon: '⚡' },
            { key: 'computer', label: 'Comp', icon: '🎯' },
            { key: 'shield', label: 'Shld', icon: '🛡' },
            { key: 'hull', label: 'Hull', icon: '❤️' },
            { key: 'cannons', label: 'Cann', icon: '💥' },
            { key: 'missiles', label: 'Miss', icon: '🚀' },
            { key: 'drives', label: 'Move', icon: '🔧' },
        ];
        
        statsList.forEach(stat => {
            const value = design[stat.key] || 0;
            if (value > 0 || stat.key === 'hull' || stat.key === 'initiative') {
                const statDiv = document.createElement('div');
                statDiv.className = 'flex items-center space-x-1';
                statDiv.innerHTML = `
                    <span class="opacity-60">${stat.icon}</span>
                    <span class="text-gray-300">${value}</span>
                `;
                stats.appendChild(statDiv);
            }
        });
        
        // Special features
        if (design.has_jump_drive) {
            const jump = document.createElement('div');
            jump.className = 'text-xs text-purple-400 mt-1';
            jump.innerHTML = '🌀 Jump Drive';
            stats.appendChild(jump);
        }
        
        if (design.interceptor_bays > 0) {
            const bays = document.createElement('div');
            bays.className = 'text-xs text-blue-400 mt-1';
            bays.innerHTML = `🛸 Bays: ${design.interceptor_bays}`;
            stats.appendChild(bays);
        }
        
        div.appendChild(stats);
        return div;
    }
    
    createEnhancedShipBlueprint(shipType, design) {
        const config = window.UIConstants.getShipConfig(shipType);
        
        const div = document.createElement('div');
        div.className = `ship-card bg-gradient-to-r ${config.gradient} rounded-lg p-3 border-2 border-white/10`;
        
        div.innerHTML = `
            <!-- Ship header -->
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                    <span class="text-2xl">${config.icon}</span>
                    <span class="text-sm font-bold text-white">${config.name}</span>
                </div>
            </div>
            
            <!-- Stats grid with icons -->
            <div class="grid grid-cols-4 gap-2 text-xs mb-2">
                ${this.renderShipStat('⚡', 'Init', design.initiative || 0, 'yellow')}
                ${this.renderShipStat('❤️', 'Hull', design.hull || 1, 'red')}
                ${this.renderShipStat('🎯', 'Comp', design.computer || 0, 'blue')}
                ${this.renderShipStat('🛡', 'Shield', design.shield || 0, 'green')}
                ${design.cannons > 0 ? this.renderShipStat('💥', 'Cannon', design.cannons, 'orange') : ''}
                ${design.missiles > 0 ? this.renderShipStat('🚀', 'Missile', design.missiles, 'purple') : ''}
                ${design.drives > 0 ? this.renderShipStat('🔧', 'Drive', design.drives, 'cyan') : ''}
            </div>
        `;
        
        // Add ship parts section
        const partsSection = this.renderShipParts(design);
        if (partsSection) {
            div.appendChild(partsSection);
        }
        
        // Special features
        if (design.has_jump_drive || design.interceptor_bays > 0) {
            const specialDiv = document.createElement('div');
            specialDiv.className = 'mt-2 pt-2 border-t border-white/20 flex flex-wrap gap-1';
            
            if (design.has_jump_drive) {
                const jumpBadge = document.createElement('span');
                jumpBadge.className = 'bg-purple-500/30 text-purple-200 px-2 py-1 rounded text-xs font-semibold';
                jumpBadge.innerHTML = '🌀 Jump Drive';
                specialDiv.appendChild(jumpBadge);
            }
            
            if (design.interceptor_bays > 0) {
                const baysBadge = document.createElement('span');
                baysBadge.className = 'bg-blue-500/30 text-blue-200 px-2 py-1 rounded text-xs font-semibold';
                baysBadge.innerHTML = `🛸 ${design.interceptor_bays} Bays`;
                specialDiv.appendChild(baysBadge);
            }
            
            div.appendChild(specialDiv);
        }
        
        return div;
    }
    
    renderShipStat(icon, label, value, color) {
        return `
            <div class="stat-badge bg-black/30 rounded px-2 py-1 flex flex-col items-center">
                <span class="text-lg mb-0.5">${icon}</span>
                <span class="text-white font-bold">${value}</span>
                <span class="text-${color}-300 text-[10px] opacity-70">${label}</span>
            </div>
        `;
    }
    
    renderShipParts(design) {
        // Collect all part categories that exist
        const partCategories = [
            { key: 'cannon_parts', label: 'Cannons', icon: '💥', color: 'orange' },
            { key: 'missile_parts', label: 'Missiles', icon: '🚀', color: 'purple' },
            { key: 'computer_parts', label: 'Computers', icon: '🎯', color: 'blue' },
            { key: 'shield_parts', label: 'Shields', icon: '🛡', color: 'green' },
            { key: 'drive_parts', label: 'Drives', icon: '🔧', color: 'cyan' },
            { key: 'energy_sources', label: 'Energy', icon: '⚡', color: 'yellow' },
            { key: 'hull_parts', label: 'Hull', icon: '❤️', color: 'red' }
        ];
        
        // Check if there are any parts to display
        const hasParts = partCategories.some(cat => {
            const parts = design[cat.key];
            return parts && Object.keys(parts).length > 0;
        });
        
        if (!hasParts) {
            return null;
        }
        
        const container = document.createElement('div');
        container.className = 'mt-2 pt-2 border-t border-white/20';
        
        const header = document.createElement('div');
        header.className = 'text-xs font-semibold text-gray-300 mb-1';
        header.textContent = '🔧 Installed Parts';
        container.appendChild(header);
        
        const partsList = document.createElement('div');
        partsList.className = 'space-y-1';
        
        partCategories.forEach(category => {
            const parts = design[category.key];
            if (parts && Object.keys(parts).length > 0) {
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'text-xs';
                
                const partsText = Object.entries(parts)
                    .map(([partName, count]) => {
                        return count > 1 ? `${partName} ×${count}` : partName;
                    })
                    .join(', ');
                
                categoryDiv.innerHTML = `
                    <span class="text-${category.color}-400">${category.icon}</span>
                    <span class="text-gray-300 ml-1">${partsText}</span>
                `;
                
                partsList.appendChild(categoryDiv);
            }
        });
        
        container.appendChild(partsList);
        return container;
    }
    
    renderTechnologies(player) {
        const container = document.createElement('div');
        container.className = 'space-y-2';
        
        // Get all techs (try multiple property names for compatibility)
        const techs = player.known_techs || player.owned_tech_ids || player.techs || [];
        
        if (techs.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'text-xs text-gray-500 italic';
            empty.textContent = 'No technologies researched';
            container.appendChild(empty);
            return container;
        }
        
        // Group techs by category
        const techsByCategory = this.groupTechsByCategory(techs);
        
        Object.entries(techsByCategory).forEach(([category, categoryTechs]) => {
            if (categoryTechs.length > 0) {
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'mb-1.5';
                
                const categoryLabel = document.createElement('div');
                categoryLabel.className = 'text-[10px] font-medium text-gray-500 mb-1 uppercase tracking-wide';
                categoryLabel.innerHTML = `<span class="opacity-60">${this.getCategoryIcon(category)}</span> ${category}`;
                categoryDiv.appendChild(categoryLabel);
                
                const techList = document.createElement('div');
                techList.className = 'space-y-0.5';
                
                categoryTechs.forEach(tech => {
                    const techItem = document.createElement('div');
                    techItem.className = 'text-xs text-gray-300 pl-4 py-0.5 hover:text-gray-100 transition-colors cursor-default';
                    
                    const bullet = document.createElement('span');
                    bullet.className = 'text-gray-600 mr-1.5';
                    bullet.textContent = '•';
                    
                    const techName = document.createElement('span');
                    techName.textContent = this.getTechDisplayName(tech);
                    
                    techItem.appendChild(bullet);
                    techItem.appendChild(techName);
                    techList.appendChild(techItem);
                });
                
                categoryDiv.appendChild(techList);
                container.appendChild(categoryDiv);
            }
        });
        
        return container;
    }
    
    groupTechsByCategory(techs) {
        const categories = {
            'Military': [],
            'Grid': [],
            'Nano': [],
            'Rare': [],
            'Other': []
        };
        
        techs.forEach(tech => {
            const techName = typeof tech === 'string' ? tech : tech.name || tech.id || '';
            const category = window.UIConstants.detectTechCategory(techName);
            categories[category].push(tech);
        });
        
        return categories;
    }
    
    getCategoryIcon(category) {
        const style = window.UIConstants.getCategoryStyle(category);
        return style.icon;
    }
    
    getTechDisplayName(tech) {
        if (typeof tech === 'string') return tech;
        return tech.name || tech.id || 'Unknown Tech';
    }
    
    getPlayerName(playerId, player) {
        // Try to get species name
        if (player.species_id) {
            const species = player.species_id.replace(/_/g, ' ');
            return species.charAt(0).toUpperCase() + species.slice(1);
        }
        return playerId.charAt(0).toUpperCase() + playerId.slice(1);
    }
}

// Initialize player panel
window.addEventListener('DOMContentLoaded', () => {
    window.playerPanel = new PlayerPanel();
    console.log('PlayerPanel created and attached to window');
});

