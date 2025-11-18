/**
 * UI Constants - Centralized styling and configuration
 * Single source of truth for colors, icons, and UI patterns across all components
 */

window.UIConstants = {
    // Tech Category Styling
    TECH_CATEGORY_STYLES: {
        'Military': {
            gradient: 'from-red-600 to-red-700',
            bgClass: 'bg-red-600',
            borderClass: 'border-red-400',
            borderDark: 'border-red-500/50',
            bgDark: 'bg-red-900',
            borderDarkClass: 'border-red-600',
            glow: 'shadow-red-500/20',
            icon: '⚔️',
            label: 'Military'
        },
        'Grid': {
            gradient: 'from-yellow-600 to-yellow-700',
            bgClass: 'bg-yellow-600',
            borderClass: 'border-yellow-400',
            borderDark: 'border-yellow-500/50',
            bgDark: 'bg-yellow-900',
            borderDarkClass: 'border-yellow-600',
            glow: 'shadow-yellow-500/20',
            icon: '⚡',
            label: 'Grid'
        },
        'Nano': {
            gradient: 'from-green-600 to-green-700',
            bgClass: 'bg-green-600',
            borderClass: 'border-green-400',
            borderDark: 'border-green-500/50',
            bgDark: 'bg-green-900',
            borderDarkClass: 'border-green-600',
            glow: 'shadow-green-500/20',
            icon: '🔬',
            label: 'Nano'
        },
        'Rare': {
            gradient: 'from-purple-600 to-purple-700',
            bgClass: 'bg-purple-600',
            borderClass: 'border-purple-400',
            borderDark: 'border-purple-500/50',
            bgDark: 'bg-purple-900',
            borderDarkClass: 'border-purple-600',
            glow: 'shadow-purple-500/20',
            icon: '💎',
            label: 'Rare'
        },
        'Other': {
            gradient: 'from-gray-600 to-gray-700',
            bgClass: 'bg-gray-600',
            borderClass: 'border-gray-400',
            borderDark: 'border-gray-500/50',
            bgDark: 'bg-gray-800',
            borderDarkClass: 'border-gray-600',
            glow: 'shadow-gray-500/20',
            icon: '🔧',
            label: 'Other'
        }
    },

    // Ship Type Configuration
    SHIP_TYPE_CONFIG: {
        interceptor: {
            icon: '🛸',
            iconSimple: '▲',
            name: 'Interceptor',
            gradient: 'from-cyan-600 to-cyan-700',
            color: 'cyan'
        },
        cruiser: {
            icon: '🚀',
            iconSimple: '◆',
            name: 'Cruiser',
            gradient: 'from-purple-600 to-purple-700',
            color: 'purple'
        },
        dreadnought: {
            icon: '🛡️',
            iconSimple: '■',
            name: 'Dreadnought',
            gradient: 'from-red-600 to-red-700',
            color: 'red'
        },
        starbase: {
            icon: '🏭',
            iconSimple: '⬡',
            name: 'Starbase',
            gradient: 'from-blue-600 to-blue-700',
            color: 'blue'
        }
    },

    // Resource Configuration
    RESOURCE_CONFIG: {
        money: {
            icon: '💰',
            label: 'Credits',
            color: 'yellow',
            gradient: 'from-yellow-500 to-yellow-600',
            textColor: 'text-yellow-400'
        },
        science: {
            icon: '🔬',
            label: 'Science',
            color: 'blue',
            gradient: 'from-blue-500 to-blue-600',
            textColor: 'text-blue-400'
        },
        materials: {
            icon: '🔩',
            label: 'Materials',
            color: 'orange',
            gradient: 'from-orange-500 to-orange-600',
            textColor: 'text-orange-400'
        }
    },

    // Tier Configuration
    TIER_CONFIG: {
        'I': {
            label: 'Tier I',
            maxCost: 4,
            badgeColor: 'from-eclipse-primary to-eclipse-accent'
        },
        'II': {
            label: 'Tier II',
            maxCost: 7,
            badgeColor: 'from-eclipse-primary to-eclipse-accent'
        },
        'III': {
            label: 'Tier III',
            maxCost: Infinity,
            badgeColor: 'from-eclipse-primary to-eclipse-accent'
        }
    },

    // Ship Stat Icons
    SHIP_STAT_ICONS: {
        initiative: { icon: '⚡', label: 'Init', color: 'yellow' },
        hull: { icon: '❤️', label: 'Hull', color: 'red' },
        computer: { icon: '🎯', label: 'Comp', color: 'blue' },
        shield: { icon: '🛡', label: 'Shield', color: 'green' },
        cannons: { icon: '💥', label: 'Cannon', color: 'orange' },
        missiles: { icon: '🚀', label: 'Missile', color: 'purple' },
        drives: { icon: '🔧', label: 'Drive', color: 'cyan' }
    },

    // Utility Functions
    getTechTier: function(cost) {
        if (cost <= 4) return 'I';
        if (cost <= 7) return 'II';
        return 'III';
    },

    getCategoryStyle: function(category) {
        return this.TECH_CATEGORY_STYLES[category] || this.TECH_CATEGORY_STYLES['Other'];
    },

    getShipConfig: function(shipType) {
        return this.SHIP_TYPE_CONFIG[shipType] || {
            icon: '🚀',
            iconSimple: '●',
            name: shipType,
            gradient: 'from-gray-600 to-gray-700',
            color: 'gray'
        };
    },

    getResourceConfig: function(resourceType) {
        return this.RESOURCE_CONFIG[resourceType] || {
            icon: '●',
            label: resourceType,
            color: 'gray',
            gradient: 'from-gray-500 to-gray-600',
            textColor: 'text-gray-400'
        };
    },

    // Category detection helpers
    detectTechCategory: function(techName) {
        const lower = (techName || '').toLowerCase();
        
        if (lower.includes('cannon') || lower.includes('missile') || lower.includes('hull') || 
            lower.includes('bomb') || lower.includes('cruiser') || lower.includes('dreadnought')) {
            return 'Military';
        }
        
        if (lower.includes('computer') || lower.includes('targeting') || lower.includes('grid')) {
            return 'Grid';
        }
        
        if (lower.includes('shield') || lower.includes('armor') || lower.includes('drive') || 
            lower.includes('jump') || lower.includes('nano')) {
            return 'Nano';
        }
        
        if (lower.includes('rare') || lower.includes('ancient') || lower.includes('artifact')) {
            return 'Rare';
        }
        
        return 'Other';
    }
};

// Export for ES6 modules if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.UIConstants;
}

console.log('UI Constants loaded');

