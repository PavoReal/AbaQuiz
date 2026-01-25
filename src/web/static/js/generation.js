/**
 * Alpine.js component for Question Generation page
 */

function generationControls() {
    return {
        // Pool stats
        poolStats: {
            total_questions: 0,
            active_users: 0,
            avg_unseen: 0,
            threshold: 20,
            health: 'loading',
            health_message: 'Loading...',
            areas: []
        },

        // Generation controls
        questionCount: 50,
        skipDedup: false,
        difficultyMin: '',
        distribution: {},
        costEstimate: 0,
        selectedAreas: [],  // Empty = all selected (initialized in init)

        // State
        isRunning: false,
        isStarting: false,
        progress: null,
        pollingInterval: null,

        // Configuration
        config: {
            threshold: 20,
            batch_size: 50,
            dedup_threshold: 0.85,
            dedup_check_limit: 30,
            generation_batch_size: 5,
            max_concurrent_generation: 20
        },

        // Cost constants (from DESIGN.md)
        COST_PER_QUESTION: 0.09,
        COST_PER_DEDUP: 0.002 * 5, // ~5 dedup checks per question

        // Computed property for all categories selected
        get allCategoriesSelected() {
            return this.poolStats.areas.length > 0 &&
                   this.selectedAreas.length === this.poolStats.areas.length;
        },

        init() {
            // Load initial data
            this.loadPoolStats().then(() => {
                // Initialize selectedAreas with all areas after pool stats load
                if (this.selectedAreas.length === 0 && this.poolStats.areas.length > 0) {
                    this.selectedAreas = this.poolStats.areas.map(a => a.name);
                }
                this.updateDistribution();
            });
            this.loadConfig();

            // Check for running generation
            this.checkProgress();

            // Listen for custom events
            window.addEventListener('generation-cancelled', () => {
                this.isRunning = false;
                this.stopPolling();
                this.loadPoolStats();
            });

            window.addEventListener('generation-reset', () => {
                this.progress = null;
                this.isRunning = false;
            });
        },

        toggleCategory(areaName) {
            const index = this.selectedAreas.indexOf(areaName);
            if (index === -1) {
                this.selectedAreas.push(areaName);
            } else {
                this.selectedAreas.splice(index, 1);
            }
            this.updateDistribution();
        },

        toggleAllCategories() {
            if (this.allCategoriesSelected) {
                // Deselect all
                this.selectedAreas = [];
            } else {
                // Select all
                this.selectedAreas = this.poolStats.areas.map(a => a.name);
            }
            this.updateDistribution();
        },

        async loadPoolStats() {
            try {
                const response = await fetch('/api/generation/pool-stats');
                if (response.ok) {
                    const newStats = await response.json();
                    // If this is the first load, initialize selectedAreas with all areas
                    const isFirstLoad = this.poolStats.areas.length === 0;
                    this.poolStats = newStats;
                    if (isFirstLoad && this.selectedAreas.length === 0) {
                        this.selectedAreas = newStats.areas.map(a => a.name);
                    }
                }
            } catch (error) {
                console.error('Failed to load pool stats:', error);
            }
        },

        async loadConfig() {
            try {
                const response = await fetch('/api/generation/config');
                if (response.ok) {
                    this.config = await response.json();
                }
            } catch (error) {
                console.error('Failed to load config:', error);
            }
        },

        async saveConfig() {
            try {
                const response = await fetch('/api/generation/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.config)
                });
                if (response.ok) {
                    // Show success message (could use a toast notification)
                    alert('Configuration saved');
                } else {
                    const data = await response.json();
                    alert('Failed to save: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Failed to save config:', error);
                alert('Failed to save configuration');
            }
        },

        async updateDistribution() {
            // Validate count and selection
            if (this.questionCount < 1 || this.questionCount > 500) {
                this.distribution = {};
                this.costEstimate = 0;
                return;
            }

            // If no areas selected, show empty distribution
            if (this.selectedAreas.length === 0) {
                this.distribution = {};
                this.costEstimate = 0;
                return;
            }

            try {
                // Build query string with selected areas
                const params = new URLSearchParams({ count: this.questionCount });
                this.selectedAreas.forEach(area => params.append('areas', area));

                const response = await fetch(`/api/generation/distribution?${params.toString()}`);
                if (response.ok) {
                    const data = await response.json();
                    this.distribution = data.distribution;

                    // Update cost estimate based on skip_dedup setting
                    if (this.skipDedup) {
                        this.costEstimate = data.cost_estimate.without_dedup;
                    } else {
                        this.costEstimate = data.cost_estimate.with_dedup;
                    }
                }
            } catch (error) {
                // Fallback to local calculation
                this.costEstimate = this.calculateCost();
            }
        },

        calculateCost() {
            const baseCost = this.questionCount * this.COST_PER_QUESTION;
            if (this.skipDedup) {
                return baseCost;
            }
            return baseCost + (this.questionCount * this.COST_PER_DEDUP);
        },

        async startGeneration() {
            if (this.isStarting || this.isRunning) return;
            if (this.questionCount < 1 || this.questionCount > 500) {
                alert('Please enter a valid question count (1-500)');
                return;
            }
            if (this.selectedAreas.length === 0) {
                alert('Please select at least one content area');
                return;
            }

            this.isStarting = true;

            try {
                const response = await fetch('/api/generation/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        count: this.questionCount,
                        skip_dedup: this.skipDedup,
                        difficulty_min: this.difficultyMin ? parseInt(this.difficultyMin) : null,
                        selected_areas: this.selectedAreas
                    })
                });

                const data = await response.json();

                if (response.ok) {
                    this.isRunning = true;
                    this.startPolling();
                } else {
                    alert('Failed to start: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Failed to start generation:', error);
                alert('Failed to start generation');
            } finally {
                this.isStarting = false;
            }
        },

        async checkProgress() {
            try {
                const response = await fetch('/api/generation/progress');
                if (response.ok) {
                    const data = await response.json();
                    if (data.running) {
                        this.isRunning = true;
                        this.progress = data;
                        this.startPolling();
                    } else if (data.progress && data.progress.complete) {
                        this.progress = data.progress;
                    }
                }
            } catch (error) {
                console.error('Failed to check progress:', error);
            }
        },

        startPolling() {
            if (this.pollingInterval) return;

            this.pollingInterval = setInterval(async () => {
                try {
                    const response = await fetch('/api/generation/progress');
                    if (response.ok) {
                        const data = await response.json();
                        this.progress = data;

                        if (!data.running) {
                            this.isRunning = false;
                            this.stopPolling();
                            this.loadPoolStats();
                        }
                    }
                } catch (error) {
                    console.error('Polling error:', error);
                }
            }, 1000);
        },

        stopPolling() {
            if (this.pollingInterval) {
                clearInterval(this.pollingInterval);
                this.pollingInterval = null;
            }
        },

        async cancelGeneration() {
            try {
                const response = await fetch('/api/generation/cancel', {
                    method: 'POST'
                });
                if (response.ok) {
                    // Will be updated by next poll
                } else {
                    const data = await response.json();
                    alert('Failed to cancel: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Failed to cancel:', error);
                alert('Failed to cancel generation');
            }
        },

        formatElapsed(seconds) {
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
    };
}
