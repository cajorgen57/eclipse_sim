/**
 * API Client for Eclipse AI Backend
 */

const API_BASE = '/api';

class APIClient {
    constructor() {
        this.baseURL = API_BASE;
    }

    async get(endpoint) {
        const response = await fetch(`${this.baseURL}${endpoint}`);
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            // Handle nested error objects (e.g., {detail: {error: "...", traceback: "..."}})
            let errorMessage = 'API request failed';
            if (typeof error.detail === 'object' && error.detail !== null) {
                errorMessage = error.detail.error || JSON.stringify(error.detail);
                // Log full error details for debugging
                if (error.detail.traceback) {
                    console.error('Backend traceback:', error.detail.traceback);
                }
            } else if (error.detail) {
                errorMessage = error.detail;
            } else if (error.error) {
                errorMessage = error.error;
            }
            throw new Error(errorMessage);
        }
        return response.json();
    }

    async post(endpoint, data) {
        const response = await fetch(`${this.baseURL}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            // Handle nested error objects (e.g., {detail: {error: "...", traceback: "..."}})
            let errorMessage = 'API request failed';
            if (typeof error.detail === 'object' && error.detail !== null) {
                errorMessage = error.detail.error || JSON.stringify(error.detail);
                // Log full error details for debugging
                if (error.detail.traceback) {
                    console.error('Backend traceback:', error.detail.traceback);
                }
            } else if (error.detail) {
                errorMessage = error.detail;
            } else if (error.error) {
                errorMessage = error.error;
            }
            throw new Error(errorMessage);
        }
        return response.json();
    }

    // Fixtures
    async listFixtures() {
        return this.get('/fixtures');
    }

    async loadFixture(name) {
        return this.get(`/fixtures/${encodeURIComponent(name)}`);
    }

    // State management
    async saveState(state, filename) {
        return this.post('/state/save', { state, filename });
    }

    // Prediction
    async predict(state, config) {
        return this.post('/predict', { state, config });
    }

    // Game generation
    async generateGame(numPlayers, speciesByPlayer = null, seed = null, ancientHomeworlds = false, startingRound = 1) {
        return this.post('/generate', {
            num_players: numPlayers,
            species_by_player: speciesByPlayer,
            seed: seed,
            ancient_homeworlds: ancientHomeworlds,
            starting_round: startingRound
        });
    }

    // Reference data
    async listProfiles() {
        return this.get('/profiles');
    }

    async listSpecies() {
        return this.get('/species');
    }

    async listTechs() {
        return this.get('/techs');
    }
}

// Global API client instance
const api = new APIClient();

