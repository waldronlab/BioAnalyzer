// Global variables
window.chatHistory = [];
window.ws = null;
window.isConnected = false;

// Immediately define the function globally
window.analyzeForCuration = async function() {
    
    const fileInput = document.getElementById('fileInput');
    const singlePmid = document.getElementById('singlePmid').value.trim();
    const batchPmids = document.getElementById('batchPmids').value.trim();
    
    // Check if any input is provided
    if (!fileInput.files.length && !singlePmid && !batchPmids) {
        alert('Please provide input: upload a file, enter a PMID, or provide a list of PMIDs');
        return;
    }
    
    // Show loading state
    showLoading();
    
    try {
        let results = [];
        
        // Handle file upload
        if (fileInput.files.length > 0) {
            results = await handleFileUpload(fileInput.files[0]);
        }
        // Handle single PMID
        else if (singlePmid) {
            results = await handleSinglePmid(singlePmid);
        }
        // Handle batch PMIDs
        else if (batchPmids) {
            results = await handleBatchPmids(batchPmids);
        }
        
        // Display results
        displayResults(results);
        
    } catch (error) {
        console.error('Error in analysis:', error);
        showError(`Analysis failed: ${error.message}`);
    } finally {
        hideLoading();
    }
};

// Handle file upload
async function handleFileUpload(file) {
    // Validate file before upload
    if (!file) {
        throw new Error('No file selected');
    }
    
    // Check file type - support CSV and Excel files
    const allowedExtensions = ['.csv', '.xls', '.xlsx'];
    const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    
    if (!allowedExtensions.includes(fileExtension)) {
        throw new Error('Please select a CSV or Excel file (.csv, .xls, .xlsx)');
    }
    
    // Check file size (max 10MB for Excel files)
    const maxSize = fileExtension === '.csv' ? 5 * 1024 * 1024 : 10 * 1024 * 1024;
    if (file.size > maxSize) {
        const maxSizeMB = maxSize / (1024 * 1024);
        throw new Error(`File size must be less than ${maxSizeMB}MB`);
    }
    
    console.log('Uploading file:', file.name, 'Size:', file.size, 'bytes', 'Type:', file.type, 'Extension:', fileExtension);
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/upload_csv', {
            method: 'POST',
            body: formData
        });
        
        console.log('Upload response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Upload failed:', response.status, errorText);
            
            // Try to parse error details
            let errorMessage = `Upload failed (${response.status})`;
            try {
                const errorData = JSON.parse(errorText);
                if (errorData.detail) {
                    errorMessage = errorData.detail;
                }
            } catch (e) {
                if (errorText) {
                    errorMessage += `: ${errorText}`;
                }
            }
            
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }
        
        console.log('Upload successful, results:', data);
        return data.results || [];
        
    } catch (error) {
        console.error('File upload error:', error);
        throw error;
    }
}

// Handle single PMID
async function handleSinglePmid(pmid) {
    try {
        // Show progress indicator
        showProgress('Retrieving paper metadata...', 25);
        
        // Create AbortController for timeout handling
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
        
        const response = await fetch(`/enhanced_analysis/${pmid}`, {
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            if (response.status === 408) {
                throw new Error('Request timed out. The analysis is taking longer than expected. Please try again.');
            } else if (response.status === 404) {
                throw new Error('Paper not found. Please verify the PMID is correct.');
            } else {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        }
        
        showProgress('Analyzing paper content...', 75);
        
        const data = await response.json();
        if (data.error) {
            // Enhanced error handling for Gemini API issues
            if (data.error_type && data.debug_info) {
                throw new Error(formatDetailedError(data.error, data.error_type, data.debug_info));
            } else {
                throw new Error(data.error);
            }
        }
        
        showProgress('Analysis complete!', 100);
        
        return [{
            pmid: pmid,
            title: data.title || 'N/A',
            enhanced_analysis: data.enhanced_analysis || {}
        }];
        
    } catch (error) {
        console.error('Error in handleSinglePmid:', error);
        if (error.name === 'AbortError') {
            throw new Error('Request timed out after 60 seconds. Please try again.');
        }
        throw error;
    }
}

// Format detailed error messages for better user understanding
function formatDetailedError(error, errorType, debugInfo) {
    let formattedError = `🚨 ${error}\n\n`;
    
    // Add error type information
    if (errorType) {
        formattedError += `📋 Error Type: ${errorType}\n`;
    }
    
    // Add debug information
    if (debugInfo) {
        if (debugInfo.issue) {
            formattedError += `🔍 Issue: ${debugInfo.issue}\n`;
        }
        if (debugInfo.solution) {
            formattedError += `💡 Solution: ${debugInfo.solution}\n`;
        }
        if (debugInfo.suggestions && Array.isArray(debugInfo.suggestions)) {
            formattedError += `💡 Suggestions:\n`;
            debugInfo.suggestions.forEach(suggestion => {
                formattedError += `   • ${suggestion}\n`;
            });
        }
        if (debugInfo.timestamp) {
            formattedError += `⏰ Timestamp: ${debugInfo.timestamp}\n`;
        }
    }
    
    // Add common troubleshooting steps for Gemini API issues
    if (errorType && (errorType.includes('API') || errorType.includes('Gemini'))) {
        formattedError += `\n🔧 Common Troubleshooting Steps:\n`;
        formattedError += `   1. Check your Gemini API key in environment variables\n`;
        formattedError += `   2. Verify your IP address is not restricted\n`;
        formattedError += `   3. Check your API quota usage\n`;
        formattedError += `   4. Ensure your API key has proper permissions\n`;
        formattedError += `   5. Check network connectivity\n`;
    }
    
    return formattedError;
}

// Handle batch PMIDs
async function handleBatchPmids(pmidsText) {
    const pmids = pmidsText.split(/[,\n]/).map(pmid => pmid.trim()).filter(pmid => pmid);
    
    if (pmids.length === 0) {
        throw new Error('No valid PMIDs found');
    }
    
    // Validate PMIDs are numeric
    const invalidPmids = pmids.filter(pmid => !/^\d+$/.test(pmid));
    if (invalidPmids.length > 0) {
        throw new Error(`Invalid PMIDs found: ${invalidPmids.join(', ')}. PMIDs must be numeric.`);
    }
    
    // Try the enhanced endpoint first
    try {
        const response = await fetch('/enhanced_analysis_batch', {
                method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(pmids)  // Send the list directly, not wrapped in an object
        });
        
            if (!response.ok) {
            const errorText = await response.text();
            
            // If enhanced fails, try the regular batch endpoint
            const regularResponse = await fetch('/analyze_batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(pmids)
            });
            
            if (!regularResponse.ok) {
                const regularErrorText = await regularResponse.text();
                throw new Error(`Both batch endpoints failed. Enhanced: ${response.status}, Regular: ${regularResponse.status}`);
            }
            
            const regularData = await regularResponse.json();
            return regularData || [];
        }
        
        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }
        
        return data.batch_results || [];
            
        } catch (error) {
        throw error;
    }
}

// Show progress indicator
function showProgress(message, percentage) {
    const loadingElement = document.getElementById('loading');
    if (loadingElement) {
        loadingElement.innerHTML = `
            <div class="text-center">
                <div class="spinner-border text-primary mb-3" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div class="progress mb-3" style="height: 20px;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                         role="progressbar" 
                         style="width: ${percentage}%" 
                         aria-valuenow="${percentage}" 
                         aria-valuemin="0" 
                         aria-valuemax="100">
                        ${percentage}%
                    </div>
                </div>
                <p class="text-muted">${message}</p>
            </div>
        `;
        loadingElement.style.display = 'block';
    }
}

// Show loading state
function showLoading() {
    const loadingElement = document.getElementById('loading');
    const emptyStateElement = document.getElementById('empty-state');
    const resultsContentElement = document.getElementById('results-content');
    
    if (loadingElement) {
        loadingElement.innerHTML = `
            <div class="text-center">
                <div class="spinner-border text-primary mb-3" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="text-muted">Initializing analysis...</p>
            </div>
        `;
        loadingElement.style.display = 'block';
    }
    if (emptyStateElement) emptyStateElement.style.display = 'none';
    if (resultsContentElement) resultsContentElement.style.display = 'none';
}

// Hide loading state
function hideLoading() {
    const loadingElement = document.getElementById('loading');
    if (loadingElement) loadingElement.style.display = 'none';
}

// Show error message
function showError(message) {
    const resultsContent = document.getElementById('results-content');
    if (resultsContent) {
        // Format multi-line error messages
        const formattedMessage = message.replace(/\n/g, '<br>');
        
        resultsContent.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <div style="white-space: pre-line; font-family: monospace; font-size: 0.9em;">
                    ${formattedMessage}
                </div>
            </div>
        `;
        resultsContent.style.display = 'block';
    }
    
    const emptyState = document.getElementById('empty-state');
    if (emptyState) emptyState.style.display = 'none';
}

// Display results in the new format
function displayResults(results) {
    
    if (!results || results.length === 0) {
        showError('No results to display');
            return;
        }
        
    const resultsContent = document.getElementById('results-content');
    if (!resultsContent) {
        console.error('Results content element not found');
            return;
        }
        
    // Create results HTML
    let resultsHTML = `
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h4 class="mb-0">
                <i class="fas fa-chart-bar me-2"></i>Analysis Results
            </h4>
            <div>
                <button class="btn btn-outline-success btn-sm me-2" onclick="exportResults()">
                    <i class="fas fa-download me-2"></i>Export CSV
                </button>
                <button class="btn btn-outline-secondary btn-sm" onclick="clearResults()">
                    <i class="fas fa-trash me-2"></i>Clear
                </button>
            </div>
            </div>
        
        <div class="row">
            <div class="col-md-6">
                <div class="card bg-light">
                    <div class="card-body text-center">
                        <h5 class="card-title">Papers Analyzed</h5>
                        <h2 class="text-primary">${results.length}</h2>
                </div>
                    </div>
                    </div>
            <div class="col-md-6">
                <div class="card bg-light">
                    <div class="card-body text-center">
                        <h5 class="card-title">Ready for Curation</h5>
                        <h2 class="text-success">${results.filter(r => r.enhanced_analysis?.curation_ready).length}</h2>
            </div>
            </div>
                </div>
            </div>
        `;
        
    // Add individual paper results
    results.forEach((result, index) => {
        const analysis = result.enhanced_analysis || {};
        const curationReady = analysis.curation_ready ? 'Yes' : 'No';
        
        resultsHTML += `
            <div class="card mt-3">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">
                        <strong>PMID ${result.pmid}</strong> - ${result.title || 'N/A'}
                    </h6>
                    <span class="badge ${analysis.curation_ready ? 'bg-success' : 'bg-warning'}">
                        Curation Ready: ${curationReady}
                    </span>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <div class="field-card">
                                <h6><i class="fas fa-dna me-2"></i>Host Species</h6>
                                <p class="mb-1"><strong>Value:</strong> ${analysis.host_species?.primary || 'Unknown'}</p>
                                <p class="mb-1"><strong>Status:</strong> <span class="status-${analysis.host_species?.status?.toLowerCase() || 'absent'}">${analysis.host_species?.status || 'ABSENT'}</span></p>
                                <p class="mb-1"><strong>Confidence:</strong> ${(analysis.host_species?.confidence || 0).toFixed(2)}</p>
                </div>
                </div>
                        <div class="col-md-6">
                            <div class="field-card">
                                <h6><i class="fas fa-map-marker-alt me-2"></i>Body Site</h6>
                                <p class="mb-1"><strong>Value:</strong> ${analysis.body_site?.site || 'Unknown'}</p>
                                <p class="mb-1"><strong>Status:</strong> <span class="status-${analysis.body_site?.status?.toLowerCase() || 'absent'}">${analysis.body_site?.status || 'ABSENT'}</span></p>
                                <p class="mb-1"><strong>Confidence:</strong> ${(analysis.body_site?.confidence || 0).toFixed(2)}</p>
            </div>
                </div>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <div class="field-card">
                                <h6><i class="fas fa-stethoscope me-2"></i>Condition</h6>
                                <p class="mb-1"><strong>Value:</strong> ${analysis.condition?.description || 'Unknown'}</p>
                                <p class="mb-1"><strong>Status:</strong> <span class="status-${analysis.condition?.status?.toLowerCase() || 'absent'}">${analysis.condition?.status || 'ABSENT'}</span></p>
                                <p class="mb-1"><strong>Confidence:</strong> ${(analysis.condition?.confidence || 0).toFixed(2)}</p>
                </div>
                    </div>
                        <div class="col-md-6">
                            <div class="field-card">
                                <h6><i class="fas fa-microscope me-2"></i>Sequencing Type</h6>
                                <p class="mb-1"><strong>Value:</strong> ${analysis.sequencing_type?.method || 'Unknown'}</p>
                                <p class="mb-1"><strong>Status:</strong> <span class="status-${analysis.condition?.status?.toLowerCase() || 'absent'}">${analysis.sequencing_type?.status || 'ABSENT'}</span></p>
                                <p class="mb-1"><strong>Confidence:</strong> ${(analysis.sequencing_type?.confidence || 0).toFixed(2)}</p>
                </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <div class="field-card">
                                <h6><i class="fas fa-sitemap me-2"></i>Taxa Level</h6>
                                <p class="mb-1"><strong>Value:</strong> ${analysis.taxa_level?.level || 'Unknown'}</p>
                                <p class="mb-1"><strong>Status:</strong> <span class="status-${analysis.taxa_level?.status?.toLowerCase() || 'absent'}">${analysis.taxa_level?.status || 'ABSENT'}</span></p>
                                <p class="mb-1"><strong>Confidence:</strong> ${(analysis.taxa_level?.confidence || 0).toFixed(2)}</p>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="field-card">
                                <h6><i class="fas fa-hashtag me-2"></i>Sample Size</h6>
                                <p class="mb-1"><strong>Value:</strong> ${analysis.sample_size?.size || 'Unknown'}</p>
                                <p class="mb-1"><strong>Status:</strong> <span class="status-${analysis.sample_size?.status?.toLowerCase() || 'absent'}">${analysis.sample_size?.status || 'ABSENT'}</span></p>
                                <p class="mb-1"><strong>Confidence:</strong> ${(analysis.sample_size?.confidence || 0).toFixed(2)}</p>
                    </div>
                </div>
            </div>
            
                    ${analysis.missing_fields && analysis.missing_fields.length > 0 ? `
                        <div class="alert alert-warning mt-3">
                            <h6><i class="fas fa-exclamation-triangle me-2"></i>Missing Fields</h6>
                            <p class="mb-1"><strong>Fields to review:</strong> ${analysis.missing_fields.join(', ')}</p>
                            <p class="mb-0"><strong>Summary:</strong> ${analysis.curation_preparation_summary || 'Review required'}</p>
                        </div>
                    ` : ''}
                    
                    ${analysis.error ? `
                        <div class="alert alert-danger mt-3">
                            <h6><i class="fas fa-exclamation-circle me-2"></i>Analysis Error</h6>
                            <p class="mb-1"><strong>Error Type:</strong> ${analysis.error_type || 'Unknown'}</p>
                            <p class="mb-1"><strong>Error:</strong> ${analysis.error}</p>
                            ${analysis.debug_info ? `
                                <details class="mt-2">
                                    <summary><strong>Debug Information</strong></summary>
                                    <div class="mt-2 p-2 bg-light rounded" style="font-family: monospace; font-size: 0.8em;">
                                        ${Object.entries(analysis.debug_info).map(([key, value]) => 
                                            `<div><strong>${key}:</strong> ${value}</div>`
                                        ).join('')}
                                    </div>
                                </details>
                            ` : ''}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    });
    
    resultsContent.innerHTML = resultsHTML;
    resultsContent.style.display = 'block';
    
    const emptyState = document.getElementById('empty-state');
    if (emptyState) emptyState.style.display = 'none';
    
}

// Export results to CSV
window.exportResults = function() {
    // Implementation for CSV export
    alert('CSV export functionality will be implemented here');
};

// Clear results
window.clearResults = function() {
    document.getElementById('results-content').style.display = 'none';
    document.getElementById('empty-state').style.display = 'block';
    
    // Clear input fields
    document.getElementById('fileInput').value = '';
    document.getElementById('singlePmid').value = '';
    document.getElementById('batchPmids').value = '';
};

// Legacy functions for backward compatibility (can be removed later)
window.analyzeSinglePaper = window.analyzeForCuration;
window.analyzeBatchPapers = window.analyzeForCuration;

    // Chat helper functions
    function handleChatKeyPress(event) {
        if (event.key === 'Enter') {
            sendMessage();
        }
    }

    function sendMessage() {
        const messageInput = document.getElementById('chat-input');
        if (!messageInput) return;
        
        const message = messageInput.value.trim();
        if (!message) return;
        
        // For now, just display the message (WebSocket functionality can be added later)
        displayChatMessage(message, 'user');
        messageInput.value = '';
        
        // Simulate a response (replace with actual AI chat later)
        setTimeout(() => {
            displayChatMessage('Thank you for your message. The chat assistant is currently being configured.', 'assistant');
        }, 1000);
    }

    function displayChatMessage(message, role) {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `mb-3 ${role === 'user' ? 'text-end' : 'text-start'}`;
        
        const messageBubble = document.createElement('div');
        messageBubble.className = `d-inline-block p-2 rounded ${role === 'user' ? 'bg-primary text-white' : 'bg-light'}`;
        messageBubble.style.maxWidth = '70%';
        messageBubble.textContent = message;
        
        messageDiv.appendChild(messageBubble);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    
    // Initialize chat functionality
    const messageInput = document.getElementById('chat-input');
    if (messageInput) {
        messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
    
    // Initialize tab functionality
    const tabLinks = document.querySelectorAll('.nav-tabs .nav-link');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    tabLinks.forEach(tab => {
        tab.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remove active class from all tabs and panes
            tabLinks.forEach(t => t.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active', 'show'));
            
            // Add active class to clicked tab
            this.classList.add('active');
            
            // Find and activate corresponding pane
            const targetId = this.getAttribute('data-bs-target');
            const targetPane = document.querySelector(targetId);
            if (targetPane) {
                targetPane.classList.add('active', 'show');
            }
        });
    });
    
});

// Clean up function to prevent memory leaks
window.addEventListener('beforeunload', function() {
    // Clean up any pending operations
    if (window.ws) {
        window.ws.close();
    }
    
    // Remove event listeners
    const messageInput = document.getElementById('chat-input');
    if (messageInput) {
        messageInput.removeEventListener('keydown', handleChatKeyPress);
    }
    
});

// Also define functions in global scope for compatibility
window.showLoading = showLoading;
window.hideLoading = hideLoading;
window.showError = showError;
window.displayResults = displayResults;