// Simple BioAnalyzer - Focused on 6 Essential BugSigDB Fields
console.log('Simple BioAnalyzer loaded');

// Field definitions with icons
const FIELD_DEFINITIONS = {
    host_species: {
        name: 'Host Species',
        icon: 'dna',
        description: 'The host organism being studied'
    },
    body_site: {
        name: 'Body Site',
        icon: 'map-marker-alt',
        description: 'Where the microbiome sample was collected'
    },
    condition: {
        name: 'Condition',
        icon: 'stethoscope',
        description: 'What disease, treatment, or exposure is being studied'
    },
    sequencing_type: {
        name: 'Sequencing Type',
        icon: 'microscope',
        description: 'What molecular method was used'
    },
    taxa_level: {
        name: 'Taxa Level',
        icon: 'sitemap',
        description: 'What taxonomic level was analyzed'
    },
    sample_size: {
        name: 'Sample Size',
        icon: 'hashtag',
        description: 'Number of samples or participants analyzed'
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, setting up event listeners...');
    
    const analyzeButton = document.getElementById('analyze-btn');
    const pmidInput = document.getElementById('pmid-input');
    
    if (analyzeButton && pmidInput) {
        analyzeButton.addEventListener('click', handleAnalyze);
        pmidInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleAnalyze();
            }
        });
    }
});

// Handle analyze button click
async function handleAnalyze() {
    const pmid = document.getElementById('pmid-input').value.trim();
    
    if (!pmid) {
        showAlert('Please enter a valid PubMed ID.', 'warning');
        return;
    }
    
    if (!/^\d+$/.test(pmid)) {
        showAlert('Please enter a valid numeric PubMed ID.', 'warning');
        return;
    }
    
    console.log('Starting analysis for PMID:', pmid);
    showLoading();
    
    try {
        const response = await fetch(`/api/v1/analyze/${pmid}`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Analysis completed:', data);
        displayResults(data);
        
    } catch (error) {
        console.error('Analysis error:', error);
        showError(`Analysis failed: ${error.message}`);
    } finally {
        hideLoading();
    }
}

// Show loading state
function showLoading() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('empty-state').style.display = 'none';
    document.getElementById('results-content').style.display = 'none';
}

// Hide loading state
function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

// Show error message
function showError(message) {
    const resultsContent = document.getElementById('results-content');
    resultsContent.innerHTML = `
        <div class="alert alert-danger">
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>Error:</strong> ${message}
        </div>
    `;
    resultsContent.style.display = 'block';
    document.getElementById('empty-state').style.display = 'none';
}

// Display analysis results
function displayResults(data) {
    const resultsContent = document.getElementById('results-content');
    
    // Paper header
    let html = `
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">
                            <i class="fas fa-file-alt me-2"></i>
                            Analysis Results for PMID ${data.pmid}
                        </h5>
                    </div>
                    <div class="card-body">
                        <h6 class="card-title">${data.title || 'No title available'}</h6>
                        <p class="card-text">
                            <strong>Journal:</strong> ${data.journal || 'Not specified'}<br>
                            <strong>Authors:</strong> ${data.authors ? data.authors.join(', ') : 'Not specified'}<br>
                            <strong>Publication Date:</strong> ${data.publication_date || 'Not specified'}
                        </p>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-12">
                <h5 class="mb-3">
                    <i class="fas fa-list-check me-2"></i>
                    BugSigDB Essential Fields Analysis
                </h5>
            </div>
        </div>
    `;
    
    // Field analysis results
    const fields = data.fields || {};
    const fieldOrder = ['host_species', 'body_site', 'condition', 'sequencing_type', 'taxa_level', 'sample_size'];
    
    fieldOrder.forEach(fieldKey => {
        const field = fields[fieldKey] || {};
        const fieldDef = FIELD_DEFINITIONS[fieldKey];
        const status = field.status || 'ABSENT';
        const value = field.value || 'Not found';
        const confidence = field.confidence || 0;
        const reason = field.reason_if_missing || '';
        
        html += renderFieldCard(fieldKey, fieldDef, status, value, confidence, reason);
    });
    
    // Summary
    const presentCount = fieldOrder.filter(key => fields[key]?.status === 'PRESENT').length;
    const partiallyCount = fieldOrder.filter(key => fields[key]?.status === 'PARTIALLY_PRESENT').length;
    const absentCount = fieldOrder.filter(key => fields[key]?.status === 'ABSENT').length;
    
    html += `
        <div class="row mt-4">
            <div class="col-12">
                <div class="card bg-light">
                    <div class="card-body">
                        <h6 class="card-title">
                            <i class="fas fa-chart-pie me-2"></i>
                            Analysis Summary
                        </h6>
                        <div class="row text-center">
                            <div class="col-md-4">
                                <div class="text-success">
                                    <i class="fas fa-check-circle fa-2x mb-2"></i>
                                    <h5>${presentCount}</h5>
                                    <small>Present</small>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="text-warning">
                                    <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                                    <h5>${partiallyCount}</h5>
                                    <small>Partially Present</small>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="text-danger">
                                    <i class="fas fa-times-circle fa-2x mb-2"></i>
                                    <h5>${absentCount}</h5>
                                    <small>Absent</small>
                                </div>
                            </div>
                        </div>
                        <div class="mt-3">
                            <div class="progress">
                                <div class="progress-bar bg-success" style="width: ${(presentCount / 6) * 100}%"></div>
                                <div class="progress-bar bg-warning" style="width: ${(partiallyCount / 6) * 100}%"></div>
                                <div class="progress-bar bg-danger" style="width: ${(absentCount / 6) * 100}%"></div>
                            </div>
                            <small class="text-muted">Curation Readiness: ${presentCount}/6 fields present</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    resultsContent.innerHTML = html;
    resultsContent.style.display = 'block';
    document.getElementById('empty-state').style.display = 'none';
}

// Render individual field card
function renderFieldCard(fieldKey, fieldDef, status, value, confidence, reason) {
    const statusClass = status.toLowerCase().replace('_', '-');
    const statusIcon = status === 'PRESENT' ? 'check-circle' : 
                     status === 'PARTIALLY_PRESENT' ? 'exclamation-triangle' : 'times-circle';
    const statusColor = status === 'PRESENT' ? 'success' : 
                       status === 'PARTIALLY_PRESENT' ? 'warning' : 'danger';
    
    return `
        <div class="col-md-6 mb-3">
            <div class="field-card ${statusClass}">
                <div class="d-flex align-items-start">
                    <div class="me-3">
                        <i class="fas fa-${fieldDef.icon} field-icon text-${statusColor}"></i>
                    </div>
                    <div class="flex-grow-1">
                        <h6 class="mb-2">
                            <i class="fas fa-${statusIcon} me-2 text-${statusColor}"></i>
                            ${fieldDef.name}
                            <span class="badge bg-${statusColor} ms-2">${status}</span>
                        </h6>
                        <p class="mb-2">
                            <strong>Value:</strong> 
                            <span class="text-muted">${value}</span>
                        </p>
                        <div class="mb-2">
                            <small class="text-muted">Confidence: ${(confidence * 100).toFixed(1)}%</small>
                            <div class="confidence-bar">
                                <div class="confidence-fill" style="width: ${confidence * 100}%"></div>
                            </div>
                        </div>
                        ${reason ? `<small class="text-muted"><strong>Note:</strong> ${reason}</small>` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Show alert message
function showAlert(message, type = 'info') {
    const alertBox = document.createElement('div');
    alertBox.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertBox.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alertBox.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(alertBox);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertBox.parentNode) {
            alertBox.parentNode.removeChild(alertBox);
        }
    }, 5000);
}
