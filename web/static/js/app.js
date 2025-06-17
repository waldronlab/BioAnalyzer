document.addEventListener('DOMContentLoaded', () => {
    // Initialize state
    let ws = null;
    let currentPaper = null;
    let isAnalyzing = false;
    let isConnected = false;

    // Ensure all required elements are available
    function checkElements() {
        const requiredElements = [
            'pmid',
            'loading',
            'results',
            'paper-title',
            'paper-authors',
            'paper-journal',
            'paper-abstract',
            'confidence-fill',
            'confidence-value',
            'category-scores',
            'found-terms',
            'key-findings',
            'suggested-topics',
            'analysis-status',
            'tokens-generated',
            'paper-pmid',
            'paper-journal-short',
            'paper-title-short',
            'paper-year',
            'paper-host',
            'paper-body-site',
            'paper-condition',
            'paper-sequencing-type',
            'paper-in-bugsigdb',
            'paper-signature-prob',
            'paper-sample-size',
            'paper-taxa-level',
            'paper-statistical-method'
        ];

        const missingElements = requiredElements.filter(id => {
            const element = document.getElementById(id);
            if (!element) {
                console.error(`Missing required element: ${id}`);
                return true;
            }
            console.log(`Found required element: ${id}`);
            return false;
        });

        if (missingElements.length > 0) {
            console.error('Missing required elements:', missingElements);
            return false;
        }
        return true;
    }

    // Initialize WebSocket connection
    function initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        ws = new WebSocket(wsUrl);
        
        ws.onopen = function() {
            console.log('WebSocket connection established');
            isConnected = true;
            updateConnectionStatus('Connected', 'success');
            const messageInput = document.getElementById('message-input');
            const sendButton = document.getElementById('send-button');
            if (messageInput) messageInput.disabled = false;
            if (sendButton) sendButton.disabled = false;
        };
        
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            console.log('Received message:', data);
            if (data.type === 'analysis_result') {
                displayAnalysisResults(data);
            } else if (data.error) {
                showError(data.error);
            } else if (data.response) {
                displayChatMessage(data.response, 'assistant');
            }
        };
        
        ws.onclose = function() {
            console.log('WebSocket connection closed');
            isConnected = false;
            updateConnectionStatus('Disconnected', 'danger');
            const messageInput = document.getElementById('message-input');
            const sendButton = document.getElementById('send-button');
            if (messageInput) messageInput.disabled = true;
            if (sendButton) sendButton.disabled = true;
            
            // Attempt to reconnect after 5 seconds
            setTimeout(initWebSocket, 5000);
        };
        
        ws.onerror = function(error) {
            console.error('WebSocket error:', error);
            updateConnectionStatus('Connection error', 'danger');
        };
    }

    // Update connection status display
    function updateConnectionStatus(message, type) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.className = `alert alert-${type}`;
            statusElement.textContent = message;
            statusElement.style.display = 'block';
        }
        
        const messageInput = document.getElementById('message-input');
        const sendButton = document.getElementById('send-button');
        const usernameInput = document.getElementById('username');

        if (messageInput) messageInput.disabled = !isConnected;
        if (sendButton) sendButton.disabled = !isConnected;
        if (usernameInput) usernameInput.disabled = isConnected;
    }

    // Display analysis results
    function displayAnalysisResults(data) {
        console.log('Displaying analysis results:', data);
        
        // Update paper metadata
        const titleEl = document.getElementById('paper-title');
        const authorsEl = document.getElementById('paper-authors');
        const journalEl = document.getElementById('paper-journal');
        const abstractEl = document.getElementById('paper-abstract');
        
        if (titleEl && data.metadata?.title) {
            titleEl.textContent = data.metadata.title;
        }
        
        if (authorsEl && data.metadata?.authors) {
            authorsEl.textContent = data.metadata.authors;
        }
        
        if (journalEl && data.metadata?.journal) {
            journalEl.textContent = data.metadata.journal;
        }
        
        if (abstractEl && data.metadata?.abstract) {
            abstractEl.textContent = data.metadata.abstract;
        }
        
        // Update confidence score
        const confidenceFill = document.getElementById('confidence-fill');
        const confidenceValue = document.getElementById('confidence-value');
        if (confidenceFill && confidenceValue && data.analysis?.confidence) {
            const confidence = data.analysis.confidence * 100;
            confidenceFill.style.width = `${confidence}%`;
            confidenceFill.className = `progress-bar ${getScoreColor(data.analysis.confidence)}`;
            confidenceValue.textContent = `${confidence.toFixed(1)}%`;
        }
        
        // Update category scores
        if (data.analysis?.category_scores) {
            updateCategoryScores(data.analysis.category_scores);
        }
        
        // Update found terms
        const foundTermsEl = document.getElementById('found-terms');
        if (foundTermsEl && data.analysis?.found_terms) {
            foundTermsEl.innerHTML = '';
            for (const [category, terms] of Object.entries(data.analysis.found_terms)) {
                if (terms && terms.length > 0) {
                    const categoryDiv = document.createElement('div');
                    categoryDiv.className = 'mb-3';
                    categoryDiv.innerHTML = `
                        <h6 class="mb-2">${category}</h6>
                        <div class="d-flex flex-wrap gap-2">
                            ${terms.map(term => `<span class="badge bg-secondary">${term}</span>`).join('')}
                        </div>
                    `;
                    foundTermsEl.appendChild(categoryDiv);
                }
            }
        }
        
        // Update key findings
        const keyFindingsEl = document.getElementById('key-findings');
        if (keyFindingsEl && data.analysis?.key_findings) {
            keyFindingsEl.innerHTML = data.analysis.key_findings
                .map(finding => `<li class="mb-2"><i class="fas fa-check-circle text-success me-2"></i>${finding}</li>`)
                .join('');
        }
        
        // Update suggested topics
        const suggestedTopicsEl = document.getElementById('suggested-topics');
        if (suggestedTopicsEl && data.analysis?.suggested_topics) {
            suggestedTopicsEl.innerHTML = data.analysis.suggested_topics
                .map(topic => `<li class="mb-2"><i class="fas fa-tag text-primary me-2"></i>${topic}</li>`)
                .join('');
        }
        
        // Update analysis status
        const statusEl = document.getElementById('analysis-status');
        if (statusEl && data.analysis?.status) {
            statusEl.textContent = data.analysis.status;
            statusEl.className = `badge ${data.analysis.status === 'success' ? 'bg-success' : 'bg-danger'}`;
        }
        
        // Update tokens generated
        const tokensEl = document.getElementById('tokens-generated');
        if (tokensEl && data.analysis?.num_tokens) {
            tokensEl.textContent = data.analysis.num_tokens;
        }
        
        // Show results container
        const resultsDiv = document.getElementById('results');
        if (resultsDiv) {
            resultsDiv.style.display = 'block';
            resultsDiv.style.opacity = '0';
            setTimeout(() => {
                resultsDiv.style.opacity = '1';
            }, 100);
        }
    }

    // Display chat message
    function displayChatMessage(message, type) {
        const chatContainer = document.getElementById('chat-container');
        if (!chatContainer) return;

        const messageElement = document.createElement('div');
        messageElement.className = `message ${type}-message`;
        messageElement.textContent = message;
        chatContainer.appendChild(messageElement);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // Show error message
    function showError(message) {
        console.error('Error:', message);
        
        // Create or get error container
        let errorContainer = document.getElementById('error-container');
        if (!errorContainer) {
            errorContainer = document.createElement('div');
            errorContainer.id = 'error-container';
            errorContainer.className = 'alert alert-danger mt-3';
            errorContainer.style.position = 'fixed';
            errorContainer.style.top = '20px';
            errorContainer.style.left = '50%';
            errorContainer.style.transform = 'translateX(-50%)';
            errorContainer.style.zIndex = '9999';
            errorContainer.style.minWidth = '300px';
            errorContainer.style.textAlign = 'center';
            document.body.appendChild(errorContainer);
        }

        // Set error message
        errorContainer.innerHTML = `
            <strong>Error:</strong> ${message}
            <button type="button" class="btn-close" style="float: right;" onclick="this.parentElement.style.display='none'"></button>
        `;
        errorContainer.style.display = 'block';

        // Also show in results area if it exists
        const resultsDiv = document.getElementById('results');
        if (resultsDiv) {
            const resultsError = document.createElement('div');
            resultsError.className = 'alert alert-danger mt-3';
            resultsError.innerHTML = `<strong>Error:</strong> ${message}`;
            resultsDiv.insertBefore(resultsError, resultsDiv.firstChild);
        }

        // Hide loading indicator if it exists
        const loadingDiv = document.getElementById('loading');
        if (loadingDiv) {
            loadingDiv.style.display = 'none';
        }
    }

    // Analyze paper
    async function analyzePaper() {
        const pmid = document.getElementById('pmid').value.trim();
        if (!pmid) {
            showError('Please enter a PubMed ID');
            return;
        }

        // Show loading indicator
        const loadingDiv = document.getElementById('loading');
        const resultsDiv = document.getElementById('results');
        
        if (loadingDiv) loadingDiv.style.display = 'block';
        if (resultsDiv) resultsDiv.style.display = 'none';

        try {
            console.log('Sending request to analyze paper:', pmid);
            const response = await fetch(`/analyze/${pmid}`);
            console.log('Received response:', response);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! Status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Received data:', data);
            
            if (data.analysis?.error) {
                throw new Error(data.analysis.error);
            }

            // Show results
            if (resultsDiv) {
                resultsDiv.style.display = 'block';
                displayAnalysisResults(data);
            } else {
                console.error('Results div not found');
                showError('Results container not found');
            }
        } catch (error) {
            console.error('Error analyzing paper:', error);
            showError('Error analyzing paper: ' + error.message);
        } finally {
            if (loadingDiv) {
                loadingDiv.style.display = 'none';
            }
        }
    }

    // Send message
    function sendMessage() {
        const messageInput = document.getElementById('message-input');
        if (!messageInput || !ws || !isConnected) return;

        const message = messageInput.value.trim();
        if (!message) return;

        displayChatMessage(message, 'user');
        ws.send(JSON.stringify({
            content: message,
            role: 'user'
        }));

        messageInput.value = '';
    }

    // Initialize UI
    function initializeUI() {
        // Initialize WebSocket
        initWebSocket();

        // Add event listeners
        const analyzeButton = document.getElementById('analyze-button');
        if (analyzeButton) {
            analyzeButton.addEventListener('click', analyzePaper);
        }

        const pmidInput = document.getElementById('pmid');
        if (pmidInput) {
            pmidInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    analyzePaper();
                }
            });
        }

        const sendButton = document.getElementById('send-button');
        const messageInput = document.getElementById('message-input');
        if (sendButton && messageInput) {
            sendButton.addEventListener('click', sendMessage);
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
        }

        // Create results container if it doesn't exist
        const analyzeTab = document.getElementById('analyze');
        if (analyzeTab && !document.getElementById('results')) {
            const resultsDiv = document.createElement('div');
            resultsDiv.id = 'results';
            resultsDiv.className = 'mt-4';
            resultsDiv.style.display = 'none';
            analyzeTab.appendChild(resultsDiv);
        }

        // Create loading indicator if it doesn't exist
        if (analyzeTab && !document.getElementById('loading')) {
            const loadingDiv = document.createElement('div');
            loadingDiv.id = 'loading';
            loadingDiv.className = 'text-center mt-4';
            loadingDiv.style.display = 'none';
            loadingDiv.innerHTML = `
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2">Analyzing paper...</p>
            `;
            analyzeTab.appendChild(loadingDiv);
        }
    }

    // Initialize the UI when the DOM is loaded
    document.addEventListener('DOMContentLoaded', initializeUI);

    // Page Settings Event Handlers
    document.addEventListener('DOMContentLoaded', function() {
        // Font size control
        const fontSizeSlider = document.getElementById('fontSize');
        const fontSizeValue = document.getElementById('fontSizeValue');
        
        fontSizeSlider.addEventListener('input', function() {
            const size = this.value;
            document.body.style.fontSize = size + 'px';
            fontSizeValue.textContent = size + 'px';
            localStorage.setItem('fontSize', size);
        });


        // Zoom level control
        const zoomSlider = document.getElementById('zoomLevel');
        const zoomValue = document.getElementById('zoomLevelValue');
        
        zoomSlider.addEventListener('input', function() {
            const zoom = this.value;
            document.body.style.zoom = zoom + '%';
            zoomValue.textContent = zoom + '%';
            localStorage.setItem('zoomLevel', zoom);
        });

        // Theme selection
        const themeSelect = document.getElementById('themeSelect');
        
        themeSelect.addEventListener('change', function() {
            const theme = this.value;
            document.body.className = theme;
            localStorage.setItem('theme', theme);
        });

        // Load saved settings
        const savedFontSize = localStorage.getItem('fontSize') || '16';
        const savedZoom = localStorage.getItem('zoomLevel') || '100';
        const savedTheme = localStorage.getItem('theme') || 'light';

        fontSizeSlider.value = savedFontSize;
        document.body.style.fontSize = savedFontSize + 'px';
        fontSizeValue.textContent = savedFontSize + 'px';

        zoomSlider.value = savedZoom;
        document.body.style.zoom = savedZoom + '%';
        zoomValue.textContent = savedZoom + '%';

        themeSelect.value = savedTheme;
        document.body.className = savedTheme;
    });

    function getScoreColor(score) {
        const percentage = score * 100;
        if (percentage >= 70) return 'bg-success';
        if (percentage >= 30) return 'bg-warning';
        return 'bg-danger';
    }

    function updateCategoryScores(scores) {
        console.log('updateCategoryScores called with:', scores);
        
        // Wait for DOM to be ready
        const waitForElement = () => {
            const categoryScoresDiv = document.getElementById('category-scores');
            if (!categoryScoresDiv) {
                console.log('Category scores div not found, waiting...');
                setTimeout(waitForElement, 100);
                return;
            }

            console.log('Found category scores div:', categoryScoresDiv);
            categoryScoresDiv.innerHTML = '';
            
            if (!scores || typeof scores !== 'object' || Object.keys(scores).length === 0) {
                console.log('No valid scores provided, showing empty message');
                categoryScoresDiv.innerHTML = '<p class="text-muted">No category scores available</p>';
                return;
            }

            const scoresList = document.createElement('div');
            scoresList.className = 'category-scores-list';
            
            // Sort categories alphabetically
            const sortedCategories = Object.entries(scores)
                .filter(([_, score]) => score !== null && !isNaN(score))
                .sort((a, b) => a[0].localeCompare(b[0]));
            
            console.log('Sorted and filtered categories:', sortedCategories);
            
            if (sortedCategories.length === 0) {
                categoryScoresDiv.innerHTML = '<p class="text-muted">No valid category scores available</p>';
                return;
            }
            
            sortedCategories.forEach(([category, score]) => {
                console.log(`Creating score element for ${category}: ${score}`);
                const scorePercentage = (parseFloat(score) || 0) * 100;
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'category-score-item';
                
                const formattedCategory = category
                    .split('_')
                    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                    .join(' ');
                
                const scoreLevel = getScoreColor(score);
                
                categoryDiv.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="category-name">${formattedCategory}</span>
                        <span class="score-value">${scorePercentage.toFixed(1)}%</span>
                    </div>
                    <div class="progress" style="height: 8px;">
                        <div class="progress-bar ${scoreLevel}" role="progressbar" 
                             style="width: ${scorePercentage}%"
                             aria-valuenow="${scorePercentage}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                        </div>
                    </div>
                `;
                scoresList.appendChild(categoryDiv);
            });
            
            console.log('Appending scores list to container');
            categoryScoresDiv.appendChild(scoresList);

            // Add a legend
            const legendDiv = document.createElement('div');
            legendDiv.className = 'mt-3 small text-muted d-flex justify-content-center gap-4';
            legendDiv.innerHTML = `
                <span><i class="fas fa-circle text-success"></i> High (>70%)</span>
                <span><i class="fas fa-circle text-warning"></i> Medium (30-70%)</span>
                <span><i class="fas fa-circle text-danger"></i> Low (<30%)</span>
            `;
            categoryScoresDiv.appendChild(legendDiv);
            console.log('Category scores update complete');
        };

        // Start waiting for element
        waitForElement();
    }
});