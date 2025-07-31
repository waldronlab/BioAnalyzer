console.log("app.js loaded!");

// File upload function for PMIDs - defined globally for immediate access
window.uploadPmidsFile = async function() {
    const fileInput = document.getElementById('pmid-file-upload');
    const statusDiv = document.getElementById('upload-status');
    
    if (!fileInput || !fileInput.files.length) {
        if (statusDiv) {
            statusDiv.innerHTML = '<div class="alert alert-warning">Please select a file first.</div>';
        }
        return;
    }
    
    const file = fileInput.files[0];
    
    // Validate file type
    if (!file.name.toLowerCase().endsWith('.xls') && !file.name.toLowerCase().endsWith('.xlsx')) {
        if (statusDiv) {
            statusDiv.innerHTML = '<div class="alert alert-danger">Please select an Excel file (.xls or .xlsx).</div>';
        }
        return;
    }
    
    // Show loading status
    if (statusDiv) {
        statusDiv.innerHTML = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin me-2"></i>Uploading and analyzing file...</div>';
    }
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/upload_pmids_file', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.error) {
            if (statusDiv) {
                statusDiv.innerHTML = `<div class="alert alert-danger">Error: ${result.error}</div>`;
            }
            return;
        }
        
        // Display results
        if (statusDiv) {
            statusDiv.innerHTML = `
                <div class="alert alert-success">
                    <h6><i class="fas fa-check-circle me-2"></i>${result.message}</h6>
                    <p>Found ${result.pmids.length} PMIDs in the file.</p>
                </div>
            `;
        }
        
        // Update browse state with the results
        if (window.browsePapersState) {
            window.browsePapersState.allPmids = result.pmids;
            window.browsePapersState.filteredPmids = result.pmids;
            window.browsePapersState.page = 1;
            window.browsePapersState.loadedPages = {};
            window.browsePapersState.uploadedResults = result.results;
        }
        
        // Display the results in the table
        if (typeof displayUploadedResults === 'function') {
            displayUploadedResults(result.results);
        }
        
    } catch (error) {
        console.error('Error uploading file:', error);
        if (statusDiv) {
            statusDiv.innerHTML = `<div class="alert alert-danger">Error uploading file: ${error.message}</div>`;
        }
    }
};

// Initialize browse papers state globally
window.browsePapersState = {
    allPmids: [], // store all PMIDs
    loadedPages: {}, // cache loaded pages: {pageNum: [papers]}
    filteredPmids: [], // PMIDs after filtering
    filters: {
        curationStatus: '',
        host: '',
        keyword: '',
        year: '',
        sequencingType: ''
    },
    page: 1,
    pageSize: 20
};

// Function to display uploaded results - defined globally
window.displayUploadedResults = function(results) {
    if (!results || !results.length) {
        const container = document.getElementById('browse-table-container');
        if (container) {
            container.innerHTML = '<div class="alert alert-info">No results to display.</div>';
        }
        return;
    }
    
    let html = '<table class="table table-bordered table-hover"><thead><tr>' +
        '<th>PMID</th><th>Title</th><th>Authors</th><th>Journal</th><th>Year</th>' +
        '<th>Host</th><th>Body Site</th><th>Sequencing Type</th><th>Curation Status</th><th>Actions</th></tr></thead><tbody>';
    
    for (const paper of results) {
        // Enhanced curation status display
        let statusBadge = '';
        let statusText = paper.curation_status || 'Unknown';
        
        switch (statusText) {
            case 'already_curated':
                statusBadge = '<span class="badge bg-success">Already Curated</span>';
                break;
            case 'ready':
                statusBadge = '<span class="badge bg-primary">Ready for Curation</span>';
                break;
            case 'not_ready':
                statusBadge = '<span class="badge bg-warning">Not Ready</span>';
                break;
            case 'not_found':
                statusBadge = '<span class="badge bg-secondary">Not Found</span>';
                break;
            case 'error':
                statusBadge = '<span class="badge bg-danger">Error</span>';
                break;
            default:
                statusBadge = '<span class="badge bg-secondary">Unknown</span>';
        }
        
        // Add confidence score if available
        let confidenceInfo = '';
        if (paper.confidence) {
            const confidence = (paper.confidence * 100).toFixed(1);
            confidenceInfo = `<br><small class="text-muted">Confidence: ${confidence}%</small>`;
        }
        
        html += `<tr>
            <td>${paper.pmid}</td>
            <td>${paper.title || 'N/A'}</td>
            <td>${paper.authors || 'N/A'}</td>
            <td>${paper.journal || 'N/A'}</td>
            <td>${paper.year || 'N/A'}</td>
            <td>${paper.host || 'N/A'}</td>
            <td>${paper.body_site || 'N/A'}</td>
            <td>${paper.sequencing_type || 'N/A'}</td>
            <td>${statusBadge}${confidenceInfo}</td>
            <td><button class="btn btn-sm btn-info" onclick="viewPaperDetails('${paper.pmid}', event)">Details</button></td>
        </tr>`;
    }
    
    html += '</tbody></table>';
    
    // Add summary statistics
    const stats = {
        total: results.length,
        already_curated: results.filter(p => p.curation_status === 'already_curated').length,
        ready: results.filter(p => p.curation_status === 'ready').length,
        not_ready: results.filter(p => p.curation_status === 'not_ready').length,
        not_found: results.filter(p => p.curation_status === 'not_found').length,
        error: results.filter(p => p.curation_status === 'error').length
    };
    
    const summaryHtml = `
        <div class="card mb-3">
            <div class="card-header">
                <h6 class="mb-0"><i class="fas fa-chart-bar me-2"></i>Summary Statistics</h6>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-2">
                        <div class="text-center">
                            <h4 class="text-primary">${stats.total}</h4>
                            <small class="text-muted">Total Papers</small>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="text-center">
                            <h4 class="text-success">${stats.already_curated}</h4>
                            <small class="text-muted">Already Curated</small>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="text-center">
                            <h4 class="text-primary">${stats.ready}</h4>
                            <small class="text-muted">Ready for Curation</small>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="text-center">
                            <h4 class="text-warning">${stats.not_ready}</h4>
                            <small class="text-muted">Not Ready</small>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="text-center">
                            <h4 class="text-secondary">${stats.not_found}</h4>
                            <small class="text-muted">Not Found</small>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="text-center">
                            <h4 class="text-danger">${stats.error}</h4>
                            <small class="text-muted">Errors</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    const container = document.getElementById('browse-table-container');
    if (container) {
        container.innerHTML = summaryHtml + html;
    }
};

// Export functions - defined globally for immediate access
window.exportBrowseResults = function() {
    // Check if we have uploaded results first
    if (window.browsePapersState.uploadedResults && window.browsePapersState.uploadedResults.length > 0) {
        const results = window.browsePapersState.uploadedResults;
        const headers = ['PMID','Title','Authors','Journal','Year','Host','Body Site','Sequencing Type','Curation Status'];
        const rows = results.map(p => [
            p.pmid, p.title || '', p.authors || '', p.journal || '', p.year || '', 
            p.host || '', p.body_site || '', p.sequencing_type || '', p.curation_status || ''
        ]);
        let csv = headers.join(',') + '\n';
        rows.forEach(row => {
            csv += row.map(val => '"' + (val ? ('' + val).replace(/"/g, '""') : '') + '"').join(',') + '\n';
        });
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'uploaded_pmids_results.csv';
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 100);
        return;
    }
    
    // Check if we have loaded papers in the current page
    const currentPage = window.browsePapersState.page || 1;
    const loadedPages = window.browsePapersState.loadedPages || {};
    const papers = loadedPages[currentPage];
    
    if (!papers || !papers.length) {
        alert('No papers to export. Please load papers first by clicking "Load All Papers" or upload an Excel file with PMIDs.');
        return;
    }
    
    const headers = ['PMID','Title','Authors','Journal','Year','Host','Body Site','Sequencing Type','Curation Status'];
    const rows = papers.map(p => [
        p.pmid, p.title || '', p.authors || '', p.journal || '', p.year || '', 
        p.host || '', p.body_site || '', p.sequencing_type || '', p.curation_status || ''
    ]);
    let csv = headers.join(',') + '\n';
    rows.forEach(row => {
        csv += row.map(val => '"' + (val ? ('' + val).replace(/"/g, '""') : '') + '"').join(',') + '\n';
    });
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'filtered_papers.csv';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, 100);
};

// Enhanced export function for curation reports
window.exportCurationReport = function() {
    // Check if we have uploaded results first
    if (window.browsePapersState.uploadedResults && window.browsePapersState.uploadedResults.length > 0) {
        const results = window.browsePapersState.uploadedResults;
        const headers = [
            'PMID', 'Title', 'Authors', 'Journal', 'Year', 'Host', 'Body Site', 
            'Sequencing Type', 'Curation Status', 'Curation Status Message', 
            'In BugSigDB', 'Curated', 'Confidence Score', 'Key Findings'
        ];
        
        const rows = results.map(p => [
            p.pmid,
            p.title || '',
            p.authors || '',
            p.journal || '',
            p.year || '',
            p.host || '',
            p.body_site || '',
            p.sequencing_type || '',
            p.curation_status || '',
            p.curation_status_message || '',
            p.in_bugsigdb ? 'Yes' : 'No',
            p.curated ? 'Yes' : 'No',
            p.confidence ? (p.confidence * 100).toFixed(1) + '%' : '',
            p.key_findings ? p.key_findings.join('; ') : ''
        ]);
        
        let csv = headers.join(',') + '\n';
        rows.forEach(row => {
            csv += row.map(val => '"' + (val ? ('' + val).replace(/"/g, '""') : '') + '"').join(',') + '\n';
        });
        
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `curation_report_uploaded_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 100);
        return;
    }
    
    // Check if we have loaded papers in the current page
    const currentPage = window.browsePapersState.page || 1;
    const loadedPages = window.browsePapersState.loadedPages || {};
    const papers = loadedPages[currentPage];
    
    if (!papers || !papers.length) {
        alert('No papers to export. Please load papers first by clicking "Load All Papers" or upload an Excel file with PMIDs.');
        return;
    }
    
    const headers = [
        'PMID', 'Title', 'Authors', 'Journal', 'Year', 'Host', 'Body Site', 
        'Sequencing Type', 'Curation Status', 'Curation Status Message', 
        'In BugSigDB', 'Curated', 'Confidence Score', 'Key Findings'
    ];
    
    const rows = papers.map(p => [
        p.pmid,
        p.title || '',
        p.authors || '',
        p.journal || '',
        p.year || '',
        p.host || '',
        p.body_site || '',
        p.sequencing_type || '',
        p.curation_status || '',
        p.curation_status_message || '',
        p.in_bugsigdb ? 'Yes' : 'No',
        p.curated ? 'Yes' : 'No',
        p.confidence ? (p.confidence * 100).toFixed(1) + '%' : '',
        p.key_findings ? p.key_findings.join('; ') : ''
    ]);
    
    let csv = headers.join(',') + '\n';
    rows.forEach(row => {
        csv += row.map(val => '"' + (val ? ('' + val).replace(/"/g, '""') : '') + '"').join(',') + '\n';
    });
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `curation_report_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, 100);
};

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded: Initializing app.js and page settings');
    // Initialize state
    let ws = null;
    let currentPaper = null;
    let isAnalyzing = false;
    let isConnected = false;
    let userName = null;
    let currentPaperMeta = null;
    let lastUserMessage = '';
    let chatPaperContext = null;
    let chatHistory = [];

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
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            ws = new WebSocket(wsUrl);
            ws.onopen = function() {
                isConnected = true;
                updateConnectionStatus('Connected', 'success');
                // Show welcome message if chat is empty
                const chatContainer = document.getElementById('chat-container');
                if (chatContainer && chatContainer.children.length === 1) { // Only download button present
                    displayChatMessage('Hey there! How can I help you today?', 'assistant');
                }
            };
            ws.onclose = function() {
                isConnected = false;
                updateConnectionStatus('Disconnected', 'danger');
            };
            ws.onerror = function(error) {
                isConnected = false;
                updateConnectionStatus('Connection failed', 'danger');
            };
            // Add onmessage handler to display assistant replies
            ws.onmessage = function(event) {
                console.log("Received from backend:", event.data);
                console.log("[DEBUG] lastUserMessage before handling:", lastUserMessage);
                try {
                    const data = JSON.parse(event.data);
                    if (data.response) {
                        displayChatMessage(data.response, 'assistant');
                        // Only display confidence if user asked for it
                        let showConfidence = false;
                        if (
                            data.confidence !== undefined && data.confidence !== null &&
                            typeof lastUserMessage === 'string' &&
                            /confidence|how sure|certainty|how certain/i.test(lastUserMessage)
                        ) {
                            showConfidence = true;
                        }
                        console.log('[DEBUG] showConfidence:', showConfidence, '| lastUserMessage:', lastUserMessage);
                        if (showConfidence) {
                            displayChatMessage(`Confidence: ${(data.confidence * 100).toFixed(1)}%`, 'system');
                        }
                        lastUserMessage = '';
                    } else if (data.error) {
                        displayChatMessage("Error: " + data.error, 'error');
                    }
                } catch (e) {
                    console.error("Error parsing WebSocket message:", e, event.data);
                }
            };
        } catch (error) {
            isConnected = false;
            updateConnectionStatus('Connection failed', 'danger');
        }
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
        console.log('[displayAnalysisResults] Data:', data);
        
        // Show curation status at the top
        let resultsDiv = getElement('results');
        if (resultsDiv) {
            let curationStatusDiv = document.getElementById('curation-status');
            if (!curationStatusDiv) {
                curationStatusDiv = document.createElement('div');
                curationStatusDiv.id = 'curation-status';
                curationStatusDiv.className = 'mb-3';
                resultsDiv.insertBefore(curationStatusDiv, resultsDiv.firstChild);
            }
            // Set badge color and text
            let statusMsg = data.curation_status_message || '';
            let badgeClass = 'alert-secondary';
            if (data.curated) badgeClass = 'alert-success';
            else if (data.in_bugsigdb) badgeClass = 'alert-warning';
            else if (statusMsg.toLowerCase().includes('ready')) badgeClass = 'alert-primary';
            else if (statusMsg.toLowerCase().includes('not ready')) badgeClass = 'alert-danger';
            curationStatusDiv.className = `alert ${badgeClass} mb-3`;
            curationStatusDiv.textContent = statusMsg;
            if (data.missing_curation_fields && data.missing_curation_fields.length > 0 && !data.curated) {
                curationStatusDiv.textContent += ' (Missing: ' + data.missing_curation_fields.join(', ') + ')';
            }
        }

        // Display enhanced curation analysis if available
        if (data.analysis && data.analysis.curation_analysis) {
            if (typeof displayEnhancedCurationAnalysis === 'function') {
                displayEnhancedCurationAnalysis(data.analysis.curation_analysis);
            } else {
                console.warn('Enhanced curation analysis display function not available');
            }
        } else {
            // Clear curation analysis display if no data
            if (typeof clearCurationAnalysis === 'function') {
                clearCurationAnalysis();
            }
        }

        // Show top-level warning or error if present (suppress duplicates)
        resultsDiv = getElement('results');
        if (resultsDiv) {
            // Remove previous alerts
            const oldAlerts = resultsDiv.querySelectorAll('.backend-alert');
            oldAlerts.forEach(el => el.remove());
            // Only show the first available error/warning
            let shown = false;
            if (!shown && data.error) {
                const errDiv = document.createElement('div');
                errDiv.className = 'alert alert-danger backend-alert';
                errDiv.innerHTML = `<strong>Error:</strong> <span style="font-size:1.05em;">${data.error}</span>`;
                if (data.full_text_type) {
                    errDiv.innerHTML += `<br><small>Full text type: <code>${data.full_text_type}</code></small>`;
                }
                resultsDiv.insertBefore(errDiv, resultsDiv.firstChild);
                shown = true;
            } else if (!shown && data.warning) {
                const warnDiv = document.createElement('div');
                warnDiv.className = 'alert alert-warning backend-alert';
                warnDiv.innerHTML = `<strong>Warning:</strong> <span style="font-size:1.05em;">${data.warning}</span>`;
                resultsDiv.insertBefore(warnDiv, resultsDiv.firstChild);
                shown = true;
            } else if (!shown && data.analysis?.error) {
                const errDiv = document.createElement('div');
                errDiv.className = 'alert alert-danger backend-alert';
                errDiv.innerHTML = `<strong>Analysis Error:</strong> <span style="font-size:1.05em;">${data.analysis.error}</span>`;
                resultsDiv.insertBefore(errDiv, resultsDiv.firstChild);
                shown = true;
            } else if (!shown && data.analysis?.warning) {
                const warnDiv = document.createElement('div');
                warnDiv.className = 'alert alert-warning backend-alert';
                warnDiv.innerHTML = `<strong>Analysis Warning:</strong> <span style="font-size:1.05em;">${data.analysis.warning}</span>`;
                resultsDiv.insertBefore(warnDiv, resultsDiv.firstChild);
                shown = true;
            }
        }

        // Update paper metadata (always show, with fallback)
        const titleEl = getElement('paper-title');
        const authorsEl = getElement('paper-authors');
        const journalEl = getElement('paper-journal');
        const abstractEl = getElement('paper-abstract');
        const dateEl = getElement('paper-date');
        const doiEl = getElement('paper-doi');
        const dateDetailEl = getElement('paper-date-detail');
        const doiDetailEl = getElement('paper-doi-detail');
        if (titleEl) {
            titleEl.textContent = data.metadata?.title || 'No data available';
        }
        if (authorsEl) {
            authorsEl.textContent = data.metadata?.authors || 'No data available';
        }
        if (journalEl) {
            journalEl.textContent = data.metadata?.journal || 'No data available';
        }
        if (abstractEl) {
            abstractEl.textContent = data.metadata?.abstract || 'No data available';
        }
        if (dateEl) {
            dateEl.textContent = data.metadata?.publication_date || 'No data available';
        }
        if (doiEl) {
            doiEl.textContent = data.metadata?.doi || 'No data available';
        }
        if (dateDetailEl) {
            dateDetailEl.textContent = data.metadata?.publication_date || 'No data available';
        }
        if (doiDetailEl) {
            doiDetailEl.textContent = data.metadata?.doi || 'No data available';
        }

        // Show MeSH Terms and Publication Types in a prominent section
        const meshTermsSection = document.getElementById('mesh-terms-section');
        if (meshTermsSection) {
            let html = '';
            if (data.metadata?.mesh_terms && data.metadata.mesh_terms.length > 0) {
                html += `<h6 class="mb-2">MeSH Terms</h6><div class="d-flex flex-wrap gap-2">${data.metadata.mesh_terms.map(term => `<span class="badge bg-secondary">${term}</span>`).join('')}</div>`;
            }
            if (data.metadata?.publication_types && data.metadata.publication_types.length > 0) {
                html += `<h6 class="mb-2 mt-3">Publication Types</h6><div class="d-flex flex-wrap gap-2">${data.metadata.publication_types.map(type => `<span class="badge bg-info">${type}</span>`).join('')}</div>`;
            }
            meshTermsSection.innerHTML = html;
        }

        // Update paper analysis details table (always show, with fallback)
        const pmidEl = getElement('paper-pmid');
        const journalShortEl = getElement('paper-journal-short');
        const titleShortEl = getElement('paper-title-short');
        const yearEl = getElement('paper-year');
        const hostEl = getElement('paper-host');
        const bodySiteEl = getElement('paper-body-site');
        const conditionEl = getElement('paper-condition');
        const sequencingTypeEl = getElement('paper-sequencing-type');
        const inBugSigDBEl = getElement('paper-in-bugsigdb');
        const signatureProbEl = getElement('paper-signature-prob');
        const sampleSizeEl = getElement('paper-sample-size');
        const taxaLevelEl = getElement('paper-taxa-level');
        const statMethodEl = getElement('paper-statistical-method');
        if (pmidEl) pmidEl.textContent = data.metadata?.pmid || 'No data available';
        if (journalShortEl) journalShortEl.textContent = data.metadata?.journal || 'No data available';
        if (titleShortEl) titleShortEl.textContent = data.metadata?.title || 'No data available';
        if (yearEl) yearEl.textContent = data.metadata?.year || 'No data available';
        if (hostEl) hostEl.textContent = data.metadata?.host || 'No data available';
        if (bodySiteEl) bodySiteEl.textContent = data.metadata?.body_site || 'No data available';
        if (conditionEl) conditionEl.textContent = data.metadata?.condition || 'No data available';
        if (sequencingTypeEl) sequencingTypeEl.textContent = data.metadata?.sequencing_type || 'No data available';
        // Only use the top-level in_bugsigdb boolean or string for display
        if (inBugSigDBEl) {
            console.log('in_bugsigdb value:', data.in_bugsigdb);
            if (typeof data.in_bugsigdb === 'boolean') {
                inBugSigDBEl.textContent = data.in_bugsigdb ? 'Yes' : 'No';
            } else if (typeof data.in_bugsigdb === 'string') {
                const val = data.in_bugsigdb.trim().toLowerCase();
                inBugSigDBEl.textContent = ['true', 'yes', '1', 'y'].includes(val) ? 'Yes' : 'No';
            } else {
                inBugSigDBEl.textContent = 'No data available';
            }
        }
        if (signatureProbEl) signatureProbEl.textContent = data.metadata?.signature_probability || 'No data available';
        if (sampleSizeEl) sampleSizeEl.textContent = data.metadata?.sample_size || 'No data available';
        if (taxaLevelEl) taxaLevelEl.textContent = data.metadata?.taxa_level || 'No data available';
        if (statMethodEl) statMethodEl.textContent = data.metadata?.statistical_method || 'No data available';

        // Update confidence score (show fallback if missing)
        const confidenceFill = getElement('confidence-fill');
        const confidenceValue = getElement('confidence-value');
        if (confidenceFill && confidenceValue) {
            if (data.analysis?.confidence !== undefined && data.analysis?.confidence !== null) {
                const confidence = data.analysis.confidence * 100;
                confidenceFill.style.width = `${confidence}%`;
                confidenceFill.className = `progress-bar ${getScoreColor(data.analysis.confidence)}`;
                confidenceValue.textContent = `${confidence.toFixed(1)}%`;
            } else {
                confidenceFill.style.width = '0%';
                confidenceFill.className = 'progress-bar bg-secondary';
                confidenceValue.textContent = 'No data available';
            }
        }

        // Update category scores (show fallback if missing)
        if (data.analysis?.category_scores && Object.keys(data.analysis.category_scores).length > 0) {
            updateCategoryScores(data.analysis.category_scores);
        } else {
            const categoryScoresDiv = getElement('category-scores');
            if (categoryScoresDiv) {
                categoryScoresDiv.innerHTML = '<span class="text-muted">No category scores available</span>';
            }
        }

        // Update key findings (show fallback if missing)
        const keyFindingsEl = getElement('key-findings');
        if (keyFindingsEl) {
            if (data.analysis?.key_findings && data.analysis.key_findings.length > 0) {
                let html = '';
                
                data.analysis.key_findings.forEach(finding => {
                    // Check if this is a heading (contains ** at start and end)
                    if (finding.startsWith('**') && finding.endsWith('**')) {
                        // This is a heading - remove ** and make it bold without checkmark
                        const headingText = finding.replace(/\*\*/g, '');
                        html += `<li class="finding-heading mb-3"><strong>${headingText}</strong></li>`;
                    } else {
                        // This is a regular finding - add checkmark
                        html += `<li class="mb-2"><i class="fas fa-check-circle text-success me-2"></i>${finding}</li>`;
                    }
                });
                
                keyFindingsEl.innerHTML = html;
            } else {
                keyFindingsEl.innerHTML = '<li class="text-muted">No key findings available</li>';
            }
        }

        // Update suggested topics (show fallback if missing)
        const suggestedTopicsEl = getElement('suggested-topics');
        if (suggestedTopicsEl) {
            if (data.analysis?.suggested_topics && data.analysis.suggested_topics.length > 0) {
                let html = '';
                
                data.analysis.suggested_topics.forEach(topic => {
                    // Check if this is a heading (contains ** at start and end)
                    if (topic.startsWith('**') && topic.endsWith('**')) {
                        // This is a heading - remove ** and make it bold without tag icon
                        const headingText = topic.replace(/\*\*/g, '');
                        html += `<li class="topic-heading mb-3"><strong>${headingText}</strong></li>`;
                    } else {
                        // This is a regular topic - add tag icon
                        html += `<li class="mb-2"><i class="fas fa-tag text-primary me-2"></i>${topic}</li>`;
                    }
                });
                
                suggestedTopicsEl.innerHTML = html;
            } else {
                suggestedTopicsEl.innerHTML = '<li class="text-muted">No suggested topics available</li>';
            }
        }

        // Update analysis status (show fallback if missing)
        const statusEl = getElement('analysis-status');
        if (statusEl) {
            if (data.analysis?.status) {
                statusEl.textContent = data.analysis.status;
                statusEl.className = `badge ${data.analysis.status === 'success' ? 'bg-success' : 'bg-danger'}`;
            } else {
                statusEl.textContent = 'No data available';
                statusEl.className = 'badge bg-secondary';
            }
        }

        // Update tokens generated (show fallback if missing)
        const tokensEl = getElement('tokens-generated');
        if (tokensEl) {
            if (data.analysis?.num_tokens !== undefined && data.analysis?.num_tokens !== null) {
                tokensEl.textContent = data.analysis.num_tokens;
            } else {
                tokensEl.textContent = 'No data available';
            }
        }

        // Show results container with smooth animation
        if (resultsDiv) {
            resultsDiv.style.display = 'block';
            resultsDiv.style.opacity = '0';
            resultsDiv.style.transform = 'translateY(20px)';
            setTimeout(() => {
                resultsDiv.style.opacity = '1';
                resultsDiv.style.transform = 'translateY(0)';
                resultsDiv.style.transition = 'all 0.4s ease-out';
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
        if (type === 'assistant') {
            chatHistory.push({ role: 'assistant', content: message });
        }
    }
    window.displayChatMessage = displayChatMessage;

    // Show error message
    function showError(message, errorObj = null) {
        console.error('Error:', message, errorObj);
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
        let detailsHtml = '';
        if (errorObj) {
            detailsHtml = `<details style="text-align:left;max-width:600px;overflow-x:auto;margin-top:8px;">
                <summary style="cursor:pointer;">Show technical details</summary>
                <pre>${typeof errorObj === 'object' ? JSON.stringify(errorObj, null, 2) : errorObj}</pre>
            </details>`;
        }
        errorContainer.innerHTML = `
            <strong style="font-size:1.1em;">Error:</strong> <span style="font-size:1.05em;">${message}</span>
            <button type="button" class="btn-close" style="float: right;" onclick="this.parentElement.style.display='none'"></button>
            ${detailsHtml}
        `;
        errorContainer.style.display = 'block';
        // Also show in results area if it exists
        const resultsDiv = document.getElementById('results');
        if (resultsDiv) {
            const resultsError = document.createElement('div');
            resultsError.className = 'alert alert-danger mt-3';
            resultsError.innerHTML = `<strong>Error:</strong> ${message}${detailsHtml}`;
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
        console.log("Analyze clicked, pmid:", pmid);
        if (!pmid) {
            showError('Please enter a PMID');
            return;
        }

        // Show enhanced loader immediately
        const loader = document.getElementById('loading');
        const analyzeBtn = document.getElementById('analyze-btn') || document.getElementById('analyze-button');
        const resultsDiv = document.getElementById('results');
        
        if (loader) {
            loader.style.display = 'block';
            loader.classList.add('loading-enhanced');
            loader.innerHTML = `
                <div class="text-center my-4">
                    <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-3 text-primary fw-bold">Analyzing Paper...</p>
                    <p class="text-muted">This may take a few moments as we process the paper content</p>
                </div>
            `;
        }
        if (analyzeBtn) {
            analyzeBtn.disabled = true;
            analyzeBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Analyzing...';
        }
        if (resultsDiv) {
            resultsDiv.style.display = 'block';
            resultsDiv.style.opacity = '0.5';
        }

        try {
            const response = await fetch(`/analyze/${pmid}`);
            console.log('[analyzePaper] Raw fetch response:', response);
            if (!response.ok) {
                const text = await response.text();
                console.error('[analyzePaper] Non-OK response:', response.status, text);
                throw new Error(`HTTP error! status: ${response.status} - ${text}`);
            }
            const data = await response.json();
            console.log('[analyzePaper] Parsed JSON:', data);
            if (!data || Object.keys(data).length === 0) {
                showError('No data returned from backend.');
                if (resultsDiv) {
                    resultsDiv.style.display = 'block';
                    resultsDiv.style.opacity = '1';
                }
                return;
            }
            displayAnalysisResults(data);
            if (resultsDiv) {
                resultsDiv.style.display = 'block';
                resultsDiv.style.opacity = '1';
            }
        } catch (error) {
            console.error('[analyzePaper] Analysis error:', error);
            showError(error.message || 'Failed to analyze paper');
            if (resultsDiv) {
                resultsDiv.style.display = 'block';
                resultsDiv.style.opacity = '1';
            }
        } finally {
            // Always hide loader and enable button
            if (loader) {
                loader.style.display = 'none';
            }
            if (analyzeBtn) {
                analyzeBtn.disabled = false;
                analyzeBtn.innerHTML = '<i class="fas fa-search me-2"></i>Analyze Paper';
            }
        }
    }

    // Send message
    function sendMessage() {
        const messageInput = document.getElementById('message-input');
        if (!messageInput || !ws || !isConnected) return;

        const message = messageInput.value.trim();
        if (!message) return;

        lastUserMessage = message; // Track last user message
        displayChatMessage(message, 'user');
        // Add to chat history
        chatHistory.push({ role: 'user', content: message });
        // Prepare context for backend
        let contextMessages = [];
        if (!chatPaperContext) {
            // Only send history if not in paper context
            contextMessages = chatHistory.slice(-10); // last 10 messages
        }
        ws.send(JSON.stringify({
            content: message,
            role: 'user',
            currentPaper: chatPaperContext ? chatPaperContext.pmid : null,
            paperContext: chatPaperContext || null,
            chatHistory: contextMessages
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
            console.log("Attaching analyzePaper to analyzeButton", analyzeButton);
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

    // Enhanced Tab Management
    function initializeEnhancedTabManagement() {
        const tabLinks = document.querySelectorAll('.nav-tabs .nav-link');
        const tabPanes = document.querySelectorAll('.tab-pane');
        
        // Add enhanced tab switching behavior
        tabLinks.forEach(tab => {
            tab.addEventListener('click', function(e) {
                e.preventDefault();
                
                // Remove active class from all tabs and panes
                tabLinks.forEach(t => t.classList.remove('active'));
                tabPanes.forEach(p => p.classList.remove('active'));
                
                // Add active class to clicked tab
                this.classList.add('active');
                
                // Find and activate corresponding pane
                const targetId = this.getAttribute('href') || this.getAttribute('data-bs-target');
                const targetPane = document.querySelector(targetId);
                if (targetPane) {
                    targetPane.classList.add('active');
                    
                    // Scroll to top of the newly active tab
                    setTimeout(() => {
                        targetPane.scrollTop = 0;
                        targetPane.focus();
                    }, 100);
                    
                    // Trigger custom event for tab activation
                    const event = new CustomEvent('tabActivated', {
                        detail: { tabId: targetId, tabElement: this, paneElement: targetPane }
                    });
                    document.dispatchEvent(event);
                }
            });
        });
        
        // Add visual feedback for tab interactions
        tabLinks.forEach(tab => {
            tab.addEventListener('mouseenter', function() {
                if (!this.classList.contains('active')) {
                    this.style.transform = 'translateY(-1px)';
                }
            });
            
            tab.addEventListener('mouseleave', function() {
                if (!this.classList.contains('active')) {
                    this.style.transform = 'translateY(0)';
                }
            });
        });
        
        // Handle keyboard navigation
        document.addEventListener('keydown', function(e) {
            if (e.ctrlKey || e.metaKey) {
                const activeTab = document.querySelector('.nav-tabs .nav-link.active');
                if (activeTab) {
                    const tabIndex = Array.from(tabLinks).indexOf(activeTab);
                    
                    switch(e.key) {
                        case '1':
                        case '2':
                        case '3':
                        case '4':
                            const targetIndex = parseInt(e.key) - 1;
                            if (targetIndex < tabLinks.length) {
                                e.preventDefault();
                                tabLinks[targetIndex].click();
                            }
                            break;
                        case 'ArrowLeft':
                            e.preventDefault();
                            const prevIndex = (tabIndex - 1 + tabLinks.length) % tabLinks.length;
                            tabLinks[prevIndex].click();
                            break;
                        case 'ArrowRight':
                            e.preventDefault();
                            const nextIndex = (tabIndex + 1) % tabLinks.length;
                            tabLinks[nextIndex].click();
                            break;
                    }
                }
            }
        });
        
        // Auto-focus management for active tab content
        document.addEventListener('tabActivated', function(e) {
            const pane = e.detail.paneElement;
            
            // Focus the first interactive element in the active tab
            setTimeout(() => {
                const firstFocusable = pane.querySelector('input, button, select, textarea, [tabindex]:not([tabindex="-1"])');
                if (firstFocusable) {
                    firstFocusable.focus();
                }
            }, 150);
        });
        
        // Performance optimization: lazy load tab content
        tabPanes.forEach(pane => {
            if (!pane.classList.contains('active')) {
                pane.style.display = 'none';
            }
        });
        
        document.addEventListener('tabActivated', function(e) {
            const activePane = e.detail.paneElement;
            const inactivePanes = Array.from(tabPanes).filter(p => p !== activePane);
            
            // Show active pane
            activePane.style.display = 'block';
            
            // Hide inactive panes after animation
            setTimeout(() => {
                inactivePanes.forEach(pane => {
                    pane.style.display = 'none';
                });
            }, 300);
        });
        
        // Add tab indicators functionality
        function updateTabIndicators() {
            const activeTab = document.querySelector('.nav-tabs .nav-link.active');
            const allTabs = document.querySelectorAll('.nav-tabs .nav-link');
            
            allTabs.forEach(tab => {
                const indicator = tab.querySelector('.tab-indicator');
                if (indicator) {
                    if (tab === activeTab) {
                        indicator.style.width = '80%';
                        indicator.style.backgroundColor = '#0d6efd';
                    } else {
                        indicator.style.width = '0%';
                        indicator.style.backgroundColor = '#6ea8fe';
                    }
                }
            });
        }
        
        // Update indicators on tab switch
        document.addEventListener('tabActivated', updateTabIndicators);
        
        // Initialize indicators
        updateTabIndicators();
        
        // Add hover effects for tab indicators
        tabLinks.forEach(tab => {
            const indicator = tab.querySelector('.tab-indicator');
            if (indicator) {
                tab.addEventListener('mouseenter', function() {
                    if (!this.classList.contains('active')) {
                        indicator.style.width = '60%';
                        indicator.style.backgroundColor = '#6ea8fe';
                    }
                });
                
                tab.addEventListener('mouseleave', function() {
                    if (!this.classList.contains('active')) {
                        indicator.style.width = '0%';
                    }
                });
            }
        });
        
        // Add loading states for tab content
        function showTabLoading(tabId) {
            const pane = document.querySelector(tabId);
            if (pane) {
                pane.classList.add('loading');
            }
        }
        
        function hideTabLoading(tabId) {
            const pane = document.querySelector(tabId);
            if (pane) {
                pane.classList.remove('loading');
            }
        }
        
        // Expose loading functions globally
        window.showTabLoading = showTabLoading;
        window.hideTabLoading = hideTabLoading;
        
        // Add tab counter functionality
        function updateTabCounter(tabId, count) {
            const tab = document.querySelector(`[href="${tabId}"], [data-bs-target="${tabId}"]`);
            if (tab) {
                let counter = tab.querySelector('.tab-counter');
                if (!counter && count > 0) {
                    counter = document.createElement('span');
                    counter.className = 'tab-counter';
                    tab.appendChild(counter);
                }
                if (counter) {
                    counter.textContent = count;
                    counter.style.display = count > 0 ? 'flex' : 'none';
                }
            }
        }
        
        // Expose counter function globally
        window.updateTabCounter = updateTabCounter;
        
        // Add tab status indicators
        function setTabStatus(tabId, status) {
            const tab = document.querySelector(`[href="${tabId}"], [data-bs-target="${tabId}"]`);
            if (tab) {
                let statusIndicator = tab.querySelector('.tab-status');
                if (!statusIndicator) {
                    statusIndicator = document.createElement('span');
                    statusIndicator.className = 'tab-status';
                    tab.appendChild(statusIndicator);
                }
                
                // Set status color
                switch (status) {
                    case 'success':
                        statusIndicator.style.backgroundColor = '#28a745';
                        break;
                    case 'warning':
                        statusIndicator.style.backgroundColor = '#ffc107';
                        break;
                    case 'error':
                        statusIndicator.style.backgroundColor = '#dc3545';
                        break;
                    case 'info':
                        statusIndicator.style.backgroundColor = '#17a2b8';
                        break;
                    default:
                        statusIndicator.style.backgroundColor = '#6c757d';
                }
            }
        }
        
        // Expose status function globally
        window.setTabStatus = setTabStatus;
    }
    
    // Initialize enhanced tab management
    document.addEventListener('DOMContentLoaded', initializeEnhancedTabManagement);

    // Page Settings Event Handlers
    const fontSizeSlider = document.getElementById('fontSize');
    const fontSizeValue = document.getElementById('fontSizeValue');
    if (!fontSizeSlider || !fontSizeValue) {
        console.warn('Font size slider or value element missing');
    } else {
        fontSizeSlider.addEventListener('input', function() {
            const size = this.value;
            console.log('Font size changed to:', size);
            document.body.style.fontSize = size + 'px';
            fontSizeValue.textContent = size + 'px';
            localStorage.setItem('fontSize', size);
        });
    }
    const zoomSlider = document.getElementById('zoomLevel');
    const zoomValue = document.getElementById('zoomLevelValue');
    if (!zoomSlider || !zoomValue) {
        console.warn('Zoom slider or value element missing');
    } else {
        zoomSlider.addEventListener('input', function() {
            const zoom = this.value;
            console.log('Zoom level changed to:', zoom);
            document.body.style.zoom = zoom + '%';
            zoomValue.textContent = zoom + '%';
            localStorage.setItem('zoomLevel', zoom);
        });
    }
    const themeSelect = document.getElementById('themeSelect');
    if (!themeSelect) {
        console.warn('Theme select element missing');
    } else {
        themeSelect.addEventListener('change', function() {
            const theme = this.value;
            console.log('Theme changed to:', theme);
            document.body.classList.remove('dark', 'light');
            document.body.classList.add(theme);
            localStorage.setItem('theme', theme);
        });
    }
    // Load saved settings
    const savedFontSize = localStorage.getItem('fontSize') || '16';
    const savedZoom = localStorage.getItem('zoomLevel') || '100';
    const savedTheme = localStorage.getItem('theme') || 'light';
    if (fontSizeSlider && fontSizeValue) {
        fontSizeSlider.value = savedFontSize;
        document.body.style.fontSize = savedFontSize + 'px';
        fontSizeValue.textContent = savedFontSize + 'px';
    }
    if (zoomSlider && zoomValue) {
        zoomSlider.value = savedZoom;
        document.body.style.zoom = savedZoom + '%';
        zoomValue.textContent = savedZoom + '%';
    }
    if (themeSelect) {
        themeSelect.value = savedTheme;
        document.body.classList.remove('dark', 'light');
        document.body.classList.add(savedTheme);
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

    // Helper function to safely get element
    function getElement(id) {
        const element = document.getElementById(id);
        if (!element) {
            console.warn(`Element with id '${id}' not found`);
        }
        return element;
    }

    const analyzeButton = document.getElementById('analyze-button');
    if (analyzeButton) {
        analyzeButton.addEventListener('click', analyzePaper);
        console.log('Analyze button listener registered');
    } else {
        console.error('Analyze button not found');
    }
    initWebSocket();

    // Download chat as .txt file
    window.downloadChat = function() {
        const chatContainer = document.getElementById('chat-container');
        if (!chatContainer) return;
        const messages = chatContainer.querySelectorAll('.message, .system-message, .error-message');
        let chatText = '';
        messages.forEach(msg => {
            let sender = '';
            if (msg.classList.contains('user-message')) sender = 'You: ';
            else if (msg.classList.contains('assistant-message')) sender = 'Assistant: ';
            else if (msg.classList.contains('system-message')) sender = 'System: ';
            else if (msg.classList.contains('error-message')) sender = 'Error: ';
            chatText += sender + msg.textContent.trim() + '\n\n';
        });
        const blob = new Blob([chatText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'chat_history.txt';
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 100);
    }

    // Ensure chat input is enabled when chat tab is active
    function enableChatInput() {
        const messageInput = document.getElementById('message-input');
        const sendButton = document.getElementById('send-button');
        if (messageInput) messageInput.disabled = false;
        if (sendButton) sendButton.disabled = false;
    }

    // Listen for tab change to enable chat input and show personalized welcome
    const chatTab = document.getElementById('chat-tab');
    if (chatTab) {
        chatTab.addEventListener('click', enableChatInput);
        chatTab.addEventListener('click', showPersonalizedWelcome);
    }

    // Also enable chat input on DOMContentLoaded if chat tab is already active
    if (document.getElementById('chat').classList.contains('active')) {
        enableChatInput();
    }

    // Helper: display assistant message
    function displayAssistantMessage(msg) {
        displayChatMessage(msg, 'assistant');
    }

    // Helper: display user message
    function displayUserMessage(msg) {
        displayChatMessage(msg, 'user');
    }

    // On chat tab open, show personalized welcome if no username
    function showPersonalizedWelcome() {
        const chatContainer = document.getElementById('chat-container');
        if (chatContainer && chatContainer.children.length === 1 && !userName) {
            displayAssistantMessage('Welcome to BugSigDB Analyzer.');
            setTimeout(() => {
                displayAssistantMessage('Could you let me know your name please?');
            }, 500);
        }
    }

    // Listen for user name input (first message after welcome)
    function handleUserNameInput() {
        const messageInput = document.getElementById('message-input');
        if (!userName && messageInput) {
            const originalSend = sendMessage;
            window.sendMessage = function() {
                const msg = messageInput.value.trim();
                if (!msg) return;
                if (!userName) {
                    userName = msg;
                    lastUserMessage = msg;
                    displayUserMessage(msg);
                    displayAssistantMessage(`Nice to meet you, ${userName}! How can I help you today?`);
                    messageInput.value = '';
                    // Restore sendMessage for normal chat
                    window.sendMessage = originalSend;
                    return;
                }
                originalSend();
            }
        }
    }
    document.addEventListener('DOMContentLoaded', handleUserNameInput);

    // Paper chat: store paper meta and greet
    window.switchToChatWithPaper = function() {
        // Get paper title and PMID from DOM
        const title = document.getElementById('paper-title-short')?.textContent || '';
        const pmid = document.getElementById('paper-pmid')?.textContent || '';
        chatPaperContext = { title, pmid };
        // Switch to chat tab
        document.getElementById('chat-tab').click();
        setTimeout(() => {
            // Pre-fill chat input with a reference to the paper
            const messageInput = document.getElementById('message-input');
            if (messageInput) {
                messageInput.value = `I want to discuss the paper: \"${title}\" (PMID: ${pmid})`;
                lastUserMessage = messageInput.value;
                messageInput.focus();
            }
            displayAssistantMessage(`What would you like to know about this paper: "${title}" (PMID: ${pmid})?`);
        }, 500);
    }

    // Make sendMessage globally available
    window.sendMessage = sendMessage;

    // Implement askQuestion logic
    window.askQuestion = async function() {
        const questionInput = document.getElementById('paper-question');
        const qaResults = document.getElementById('qa-results');
        const pmid = document.getElementById('paper-pmid')?.textContent?.trim();
        if (!questionInput || !qaResults || !pmid) {
            qaResults.innerHTML = '<div class="alert alert-danger">Unable to find paper or question input.</div>';
            return;
        }
        const question = questionInput.value.trim();
        if (!question) {
            qaResults.innerHTML = '<div class="alert alert-warning">Please enter a question.</div>';
            return;
        }
        qaResults.innerHTML = '<div class="alert alert-info">Asking your question...</div>';
        try {
            const response = await fetch(`/ask_question/${pmid}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question })
            });
            if (!response.ok) {
                throw new Error('Server error: ' + response.status);
            }
            const data = await response.json();
            let answer = data.answer;
            if (Array.isArray(answer)) answer = answer.join('<br>');
            let userRef = window.userName ? window.userName : 'User';
            qaResults.innerHTML = `<div class="alert alert-success"><strong>Answer for ${userRef}:</strong><br>${answer}</div>`;
        } catch (err) {
            qaResults.innerHTML = `<div class="alert alert-danger">Error: ${err.message}</div>`;
        }
    };

    // Make switchToChatWithPaper globally available
    window.switchToChatWithPaper = switchToChatWithPaper;

    window.analyzePaper = analyzePaper;

    // === Browse Papers Tab Logic ===
    window.loadBrowsePapers = async function() {
        // Show loading spinner
        let browseTable = document.getElementById('browse-table-container');
        if (browseTable) browseTable.innerHTML = '<div class="text-center my-4"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div><p>Loading papers...</p></div>';
        // Fetch PMIDs from backend
        const pmidResp = await fetch('/list_pmids');
        const pmids = await pmidResp.json();
        window.browsePapersState.allPmids = pmids;
        window.browsePapersState.page = 1;
        window.browsePapersState.loadedPages = {};
        applyBrowseFilters(); // will trigger first page load
    }

    window.applyBrowseFilters = function() {
        // For now, filtering only by host, year, sequencingType, keyword (not curation status, since that's not in PMIDs)
        const host = document.getElementById('filter-host')?.value.toLowerCase() || '';
        const year = document.getElementById('filter-year')?.value.trim() || '';
        const sequencingType = document.getElementById('filter-sequencing-type')?.value.toLowerCase() || '';
        const keyword = document.getElementById('filter-keyword')?.value.toLowerCase() || '';
        let pmids = window.browsePapersState.allPmids;
        // Filtering is only on metadata, so we filter after loading each page
        // For now, just use all PMIDs
        window.browsePapersState.filteredPmids = pmids;
        window.browsePapersState.page = 1;
        loadBrowsePage(1);
    }

    window.loadBrowsePage = async function(page) {
        const pageSize = window.browsePapersState.pageSize;
        const pmids = window.browsePapersState.filteredPmids;
        const totalPages = Math.ceil(pmids.length / pageSize);
        if (page < 1 || page > totalPages) return;
        window.browsePapersState.page = page;
        // Check cache
        if (window.browsePapersState.loadedPages[page]) {
            renderBrowseTable(window.browsePapersState.loadedPages[page]);
            prefetchBrowsePages(page, totalPages, 3); // Prefetch next 3 pages
            return;
        }
        // Show loading spinner
        let browseTable = document.getElementById('browse-table-container');
        if (browseTable) browseTable.innerHTML = '<div class="text-center my-4"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div><p>Loading papers...</p></div>';
        // Fetch batch from backend (send full pmids array)
        const response = await fetch(`/analyze_batch?page=${page}&page_size=${pageSize}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(pmids)
        });
        const papers = await response.json();
        window.browsePapersState.loadedPages[page] = papers;
        renderBrowseTable(papers);
        prefetchBrowsePages(page, totalPages, 3); // Prefetch next 3 pages
    }

    window.prefetchBrowsePages = function(currentPage, totalPages, numPagesAhead) {
        const pageSize = window.browsePapersState.pageSize;
        const pmids = window.browsePapersState.filteredPmids;
        for (let i = 1; i <= numPagesAhead; i++) {
            const nextPage = currentPage + i;
            if (nextPage > totalPages) break;
            if (window.browsePapersState.loadedPages[nextPage]) continue;
            // Prefetch in background (send full pmids array)
            fetch(`/analyze_batch?page=${nextPage}&page_size=${pageSize}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(pmids)
            })
            .then(resp => resp.json())
            .then(papers => {
                window.browsePapersState.loadedPages[nextPage] = papers;
            })
            .catch(() => {});
        }
    }

    window.renderBrowseTable = function(papers) {
        const page = window.browsePapersState.page;
        const pageSize = window.browsePapersState.pageSize;
        const pmids = window.browsePapersState.filteredPmids;
        const totalPages = Math.ceil(pmids.length / pageSize);
        let html = '<table class="table table-bordered"><thead><tr>' +
            '<th>PMID</th><th>Title</th><th>Authors</th><th>Journal</th><th>Year</th>' +
            '<th>Host</th><th>Body Site</th><th>Sequencing Type</th><th>Curation Status</th><th>Actions</th></tr></thead><tbody>';
        for (const paper of papers) {
            // Enhanced curation status display
            let statusBadge = '';
            let statusText = paper.curation_status || 'Unknown';
            
            switch (statusText) {
                case 'already_curated':
                    statusBadge = '<span class="badge bg-success">Already Curated</span>';
                    break;
                case 'ready':
                    statusBadge = '<span class="badge bg-primary">Ready for Curation</span>';
                    break;
                case 'not_ready':
                    statusBadge = '<span class="badge bg-warning">Not Ready</span>';
                    break;
                default:
                    statusBadge = '<span class="badge bg-secondary">Unknown</span>';
            }
            
            // Add confidence score if available
            let confidenceInfo = '';
            if (paper.curation_analysis && paper.curation_analysis.confidence) {
                const confidence = (paper.curation_analysis.confidence * 100).toFixed(1);
                confidenceInfo = `<br><small class="text-muted">Confidence: ${confidence}%</small>`;
            }
            
            html += `<tr>
                <td>${paper.pmid}</td>
                <td>${paper.title}</td>
                <td>${paper.authors}</td>
                <td>${paper.journal}</td>
                <td>${paper.year}</td>
                <td>${paper.host}</td>
                <td>${paper.body_site}</td>
                <td>${paper.sequencing_type}</td>
                <td>${statusBadge}${confidenceInfo}</td>
                <td><button class="btn btn-sm btn-info" onclick="viewPaperDetails('${paper.pmid}', event)">Details</button></td>
            </tr>`;
        }
        html += '</tbody></table>';
        // Pagination controls
        html += '<nav><ul class="pagination">';
        for (let i = 1; i <= totalPages; i++) {
            html += `<li class="page-item${i === page ? ' active' : ''}"><a class="page-link" href="#" onclick="loadBrowsePage(${i});return false;">${i}</a></li>`;
        }
        html += '</ul></nav>';
        const container = document.getElementById('browse-table-container');
        container.innerHTML = html;
        // Scroll to top of table
        container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    window.gotoBrowsePage = function(page) {
        loadBrowsePage(page);
    }

    // File upload function for PMIDs
    // This function is now defined globally and called directly from DOMContentLoaded

    // Function to display uploaded results
    // This function is now defined globally and called directly from DOMContentLoaded

    window.viewPaperDetails = async function(pmid, event) {
        console.log('=== viewPaperDetails called ===');
        console.log('PMID:', pmid);
        console.log('Event:', event);
        
        // Prevent any default behavior
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        
        // Clear any existing popups first (just in case)
        const existingPopup = document.getElementById('enhanced-details-popup');
        const existingBackdrop = document.getElementById('popup-backdrop');
        if (existingPopup) existingPopup.remove();
        if (existingBackdrop) existingBackdrop.remove();
        
        console.log('Navigating to paper details page...');
        
        // Force a hard navigation to ensure no caching issues
        window.location.replace(`paper-details.html?pmid=${pmid}&v=${Date.now()}`);
    };

    window.showModal = function(title, bodyHtml) {
        let modal = document.getElementById('browse-details-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'browse-details-modal';
            modal.className = 'modal fade';
            modal.tabIndex = -1;
            modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title"></h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body"></div>
                </div>
            </div>`;
            document.body.appendChild(modal);
        }
        modal.querySelector('.modal-title').innerHTML = title;
        modal.querySelector('.modal-body').innerHTML = bodyHtml;
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }

    window.analyzeUserPmids = async function() {
        let textarea = document.getElementById('user-pmid-list');
        if (!textarea) return;
        let raw = textarea.value.trim();
        if (!raw) return;
        
        // Parse PMIDs (comma, space, or newline separated)
        let pmids = raw.split(/[^0-9A-Za-z]+/).filter(x => x.length > 0);
        if (!pmids.length) return;
        
        // Show loading spinner
        let browseTable = document.getElementById('browse-table-container');
        if (browseTable) browseTable.innerHTML = '<div class="text-center my-4"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div><p>Analyzing papers...</p></div>';
        
        try {
            // Use the batch analysis endpoint
            const response = await fetch('/analyze_batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(pmids)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const results = await response.json();
            
            if (results.error) {
                browseTable.innerHTML = `<div class="alert alert-danger">Error: ${results.error}</div>`;
                return;
            }
            
            // Update browse state with the results
            window.browsePapersState.allPmids = pmids;
            window.browsePapersState.filteredPmids = pmids;
            window.browsePapersState.page = 1;
            window.browsePapersState.loadedPages = {};
            window.browsePapersState.uploadedResults = results;
            
            // Display the results
            displayUploadedResults(results);
            
        } catch (error) {
            console.error('Error analyzing PMIDs:', error);
            browseTable.innerHTML = `<div class="alert alert-danger">Error analyzing PMIDs: ${error.message}</div>`;
        }
    }
});

window.addEventListener('DOMContentLoaded', () => {
    // Enable sending chat messages with Enter
    const messageInput = document.getElementById('message-input');
    if (messageInput) {
        messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                window.sendMessage();
            }
        });
    }
    // Enable analyze paper with Enter in PMID input
    const pmidInput = document.getElementById('pmid');
    if (pmidInput) {
        pmidInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                window.analyzePaper();
            }
        });
    }
    // Enable Analyze Entered PMIDs with Enter in textarea
    const userPmidList = document.getElementById('user-pmid-list');
    if (userPmidList) {
        userPmidList.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                window.analyzeUserPmids();
            }
        });
    }
});