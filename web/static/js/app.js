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
            document.getElementById('message-input').disabled = false;
            document.getElementById('send-button').disabled = false;
        };
        
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        };
        
        ws.onclose = function() {
            console.log('WebSocket connection closed');
            isConnected = false;
            updateConnectionStatus('Disconnected', 'danger');
            document.getElementById('message-input').disabled = true;
            document.getElementById('send-button').disabled = true;
            
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
        }
    }

    // Handle incoming WebSocket messages
    function handleWebSocketMessage(data) {
        if (data.type === 'analysis_result') {
            displayAnalysisResults(data);
        } else if (data.type === 'error') {
            showError(data.message);
        }
    }

    // Display analysis results
    function displayAnalysisResults(data) {
        const resultsDiv = document.getElementById('results');
        if (!resultsDiv) return;
        
        // Update paper metadata
        document.getElementById('paper-title').textContent = data.title || 'N/A';
        document.getElementById('paper-authors').textContent = data.authors || 'N/A';
        document.getElementById('paper-journal').textContent = data.journal || 'N/A';
        document.getElementById('paper-date').textContent = data.date || 'N/A';
        document.getElementById('paper-doi').textContent = data.doi || 'N/A';
        document.getElementById('paper-abstract').textContent = data.abstract || 'N/A';
        
        // Update analysis details
        document.getElementById('paper-pmid').textContent = data.pmid || 'N/A';
        document.getElementById('paper-journal-short').textContent = data.journal || 'N/A';
        document.getElementById('paper-title-short').textContent = data.title || 'N/A';
        document.getElementById('paper-year').textContent = data.year || 'N/A';
        document.getElementById('paper-host').textContent = data.host || 'N/A';
        document.getElementById('paper-body-site').textContent = data.body_site || 'N/A';
        document.getElementById('paper-condition').textContent = data.condition || 'N/A';
        document.getElementById('paper-sequencing-type').textContent = data.sequencing_type || 'N/A';
        document.getElementById('paper-in-bugsigdb').textContent = data.in_bugsigdb ? 'Yes' : 'No';
        document.getElementById('paper-signature-prob').textContent = data.signature_prob || 'N/A';
        document.getElementById('paper-sample-size').textContent = data.sample_size || 'N/A';
        document.getElementById('paper-taxa-level').textContent = data.taxa_level || 'N/A';
        document.getElementById('paper-statistical-method').textContent = data.statistical_method || 'N/A';
        
        // Update confidence score
        const confidenceFill = document.getElementById('confidence-fill');
        const confidenceValue = document.getElementById('confidence-value');
        if (confidenceFill && confidenceValue) {
            const confidence = data.confidence || 0;
            confidenceFill.style.width = `${confidence}%`;
            confidenceValue.textContent = `${confidence}%`;
        }
        
        // Update category scores
        const categoryScores = document.getElementById('category-scores');
        if (categoryScores && data.category_scores) {
            categoryScores.innerHTML = '';
            Object.entries(data.category_scores).forEach(([category, score]) => {
                const scoreElement = document.createElement('div');
                scoreElement.className = 'category-score';
                scoreElement.innerHTML = `
                    <span class="category-name">${category}</span>
                    <div class="score-bar">
                        <div class="score-fill" style="width: ${score}%"></div>
                    </div>
                    <span class="score-value">${score}%</span>
                `;
                categoryScores.appendChild(scoreElement);
            });
        }
        
        // Update found terms
        const foundTerms = document.getElementById('found-terms');
        if (foundTerms && data.found_terms) {
            foundTerms.innerHTML = data.found_terms.map(term => 
                `<span class="badge bg-primary me-2 mb-2">${term}</span>`
            ).join('');
        }
        
        // Update key findings
        const keyFindings = document.getElementById('key-findings');
        if (keyFindings && data.key_findings) {
            keyFindings.innerHTML = data.key_findings.map(finding => 
                `<p class="mb-2">${finding}</p>`
            ).join('');
        }
        
        // Update suggested topics
        const suggestedTopics = document.getElementById('suggested-topics');
        if (suggestedTopics && data.suggested_topics) {
            suggestedTopics.innerHTML = data.suggested_topics.map(topic => 
                `<span class="badge bg-secondary me-2 mb-2">${topic}</span>`
            ).join('');
        }
        
        // Update analysis status
        document.getElementById('analysis-status').textContent = data.status || 'Completed';
        document.getElementById('tokens-generated').textContent = data.tokens_generated || '0';
    }

    // Show error message
    function showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger';
        errorDiv.textContent = message;
        document.getElementById('results').prepend(errorDiv);
        
        // Remove error message after 5 seconds
        setTimeout(() => errorDiv.remove(), 5000);
    }

    // Analyze paper
    function analyzePaper() {
        const pmid = document.getElementById('pmid').value.trim();
        if (!pmid) {
            showError('Please enter a PubMed ID');
            return;
        }
        
        if (!isConnected) {
            showError('Not connected to server');
            return;
        }
        
        // Show loading state
        document.getElementById('loading').style.display = 'block';
        document.getElementById('results').style.display = 'none';
        
        // Send analysis request
        ws.send(JSON.stringify({
            type: 'analyze_paper',
            pmid: pmid
        }));
    }

    // Initialize UI elements
    function initializeUI() {
        const messageInput = document.getElementById('message-input');
        const sendButton = document.getElementById('send-button');
        const analyzeButton = document.querySelector('button[onclick="analyzePaper()"]');

        if (sendButton) {
            sendButton.addEventListener('click', sendMessage);
        }
        if (messageInput) {
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') sendMessage();
            });
        }
        if (analyzeButton) {
            analyzeButton.removeAttribute('onclick');
            analyzeButton.addEventListener('click', analyzePaper);
        }
    }

    // Initialize everything
    initializeUI();
    initWebSocket();

    function sendMessage() {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            console.error('WebSocket is not connected');
            showError('Cannot send message: WebSocket is not connected');
            return;
        }
        
        const messageInput = document.getElementById('message-input');
        if (!messageInput) {
            console.error('Message input element not found');
            return;
        }
        
        const message = messageInput.value.trim();
        if (!message) return;
        
        addMessage('You', message, 'user-message');
        messageInput.value = '';
        
        try {
            ws.send(JSON.stringify({
                content: message,
                currentPaper: currentPaper
            }));
        } catch (error) {
            console.error('Error sending message:', error);
            showError('Failed to send message');
        }
    }

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