document.addEventListener('DOMContentLoaded', () => {
    // Initialize state
    let currentUser = null;
    let ws = null;
    let currentPaper = null;
    let isAnalyzing = false;

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
            'tokens-generated'
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

    // DOM Elements
    const loginScreen = document.getElementById('login-screen');
    const usernameInput = document.getElementById('username');
    const startChatButton = document.getElementById('start-chat');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const analyzeButton = document.querySelector('button[onclick="analyzePaper()"]');

    // Event Listeners
    if (startChatButton) {
        startChatButton.addEventListener('click', startChat);
    }
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

    // Chat Functions
    async function startChat() {
        if (!usernameInput) return;
        const username = usernameInput.value.trim();
        if (!username) {
            alert('Please enter your name');
            return;
        }
        
        try {
            const response = await fetch(`/start_session/${username}`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                throw new Error(`Failed to start session: ${response.status}`);
            }
            currentUser = username;
            if (loginScreen) loginScreen.classList.add('hidden');
            document.getElementById('main-interface').classList.remove('hidden');
            
            // Add welcome message
            addMessage('Assistant', 'Welcome! How can I help you today?', 'assistant');
            
            // Setup WebSocket
            setupWebSocket();
        } catch (error) {
            console.error('Error starting chat:', error);
            alert('Error starting chat: ' + error.message);
        }
    }

    function setupWebSocket() {
        if (ws && ws.readyState === WebSocket.OPEN) {
            console.log('WebSocket already connected');
            return;
        }

        const encodedUsername = encodeURIComponent(currentUser);
        ws = new WebSocket(`ws://${window.location.host}/ws/${encodedUsername}`);
        
        ws.onopen = () => {
            console.log('Connected to WebSocket');
            updateConnectionStatus(true);
            addMessage('System', 'Connected to chat server', 'system-message');
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.error) {
                    addMessage('Error', data.error, 'error-message');
                } else if (data.response) {
                    addMessage('Assistant', data.response, 'assistant-message');
                }
            } catch (error) {
                console.error('Error processing message:', error);
                addMessage('Error', 'Error processing message', 'error-message');
            }
        };

        ws.onclose = (event) => {
            console.log('WebSocket connection closed:', event.code, event.reason);
            updateConnectionStatus(false);
            addMessage('System', 'Disconnected from chat server', 'system-message');
            ws = null;

            // Only attempt to reconnect if the close wasn't intentional
            if (event.code !== 1000) {
                setTimeout(() => {
                    console.log('Attempting to reconnect...');
                    setupWebSocket();
                }, 3000);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            addMessage('Error', 'Connection error occurred', 'error-message');
        };
    }

    function updateConnectionStatus(connected) {
        const status = document.getElementById('connection-status');
        if (status) {
            status.textContent = connected ? 'Connected' : 'Disconnected';
            status.className = connected ? 'alert alert-success mb-3' : 'alert alert-danger mb-3';
        }
        if (messageInput) messageInput.disabled = !connected;
        if (sendButton) sendButton.disabled = !connected;
    }

    function addMessage(sender, content, type = 'assistant') {
        const container = document.getElementById('chat-container');
        if (!container) return;
        const messageDiv = document.createElement('div');
        const timestamp = new Date().toLocaleTimeString();
        
        messageDiv.className = `message ${type}-message`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        if (type !== 'system' && type !== 'error') {
            const senderSpan = document.createElement('div');
            senderSpan.className = 'message-sender';
            senderSpan.textContent = sender;
            messageContent.appendChild(senderSpan);
        }
        
        const textSpan = document.createElement('div');
        textSpan.className = 'message-text';
        textSpan.textContent = content;
        messageContent.appendChild(textSpan);
        
        const timeSpan = document.createElement('div');
        timeSpan.className = 'message-time';
        timeSpan.textContent = timestamp;
        messageContent.appendChild(timeSpan);
        
        messageDiv.appendChild(messageContent);
        container.appendChild(messageDiv);
        
        const clearDiv = document.createElement('div');
        clearDiv.style.clear = 'both';
        container.appendChild(clearDiv);
        
        container.scrollTop = container.scrollHeight;
    }

    function sendMessage() {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            console.log('WebSocket not connected, attempting to reconnect...');
            setupWebSocket();
            setTimeout(() => sendMessage(), 1000); // Retry after connection attempt
            return;
        }

        const messageInput = document.getElementById('message-input');
        if (!messageInput) return;

        const message = messageInput.value.trim();
        if (!message) return;

        try {
            ws.send(JSON.stringify({ content: message }));
            addMessage('You', message, 'user-message');
            messageInput.value = '';
        } catch (error) {
            console.error('Error sending message:', error);
            addMessage('Error', 'Failed to send message', 'error-message');
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

    async function analyzePaper() {
        if (!checkElements()) {
            alert('Error: Some required page elements are missing. Please refresh the page.');
            return;
        }

        const pmid = document.getElementById('pmid').value.trim();
        if (!pmid) {
            alert('Please enter a PubMed ID');
            return;
        }

        try {
            isAnalyzing = true;
            document.getElementById('loading').style.display = 'block';
            document.getElementById('results').style.display = 'none';

            console.log('Fetching analysis for PMID:', pmid);
            const response = await fetch(`/analyze/${pmid}`);
            const data = await response.json();
            console.log('Full API Response:', data);
            
            // Hide loading message immediately after getting response
            document.getElementById('loading').style.display = 'none';

            if (data.error) {
                throw new Error(data.error);
            }

            currentPaper = pmid;

            // Update paper metadata
            document.getElementById('paper-title').textContent = data.metadata.title || 'No title available';
            document.getElementById('paper-authors').textContent = Array.isArray(data.metadata.authors)
                ? data.metadata.authors.join(', ')
                : (data.metadata.authors || 'No authors available');
            document.getElementById('paper-journal').textContent = 
                `${data.metadata.journal || 'Unknown Journal'} (${data.metadata.publication_date || 'No date'})`;
            document.getElementById('paper-date').textContent = data.metadata.publication_date || 'Not available';
            document.getElementById('paper-doi').textContent = data.metadata.doi || 'Not available';
            document.getElementById('paper-abstract').textContent = data.metadata.abstract || 'No abstract available';

            // Update confidence bar
            const confidence = data.analysis?.confidence || 0;
            const confidenceFill = document.getElementById('confidence-fill');
            if (confidenceFill) {
                confidenceFill.style.width = `${confidence * 100}%`;
                document.getElementById('confidence-value').textContent = 
                    `${(confidence * 100).toFixed(1)}%`;
            }

            // Update category scores
            console.log('Category scores from API:', data.analysis?.category_scores);
            if (data.analysis?.category_scores) {
                updateCategoryScores(data.analysis.category_scores);
            } else {
                updateCategoryScores({});
            }

            // Update found terms
            const foundTermsDiv = document.getElementById('found-terms');
            if (foundTermsDiv) {
                foundTermsDiv.innerHTML = '';
                const foundTerms = data.analysis?.found_terms || {};
                
                Object.entries(foundTerms).forEach(([category, terms]) => {
                    if (terms && terms.length > 0) {
                        const categoryDiv = document.createElement('div');
                        categoryDiv.className = 'mb-3';
                        categoryDiv.innerHTML = `<h6 class="text-muted mb-2">${category}:</h6>`;
                        const termsContainer = document.createElement('div');
                        termsContainer.className = 'd-flex flex-wrap gap-2';
                        terms.forEach(term => {
                            const termSpan = document.createElement('span');
                            termSpan.className = 'found-term';
                            termSpan.textContent = term;
                            termsContainer.appendChild(termSpan);
                        });
                        categoryDiv.appendChild(termsContainer);
                        foundTermsDiv.appendChild(categoryDiv);
                    }
                });

                if (foundTermsDiv.children.length === 0) {
                    foundTermsDiv.innerHTML = '<p class="text-muted">No terms found</p>';
                }
            }

            // Update key findings
            const keyFindingsDiv = document.getElementById('key-findings');
            if (keyFindingsDiv) {
                const findings = Array.isArray(data.analysis?.key_findings) ? data.analysis.key_findings : [];
                if (findings.length > 0) {
                    const findingsList = document.createElement('ul');
                    findingsList.className = 'list-unstyled';
                    findings.forEach(finding => {
                        if (finding && typeof finding === 'string' && finding.trim()) {
                            const li = document.createElement('li');
                            li.className = 'mb-2 finding-item';
                            li.innerHTML = `<i class="fas fa-${data.analysis.warning ? 'info text-info' : 'check text-success'} me-2"></i>${finding.trim()}`;
                            findingsList.appendChild(li);
                        }
                    });
                    keyFindingsDiv.innerHTML = '';
                    keyFindingsDiv.appendChild(findingsList);
                } else {
                    keyFindingsDiv.innerHTML = '<p class="text-muted">No findings available</p>';
                }
            }

            // Update suggested topics
            const suggestedTopicsDiv = document.getElementById('suggested-topics');
            if (suggestedTopicsDiv) {
                suggestedTopicsDiv.innerHTML = '';
                const topics = data.analysis?.suggested_topics || [];
                if (topics.length > 0) {
                    const topicsContainer = document.createElement('div');
                    topicsContainer.className = 'd-flex flex-wrap gap-2';
                    topics.forEach(topic => {
                        const badge = document.createElement('span');
                        badge.className = 'badge bg-secondary';
                        badge.textContent = topic;
                        topicsContainer.appendChild(badge);
                    });
                    suggestedTopicsDiv.appendChild(topicsContainer);
                } else {
                    suggestedTopicsDiv.innerHTML = '<p class="text-muted">No suggested topics available</p>';
                }
            }

            // Update analysis status and tokens
            const statusElement = document.getElementById('analysis-status');
            if (statusElement) {
                statusElement.textContent = data.analysis?.status || 'Unknown';
            }
            const tokensElement = document.getElementById('tokens-generated');
            if (tokensElement) {
                tokensElement.textContent = data.analysis?.num_tokens || '0';
            }

            // Show results with animation
            const results = document.getElementById('results');
            if (results) {
                results.style.display = 'block';
                results.style.opacity = '0';
                requestAnimationFrame(() => {
                    results.style.opacity = '1';
                });
            }

        } catch (error) {
            console.error('Error analyzing paper:', error);
            alert('Error analyzing paper: ' + error.message);
        } finally {
            isAnalyzing = false;
            document.getElementById('loading').style.display = 'none';
        }
    }

    // Initialize WebSocket connection if needed
    if (document.getElementById('chat-container')) {
        setupWebSocket();
    }
});