// Global variables
window.chatHistory = [];
window.ws = null;
window.isConnected = false;
window.latestResults = []; // holds the most recent analysis results shown in UI

// ---------------------------------------------------------------------------
// Default frontend configuration (merged with backend config if available)
// ---------------------------------------------------------------------------
const defaultConfig = {
    frontend: {
        apiBaseUrl: '/api/v1',
        analysisTimeout: 30000, // 30 seconds default
        model: {
            hidden_size: 768,
            num_hidden_layers: 6,
            num_attention_heads: 12,
            intermediate_size: 3072,
        },
    },
};

// Global configuration (timeouts preserved from existing app expectations)
let appConfig = {
    // Keep the existing timeouts structure for backward compatibility
    timeouts: {
        frontend: 180000, // Default 180 seconds in milliseconds
        gemini: 90000, // Default 90 seconds in milliseconds
        analysis: 30000, // Default 30 seconds in milliseconds
    },
    // Start with default frontend config; fetchConfig will merge real values
    frontend: { ...defaultConfig.frontend },
};

// Fetch configuration from backend and merge into defaults
async function fetchConfig() {
    try {
        const response = await fetch('/api/v1/config');
        if (!response.ok) {
            console.warn('Config endpoint returned non-OK status:', response.status);
            return appConfig;
        }

        const config = await response.json();

        // Merge frontend config if provided by the backend
        if (config.frontend) {
            appConfig.frontend = { ...defaultConfig.frontend, ...config.frontend };
        }

        // Support legacy/timeouts section in seconds -> convert to ms
        if (config.timeouts) {
            appConfig.timeouts = {
                frontend: (config.timeouts.frontend || appConfig.timeouts.frontend / 1000) * 1000,
                gemini: (config.timeouts.gemini || appConfig.timeouts.gemini / 1000) * 1000,
                analysis: (config.timeouts.analysis || appConfig.timeouts.analysis / 1000) * 1000,
            };
        }

        console.log('Configuration loaded and merged:', appConfig);
        return appConfig;
    } catch (error) {
        console.warn('Failed to load configuration, using defaults:', error);
        return appConfig;
    }
}

// Initialize configuration when the page loads and wire quick UI controls
document.addEventListener('DOMContentLoaded', async function() {
    await fetchConfig();

    // Bind optional analyze button (newer HTML may use #analyze-btn and #pmid-input)
    const analyzeButton = document.getElementById('analyze-btn');
    const pmidInput = document.getElementById('pmid-input') || document.getElementById('singlePmid');
    if (analyzeButton && pmidInput) {
        analyzeButton.addEventListener('click', async () => {
            const pmid = pmidInput.value.trim();
            if (!pmid) {
                showAlert('Please enter a valid PubMed ID.', 'warning');
                return;
            }
            showLoading();
            try {
                const results = await handleSinglePmid(pmid);
                displayResults(results);
            } catch (e) {
                console.error('Analysis error:', e);
            } finally {
                hideLoading();
            }
        });
    }
});

// Utility: Display alerts for user feedback
function showAlert(message, type = 'info') {
    const alertBox = document.getElementById('alert-box');
    if (alertBox) {
        alertBox.innerHTML = `
      <div class="alert ${type}">
        <strong>${type.toUpperCase()}:</strong> ${message}
      </div>
    `;
    } else {
        alert(message);
    }
}

// Immediately define the function globally
window.analyzePapers = async function() {
    
    const fileInput = document.getElementById('fileInput');
    const singlePmid = document.getElementById('singlePmid').value.trim();
    const batchPmids = document.getElementById('batchPmids').value.trim();
    
    // Check if any input is provided
    if (!fileInput.files.length && !singlePmid && !batchPmids) {
        showError('Please provide input: upload a file, enter a PMID, or provide a list of PMIDs');
        return;
    }
    
    // Ensure we have the latest configuration
    await fetchConfig();
    
    // Show loading state
    showLoading();
    
    try {
        let results = [];
        
        // Handle file upload
        if (fileInput.files.length > 0) {
            showProgress('Processing file...', 10);
            results = await handleFileUpload(fileInput.files[0]);
        }
        // Handle single PMID
        else if (singlePmid) {
            showProgress('Starting analysis...', 10);
            results = await handleSinglePmid(singlePmid);
        }
        // Handle batch PMIDs
        else if (batchPmids) {
            showProgress('Processing batch...', 10);
            results = await handleBatchPmids(batchPmids);
        }
        
        // Display results
        displayResults(results);
        
    } catch (error) {
        console.error('Error in analysis:', error);
        let errorMessage = error.message;
        
        // Provide more user-friendly error messages
        if (error.message.includes('timeout')) {
            errorMessage = 'Analysis timed out. This can happen with complex papers. Please try again.';
        } else if (error.message.includes('404')) {
            errorMessage = 'Paper not found. Please verify the PMID is correct.';
        } else if (error.message.includes('500')) {
            errorMessage = 'Server error occurred. Please try again later.';
        } else if (error.message.includes('AbortError')) {
            errorMessage = 'Request was cancelled. Please try again.';
        }
        
        showError(`Analysis failed: ${errorMessage}`);
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
        const response = await fetch('/api/v1/upload_csv', {
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
        
        // If upload returned PMIDs, kick off streaming batch analysis automatically
        const pmids = Array.isArray(data.pmids) ? data.pmids : [];
        if (pmids.length > 0) {
            showProgress('Starting batch analysis (streaming)...', 15);
            const results = await analyzeBatchStreaming(pmids);
            return results;
        }
        
        // If no PMIDs present, nothing to analyze
        return [];
        
    } catch (error) {
        console.error('File upload error:', error);
        throw error;
    }
}

// Handle single PMID (call original enhanced_analysis endpoint and keep timeout/progress handling)
async function handleSinglePmid(pmid) {
    try {
        // Ensure we have the latest configuration
        await fetchConfig();

        // Prefer frontend-configured timeout if present, otherwise fallback to legacy timeouts
        const timeout = (appConfig.frontend && appConfig.frontend.analysisTimeout) || appConfig.timeouts.analysis || 30000;

        showProgress('Retrieving paper metadata...', 25);

        const controller = new AbortController();
        console.log('Using analysis timeout:', timeout, 'ms (', timeout / 1000, 'seconds)');

        // Declare timeout and interval variables outside try block for error handling
        let timeoutId;
        let progressInterval;

        try {
            timeoutId = setTimeout(() => controller.abort(), timeout);

            const startTime = Date.now();

            // Add progress updates during the request
            progressInterval = setInterval(() => {
                const currentProgress = Math.min(75, 25 + (Date.now() - startTime) / (timeout * 0.75) * 50);
                showProgress('Analyzing paper content...', Math.round(currentProgress));
            }, 2000); // Update every 2 seconds

            // Keep the original API endpoint unchanged
            const response = await fetch(`/api/v1/enhanced_analysis/${pmid}`, {
                signal: controller.signal,
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
            });

            // Clear timeout and interval immediately after response
            clearTimeout(timeoutId);
            clearInterval(progressInterval);

            if (!response.ok) {
                if (response.status === 408) {
                    throw new Error('Request timed out. The analysis is taking longer than expected. Please try again.');
                } else if (response.status === 404) {
                    throw new Error('Paper not found. Please verify the PMID is correct.');
                } else if (response.status === 500) {
                    throw new Error('Server error occurred during analysis. Please try again later.');
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
                enhanced_analysis: data.enhanced_analysis || data
            }];
        } catch (innerError) {
            // Clear timeout and interval in case of error
            if (timeoutId) clearTimeout(timeoutId);
            if (progressInterval) clearInterval(progressInterval);
            throw innerError;
        }

    } catch (error) {
        console.error('Error in handleSinglePmid:', error);

        if (error.name === 'AbortError') {
            const timeoutSeconds = Math.round(((appConfig.frontend && appConfig.frontend.analysisTimeout) || appConfig.timeouts.analysis || 30000) / 1000);
            showAlert(`Analysis timed out after ${timeoutSeconds} seconds. Try again later.`, 'warning');
            throw new Error('AbortError');
        }

        showAlert(`Analysis failed: ${error.message}`, 'error');
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
        const response = await fetch('/api/v1/enhanced_analysis_batch', {
                method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(pmids)  // Send the list directly, not wrapped in an object
        });
        
            if (!response.ok) {
            const errorText = await response.text();
            
            // If enhanced fails, try the regular batch endpoint
            const regularResponse = await fetch('/api/v1/analyze_batch', {
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

// Escape HTML meta-characters in a string
function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/\//g, '&#x2F;');
}

// Show error message
function showError(message) {
    const resultsContent = document.getElementById('results-content');
    if (resultsContent) {
        // Escape and format multi-line error messages
        const safeMessage = escapeHtml(message).replace(/\n/g, '<br>');

        resultsContent.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <div style="white-space: pre-line; font-family: monospace; font-size: 0.9em;">
                    ${safeMessage}
                </div>
            </div>
        `;
        resultsContent.style.display = 'block';
    }

    const emptyState = document.getElementById('empty-state');
    if (emptyState) emptyState.style.display = 'none';
}

// Append a single result card (incremental rendering)
function renderResultCard(result) {
    const analysis = (result && result.enhanced_analysis) || {};
    return `
        <div class="card mt-3">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h6 class="mb-0">
                    <strong>PMID ${result.pmid || ''}</strong> - ${result.title ? escapeHtml(result.title) : 'N/A'}
                </h6>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <div class="field-card">
                            <h6><i class="fas fa-dna me-2"></i>Host Species</h6>
                            <p class="mb-1"><strong>Value:</strong> ${analysis.host_species?.primary || analysis.host_species?.value || 'Unknown'}</p>
                            <p class="mb-1"><strong>Status:</strong> <span class="status-${analysis.host_species?.status?.toLowerCase() || 'absent'}">${analysis.host_species?.status || 'ABSENT'}</span></p>
                            <p class="mb-1"><strong>Confidence:</strong> ${(analysis.host_species?.confidence || 0).toFixed(2)}</p>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="field-card">
                            <h6><i class="fas fa-map-marker-alt me-2"></i>Body Site</h6>
                            <p class="mb-1"><strong>Value:</strong> ${analysis.body_site?.site || analysis.body_site?.value || 'Unknown'}</p>
                            <p class="mb-1"><strong>Status:</strong> <span class="status-${analysis.body_site?.status?.toLowerCase() || 'absent'}">${analysis.body_site?.status || 'ABSENT'}</span></p>
                            <p class="mb-1"><strong>Confidence:</strong> ${(analysis.body_site?.confidence || 0).toFixed(2)}</p>
                        </div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-md-6">
                        <div class="field-card">
                            <h6><i class="fas fa-stethoscope me-2"></i>Condition</h6>
                            <p class="mb-1"><strong>Value:</strong> ${analysis.condition?.description || analysis.condition?.value || 'Unknown'}</p>
                            <p class="mb-1"><strong>Status:</strong> <span class="status-${analysis.condition?.status?.toLowerCase() || 'absent'}">${analysis.condition?.status || 'ABSENT'}</span></p>
                            <p class="mb-1"><strong>Confidence:</strong> ${(analysis.condition?.confidence || 0).toFixed(2)}</p>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="field-card">
                            <h6><i class="fas fa-microscope me-2"></i>Sequencing Type</h6>
                            <p class="mb-1"><strong>Value:</strong> ${analysis.sequencing_type?.method || analysis.sequencing_type?.value || 'Unknown'}</p>
                            <p class="mb-1"><strong>Status:</strong> <span class="status-${analysis.sequencing_type?.status?.toLowerCase() || 'absent'}">${analysis.sequencing_type?.status || 'ABSENT'}</span></p>
                            <p class="mb-1"><strong>Confidence:</strong> ${(analysis.sequencing_type?.confidence || 0).toFixed(2)}</p>
                        </div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-md-6">
                        <div class="field-card">
                            <h6><i class="fas fa-sitemap me-2"></i>Taxa Level</h6>
                            <p class="mb-1"><strong>Value:</strong> ${analysis.taxa_level?.level || analysis.taxa_level?.value || 'Unknown'}</p>
                            <p class="mb-1"><strong>Status:</strong> <span class="status-${analysis.taxa_level?.status?.toLowerCase() || 'absent'}">${analysis.taxa_level?.status || 'ABSENT'}</span></p>
                            <p class="mb-1"><strong>Confidence:</strong> ${(analysis.taxa_level?.confidence || 0).toFixed(2)}</p>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="field-card">
                            <h6><i class="fas fa-hashtag me-2"></i>Sample Size</h6>
                            <p class="mb-1"><strong>Value:</strong> ${analysis.sample_size?.size || analysis.sample_size?.value || 'Unknown'}</p>
                            <p class="mb-1"><strong>Status:</strong> <span class="status-${analysis.sample_size?.status?.toLowerCase() || 'absent'}">${analysis.sample_size?.status || 'ABSENT'}</span></p>
                            <p class="mb-1"><strong>Confidence:</strong> ${(analysis.sample_size?.confidence || 0).toFixed(2)}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>`;
}

function appendResult(result) {
    const resultsContent = document.getElementById('results-content');
    const emptyState = document.getElementById('empty-state');
    const loadingElement = document.getElementById('loading');

    if (emptyState) emptyState.style.display = 'none';
    if (loadingElement) loadingElement.style.display = 'none';

    if (resultsContent && resultsContent.style.display !== 'block') {
        resultsContent.innerHTML = `
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
                <div class="col-md-12">
                    <div class="card bg-light">
                        <div class="card-body text-center">
                            <h5 class="card-title">Papers Analyzed</h5>
                            <h2 class="text-primary" id="results-count">0</h2>
                        </div>
                    </div>
                </div>
            </div>
        `;
        resultsContent.style.display = 'block';
    }

    // Append card
    resultsContent.innerHTML += renderResultCard(result);

    // Store in latestResults for export
    if (Array.isArray(window.latestResults)) {
        window.latestResults.push(result);
    } else {
        window.latestResults = [result];
    }

    // Update counter
    const countEl = document.getElementById('results-count');
    if (countEl) {
        const current = parseInt(countEl.textContent || '0', 10) || 0;
        countEl.textContent = String(current + 1);
    }
}

// Stream analysis results via SSE and append as they arrive
async function analyzeBatchStreaming(pmids) {
    return new Promise((resolve, reject) => {
        const results = [];
        const url = `/api/v1/enhanced_analysis_batch_stream?pmids=${encodeURIComponent(pmids.join(','))}&max_concurrent=1`;
        const es = new EventSource(url);

        es.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data && data.pmid) {
                    appendResult(data);
                    results.push(data);
                }
            } catch (e) {
                console.warn('Failed to parse streaming event:', e);
            }
        };

        es.addEventListener('done', () => {
            es.close();
            resolve(results);
        });

        es.onerror = (err) => {
            console.warn('Streaming error:', err);
            try { es.close(); } catch {}
            // Resolve whatever we have so far
            resolve(results);
        };
    });
}

// Display results in the new format
function displayResults(results) {
    // Keep a canonical copy for export
    if (Array.isArray(results)) {
        window.latestResults = results.slice();
    }
    
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
            <div class="col-md-12">
                <div class="card bg-light">
                    <div class="card-body text-center">
                        <h5 class="card-title">Papers Analyzed</h5>
                        <h2 class="text-primary">${results.length}</h2>
                    </div>
                </div>
            </div>
        </div>
        `;
        
    // Add individual paper results
    results.forEach((result, index) => {
        const analysis = result.enhanced_analysis || {};
        
        resultsHTML += `
            <div class="card mt-3">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">
                        <strong>PMID ${result.pmid}</strong> - ${result.title || 'N/A'}
                    </h6>
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
    try {
        const rows = Array.isArray(window.latestResults) ? window.latestResults : [];
        if (rows.length === 0) {
            showAlert('No results to export yet.', 'warning');
            return;
        }
        // Build CSV header
        const header = [
            'pmid','title',
            'host_species.value','host_species.status','host_species.confidence',
            'body_site.value','body_site.status','body_site.confidence',
            'condition.value','condition.status','condition.confidence',
            'sequencing_type.value','sequencing_type.status','sequencing_type.confidence',
            'taxa_level.value','taxa_level.status','taxa_level.confidence',
            'sample_size.value','sample_size.status','sample_size.confidence'
        ];

        function val(obj, path, altKeys=[]) {
            try {
                let v = obj;
                for (const k of path.split('.')) {
                    if (v == null) return '';
                    v = v[k];
                }
                if (v == null && altKeys.length) {
                    for (const ak of altKeys) {
                        const av = obj?.enhanced_analysis?.[ak]?.value;
                        if (av != null) return String(av);
                    }
                }
                return v == null ? '' : String(v);
            } catch { return ''; }
        }

        // CSV escape
        const esc = (s) => {
            const x = String(s ?? '');
            if (/[,"\n]/.test(x)) return '"' + x.replace(/"/g, '""') + '"';
            return x;
        };

        // Build data rows
        const lines = [header.join(',')];
        for (const r of rows) {
            const a = r?.enhanced_analysis || {};
            const line = [
                esc(r.pmid || ''),
                esc(r.title || ''),
                esc(a.host_species?.value ?? a.host_species?.primary ?? ''),
                esc(a.host_species?.status ?? ''),
                esc(a.host_species?.confidence ?? ''),
                esc(a.body_site?.value ?? a.body_site?.site ?? ''),
                esc(a.body_site?.status ?? ''),
                esc(a.body_site?.confidence ?? ''),
                esc(a.condition?.value ?? a.condition?.description ?? ''),
                esc(a.condition?.status ?? ''),
                esc(a.condition?.confidence ?? ''),
                esc(a.sequencing_type?.value ?? a.sequencing_type?.method ?? ''),
                esc(a.sequencing_type?.status ?? ''),
                esc(a.sequencing_type?.confidence ?? ''),
                esc(a.taxa_level?.value ?? a.taxa_level?.level ?? ''),
                esc(a.taxa_level?.status ?? ''),
                esc(a.taxa_level?.confidence ?? ''),
                esc(a.sample_size?.value ?? a.sample_size?.size ?? ''),
                esc(a.sample_size?.status ?? ''),
                esc(a.sample_size?.confidence ?? ''),
            ];
            lines.push(line.join(','));
        }

        const csv = lines.join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const ts = new Date().toISOString().replace(/[:.]/g, '-');
        a.download = `bioanalyzer_results_${ts}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        console.error('Export failed:', e);
        showAlert('Export failed. See console for details.', 'error');
    }
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
window.analyzeSinglePaper = window.analyzePapers;
window.analyzeBatchPapers = window.analyzePapers;

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
            displayChatMessage('Thank you for your message. The assistant is being configured.', 'assistant');
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