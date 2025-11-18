/**
 * Clean Canvas 2D Board Renderer - Built from scratch
 * Renders Eclipse game board with hexes, ships, planets, tech
 */

class BoardRenderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error(`Canvas element '${canvasId}' not found`);
            return;
        }
        
        this.ctx = this.canvas.getContext('2d');
        this.state = null;
        
        // View controls
        this.zoom = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        this.isDragging = false;
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        
        // Interaction state
        this.hoveredHex = null;
        this.selectedHex = null;
        this.mouseX = 0;
        this.mouseY = 0;
        
        // Hex geometry
        this.hexSize = 60; // base size
        
        // Colors - Eclipse official aesthetic
        this.colors = {
            background: '#0a0a0f',  // Deep space black
            space: '#0a0a0f',
            hexBorder: '#5a4a3a',  // Dark brown border
            hexFill: '#8b7355',  // Tan/brown tile background
            hexHighlight: '#9d8262',  // Lighter tan for hover
            hexSelected: '#b89a78',  // Selected highlight
            text: '#f3f4f6',
            textDim: '#9ca3af',
            textVeryDim: '#64748b',
            // Eclipse official planet colors
            planetBrown: '#a67c52',  // Materials (brown)
            planetPink: '#d896a8',   // Science (pink)
            planetOrange: '#e8a05c', // Money (orange)
            planetWhite: '#c8c8c8',  // Wild/any (white)
            planetAdvanced: '#a78bfa', // Advanced (purple)
            // Player colors
            player1: '#ef4444',
            player2: '#3b82f6',
            player3: '#10b981',
            player4: '#f59e0b',
            player5: '#8b5cf6',
            player6: '#ec4899',
            // Other elements
            ship: '#60a5fa',
            planet: '#a67c52',  // Default to brown
            wormhole: '#e0e0e0',  // Light gray for wormhole rings
            warpPortal: '#a855f7',
            anomaly: '#f97316',
        };
        
        // Cached star field for background
        this.stars = null;
        
        this.setupCanvas();
        this.setupEventListeners();
    }
    
    setupCanvas() {
        // Make canvas fill container
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
    }
    
    resizeCanvas() {
        const container = this.canvas.parentElement;
        this.canvas.width = container.clientWidth;
        this.canvas.height = container.clientHeight;
        this.render();
    }
    
    setupEventListeners() {
        // Mouse wheel zoom
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            this.zoom = Math.max(0.3, Math.min(3, this.zoom * delta));
            this.render();
        });
        
        // Pan with mouse drag and hover detection
        this.canvas.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.lastMouseX = e.clientX;
            this.lastMouseY = e.clientY;
        });
        
        this.canvas.addEventListener('mousemove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            this.mouseX = e.clientX - rect.left;
            this.mouseY = e.clientY - rect.top;
            
            if (this.isDragging) {
                const dx = e.clientX - this.lastMouseX;
                const dy = e.clientY - this.lastMouseY;
                this.offsetX += dx;
                this.offsetY += dy;
                this.lastMouseX = e.clientX;
                this.lastMouseY = e.clientY;
                this.render();
            } else {
                // Update hovered hex
                const oldHovered = this.hoveredHex;
                this.hoveredHex = this.pixelToHexId(this.mouseX, this.mouseY);
                
                if (oldHovered !== this.hoveredHex) {
                    this.render();
                }
            }
        });
        
        this.canvas.addEventListener('mouseup', () => {
            this.isDragging = false;
        });
        
        this.canvas.addEventListener('mouseleave', () => {
            this.isDragging = false;
            if (this.hoveredHex) {
                this.hoveredHex = null;
                this.render();
            }
        });
        
        // Click to select hex
        this.canvas.addEventListener('click', (e) => {
            if (!this.isDragging) {
                const rect = this.canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const hexId = this.pixelToHexId(x, y);
                
                if (hexId) {
                    this.selectedHex = this.selectedHex === hexId ? null : hexId;
                    this.render();
                    
                    // Emit event for other components
                    const event = new CustomEvent('hexSelected', {
                        detail: {
                            hexId: this.selectedHex,
                            hexData: this.selectedHex ? this.state?.map?.hexes?.[this.selectedHex] : null
                        }
                    });
                    window.dispatchEvent(event);
                }
            }
        });
    }
    
    // Convert hex axial coordinates to pixel position
    // Eclipse uses POINTY-TOP hexes (pointy vertices at top/bottom)
    // This matches the vertex-angle placement of starting sectors
    hexToPixel(q, r) {
        const size = this.hexSize * this.zoom;
        // Pointy-top hex layout formulas
        const x = size * (3/2 * q);
        const y = size * (Math.sqrt(3)/2 * q + Math.sqrt(3) * r);
        
        // No special offset needed - GC at (0,0) is naturally centered
        const gcOffset = 0;
        
        return {
            x: x + this.canvas.width / 2 + this.offsetX,
            y: y + this.canvas.height / 2 + this.offsetY + gcOffset
        };
    }
    
    // Convert pixel position to hex ID (for hover/click detection)
    pixelToHexId(px, py) {
        if (!this.state?.map?.hexes) return null;
        
        const size = this.hexSize * this.zoom;
        const minDistance = size * 0.9; // Within 90% of hex size
        let closestHex = null;
        let closestDist = minDistance;
        
        // Check all hexes
        for (const [hexId, hexData] of Object.entries(this.state.map.hexes)) {
            // Try to use backend coordinates first
            let coords;
            if (hexData.axial_q !== undefined && hexData.axial_r !== undefined) {
                coords = { q: hexData.axial_q, r: hexData.axial_r };
            } else {
                // Fall back to hardcoded mapping
                coords = this.parseHexId(hexId);
            }
            if (!coords) continue;
            
            const pos = this.hexToPixel(coords.q, coords.r);
            const dx = px - pos.x;
            const dy = py - pos.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            
            if (dist < closestDist) {
                closestDist = dist;
                closestHex = hexId;
            }
        }
        
        return closestHex;
    }
    
    // Draw a hexagon with gradient for tile appearance
    drawHex(x, y, size, fillColor, strokeColor, lineWidth = 2, rotation = 0) {
        this.ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            // Flat-top hex: vertices at 30°, 90°, 150°, 210°, 270°, 330°
            // This creates flat sides at top and bottom (faces touch)
            // rotation parameter allows visual rotation of the hex shape
            const angle = Math.PI / 6 + Math.PI / 3 * i + rotation;
            const px = x + size * Math.cos(angle);
            const py = y + size * Math.sin(angle);
            if (i === 0) {
                this.ctx.moveTo(px, py);
            } else {
                this.ctx.lineTo(px, py);
            }
        }
        this.ctx.closePath();
        
        if (fillColor) {
            // Create radial gradient for tile appearance (lighter center, darker edges)
            const gradient = this.ctx.createRadialGradient(x, y, 0, x, y, size * 0.9);
            
            // Check if this is a controlled hex (has fill color other than default)
            const isControlled = fillColor.includes('rgba') || 
                                 (fillColor !== this.colors.hexFill && fillColor !== this.colors.background);
            
            if (isControlled) {
                // For controlled hexes, use the provided color with gradient
                gradient.addColorStop(0, this.lightenColor(fillColor, 1.1));
                gradient.addColorStop(1, fillColor);
            } else {
                // For tile hexes, create Eclipse tile appearance
                gradient.addColorStop(0, this.lightenColor(this.colors.hexFill, 1.15));
                gradient.addColorStop(0.7, this.colors.hexFill);
                gradient.addColorStop(1, this.darkenColor(this.colors.hexFill, 0.85));
            }
            
            this.ctx.fillStyle = gradient;
            this.ctx.fill();
        }
        
        if (strokeColor) {
            this.ctx.strokeStyle = strokeColor;
            this.ctx.lineWidth = lineWidth;
            this.ctx.stroke();
        }
    }
    
    // Draw text centered at position
    drawText(text, x, y, color = this.colors.text, fontSize = 12) {
        this.ctx.fillStyle = color;
        this.ctx.font = `${fontSize}px sans-serif`;
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(text, x, y);
    }
    
    // Draw a circle (for planets, ships)
    drawCircle(x, y, radius, fillColor, strokeColor = null, lineWidth = 1) {
        this.ctx.beginPath();
        this.ctx.arc(x, y, radius, 0, Math.PI * 2);
        this.ctx.closePath();
        
        if (fillColor) {
            this.ctx.fillStyle = fillColor;
            this.ctx.fill();
        }
        
        if (strokeColor) {
            this.ctx.strokeStyle = strokeColor;
            this.ctx.lineWidth = lineWidth;
            this.ctx.stroke();
        }
    }
    
    // Parse hex ID (e.g., "101", "201", "GC") to axial coordinates
    parseHexId(hexId) {
        if (!hexId) return null;
        
        // Look up in canonical Eclipse hex coordinate mapping
        const coords = this.getEclipseHexCoords();
        if (coords[hexId]) {
            return coords[hexId];
        }
        
        // Handle center hex aliases
        if (hexId === 'h0' || hexId.toLowerCase() === 'galactic center') {
            return { q: 0, r: 0, ring: 0 };
        }
        
        // Try parsing numeric format like "201" (ring 2, position 01)
        const match = hexId.match(/^(\d)(\d{2})$/);
        if (match) {
            const ring = parseInt(match[1]);
            const pos = parseInt(match[2]);
            return this.ringPosToAxial(ring, pos);
        }
        
        // Fallback - log warning for unmapped hexes
        console.warn(`Could not parse hex ID: ${hexId}`);
        return null;
    }
    
    // Eclipse Hex Coordinate System
    // Canonical mapping of all Eclipse hex IDs to axial (q, r) coordinates
    // Based on official Eclipse tile layout from eclipse_tiles.csv and game rules
    // NOTE: This is now used as a FALLBACK. The backend provides axial_q and axial_r
    // fields directly in hex data. This mapping is kept for legacy support and when
    // backend coordinates are unavailable.
    getEclipseHexCoords() {
        if (this._hexCoords) return this._hexCoords;
        
        this._hexCoords = {
            // Galactic Center
            'GC': { q: 0, r: 0, ring: 0 },
            'center': { q: 0, r: 0, ring: 0 },
            
            // Ring 1 (Inner) - 8 hexes, IDs 101-108
            // Clockwise from top-right
            '101': { q: 1, r: -1, ring: 1 },
            '102': { q: 1, r: 0, ring: 1 },
            '103': { q: 0, r: 1, ring: 1 },
            '104': { q: -1, r: 1, ring: 1 },
            '105': { q: -1, r: 0, ring: 1 },
            '106': { q: -1, r: -1, ring: 1 },
            '107': { q: 0, r: -1, ring: 1 },
            '108': { q: 1, r: -1, ring: 1 },  // Duplicate position for 8-hex ring
            
            // Ring 2 (Middle) - 11 hexes, IDs 201-211
            // Positioned for "two hexes from center" as per rules
            '201': { q: 2, r: -2, ring: 2 },   // Terrans (default starting position)
            '202': { q: 2, r: -1, ring: 2 },
            '203': { q: 2, r: 0, ring: 2 },
            '204': { q: 2, r: 1, ring: 2 },
            '205': { q: 1, r: 2, ring: 2 },
            '206': { q: 0, r: 2, ring: 2 },
            '207': { q: -1, r: 2, ring: 2 },
            '208': { q: -2, r: 2, ring: 2 },
            '209': { q: -2, r: 1, ring: 2 },
            '210': { q: -2, r: 0, ring: 2 },
            '211': { q: -2, r: -1, ring: 2 },
            
            // Additional middle ring hexes for species starting sectors
            '212': { q: -2, r: -2, ring: 2 },
            '213': { q: -1, r: -2, ring: 2 },
            '214': { q: 0, r: -2, ring: 2 },
            
            // Species-specific starting sectors (Ring 2, IDs 220-239)
            // Mapped to six canonical positions: E(2,0), NE(0,2), NW(-2,2), W(-2,0), SW(0,-2), SE(2,-2)
            '220': { q: 2, r: 0, ring: 2 },    // Generic - E
            '221': { q: 0, r: 2, ring: 2 },    // Generic - NE
            '222': { q: -2, r: 2, ring: 2 },   // Eridani Empire - NW
            '223': { q: -2, r: 0, ring: 2 },   // Generic - W
            '224': { q: 0, r: -2, ring: 2 },   // Hydran Progress - SW
            '225': { q: 2, r: -2, ring: 2 },   // Generic - SE
            '226': { q: 0, r: 2, ring: 2 },    // Planta - NE
            '227': { q: -2, r: 2, ring: 2 },   // Generic - NW
            '228': { q: -2, r: 0, ring: 2 },   // Descendants of Draco - W
            '229': { q: 0, r: -2, ring: 2 },   // Generic - SW
            '230': { q: 2, r: -2, ring: 2 },   // Mechanema - SE
            '231': { q: 2, r: 0, ring: 2 },    // Generic - E
            '232': { q: 0, r: 2, ring: 2 },    // Orion Hegemony - NE
            '234': { q: 2, r: 0, ring: 2 },    // Magellan - E
            '236': { q: 0, r: 2, ring: 2 },    // Generic - NE
            '237': { q: -2, r: 2, ring: 2 },   // Rho Indi - NW
            '238': { q: -2, r: 0, ring: 2 },   // Enlightened - W
            '239': { q: 0, r: -2, ring: 2 },   // The Exiles - SW
            
            // Ring 3 (Outer) - 18 hexes, IDs 301-318
            // Full outer ring
            '301': { q: 3, r: -3, ring: 3 },
            '302': { q: 3, r: -2, ring: 3 },
            '303': { q: 3, r: -1, ring: 3 },
            '304': { q: 3, r: 0, ring: 3 },
            '305': { q: 3, r: 1, ring: 3 },
            '306': { q: 2, r: 2, ring: 3 },
            '307': { q: 1, r: 3, ring: 3 },
            '308': { q: 0, r: 3, ring: 3 },
            '309': { q: -1, r: 3, ring: 3 },
            '310': { q: -2, r: 3, ring: 3 },
            '311': { q: -3, r: 3, ring: 3 },
            '312': { q: -3, r: 2, ring: 3 },
            '313': { q: -3, r: 1, ring: 3 },
            '314': { q: -3, r: 0, ring: 3 },
            '315': { q: -3, r: -1, ring: 3 },
            '316': { q: -3, r: -2, ring: 3 },
            '317': { q: -2, r: -3, ring: 3 },
            '318': { q: -1, r: -3, ring: 3 },
            
            // Additional outer ring hexes
            '319': { q: 0, r: -3, ring: 3 },
            '320': { q: 1, r: -3, ring: 3 },
            '321': { q: 2, r: -3, ring: 3 },
            '322': { q: 2, r: -2, ring: 3 },
            '323': { q: 2, r: 3, ring: 3 },
            '324': { q: 3, r: 2, ring: 3 },
        };
        
        return this._hexCoords;
    }
    
    // Convert ring/position to axial coordinates using canonical mapping
    ringPosToAxial(ring, pos) {
        if (ring === 0) return { q: 0, r: 0, ring: 0 };
        
        // Build hex ID from ring and position
        const hexId = `${ring}${String(pos).padStart(2, '0')}`;
        
        // Look up in canonical mapping
        const coords = this.getEclipseHexCoords();
        if (coords[hexId]) {
            return coords[hexId];
        }
        
        // Fallback for unmapped hexes (shouldn't happen in proper games)
        console.warn(`Hex ID ${hexId} not in canonical mapping, using fallback`);
        return { q: 0, r: 0, ring: 0 };
    }
    
    // Main render function
    render() {
        if (!this.ctx) return;
        
        // Clear canvas with space background
        this.ctx.fillStyle = this.colors.space;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Render starfield background
        this.renderStarfield();
        
        if (!this.state) {
            this.drawEmptyState();
            return;
        }
        
        // Render hexes from state
        this.renderHexes();
        
        // Render connections (wormholes)
        this.renderConnections();
        
        // Render UI elements
        this.renderUI();
        
        // Render tooltip if hovering over a hex
        if (this.hoveredHex && !this.isDragging) {
            this.renderTooltip();
        }
    }
    
    // Generate and cache starfield
    generateStarfield() {
        const count = 200;
        this.stars = [];
        
        for (let i = 0; i < count; i++) {
            this.stars.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                radius: Math.random() * 1.5 + 0.5,
                opacity: Math.random() * 0.5 + 0.3,
                color: Math.random() > 0.9 ? '#ffffcc' : '#ffffff'
            });
        }
    }
    
    // Render starfield background
    renderStarfield() {
        if (!this.stars || this.stars.length === 0) {
            this.generateStarfield();
        }
        
        this.ctx.save();
        
        this.stars.forEach(star => {
            // Apply pan offset for parallax effect (stars move slower than hex grid)
            const parallaxFactor = 0.2;
            const x = star.x + this.offsetX * parallaxFactor;
            const y = star.y + this.offsetY * parallaxFactor;
            
            // Wrap stars around screen edges
            const wrappedX = ((x % this.canvas.width) + this.canvas.width) % this.canvas.width;
            const wrappedY = ((y % this.canvas.height) + this.canvas.height) % this.canvas.height;
            
            this.ctx.fillStyle = star.color;
            this.ctx.globalAlpha = star.opacity;
            this.ctx.beginPath();
            this.ctx.arc(wrappedX, wrappedY, star.radius, 0, Math.PI * 2);
            this.ctx.fill();
        });
        
        this.ctx.globalAlpha = 1;
        this.ctx.restore();
    }
    
    drawEmptyState() {
        this.drawText(
            'No game loaded',
            this.canvas.width / 2,
            this.canvas.height / 2,
            this.colors.textDim,
            16
        );
    }
    
    renderHexes() {
        if (!this.state.map || !this.state.map.hexes) {
            console.warn('No hexes in state');
            return;
        }
        
        const size = this.hexSize * this.zoom;
        const hexCount = Object.keys(this.state.map.hexes).length;
        console.log(`Rendering ${hexCount} hexes:`, Object.keys(this.state.map.hexes));
        
        // Render each hex
        for (const [hexId, hexData] of Object.entries(this.state.map.hexes)) {
            // Try to use backend coordinates first (from new coordinate system)
            let coords;
            if (hexData.axial_q !== undefined && hexData.axial_r !== undefined) {
                coords = { q: hexData.axial_q, r: hexData.axial_r, ring: hexData.ring || 0 };
                // Only log on first render or when debugging
                // console.log(`✓ Hex ${hexId}: backend coords (${coords.q}, ${coords.r}) ring=${coords.ring}`);
            } else {
                // Fall back to hardcoded mapping for legacy states
                coords = this.parseHexId(hexId);
                console.warn(`⚠ Hex ${hexId}: using FALLBACK coords (${coords?.q}, ${coords?.r})`);
            }
            if (!coords) {
                console.warn(`Hex ${hexId}: NO COORDINATES - skipping`);
                continue;
            }
            
            const pos = this.hexToPixel(coords.q, coords.r);
            const isHovered = hexId === this.hoveredHex;
            const isSelected = hexId === this.selectedHex;
            
            // Determine hex color based on control and state
            let fillColor = this.colors.hexFill;
            let strokeColor = this.colors.hexBorder;
            let lineWidth = 2;
            
            if (hexData.controlled_by !== undefined && hexData.controlled_by !== null) {
                const playerColor = this.getPlayerColor(hexData.controlled_by);
                fillColor = this.hexAlpha(playerColor, 0.3);
                strokeColor = playerColor;
            }
            
            // Highlight selected hex
            if (isSelected) {
                strokeColor = this.colors.hexSelected;
                lineWidth = 4;
                fillColor = this.hexAlpha(this.colors.hexSelected, 0.2);
            }
            // Highlight hovered hex (if not selected)
            else if (isHovered) {
                // Brighten the fill color
                fillColor = this.lightenColor(fillColor, 1.2);
                lineWidth = 3;
            }
            
            // Rotate 30° for pointy-top hex orientation
            // This matches the pointy-top hexToPixel() formula
            let hexRotation = Math.PI / 6;  // 30° for pointy-top
            
            // Draw hex
            this.drawHex(pos.x, pos.y, size, fillColor, strokeColor, lineWidth, hexRotation);
            
            // Draw wormhole edge symbols (with same rotation as hex)
            if (hexData.wormholes && hexData.wormholes.length > 0) {
                this.drawWormholeEdges(pos.x, pos.y, size, hexData.wormholes, hexRotation);
            }
            
            // Draw hex ID label in upper-right corner (Eclipse style)
            const labelX = pos.x + size * 0.6;
            const labelY = pos.y - size * 0.6;
            this.drawText(hexId, labelX, labelY, this.colors.textVeryDim, 9 * this.zoom);
            
            // Draw hex contents
            this.renderHexContents(pos.x, pos.y, size, hexData, hexId);
        }
    }
    
    renderHexContents(x, y, hexSize, hexData, hexId) {
        let offsetY = -hexSize * 0.4;
        
        // Draw warp portal indicator at top if present
        if (hexData.is_warp_portal || hexData.warp_portal) {
            this.drawWarpPortal(x, y + offsetY, hexSize * 0.15);
            offsetY += 15 * this.zoom;
        }
        
        // Draw anomaly indicator if present
        if (hexData.anomaly) {
            this.drawAnomaly(x, y + offsetY, hexSize * 0.15);
            offsetY += 15 * this.zoom;
        }
        
        // Draw tile type
        if (hexData.tile_type && hexData.tile_type !== 'empty') {
            this.drawText(
                hexData.tile_type,
                x,
                y + offsetY,
                this.colors.textDim,
                8 * this.zoom
            );
            offsetY += 12 * this.zoom;
        }
        
        // Draw discovery tile info
        if (hexData.discovery) {
            this.drawDiscoveryTile(x, y + offsetY, hexData.discovery);
            offsetY += 15 * this.zoom;
        }
        
        // Draw planets with production details
        if (hexData.planets && hexData.planets.length > 0) {
            this.drawPlanets(x, y + offsetY, hexData.planets);
            offsetY += 30 * this.zoom;
        }
        
        // Draw influence discs/blocks
        if (hexData.influence_discs || hexData.population_cubes) {
            this.drawInfluenceDiscs(x, y + offsetY, hexData);
            offsetY += 20 * this.zoom;
        }
        
        // Draw ships
        if (hexData.ships) {
            const ships = this.countShips(hexData.ships);
            this.drawShips(x, y + offsetY, ships, hexData.controlled_by);
            offsetY += 20 * this.zoom;
        }
        
        // Draw technologies if present
        if (hexData.technologies || hexData.tech) {
            this.drawTechnologies(x, y + offsetY, hexData.technologies || hexData.tech);
            offsetY += 15 * this.zoom;
        }
        
        // Draw ancients/guardians (check feature flags)
        if (hexData.ancients || hexData.guardians) {
            this.drawAncients(x, y + offsetY, hexData.ancients || hexData.guardians);
        }
    }
    
    drawDiscoveryTile(x, y, discovery) {
        const size = 8 * this.zoom;
        
        // Draw discovery badge
        this.ctx.fillStyle = '#fbbf24';
        this.ctx.beginPath();
        this.ctx.arc(x, y, size, 0, Math.PI * 2);
        this.ctx.fill();
        
        // Draw discovery type
        let icon = '?';
        if (discovery.type === 'VP') icon = '★';
        else if (discovery.type === 'money') icon = '$';
        else if (discovery.type === 'science') icon = 'S';
        else if (discovery.type === 'materials') icon = 'M';
        
        this.drawText(icon, x, y, this.colors.background, 10 * this.zoom);
    }
    
    drawPlanets(x, y, planets) {
        const spacing = 18 * this.zoom;
        const startX = x - (planets.length - 1) * spacing / 2;
        
        planets.forEach((planet, i) => {
            const planetX = startX + i * spacing;
            
            // Determine planet color by Eclipse type
            let planetColor = this.colors.planetBrown;
            let prodIcon = null;
            let prodValue = 0;
            
            // Map planet types to Eclipse official colors
            if (planet.type === 'orange' || planet.type === 'money' || planet.production?.money) {
                planetColor = this.colors.planetOrange;
                prodIcon = '$';
                prodValue = planet.production?.money || 1;
            } else if (planet.type === 'pink' || planet.type === 'science' || planet.production?.science) {
                planetColor = this.colors.planetPink;
                prodIcon = 'S';
                prodValue = planet.production?.science || 1;
            } else if (planet.type === 'brown' || planet.type === 'materials' || planet.production?.materials) {
                planetColor = this.colors.planetBrown;
                prodIcon = 'M';
                prodValue = planet.production?.materials || 1;
            } else if (planet.type === 'white' || planet.type === 'wild') {
                planetColor = this.colors.planetWhite;
                prodIcon = '◇';
            } else if (planet.type === 'advanced' || planet.advanced) {
                planetColor = this.colors.planetAdvanced;
                prodIcon = '★';
            }
            
            // Draw planet with 3D gradient effect
            const planetRadius = 12 * this.zoom;
            this.drawPlanetWithGradient(planetX, y, planetRadius, planetColor);
            
            // Draw population cube if colonized
            if (planet.colonized || planet.population || planet.colonized_by) {
                this.drawPopulationCube(planetX, y, planetRadius, planet.colonized_by || planet.owner);
            }
            
            // Draw production icon below planet (removed for cleaner look matching reference)
            // Icons removed to match Eclipse tile aesthetic
        });
    }
    
    // Draw planet with radial gradient for 3D sphere effect
    drawPlanetWithGradient(x, y, radius, baseColor) {
        this.ctx.save();
        
        // Create radial gradient for 3D effect
        const gradient = this.ctx.createRadialGradient(
            x - radius * 0.3, 
            y - radius * 0.3, 
            radius * 0.2,
            x, 
            y, 
            radius
        );
        
        // Lighter highlight
        const highlightColor = this.lightenColor(baseColor, 1.3);
        gradient.addColorStop(0, highlightColor);
        gradient.addColorStop(0.5, baseColor);
        // Darker shadow
        const shadowColor = this.darkenColor(baseColor, 0.6);
        gradient.addColorStop(1, shadowColor);
        
        // Draw planet sphere
        this.ctx.fillStyle = gradient;
        this.ctx.beginPath();
        this.ctx.arc(x, y, radius, 0, Math.PI * 2);
        this.ctx.fill();
        
        // Add subtle border
        this.ctx.strokeStyle = this.darkenColor(baseColor, 0.5);
        this.ctx.lineWidth = 1;
        this.ctx.stroke();
        
        this.ctx.restore();
    }
    
    // Draw population cube on colonized planet
    drawPopulationCube(planetX, planetY, planetRadius, playerId) {
        const cubeSize = 6 * this.zoom;
        // Position cube on planet edge (top-right)
        const cubeX = planetX + planetRadius * 0.5;
        const cubeY = planetY - planetRadius * 0.5;
        
        // Get player color
        const playerColor = this.getPlayerColor(playerId);
        
        this.ctx.save();
        
        // Draw cube
        this.ctx.fillStyle = playerColor;
        this.ctx.fillRect(cubeX - cubeSize / 2, cubeY - cubeSize / 2, cubeSize, cubeSize);
        
        // Add border
        this.ctx.strokeStyle = this.darkenColor(playerColor, 0.7);
        this.ctx.lineWidth = 1;
        this.ctx.strokeRect(cubeX - cubeSize / 2, cubeY - cubeSize / 2, cubeSize, cubeSize);
        
        this.ctx.restore();
    }
    
    // Helper to lighten color
    lightenColor(color, factor) {
        if (!color) return '#ffffff';
        
        // Handle rgb/rgba format
        if (color.startsWith('rgb')) {
            const match = color.match(/(\d+\.?\d*)/g);
            if (match && match.length >= 3) {
                const r = Math.min(255, Math.floor(parseFloat(match[0]) * factor));
                const g = Math.min(255, Math.floor(parseFloat(match[1]) * factor));
                const b = Math.min(255, Math.floor(parseFloat(match[2]) * factor));
                return `rgb(${r}, ${g}, ${b})`;
            }
        }
        
        // Handle hex format
        const hex = color.replace('#', '');
        if (hex.length === 6) {
            const r = Math.min(255, Math.floor(parseInt(hex.substr(0, 2), 16) * factor));
            const g = Math.min(255, Math.floor(parseInt(hex.substr(2, 2), 16) * factor));
            const b = Math.min(255, Math.floor(parseInt(hex.substr(4, 2), 16) * factor));
            return `rgb(${r}, ${g}, ${b})`;
        }
        
        return color; // Fallback
    }
    
    // Helper to darken color
    darkenColor(color, factor) {
        if (!color) return '#000000';
        
        // Handle rgb/rgba format
        if (color.startsWith('rgb')) {
            const match = color.match(/(\d+\.?\d*)/g);
            if (match && match.length >= 3) {
                const r = Math.floor(parseFloat(match[0]) * factor);
                const g = Math.floor(parseFloat(match[1]) * factor);
                const b = Math.floor(parseFloat(match[2]) * factor);
                return `rgb(${r}, ${g}, ${b})`;
            }
        }
        
        // Handle hex format
        const hex = color.replace('#', '');
        if (hex.length === 6) {
            const r = Math.floor(parseInt(hex.substr(0, 2), 16) * factor);
            const g = Math.floor(parseInt(hex.substr(2, 2), 16) * factor);
            const b = Math.floor(parseInt(hex.substr(4, 2), 16) * factor);
            return `rgb(${r}, ${g}, ${b})`;
        }
        
        return color; // Fallback
    }
    
    // Draw wormhole symbols at hex edges
    drawWormholeEdges(x, y, size, wormholes, rotation = 0) {
        this.ctx.save();
        
        // Wormholes are edge indices 0-5 (clockwise from East)
        wormholes.forEach(edgeIndex => {
            // Calculate position at hex edge midpoint (flat-top orientation)
            // Edge indices: 0=E, 1=NE, 2=NW, 3=W, 4=SW, 5=SE
            // Apply rotation to match rotated hex shape
            const angle = Math.PI / 3 * edgeIndex + rotation;  // Edge midpoints at 0°, 60°, 120°, 180°, 240°, 300°
            const edgeX = x + size * 0.85 * Math.cos(angle);
            const edgeY = y + size * 0.85 * Math.sin(angle);
            
            // Draw wormhole symbol (concentric circles)
            const radius1 = 4 * this.zoom;
            const radius2 = 6 * this.zoom;
            
            this.ctx.strokeStyle = this.colors.wormhole;
            this.ctx.lineWidth = 1.5 * this.zoom;
            
            // Outer ring
            this.ctx.beginPath();
            this.ctx.arc(edgeX, edgeY, radius2, 0, Math.PI * 2);
            this.ctx.stroke();
            
            // Inner ring
            this.ctx.beginPath();
            this.ctx.arc(edgeX, edgeY, radius1, 0, Math.PI * 2);
            this.ctx.stroke();
        });
        
        this.ctx.restore();
    }
    
    drawWarpPortal(x, y, radius) {
        // Draw warp portal indicator (purple swirl)
        this.ctx.save();
        this.ctx.translate(x, y);
        
        // Draw portal ring
        this.ctx.strokeStyle = this.colors.warpPortal;
        this.ctx.lineWidth = 2 * this.zoom;
        this.ctx.beginPath();
        this.ctx.arc(0, 0, radius * this.zoom, 0, Math.PI * 2);
        this.ctx.stroke();
        
        // Draw portal symbol
        this.drawText('⚯', x, y, this.colors.warpPortal, 12 * this.zoom);
        
        this.ctx.restore();
    }
    
    drawAnomaly(x, y, radius) {
        // Draw anomaly indicator (orange warning)
        this.ctx.save();
        this.ctx.translate(x, y);
        
        // Draw pulsing danger symbol
        this.ctx.fillStyle = this.colors.anomaly;
        this.ctx.beginPath();
        this.ctx.arc(0, 0, radius * this.zoom, 0, Math.PI * 2);
        this.ctx.fill();
        
        // Draw warning symbol
        this.drawText('⚠', x, y, '#fff', 10 * this.zoom);
        
        this.ctx.restore();
    }
    
    drawInfluenceDiscs(x, y, hexData) {
        const discRadius = 6 * this.zoom;
        let numDiscs = 0;
        
        if (hexData.influence_discs) {
            numDiscs = hexData.influence_discs;
        } else if (hexData.population_cubes) {
            numDiscs = hexData.population_cubes;
        }
        
        if (numDiscs > 0) {
            const playerColor = this.getPlayerColor(hexData.controlled_by);
            
            // Draw influence disc(s)
            for (let i = 0; i < Math.min(numDiscs, 3); i++) {
                const discX = x + (i - 1) * 8 * this.zoom;
                this.drawCircle(discX, y, discRadius, playerColor, this.colors.hexBorder, 1.5);
            }
            
            // Draw count if more than 3
            if (numDiscs > 3) {
                this.drawText(`+${numDiscs - 3}`, x + 15 * this.zoom, y, this.colors.text, 8 * this.zoom);
            }
        }
    }
    
    drawShips(x, y, shipCounts, playerId) {
        const iconSize = 8 * this.zoom;
        const spacing = 18 * this.zoom;
        const shipTypes = ['interceptor', 'cruiser', 'dreadnought', 'starbase'];
        
        // Filter to only ships with count > 0
        const activeShips = shipTypes.filter(type => shipCounts[type] > 0);
        if (activeShips.length === 0) return;
        
        const startX = x - (activeShips.length - 1) * spacing / 2;
        
        activeShips.forEach((shipType, i) => {
            const count = shipCounts[shipType];
            const shipX = startX + i * spacing;
            
            // Use player color if available
            const shipColor = playerId !== undefined ? this.getPlayerColor(playerId) : this.colors.ship;
            
            this.drawShipIcon(shipX, y, shipType, count, shipColor);
        });
    }
    
    drawTechnologies(x, y, technologies) {
        if (!technologies || technologies.length === 0) return;
        
        const techSize = 6 * this.zoom;
        const spacing = 8 * this.zoom;
        const maxDisplay = 5;
        
        // Display up to maxDisplay tech icons
        const displayTechs = technologies.slice(0, maxDisplay);
        const startX = x - (displayTechs.length - 1) * spacing / 2;
        
        displayTechs.forEach((tech, i) => {
            const techX = startX + i * spacing;
            
            // Determine tech color by category
            let techColor = this.colors.hexHighlight;
            if (tech.category === 'military' || tech.type === 'military') {
                techColor = '#ef4444'; // Red
            } else if (tech.category === 'grid' || tech.type === 'grid') {
                techColor = '#fbbf24'; // Gold
            } else if (tech.category === 'nano' || tech.type === 'nano') {
                techColor = '#10b981'; // Green
            }
            
            // Draw tech square
            this.ctx.fillStyle = techColor;
            this.ctx.fillRect(
                techX - techSize / 2,
                y - techSize / 2,
                techSize,
                techSize
            );
            
            // Draw border
            this.ctx.strokeStyle = this.colors.text;
            this.ctx.lineWidth = 1;
            this.ctx.strokeRect(
                techX - techSize / 2,
                y - techSize / 2,
                techSize,
                techSize
            );
        });
        
        // Show count if more than maxDisplay
        if (technologies.length > maxDisplay) {
            this.drawText(
                `+${technologies.length - maxDisplay}`,
                x + (maxDisplay / 2) * spacing,
                y,
                this.colors.textDim,
                7 * this.zoom
            );
        }
    }
    
    drawAncients(x, y, ancients) {
        if (!ancients) return;
        
        const count = typeof ancients === 'number' ? ancients : ancients.count || 1;
        
        // Draw ancient icon (skull or danger symbol)
        this.ctx.fillStyle = '#dc2626'; // Red
        this.ctx.font = `${12 * this.zoom}px sans-serif`;
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText('☠', x, y);
        
        if (count > 1) {
            this.drawText(`×${count}`, x + 10 * this.zoom, y, this.colors.text, 8 * this.zoom);
        }
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
    
    drawShipIcon(x, y, shipType, count, color = null) {
        const iconSize = 8 * this.zoom;
        
        // Draw ship shape based on type
        this.ctx.fillStyle = color || this.colors.ship;
        this.ctx.beginPath();
        
        switch (shipType) {
            case 'interceptor':
                // Small triangle
                this.ctx.moveTo(x, y - iconSize);
                this.ctx.lineTo(x - iconSize * 0.6, y + iconSize * 0.6);
                this.ctx.lineTo(x + iconSize * 0.6, y + iconSize * 0.6);
                break;
            case 'cruiser':
                // Diamond
                this.ctx.moveTo(x, y - iconSize);
                this.ctx.lineTo(x - iconSize, y);
                this.ctx.lineTo(x, y + iconSize);
                this.ctx.lineTo(x + iconSize, y);
                break;
            case 'dreadnought':
                // Large square
                this.ctx.rect(x - iconSize, y - iconSize, iconSize * 2, iconSize * 2);
                break;
            case 'starbase':
                // Hexagon
                for (let i = 0; i < 6; i++) {
                    const angle = Math.PI / 3 * i;
                    const px = x + iconSize * Math.cos(angle);
                    const py = y + iconSize * Math.sin(angle);
                    if (i === 0) this.ctx.moveTo(px, py);
                    else this.ctx.lineTo(px, py);
                }
                break;
        }
        
        this.ctx.closePath();
        this.ctx.fill();
        
        // Draw ship outline
        this.ctx.strokeStyle = this.colors.hexBorder;
        this.ctx.lineWidth = 1;
        this.ctx.stroke();
        
        // Draw count if > 1
        if (count > 1) {
            this.drawText(count.toString(), x + iconSize * 1.2, y - iconSize * 0.8, this.colors.text, 8 * this.zoom);
        }
    }
    
    // Render ship blueprints (for player panel or detailed view)
    drawShipBlueprint(x, y, shipData, scale = 1) {
        const size = 40 * scale * this.zoom;
        const partSize = 8 * scale * this.zoom;
        
        // Draw ship outline based on type
        this.ctx.save();
        this.ctx.translate(x, y);
        
        // Draw ship background
        this.ctx.fillStyle = this.hexAlpha(this.colors.hexFill, 0.8);
        this.ctx.fillRect(-size / 2, -size / 2, size, size);
        
        // Draw ship type label
        this.ctx.fillStyle = this.colors.text;
        this.ctx.font = `${10 * scale * this.zoom}px sans-serif`;
        this.ctx.textAlign = 'center';
        this.ctx.fillText(shipData.type || 'Ship', 0, -size / 2 + 10 * scale * this.zoom);
        
        // Draw ship parts grid
        if (shipData.parts || shipData.blueprint) {
            const parts = shipData.parts || shipData.blueprint;
            const partPositions = this.getShipPartPositions(shipData.type);
            
            Object.entries(parts).forEach(([slot, part], i) => {
                if (!part) return;
                
                const pos = partPositions[i] || { x: (i % 3 - 1) * partSize * 1.5, y: Math.floor(i / 3) * partSize * 1.5 };
                
                // Draw part icon based on type
                let partColor = this.colors.hexHighlight;
                let partIcon = '?';
                
                if (part.includes('cannon') || part.includes('ion')) {
                    partColor = '#ef4444'; // Red for weapons
                    partIcon = '◊';
                } else if (part.includes('shield')) {
                    partColor = '#60a5fa'; // Blue for shields
                    partIcon = '◯';
                } else if (part.includes('computer')) {
                    partColor = '#10b981'; // Green for computers
                    partIcon = '⚡';
                } else if (part.includes('drive')) {
                    partColor = '#fbbf24'; // Gold for drives
                    partIcon = '▶';
                } else if (part.includes('hull')) {
                    partColor = '#9ca3af'; // Gray for hull
                    partIcon = '■';
                }
                
                // Draw part square
                this.ctx.fillStyle = partColor;
                this.ctx.fillRect(pos.x - partSize / 2, pos.y - partSize / 2, partSize, partSize);
                
                // Draw part border
                this.ctx.strokeStyle = this.colors.text;
                this.ctx.lineWidth = 1;
                this.ctx.strokeRect(pos.x - partSize / 2, pos.y - partSize / 2, partSize, partSize);
                
                // Draw part icon
                this.ctx.fillStyle = this.colors.text;
                this.ctx.font = `${8 * scale * this.zoom}px sans-serif`;
                this.ctx.fillText(partIcon, pos.x, pos.y + 2);
            });
        }
        
        // Draw ship stats
        if (shipData.stats) {
            let statsY = size / 2 - 20 * scale * this.zoom;
            this.ctx.font = `${8 * scale * this.zoom}px monospace`;
            this.ctx.textAlign = 'left';
            
            ['initiative', 'hull', 'computer', 'shield', 'power'].forEach((stat, i) => {
                if (shipData.stats[stat] !== undefined) {
                    const statText = `${stat[0].toUpperCase()}: ${shipData.stats[stat]}`;
                    this.ctx.fillText(statText, -size / 2 + 5, statsY + i * 10 * scale * this.zoom);
                }
            });
        }
        
        this.ctx.restore();
    }
    
    getShipPartPositions(shipType) {
        // Return predefined positions for ship parts based on type
        // This creates a more organized blueprint layout
        const positions = {
            interceptor: [
                { x: 0, y: -10 },
                { x: -10, y: 5 },
                { x: 10, y: 5 }
            ],
            cruiser: [
                { x: -12, y: -12 },
                { x: 0, y: -12 },
                { x: 12, y: -12 },
                { x: -12, y: 0 },
                { x: 0, y: 0 },
                { x: 12, y: 0 }
            ],
            dreadnought: [
                { x: -15, y: -15 },
                { x: 0, y: -15 },
                { x: 15, y: -15 },
                { x: -15, y: 0 },
                { x: 0, y: 0 },
                { x: 15, y: 0 },
                { x: -15, y: 15 },
                { x: 0, y: 15 },
                { x: 15, y: 15 }
            ],
            starbase: [
                { x: -15, y: -15 },
                { x: 0, y: -15 },
                { x: 15, y: -15 },
                { x: -15, y: 0 },
                { x: 0, y: 0 },
                { x: 15, y: 0 }
            ]
        };
        
        return positions[shipType] || positions.interceptor;
    }
    
    renderConnections() {
        if (!this.state.map || !this.state.map.wormholes) return;
        
        this.ctx.strokeStyle = this.colors.wormhole;
        this.ctx.lineWidth = 2 * this.zoom;
        this.ctx.setLineDash([5 * this.zoom, 5 * this.zoom]);
        
        this.state.map.wormholes.forEach(wormhole => {
            const from = this.parseHexId(wormhole.from || wormhole[0]);
            const to = this.parseHexId(wormhole.to || wormhole[1]);
            
            if (from && to) {
                const pos1 = this.hexToPixel(from.q, from.r);
                const pos2 = this.hexToPixel(to.q, to.r);
                
                this.ctx.beginPath();
                this.ctx.moveTo(pos1.x, pos1.y);
                this.ctx.lineTo(pos2.x, pos2.y);
                this.ctx.stroke();
            }
        });
        
        this.ctx.setLineDash([]);
    }
    
    renderTooltip() {
        if (!this.hoveredHex || !this.state?.map?.hexes) return;
        
        const hexData = this.state.map.hexes[this.hoveredHex];
        if (!hexData) return;
        
        // Build tooltip content
        const lines = [];
        lines.push(`Hex: ${this.hoveredHex}`);
        
        // Show coordinates if available from backend
        if (hexData.axial_q !== undefined && hexData.axial_r !== undefined) {
            lines.push(`Coords: (${hexData.axial_q}, ${hexData.axial_r}) Ring ${hexData.ring || '?'}`);
        }
        
        if (hexData.tile_type && hexData.tile_type !== 'empty') {
            lines.push(`Type: ${hexData.tile_type}`);
        }
        
        if (hexData.controlled_by !== undefined && hexData.controlled_by !== null) {
            lines.push(`Owner: Player ${hexData.controlled_by}`);
        }
        
        if (hexData.is_warp_portal || hexData.warp_portal) {
            lines.push('⚯ Warp Portal');
        }
        
        if (hexData.anomaly) {
            lines.push('⚠ Anomaly Present');
        }
        
        if (hexData.planets && hexData.planets.length > 0) {
            lines.push(`Planets: ${hexData.planets.length}`);
            hexData.planets.forEach((p, i) => {
                let pInfo = `  ${i + 1}: `;
                if (p.type) pInfo += p.type;
                if (p.colonized || p.population) pInfo += ' (colonized)';
                if (p.production) {
                    const prod = Object.entries(p.production).map(([k, v]) => `${k[0]}:${v}`).join(' ');
                    pInfo += ` [${prod}]`;
                }
                lines.push(pInfo);
            });
        }
        
        if (hexData.ships) {
            const ships = this.countShips(hexData.ships);
            const shipCount = Object.entries(ships).filter(([_, cnt]) => cnt > 0);
            if (shipCount.length > 0) {
                lines.push('Ships:');
                shipCount.forEach(([type, cnt]) => {
                    lines.push(`  ${type}: ${cnt}`);
                });
            }
        }
        
        if (hexData.technologies || hexData.tech) {
            const techs = hexData.technologies || hexData.tech;
            lines.push(`Tech: ${techs.length} items`);
        }
        
        if (hexData.discovery) {
            lines.push(`Discovery: ${hexData.discovery.type || '?'}`);
        }
        
        if (hexData.ancients || hexData.guardians) {
            const count = typeof (hexData.ancients || hexData.guardians) === 'number' 
                ? (hexData.ancients || hexData.guardians)
                : (hexData.ancients || hexData.guardians).count || 1;
            lines.push(`☠ Ancients: ${count}`);
        }
        
        // Calculate tooltip dimensions
        const padding = 10;
        const lineHeight = 14;
        const fontSize = 11;
        this.ctx.font = `${fontSize}px monospace`;
        
        const maxWidth = Math.max(...lines.map(l => this.ctx.measureText(l).width));
        const tooltipWidth = maxWidth + padding * 2;
        const tooltipHeight = lines.length * lineHeight + padding * 2;
        
        // Position tooltip near mouse, but keep it on screen
        let tooltipX = this.mouseX + 15;
        let tooltipY = this.mouseY + 15;
        
        if (tooltipX + tooltipWidth > this.canvas.width - 10) {
            tooltipX = this.mouseX - tooltipWidth - 15;
        }
        if (tooltipY + tooltipHeight > this.canvas.height - 10) {
            tooltipY = this.mouseY - tooltipHeight - 15;
        }
        
        // Draw tooltip background
        this.ctx.fillStyle = 'rgba(15, 23, 42, 0.95)';
        this.ctx.strokeStyle = this.colors.hexBorder;
        this.ctx.lineWidth = 2;
        this.ctx.fillRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight);
        this.ctx.strokeRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight);
        
        // Draw tooltip text
        this.ctx.fillStyle = this.colors.text;
        this.ctx.font = `${fontSize}px monospace`;
        this.ctx.textAlign = 'left';
        this.ctx.textBaseline = 'top';
        
        lines.forEach((line, i) => {
            this.ctx.fillText(
                line,
                tooltipX + padding,
                tooltipY + padding + i * lineHeight
            );
        });
        
        // Reset text alignment
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
    }
    
    renderUI() {
        // Draw zoom level indicator
        this.drawText(
            `Zoom: ${(this.zoom * 100).toFixed(0)}%`,
            this.canvas.width - 60,
            20,
            this.colors.textDim,
            12
        );
    }
    
    getPlayerColor(playerId) {
        const colorMap = {
            '0': this.colors.player1,
            '1': this.colors.player2,
            '2': this.colors.player3,
            '3': this.colors.player4,
            '4': this.colors.player5,
            '5': this.colors.player6,
        };
        return colorMap[playerId] || this.colors.hexBorder;
    }
    
    hexAlpha(color, alpha) {
        // Handle already rgba format
        if (color.startsWith('rgba')) {
            // Extract rgb values and replace alpha
            const match = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
            if (match) {
                return `rgba(${match[1]}, ${match[2]}, ${match[3]}, ${alpha})`;
            }
        }
        
        // Handle rgb format
        if (color.startsWith('rgb(')) {
            const match = color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)/);
            if (match) {
                return `rgba(${match[1]}, ${match[2]}, ${match[3]}, ${alpha})`;
            }
        }
        
        // Handle hex format
        if (color.startsWith('#')) {
            const r = parseInt(color.slice(1, 3), 16);
            const g = parseInt(color.slice(3, 5), 16);
            const b = parseInt(color.slice(5, 7), 16);
            return `rgba(${r}, ${g}, ${b}, ${alpha})`;
        }
        
        // Fallback
        return color;
    }
    
    // Public API
    setState(state) {
        this.state = state;
        this.render();
    }
    
    resetView() {
        this.zoom = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        this.render();
    }
    
    zoomIn() {
        this.zoom = Math.min(3, this.zoom * 1.2);
        this.render();
    }
    
    zoomOut() {
        this.zoom = Math.max(0.3, this.zoom / 1.2);
        this.render();
    }
}

// Export for use in other scripts
window.BoardRenderer = BoardRenderer;

// Initialize board renderer
let boardRenderer;
window.addEventListener('DOMContentLoaded', () => {
    boardRenderer = new BoardRenderer('board-canvas');
    window.boardRenderer = boardRenderer;
    
    // Connect zoom controls
    document.getElementById('zoom-in')?.addEventListener('click', () => {
        boardRenderer.zoomIn();
    });
    
    document.getElementById('zoom-out')?.addEventListener('click', () => {
        boardRenderer.zoomOut();
    });
    
    document.getElementById('reset-view')?.addEventListener('click', () => {
        boardRenderer.resetView();
    });
    
    console.log('Board renderer initialized');
});

