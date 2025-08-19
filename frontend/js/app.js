console.log("app.js loaded!");

// Global variables
window.chatHistory = [];
window.ws = null;
window.isConnected = false;

// Global functions for HTML onclick attributes
window.analyzeSinglePaper = async function() {
    const pmid = document.getElementById('singlePmid').value.trim();
    if (!pmid) {
        alert('Please enter a PMID');
        return;
    }
    
    // Show loading
    document.getElementById('loading').style.display = 'block';
    document.getElementById('results-section').style.display = 'block';
    
    try {
        const data = await analyzePaperEnhanced(pmid);
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Display results
        const results = [{
            pmid: pmid,
            title: data.title || 'N/A',
            authors: data.authors || 'N/A',
            journal: data.journal || 'N/A',
            date: data.date || 'N/A',
            enhanced_analysis: data.enhanced_analysis || {}
        }];
        
        displayBrowseResults(results);
    } catch (error) {
        console.error('Error analyzing single paper:', error);
        document.getElementById('results-container').innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                Error analyzing paper: ${error.message}
            </div>
        `;
    } finally {
        document.getElementById('loading').style.display = 'none';
    }
};

window.analyzeBatchPapers = async function() {
    const pmidsText = document.getElementById('batchPmids').value.trim();
    if (!pmidsText) {
        alert('Please enter PMIDs');
        return;
    }
    
    // Parse PMIDs (support both comma-separated and newline-separated)
    const pmids = pmidsText.split(/[,\n]/).map(pmid => pmid.trim()).filter(pmid => pmid);
    if (pmids.length === 0) {
        alert('Please enter valid PMIDs');
        return;
    }
    
    // Show loading
    document.getElementById('loading').style.display = 'block';
    document.getElementById('results-section').style.display = 'block';
    
    try {
        const response = await fetch('/enhanced_analysis_batch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ pmids: pmids })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Display results
        displayBrowseResults(data.results || []);
    } catch (error) {
        console.error('Error analyzing batch papers:', error);
        document.getElementById('results-container').innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                Error analyzing batch papers: ${error.message}
            </div>
        `;
    } finally {
        document.getElementById('loading').style.display = 'none';
    }
};

window.uploadFile = function() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput || !fileInput.files[0]) {
        alert('Please select a file first');
        return;
    }
    
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    
    // Show loading
    document.getElementById('loading').style.display = 'block';
    document.getElementById('results-section').style.display = 'block';
    
    fetch('/upload_csv', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Display results
        if (data.results && data.results.length > 0) {
            displayBrowseResults(data.results);
        } else {
            document.getElementById('results-container').innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle me-2"></i>
                    File uploaded successfully, but no results to display.
                </div>
            `;
        }
    })
    .catch(error => {
        console.error('Error uploading file:', error);
        document.getElementById('results-container').innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                Error uploading file: ${error.message}
            </div>
        `;
    })
    .finally(() => {
        document.getElementById('loading').style.display = 'none';
    });
};

window.refreshCurationStats = async function() {
    const statsContainer = document.getElementById('curation-stats-container');
    statsContainer.innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2 text-muted">Loading curation statistics...</p>
        </div>
    `;
    
    try {
        const response = await fetch('/curation/statistics');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        displayCurationStats(data);
    } catch (error) {
        console.error('Error fetching curation statistics:', error);
        statsContainer.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                Error loading curation statistics: ${error.message}
            </div>
        `;
    }
};

window.exportResults = function() {
    const table = document.getElementById('results-table');
    if (!table) {
        alert('No results to export');
        return;
    }

    const headers = ['PMID', 'Title', 'Host Species', 'Body Site', 'Condition', 'Sequencing Type', 'Taxa Level', 'Sample Size', 'Curation Ready'];
    const rows = Array.from(table.querySelectorAll('tbody tr')).filter(row => !row.classList.contains('error-row'));
    
    let csvContent = headers.join(',') + '\n';
    
    rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        const rowData = Array.from(cells).map(cell => {
            // Extract text content and clean it
            let text = cell.textContent || cell.innerText || '';
            // Remove status indicators and extra text
            text = text.replace(/[✓⚠✗]/g, '').trim();
            // Handle the curation ready column
            if (text.includes('Ready') || text.includes('Not Ready')) {
                text = text.includes('Ready') && !text.includes('Not') ? 'Ready' : 'Not Ready';
            }
            // Escape quotes and wrap in quotes if contains comma
            if (text.includes(',') || text.includes('"') || text.includes('\n')) {
                text = '"' + text.replace(/"/g, '""') + '"';
            }
            return text;
        });
        csvContent += rowData.join(',') + '\n';
    });
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', 'bioanalyzer_curation_analysis.csv');
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};

window.clearResults = function() {
    if (confirm('Are you sure you want to clear all results?')) {
        document.getElementById('results-table-body').innerHTML = '';
        const resultsContainer = document.getElementById('results-table-container');
        if (resultsContainer) {
            resultsContainer.style.display = 'none';
        }
        const errorSection = document.getElementById('browse-error');
        if (errorSection) {
            errorSection.style.display = 'none';
        }
    }
};

// Helper function to create enhanced field cells with status indicators
function getFieldCell(fieldData, valueKey, fieldName) {
    if (!fieldData) {
        return '<span class="text-muted">No data</span>';
    }
    
    const value = fieldData[valueKey] || 'Unknown';
    const status = fieldData.status || 'UNKNOWN';
    const confidence = fieldData.confidence || 0.0;
    const reasonIfMissing = fieldData.reason_if_missing || '';
    const suggestions = fieldData.suggestions_for_curation || '';
    
    let statusBadge = '';
    let tooltipContent = '';
    
    switch (status) {
        case 'PRESENT':
            statusBadge = '<span class="badge bg-success me-1" title="Field is present">✓</span>';
            tooltipContent = `Confidence: ${(confidence * 100).toFixed(1)}%`;
            break;
        case 'PARTIALLY_PRESENT':
            statusBadge = '<span class="badge bg-warning me-1" title="Field is partially present">⚠</span>';
            tooltipContent = `Partial data available. Confidence: ${(confidence * 100).toFixed(1)}%`;
            break;
        case 'ABSENT':
            statusBadge = '<span class="text-muted me-1" title="Field is missing">✗</span>';
            tooltipContent = `Missing: ${reasonIfMissing}. Suggestion: ${suggestions}`;
            break;
        default:
            statusBadge = '<span class="badge bg-secondary me-1" title="Status unknown">?</span>';
            tooltipContent = 'Status unknown';
    }
    
    return `
        <div class="d-flex align-items-center" data-bs-toggle="tooltip" data-bs-placement="top" title="${tooltipContent}">
            ${statusBadge}
            <span class="${status === 'ABSENT' ? 'text-muted' : ''}">${value}</span>
        </div>
    `;
}

// Function to show detailed field information in a modal
function showFieldDetails(result) {
    const analysis = result.enhanced_analysis;
    const metadata = result.metadata;
    
    let modalHtml = `
        <div class="modal-header">
            <h5 class="modal-title">Field Analysis Details - PMID ${result.pmid}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
        </div>
        <div class="modal-body">
            <h6>Paper Information</h6>
            <p><strong>Title:</strong> ${metadata.title || 'No title'}</p>
            <p><strong>Curation Status:</strong> 
                <span class="badge ${result.curation_ready ? 'bg-success' : 'bg-warning'}">
                    ${result.curation_ready ? 'Ready for Curation' : 'Not Ready for Curation'}
                </span>
            </p>
            
            <hr>
            <h6>Field Analysis Details</h6>
            <div class="table-responsive">
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>Field</th>
                            <th>Status</th>
                            <th>Value</th>
                            <th>Confidence</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
    `;
    
    const fieldLabels = {
        "host_species": "Host Species",
        "body_site": "Body Site", 
        "condition": "Condition",
        "sequencing_type": "Sequencing Type",
        "taxa_level": "Taxa Level",
        "sample_size": "Sample Size"
    };
    
    const fieldKeys = {
        "host_species": "primary",
        "body_site": "site",
        "condition": "description", 
        "sequencing_type": "method",
        "taxa_level": "level",
        "sample_size": "size"
    };
    
    for (const [fieldName, fieldLabel] of Object.entries(fieldLabels)) {
        const fieldData = analysis[fieldName] || {};
        const valueKey = fieldKeys[fieldName];
        const value = fieldData[valueKey] || 'Unknown';
        const status = fieldData.status || 'UNKNOWN';
        const confidence = fieldData.confidence || 0.0;
        const reasonIfMissing = fieldData.reason_if_missing || '';
        const suggestions = fieldData.suggestions_for_curation || '';
        
        let statusBadge = '';
        let details = '';
        
        switch (status) {
            case 'PRESENT':
                statusBadge = '<span class="badge bg-success">Present</span>';
                details = `Field is complete with ${(confidence * 100).toFixed(1)}% confidence`;
                break;
            case 'PARTIALLY_PRESENT':
                statusBadge = '<span class="badge bg-warning">Partial</span>';
                details = `Partial information available. Confidence: ${(confidence * 100).toFixed(1)}%`;
                break;
            case 'ABSENT':
                statusBadge = '<span class="badge bg-danger">Missing</span>';
                details = `<strong>Reason:</strong> ${reasonIfMissing}<br><strong>Suggestion:</strong> ${suggestions}`;
                break;
            default:
                statusBadge = '<span class="badge bg-secondary">Unknown</span>';
                details = 'Status could not be determined';
        }
        
        modalHtml += `
            <tr>
                <td><strong>${fieldLabel}</strong></td>
                <td>${statusBadge}</td>
                <td>${value}</td>
                <td>${(confidence * 100).toFixed(1)}%</td>
                <td>${details}</td>
            </tr>
        `;
    }
    
    modalHtml += `
                    </tbody>
                </table>
            </div>
            
            ${analysis.curation_preparation_summary ? `
                <hr>
                <h6>Curation Preparation Summary</h6>
                <div class="alert alert-info">
                    <i class="fas fa-info-circle me-2"></i>
                    ${analysis.curation_preparation_summary}
                </div>
            ` : ''}
            
            ${analysis.missing_fields && analysis.missing_fields.length > 0 ? `
                <hr>
                <h6>Missing Fields Summary</h6>
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    <strong>${analysis.missing_fields.length} field(s) missing:</strong> ${analysis.missing_fields.join(', ')}
                    <br><small>Click on individual fields above for specific details and suggestions.</small>
                </div>
            ` : ''}
        </div>
        <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
        </div>
    `;
    
    // Create and show modal
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'field-details-modal';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                ${modalHtml}
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // Clean up modal after it's hidden
    modal.addEventListener('hidden.bs.modal', () => {
        document.body.removeChild(modal);
    });
}

// Function to display browse results
function displayBrowseResults(data) {
    const { batch_results, summary } = data;
    
    const tbody = document.getElementById('results-table-body');
    if (!tbody) {
        console.error('Results table body not found');
        return;
    }
    
    tbody.innerHTML = '';
    
    batch_results.forEach(result => {
        if (result.status === 'error') {
            const row = tbody.insertRow();
            row.className = 'table-danger';
            row.innerHTML = `
                <td>${result.pmid}</td>
                <td colspan="8">
                    <span class="text-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        ${result.error}
                    </span>
                </td>
            `;
        } else {
            const row = tbody.insertRow();
            row.className = result.curation_ready ? 'table-success' : 'table-warning';
            
            const analysis = result.enhanced_analysis;
            const metadata = result.metadata;
            
            // Enhanced display with field status and missing field information
            const hostSpeciesCell = getFieldCell(analysis.host_species, 'primary', 'host_species');
            const bodySiteCell = getFieldCell(analysis.body_site, 'site', 'body_site');
            const conditionCell = getFieldCell(analysis.condition, 'description', 'condition');
            const sequencingTypeCell = getFieldCell(analysis.sequencing_type, 'method', 'sequencing_type');
            const taxaLevelCell = getFieldCell(analysis.taxa_level, 'level', 'taxa_level');
            const sampleSizeCell = getFieldCell(analysis.sample_size, 'size', 'sample_size');
            
            row.innerHTML = `
                <td><strong>${result.pmid}</strong></td>
                <td>${metadata.title ? metadata.title.substring(0, 80) + '...' : 'No title'}</td>
                <td>${hostSpeciesCell}</td>
                <td>${bodySiteCell}</td>
                <td>${conditionCell}</td>
                <td>${sequencingTypeCell}</td>
                <td>${taxaLevelCell}</td>
                <td>${sampleSizeCell}</td>
                <td>
                    <span class="badge ${result.curation_ready ? 'bg-success' : 'bg-warning'}">
                        ${result.curation_ready ? 'Ready' : 'Not Ready'}
                    </span>
                    ${!result.curation_ready && analysis.missing_fields && analysis.missing_fields.length > 0 ? 
                        `<br><small class="text-muted">Missing: ${analysis.missing_fields.length} fields</small>` : ''}
                </td>
            `;
            
            // Add click handler to show detailed field information
            row.addEventListener('click', () => showFieldDetails(result));
        }
    });
}

// Function to display curation statistics
function displayCurationStats(data) {
    const statsContainer = document.getElementById('curation-stats-container');
    
    const { overall_statistics, field_statistics } = data;
    
    let html = `
        <div class="row mb-4">
            <div class="col-md-4">
                <div class="text-center p-3 bg-light rounded">
                    <h4 class="text-primary mb-1">${overall_statistics.total_papers_analyzed}</h4>
                    <small class="text-muted">Total Papers Analyzed</small>
                </div>
            </div>
            <div class="col-md-4">
                <div class="text-center p-3 bg-light rounded">
                    <h4 class="text-success mb-1">${overall_statistics.papers_ready_for_curation}</h4>
                    <small class="text-muted">Ready for Curation</small>
                </div>
            </div>
            <div class="col-md-4">
                <div class="text-center p-3 bg-light rounded">
                    <h4 class="text-info mb-1">${(overall_statistics.overall_readiness_rate * 100).toFixed(1)}%</h4>
                    <small class="text-muted">Overall Readiness Rate</small>
                </div>
            </div>
        </div>
        
        <h6 class="mb-3">Field Analysis Performance</h6>
        <div class="table-responsive">
            <table class="table table-sm">
                <thead>
                    <tr>
                        <th>Field</th>
                        <th>Ready</th>
                        <th>Total</th>
                        <th>Readiness Rate</th>
                        <th>Avg Confidence</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    // Display statistics for each of the 6 essential fields
    const fieldLabels = {
        "host_species": "Host Species",
        "body_site": "Body Site",
        "condition": "Condition",
        "sequencing_type": "Sequencing Type",
        "taxa_level": "Taxa Level",
        "sample_size": "Sample Size"
    };
    
    for (const [fieldName, fieldData] of Object.entries(field_statistics)) {
        const readinessRate = (fieldData.readiness_rate * 100).toFixed(1);
        const avgConfidence = (fieldData.avg_confidence * 100).toFixed(1);
        
        html += `
            <tr>
                <td><strong>${fieldLabels[fieldName] || fieldName}</strong></td>
                <td><span class="badge bg-success">${fieldData.ready}</span></td>
                <td>${fieldData.total}</td>
                <td>
                    <div class="progress" style="height: 20px;">
                        <div class="progress-bar ${fieldData.readiness_rate >= 0.7 ? 'bg-success' : fieldData.readiness_rate >= 0.4 ? 'bg-warning' : 'bg-danger'}" 
                             style="width: ${readinessRate}%">
                            ${readinessRate}%
                        </div>
                    </div>
                </td>
                <td>${avgConfidence}%</td>
            </tr>
        `;
    }
    
    html += `
                </tbody>
            </table>
        </div>
        
        <div class="mt-3 text-muted small">
            <i class="fas fa-info-circle me-1"></i>
            Statistics show how well the AI analysis is identifying the 6 essential BugSigDB curation fields.
        </div>
    `;
    
    statsContainer.innerHTML = html;
}

// Enhanced analysis function for Browse Papers tab
async function analyzePaperEnhanced(pmid) {
    console.log(`Running enhanced analysis for PMID: ${pmid}`);
    
    try {
        const response = await fetch(`/enhanced_analysis/${pmid}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Enhanced analysis response:', data);
        return data;
    } catch (error) {
        console.error('Error in enhanced analysis:', error);
        throw error;
    }
}

// Display chat message - global function
function displayChatMessage(message, type) {
    console.log("=== displayChatMessage called ===");
    console.log("[DEBUG] displayChatMessage called with:", message, type);
    const chatContainer = document.getElementById('chat-container');
    console.log("[DEBUG] chatContainer found:", chatContainer);
    console.log("[DEBUG] chatContainer element:", chatContainer);
    console.log("[DEBUG] chatContainer.innerHTML before:", chatContainer ? chatContainer.innerHTML.substring(0, 200) + "..." : "null");
    if (!chatContainer) {
        console.error("[DEBUG] No chat container found!");
        return;
    }

    const messageElement = document.createElement('div');
    messageElement.className = `message ${type}-message`;
    messageElement.textContent = message;
    console.log("[DEBUG] Created message element:", messageElement);
    chatContainer.appendChild(messageElement);
    console.log("[DEBUG] Appended message to container");
    console.log("[DEBUG] chatContainer.innerHTML after:", chatContainer.innerHTML.substring(0, 200) + "...");
    console.log("[DEBUG] Number of child elements:", chatContainer.children.length);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    if (type === 'assistant') {
        if (window.chatHistory) {
            window.chatHistory.push({ role: 'assistant', content: message });
            console.log("[DEBUG] Added to chat history");
        }
    }
    console.log("[DEBUG] displayChatMessage completed successfully");
    console.log("=== End displayChatMessage ===");
}
window.displayChatMessage = displayChatMessage;

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
        '<th>Host</th><th>Body Site</th><th>Sequencing Type</th><th>Actions</th></tr></thead><tbody>';
    
    for (const paper of results) {
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
            <td><button class="btn btn-sm btn-info" onclick="viewPaperDetails('${paper.pmid}', event)">Details</button></td>
        </tr>`;
    }
    
    html += '</tbody></table>';
    
    // Add summary statistics
    const stats = {
        total: results.length
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

// Enhanced export function for analysis reports
window.exportAnalysisReport = function() {
    // Check if we have uploaded results first
    if (window.browsePapersState.uploadedResults && window.browsePapersState.uploadedResults.length > 0) {
        const results = window.browsePapersState.uploadedResults;
        const headers = [
            'PMID', 'Title', 'Authors', 'Journal', 'Year', 'Host', 'Body Site', 
            'Sequencing Type', 'Confidence Score', 'Key Findings'
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
        a.download = `analysis_report_uploaded_${new Date().toISOString().split('T')[0]}.csv`;
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
        'Sequencing Type', 'Confidence Score', 'Key Findings'
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
    a.download = `analysis_report_${new Date().toISOString().split('T')[0]}.csv`;
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
            window.ws = new WebSocket(wsUrl);
            window.ws.onopen = function() {
                window.isConnected = true;
                updateConnectionStatus('Connected', 'success');
                // Show welcome message if chat is empty
                const chatContainer = document.getElementById('chat-container');
                if (chatContainer && chatContainer.children.length === 1) { // Only download button present
                    displayChatMessage('Hey there! How can I help you today?', 'assistant');
                }
            };
            window.ws.onclose = function() {
                window.isConnected = false;
                updateConnectionStatus('Disconnected', 'danger');
            };
            window.ws.onerror = function(error) {
                window.isConnected = false;
                updateConnectionStatus('Connection failed', 'danger');
            };
            // Add onmessage handler to display assistant replies
            window.ws.onmessage = function(event) {
                console.log("=== WebSocket Message Received ===");
                console.log("Raw event data:", event.data);
                console.log("Event type:", typeof event.data);
                console.log("Received from backend:", event.data);
                console.log("[DEBUG] lastUserMessage before handling:", lastUserMessage);
                console.log("[DEBUG] WebSocket connection status:", window.ws.readyState);
                console.log("[DEBUG] isConnected variable:", window.isConnected);
                console.log("[DEBUG] About to parse JSON...");
                try {
                    const data = JSON.parse(event.data);
                    console.log("[DEBUG] JSON parsed successfully!");
                    console.log("[DEBUG] Parsed data:", data);
                    console.log("[DEBUG] Data type:", typeof data);
                    console.log("[DEBUG] Data keys:", Object.keys(data));
                    // Check for both 'response' and 'text' fields (backend sends 'text')
                    const responseText = data.response || data.text;
                    console.log("[DEBUG] responseText:", responseText);
                    console.log("[DEBUG] responseText type:", typeof responseText);
                    console.log("[DEBUG] responseText truthy:", !!responseText);
                    if (responseText) {
                        console.log("[DEBUG] About to display message:", responseText);
                        console.log("[DEBUG] Calling displayChatMessage with:", responseText, 'assistant');
                        displayChatMessage(responseText, 'assistant');
                        console.log("[DEBUG] Message displayed successfully");
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
                        console.log("[DEBUG] Displaying error:", data.error);
                        displayChatMessage("Error: " + data.error, 'error');
                    } else {
                        console.log("[DEBUG] No response text or error found in data");
                        console.log("[DEBUG] Full data object:", JSON.stringify(data, null, 2));
                    }
                } catch (e) {
                    console.error("[DEBUG] Error in WebSocket message handler:", e);
                    console.error("[DEBUG] Error stack:", e.stack);
                    console.error("[DEBUG] Event data that caused error:", event.data);
                }
                console.log("=== End WebSocket Message Handler ===");
            };
        } catch (error) {
            window.isConnected = false;
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

        if (messageInput) messageInput.disabled = !window.isConnected;
        if (sendButton) sendButton.disabled = !window.isConnected;
        if (usernameInput) usernameInput.disabled = window.isConnected;
    }

    // Display analysis results
    function displayAnalysisResults(data) {
        console.log('[displayAnalysisResults] Data:', data);
        
        // Show top-level warning or error if present (suppress duplicates)
        let resultsDiv = getElement('results');
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
        console.log("[DEBUG] displayChatMessage called with:", message, type);
        const chatContainer = document.getElementById('chat-container');
        console.log("[DEBUG] chatContainer found:", chatContainer);
        if (!chatContainer) {
            console.error("[DEBUG] No chat container found!");
            return;
        }

        const messageElement = document.createElement('div');
        messageElement.className = `message ${type}-message`;
        messageElement.textContent = message;
        console.log("[DEBUG] Created message element:", messageElement);
        chatContainer.appendChild(messageElement);
        console.log("[DEBUG] Appended message to container");
        console.log("[DEBUG] chatContainer.innerHTML after:", chatContainer.innerHTML.substring(0, 200) + "...");
        console.log("[DEBUG] Number of child elements:", chatContainer.children.length);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        if (type === 'assistant') {
            if (window.chatHistory) {
                window.chatHistory.push({ role: 'assistant', content: message });
                console.log("[DEBUG] Added to chat history");
            }
        }
        console.log("[DEBUG] displayChatMessage completed successfully");
        console.log("=== End displayChatMessage ===");
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
        console.log("[DEBUG] sendMessage called");
        const messageInput = document.getElementById('message-input');
        console.log("[DEBUG] messageInput found:", messageInput);
        console.log("[DEBUG] ws found:", window.ws);
        console.log("[DEBUG] isConnected:", window.isConnected);
        if (!messageInput || !window.ws || !window.isConnected) {
            console.log("[DEBUG] sendMessage early return - missing requirements");
            return;
        }

        const message = messageInput.value.trim();
        if (!message) return;

        lastUserMessage = message; // Track last user message
        displayChatMessage(message, 'user');
        // Add to chat history
        if (window.chatHistory) {
            window.chatHistory.push({ role: 'user', content: message });
        }
        // Prepare context for backend
        let contextMessages = [];
        if (!chatPaperContext) {
            // Only send history if not in paper context
            contextMessages = window.chatHistory ? window.chatHistory.slice(-10) : []; // last 10 messages
        }
        window.ws.send(JSON.stringify({
            content: message,
            role: 'user',
            currentPaper: chatPaperContext ? chatPaperContext.pmid : null,
            paperContext: chatPaperContext || null,
            chatHistory: contextMessages
        }));
        console.log("[DEBUG] Message sent to WebSocket");

        messageInput.value = '';
    }

    // Initialize UI
    function initializeUI() {
        // Initialize WebSocket
        initWebSocket();

        // Add event listeners - removed old analyze button and pmid input references
        
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

        // Remove old loading indicator creation - no longer needed
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

    // Page Settings Event Handlers - Removed as these elements don't exist in current interface
    // Font size, zoom, and theme controls were removed during refactoring

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

    // Remove old analyze button references - no longer needed
    
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

    // Remove old analyzePaper reference - no longer needed

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
            '<th>Host</th><th>Body Site</th><th>Sequencing Type</th><th>Actions</th></tr></thead><tbody>';
        for (const paper of papers) {
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

    // New Browse Papers functionality
    async function searchSinglePmid() {
        const pmidInput = document.getElementById('single-pmid-input');
        const pmid = pmidInput.value.trim();
        
        if (!pmid) {
            showBrowseError('Please enter a valid PubMed ID (PMID)');
            return;
        }
        
        if (!/^\d+$/.test(pmid)) {
            showBrowseError('PMID must contain only numbers');
            return;
        }
        
        await searchPmids([pmid]);
    }

    async function searchBatchPmids() {
        const batchInput = document.getElementById('batch-pmids-input');
        const pmidsText = batchInput.value.trim();
        
        if (!pmidsText) {
            showBrowseError('Please enter PMIDs for batch search');
            return;
        }
        
        const pmids = pmidsText.split(/[\n,]/).map(pmid => pmid.trim()).filter(pmid => pmid);
        
        if (pmids.length === 0) {
            showBrowseError('No valid PMIDs found');
            return;
        }
        
        if (pmids.length > 50) {
            showBrowseError('Batch search limited to 50 PMIDs at a time');
            return;
        }
        
        await searchPmids(pmids);
    }

    async function searchPmids(pmids) {
        showBrowseLoading(true);
        hideBrowseError();
        hideResultsTable();
        
        try {
            console.log(`Starting search for ${pmids.length} PMIDs`);
            
            // Call the enhanced analysis batch endpoint
            const response = await fetch('/enhanced_analysis_batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ pmids: pmids })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Search response:', data);
            
            // Display results in the table
            displayBrowseResults(data);
            
            // Show results table
            showResultsTable();
            
        } catch (error) {
            console.error('Search error:', error);
            showBrowseError(`Search failed: ${error.message}`);
        } finally {
            showBrowseLoading(false);
        }
    }

    function displayBrowseResults(data) {
        const { batch_results, summary } = data;
        
        const tbody = document.getElementById('results-table-body');
        tbody.innerHTML = '';
        
        batch_results.forEach(result => {
            if (result.status === 'error') {
                const row = tbody.insertRow();
                row.className = 'table-danger';
                row.innerHTML = `
                    <td>${result.pmid}</td>
                    <td colspan="8">
                        <span class="text-danger">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            ${result.error}
                        </span>
                    </td>
                `;
            } else {
                const row = tbody.insertRow();
                row.className = result.curation_ready ? 'table-success' : 'table-warning';
                
                const analysis = result.enhanced_analysis;
                const metadata = result.metadata;
                
                // Enhanced display with field status and missing field information
                const hostSpeciesCell = getFieldCell(analysis.host_species, 'primary', 'host_species');
                const bodySiteCell = getFieldCell(analysis.body_site, 'site', 'body_site');
                const conditionCell = getFieldCell(analysis.condition, 'description', 'condition');
                const sequencingTypeCell = getFieldCell(analysis.sequencing_type, 'method', 'sequencing_type');
                const taxaLevelCell = getFieldCell(analysis.taxa_level, 'level', 'taxa_level');
                const sampleSizeCell = getFieldCell(analysis.sample_size, 'size', 'sample_size');
                
                row.innerHTML = `
                    <td><strong>${result.pmid}</strong></td>
                    <td>${metadata.title ? metadata.title.substring(0, 80) + '...' : 'No title'}</td>
                    <td>${hostSpeciesCell}</td>
                    <td>${bodySiteCell}</td>
                    <td>${conditionCell}</td>
                    <td>${sequencingTypeCell}</td>
                    <td>${taxaLevelCell}</td>
                    <td>${sampleSizeCell}</td>
                    <td>
                        <span class="badge ${result.curation_ready ? 'bg-success' : 'bg-warning'}">
                            ${result.curation_ready ? 'Ready' : 'Not Ready'}
                        </span>
                        ${!result.curation_ready && analysis.missing_fields && analysis.missing_fields.length > 0 ? 
                            `<br><small class="text-muted">Missing: ${analysis.missing_fields.length} fields</small>` : ''}
                    </td>
                `;
                
                // Add click handler to show detailed field information
                row.addEventListener('click', () => showFieldDetails(result));
            }
        });
    }

    // Helper function to create enhanced field cells with status indicators
    function getFieldCell(fieldData, valueKey, fieldName) {
        if (!fieldData) {
            return '<span class="text-muted">No data</span>';
        }
        
        const value = fieldData[valueKey] || 'Unknown';
        const status = fieldData.status || 'UNKNOWN';
        const confidence = fieldData.confidence || 0.0;
        const reasonIfMissing = fieldData.reason_if_missing || '';
        const suggestions = fieldData.suggestions_for_curation || '';
        
        let statusBadge = '';
        let tooltipContent = '';
        
        switch (status) {
            case 'PRESENT':
                statusBadge = '<span class="badge bg-success me-1" title="Field is present">✓</span>';
                tooltipContent = `Confidence: ${(confidence * 100).toFixed(1)}%`;
                break;
            case 'PARTIALLY_PRESENT':
                statusBadge = '<span class="badge bg-warning me-1" title="Field is partially present">⚠</span>';
                tooltipContent = `Partial data available. Confidence: ${(confidence * 100).toFixed(1)}%`;
                break;
            case 'ABSENT':
                statusBadge = '<span class="text-muted me-1" title="Field is missing">✗</span>';
                tooltipContent = `Missing: ${reasonIfMissing}. Suggestion: ${suggestions}`;
                break;
            default:
                statusBadge = '<span class="badge bg-secondary me-1" title="Status unknown">?</span>';
                tooltipContent = 'Status unknown';
        }
        
        return `
            <div class="d-flex align-items-center" data-bs-toggle="tooltip" data-bs-placement="top" title="${tooltipContent}">
                ${statusBadge}
                <span class="${status === 'ABSENT' ? 'text-muted' : ''}">${value}</span>
            </div>
        `;
    }

    // Function to show detailed field information in a modal
    function showFieldDetails(result) {
        const analysis = result.enhanced_analysis;
        const metadata = result.metadata;
        
        let modalHtml = `
            <div class="modal-header">
                <h5 class="modal-title">Field Analysis Details - PMID ${result.pmid}</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <h6>Paper Information</h6>
                <p><strong>Title:</strong> ${metadata.title || 'No title'}</p>
                <p><strong>Curation Status:</strong> 
                    <span class="badge ${result.curation_ready ? 'bg-success' : 'bg-warning'}">
                        ${result.curation_ready ? 'Ready for Curation' : 'Not Ready for Curation'}
                    </span>
                </p>
                
                <hr>
                <h6>Field Analysis Details</h6>
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>Field</th>
                                <th>Status</th>
                                <th>Value</th>
                                <th>Confidence</th>
                                <th>Details</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        const fieldLabels = {
            "host_species": "Host Species",
            "body_site": "Body Site", 
            "condition": "Condition",
            "sequencing_type": "Sequencing Type",
            "taxa_level": "Taxa Level",
            "sample_size": "Sample Size"
        };
        
        const fieldKeys = {
            "host_species": "primary",
            "body_site": "site",
            "condition": "description", 
            "sequencing_type": "method",
            "taxa_level": "level",
            "sample_size": "size"
        };
        
        for (const [fieldName, fieldLabel] of Object.entries(fieldLabels)) {
            const fieldData = analysis[fieldName] || {};
            const valueKey = fieldKeys[fieldName];
            const value = fieldData[valueKey] || 'Unknown';
            const status = fieldData.status || 'UNKNOWN';
            const confidence = fieldData.confidence || 0.0;
            const reasonIfMissing = fieldData.reason_if_missing || '';
            const suggestions = fieldData.suggestions_for_curation || '';
            
            let statusBadge = '';
            let details = '';
            
            switch (status) {
                case 'PRESENT':
                    statusBadge = '<span class="badge bg-success">Present</span>';
                    details = `Field is complete with ${(confidence * 100).toFixed(1)}% confidence`;
                    break;
                case 'PARTIALLY_PRESENT':
                    statusBadge = '<span class="badge bg-warning">Partial</span>';
                    details = `Partial information available. Confidence: ${(confidence * 100).toFixed(1)}%`;
                    break;
                case 'ABSENT':
                    statusBadge = '<span class="badge bg-danger">Missing</span>';
                    details = `<strong>Reason:</strong> ${reasonIfMissing}<br><strong>Suggestion:</strong> ${suggestions}`;
                    break;
                default:
                    statusBadge = '<span class="badge bg-secondary">Unknown</span>';
                    details = 'Status could not be determined';
            }
            
            modalHtml += `
                <tr>
                    <td><strong>${fieldLabel}</strong></td>
                    <td>${statusBadge}</td>
                    <td>${value}</td>
                    <td>${(confidence * 100).toFixed(1)}%</td>
                    <td>${details}</td>
                </tr>
            `;
        }
        
        modalHtml += `
                        </tbody>
                    </table>
                </div>
                
                ${analysis.curation_preparation_summary ? `
                    <hr>
                    <h6>Curation Preparation Summary</h6>
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        ${analysis.curation_preparation_summary}
                    </div>
                ` : ''}
                
                ${analysis.missing_fields && analysis.missing_fields.length > 0 ? `
                    <hr>
                    <h6>Missing Fields Summary</h6>
                    <div class="alert alert-warning">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        <strong>${analysis.missing_fields.length} field(s) missing:</strong> ${analysis.missing_fields.join(', ')}
                        <br><small>Click on individual fields above for specific details and suggestions.</small>
                    </div>
                ` : ''}
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            </div>
        `;
        
        // Create and show modal
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'field-details-modal';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    ${modalHtml}
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        
        // Clean up modal after it's hidden
        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }

    // Utility functions for Browse Papers tab
    function showBrowseLoading(show) {
        const loadingSection = document.getElementById('browse-loading');
        loadingSection.style.display = show ? 'block' : 'none';
    }

    function showResultsTable() {
        const resultsContainer = document.getElementById('results-table-container');
        resultsContainer.style.display = 'block';
    }

    function hideResultsTable() {
        const resultsContainer = document.getElementById('results-table-container');
        resultsContainer.style.display = 'none';
    }

    function showBrowseError(message) {
        const errorSection = document.getElementById('browse-error');
        const errorMessage = errorSection.querySelector('p');
        errorMessage.textContent = message;
        errorSection.style.display = 'block';
    }

    function hideBrowseError() {
        const errorSection = document.getElementById('browse-error');
        errorSection.style.display = 'none';
    }

    // Export functions for Browse Papers tab
    function exportResults() {
        const table = document.getElementById('results-table');
        if (!table) {
            alert('No results to export');
            return;
        }

        const headers = ['PMID', 'Title', 'Host Species', 'Body Site', 'Condition', 'Sequencing Type', 'Taxa Level', 'Sample Size', 'Curation Ready'];
        const rows = Array.from(table.querySelectorAll('tbody tr')).filter(row => !row.classList.contains('error-row'));
        
        let csvContent = headers.join(',') + '\n';
        
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            const rowData = Array.from(cells).map(cell => {
                // Extract text content and clean it
                let text = cell.textContent || cell.innerText || '';
                // Remove status indicators and extra text
                text = text.replace(/[✓⚠✗]/g, '').trim();
                // Handle the curation ready column
                if (text.includes('Ready') || text.includes('Not Ready')) {
                    text = text.includes('Ready') && !text.includes('Not') ? 'Ready' : 'Not Ready';
                }
                // Escape quotes and wrap in quotes if contains comma
                if (text.includes(',') || text.includes('"') || text.includes('\n')) {
                    text = '"' + text.replace(/"/g, '""') + '"';
                }
                return text;
            });
            csvContent += rowData.join(',') + '\n';
        });
        
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', 'bioanalyzer_curation_analysis.csv');
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    function clearResults() {
        if (confirm('Are you sure you want to clear all results?')) {
            document.getElementById('results-table-body').innerHTML = '';
            hideResultsTable();
            hideBrowseError();
        }
    }

    // Essential paper analysis functions for Browse Papers tab
    async function analyzePaper(pmid) {
        console.log(`Analyzing paper with PMID: ${pmid}`);
        
        try {
            const response = await fetch(`/analyze/${pmid}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log('Paper analysis response:', data);
            return data;
        } catch (error) {
            console.error('Error analyzing paper:', error);
            throw error;
        }
    }

    // Single paper analysis function for Browse Papers tab
    async function analyzeSinglePaper() {
        const pmid = document.getElementById('singlePmid').value.trim();
        if (!pmid) {
            alert('Please enter a PMID');
            return;
        }
        
        // Show loading
        document.getElementById('loading').style.display = 'block';
        document.getElementById('results-section').style.display = 'block';
        
        try {
            const data = await analyzePaperEnhanced(pmid);
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Format the single result to match the batch results structure
            const results = [{
                pmid: pmid,
                metadata: {
                    title: data.title || 'N/A'
                },
                enhanced_analysis: data.enhanced_analysis || {},
                curation_ready: data.curation_ready || false,
                status: 'success'
            }];
            
            displayBrowseResults({ batch_results: results, summary: { total_pmids: 1 } });
        } catch (error) {
            console.error('Error analyzing single paper:', error);
            document.getElementById('results-container').innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error analyzing paper: ${error.message}
                </div>
            `;
        } finally {
            document.getElementById('loading').style.display = 'none';
        }
    }

    // Batch papers analysis function for Browse Papers tab
    async function analyzeBatchPapers() {
        const pmidsText = document.getElementById('batchPmids').value.trim();
        if (!pmidsText) {
            alert('Please enter PMIDs');
            return;
        }
        
        // Parse PMIDs (support both comma-separated and newline-separated)
        const pmids = pmidsText.split(/[,\n]/).map(pmid => pmid.trim()).filter(pmid => pmid);
        if (pmids.length === 0) {
            alert('Please enter valid PMIDs');
            return;
        }
        
        // Show loading
        document.getElementById('loading').style.display = 'block';
        document.getElementById('results-section').style.display = 'block';
        
        try {
            const response = await fetch('/enhanced_analysis_batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ pmids: pmids })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Display results
            displayBrowseResults(data.results || []);
        } catch (error) {
            console.error('Error analyzing batch papers:', error);
            document.getElementById('results-container').innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error analyzing batch papers: ${error.message}
                </div>
            `;
        } finally {
            document.getElementById('loading').style.display = 'none';
        }
    }

    // Enhanced analysis function for Browse Papers tab
    async function analyzePaperEnhanced(pmid) {
        console.log(`Running enhanced analysis for PMID: ${pmid}`);
        
        try {
            const response = await fetch(`/enhanced_analysis/${pmid}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log('Enhanced analysis response:', data);
            return data;
        } catch (error) {
            console.error('Error in enhanced analysis:', error);
            throw error;
        }
    }

    // Curation Statistics Functions
    async function refreshCurationStats() {
        const statsContainer = document.getElementById('curation-stats-container');
        statsContainer.innerHTML = `
            <div class="text-center">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2 text-muted">Loading curation statistics...</p>
            </div>
        `;
        
        try {
            const response = await fetch('/curation/statistics');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            displayCurationStats(data);
        } catch (error) {
            console.error('Error fetching curation statistics:', error);
            statsContainer.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error loading curation statistics: ${error.message}
                </div>
            `;
        }
    }

    function displayCurationStats(data) {
        const statsContainer = document.getElementById('curation-stats-container');
        
        const { overall_statistics, field_statistics } = data;
        
        let html = `
            <div class="row mb-4">
                <div class="col-md-4">
                    <div class="text-center p-3 bg-light rounded">
                        <h4 class="text-primary mb-1">${overall_statistics.total_papers_analyzed}</h4>
                        <small class="text-muted">Total Papers Analyzed</small>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="text-center p-3 bg-light rounded">
                        <h4 class="text-success mb-1">${overall_statistics.papers_ready_for_curation}</h4>
                        <small class="text-muted">Ready for Curation</small>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="text-center p-3 bg-light rounded">
                        <h4 class="text-info mb-1">${(overall_statistics.overall_readiness_rate * 100).toFixed(1)}%</h4>
                        <small class="text-muted">Overall Readiness Rate</small>
                    </div>
                </div>
            </div>
            
            <h6 class="mb-3">Field Analysis Performance</h6>
            <div class="table-responsive">
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>Field</th>
                            <th>Ready</th>
                            <th>Total</th>
                            <th>Readiness Rate</th>
                            <th>Avg Confidence</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        // Display statistics for each of the 6 essential fields
        const fieldLabels = {
            "host_species": "Host Species",
            "body_site": "Body Site",
            "condition": "Condition",
            "sequencing_type": "Sequencing Type",
            "taxa_level": "Taxa Level",
            "sample_size": "Sample Size"
        };
        
        for (const [fieldName, fieldData] of Object.entries(field_statistics)) {
            const readinessRate = (fieldData.readiness_rate * 100).toFixed(1);
            const avgConfidence = (fieldData.avg_confidence * 100).toFixed(1);
            
            html += `
                <tr>
                    <td><strong>${fieldLabels[fieldName] || fieldName}</strong></td>
                    <td><span class="badge bg-success">${fieldData.ready}</span></td>
                    <td>${fieldData.total}</td>
                    <td>
                        <div class="progress" style="height: 20px;">
                            <div class="progress-bar ${fieldData.readiness_rate >= 0.7 ? 'bg-success' : fieldData.readiness_rate >= 0.4 ? 'bg-warning' : 'bg-danger'}" 
                                 style="width: ${readinessRate}%">
                                ${readinessRate}%
                            </div>
                        </div>
                    </td>
                    <td>${avgConfidence}%</td>
                </tr>
            `;
        }
        
        html += `
                    </tbody>
                </table>
            </div>
            
            <div class="mt-3 text-muted small">
                <i class="fas fa-info-circle me-1"></i>
                Statistics show how well the AI analysis is identifying the 6 essential BugSigDB curation fields.
            </div>
        `;
        
        statsContainer.innerHTML = html;
    }

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

    // File upload function
    function uploadFile() {
        const fileInput = document.getElementById('fileInput');
        if (!fileInput || !fileInput.files[0]) {
            alert('Please select a file first');
            return;
        }
        
        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);
        
        // Show loading
        document.getElementById('loading').style.display = 'block';
        document.getElementById('results-section').style.display = 'block';
        
        fetch('/upload_csv', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Display results
            if (data.results && data.results.length > 0) {
                displayBrowseResults(data.results);
            } else {
                document.getElementById('results-container').innerHTML = `
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        File uploaded successfully, but no results to display.
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error uploading file:', error);
            document.getElementById('results-container').innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error uploading file: ${error.message}
                </div>
            `;
        })
        .finally(() => {
            document.getElementById('loading').style.display = 'none';
        });
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
    // Remove old pmid input and analyzePaper references - no longer needed
    
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