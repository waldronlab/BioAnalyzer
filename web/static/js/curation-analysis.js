// Enhanced Curation Analysis Display Functions

function displayEnhancedCurationAnalysis(curationAnalysis) {
    if (!curationAnalysis) {
        console.warn('No curation analysis data provided');
        return;
    }

    // Display curation readiness status
    displayCurationReadinessStatus(curationAnalysis.readiness, curationAnalysis.explanation);
    
    // Display detailed explanation
    displayCurationExplanation(curationAnalysis.explanation);
    
    // Display microbial signature analysis
    displayMicrobialSignatureAnalysis(curationAnalysis);
    
    // Display specific reasons
    displaySpecificReasons(curationAnalysis.specific_reasons);
    
    // Display examples and evidence
    displayExamplesAndEvidence(curationAnalysis.examples);
    
    // Display missing fields if any
    displayMissingFields(curationAnalysis.missing_fields);
}

function displayCurationReadinessStatus(readiness, explanation) {
    const statusElement = document.getElementById('curation-readiness-status');
    const textElement = document.getElementById('curation-readiness-text');
    
    if (!statusElement || !textElement) return;
    
    // Clear previous classes
    statusElement.className = 'alert';
    
    switch (readiness) {
        case 'READY':
            statusElement.classList.add('alert-success');
            textElement.innerHTML = '<strong>READY FOR CURATION</strong> - This paper contains curatable microbial signatures and meets BugSigDB requirements.';
            break;
        case 'NOT_READY':
            statusElement.classList.add('alert-warning');
            textElement.innerHTML = '<strong>NOT READY FOR CURATION</strong> - This paper lacks required elements for BugSigDB curation.';
            break;
        case 'ERROR':
            statusElement.classList.add('alert-danger');
            textElement.innerHTML = '<strong>ANALYSIS ERROR</strong> - Unable to determine curation readiness due to analysis error.';
            break;
        default:
            statusElement.classList.add('alert-info');
            textElement.innerHTML = '<strong>ANALYSIS PENDING</strong> - Curation readiness assessment in progress...';
    }
}

function displayCurationExplanation(explanation) {
    const element = document.getElementById('curation-explanation-text');
    if (element) {
        element.textContent = explanation || 'No detailed explanation available.';
    }
}

function displayMicrobialSignatureAnalysis(analysis) {
    // Display signature presence
    const signaturesElement = document.getElementById('microbial-signatures');
    if (signaturesElement) {
        const presence = analysis.microbial_signatures || 'Unknown';
        signaturesElement.textContent = presence;
        signaturesElement.className = `card-text ${getPresenceColorClass(presence)}`;
    }
    
    // Display data quality
    const qualityElement = document.getElementById('data-quality');
    if (qualityElement) {
        const quality = analysis.data_quality || 'Unknown';
        qualityElement.textContent = quality;
        qualityElement.className = `card-text ${getQualityColorClass(quality)}`;
    }
    
    // Display statistical significance
    const significanceElement = document.getElementById('statistical-significance');
    if (significanceElement) {
        const significance = analysis.statistical_significance || 'Unknown';
        significanceElement.textContent = significance;
        significanceElement.className = `card-text ${getSignificanceColorClass(significance)}`;
    }
    
    // Display signature types
    const typesElement = document.getElementById('signature-types');
    if (typesElement) {
        const types = analysis.signature_types || [];
        if (types.length > 0) {
            typesElement.innerHTML = types.map(type => 
                `<span class="badge bg-primary me-1 mb-1">${type}</span>`
            ).join('');
        } else {
            typesElement.innerHTML = '<span class="text-muted">No signature types identified</span>';
        }
    }
    
    // Display data completeness
    const completenessElement = document.getElementById('data-completeness');
    if (completenessElement) {
        const completeness = analysis.data_completeness || 'Unknown';
        completenessElement.textContent = completeness;
        completenessElement.className = `card-text ${getCompletenessColorClass(completeness)}`;
    }
}

function displaySpecificReasons(reasons) {
    const listElement = document.getElementById('specific-reasons-list');
    if (!listElement) return;
    
    if (reasons && reasons.length > 0) {
        listElement.innerHTML = reasons.map(reason => 
            `<li class="mb-2"><i class="fas fa-arrow-right text-primary me-2"></i>${reason}</li>`
        ).join('');
    } else {
        listElement.innerHTML = '<li class="text-muted">No specific reasons provided</li>';
    }
}

function displayExamplesAndEvidence(examples) {
    const listElement = document.getElementById('examples-list');
    if (!listElement) return;
    
    if (examples && examples.length > 0) {
        listElement.innerHTML = examples.map(example => 
            `<li class="mb-2"><i class="fas fa-quote-left text-secondary me-2"></i>${example}</li>`
        ).join('');
    } else {
        listElement.innerHTML = '<li class="text-muted">No examples or evidence provided</li>';
    }
}

function displayMissingFields(missingFields) {
    const sectionElement = document.getElementById('missing-fields-section');
    const listElement = document.getElementById('missing-fields-list');
    
    if (!sectionElement || !listElement) return;
    
    if (missingFields && missingFields.length > 0) {
        listElement.innerHTML = missingFields.map(field => 
            `<li class="mb-1"><i class="fas fa-times-circle text-danger me-2"></i>${field}</li>`
        ).join('');
        sectionElement.style.display = 'block';
    } else {
        sectionElement.style.display = 'none';
    }
}

// Helper functions for color coding
function getPresenceColorClass(presence) {
    switch (presence.toLowerCase()) {
        case 'present': return 'text-success fw-bold';
        case 'absent': return 'text-danger fw-bold';
        case 'partial': return 'text-warning fw-bold';
        default: return 'text-muted';
    }
}

function getQualityColorClass(quality) {
    switch (quality.toLowerCase()) {
        case 'high': return 'text-success fw-bold';
        case 'medium': return 'text-warning fw-bold';
        case 'low': return 'text-danger fw-bold';
        default: return 'text-muted';
    }
}

function getSignificanceColorClass(significance) {
    switch (significance.toLowerCase()) {
        case 'yes': return 'text-success fw-bold';
        case 'no': return 'text-danger fw-bold';
        case 'insufficient': return 'text-warning fw-bold';
        default: return 'text-muted';
    }
}

function getCompletenessColorClass(completeness) {
    switch (completeness.toLowerCase()) {
        case 'complete': return 'text-success fw-bold';
        case 'partial': return 'text-warning fw-bold';
        case 'insufficient': return 'text-danger fw-bold';
        default: return 'text-muted';
    }
}

// Function to clear curation analysis display
function clearCurationAnalysis() {
    const elements = [
        'curation-readiness-text',
        'curation-explanation-text',
        'microbial-signatures',
        'data-quality',
        'statistical-significance',
        'signature-types',
        'data-completeness',
        'specific-reasons-list',
        'examples-list',
        'missing-fields-list'
    ];
    
    elements.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.innerHTML = '<span class="text-muted">Loading...</span>';
        }
    });
    
    // Hide missing fields section
    const missingSection = document.getElementById('missing-fields-section');
    if (missingSection) {
        missingSection.style.display = 'none';
    }
    
    // Reset status alert
    const statusElement = document.getElementById('curation-readiness-status');
    if (statusElement) {
        statusElement.className = 'alert alert-info';
    }
}

// Export functions for use in main app.js
window.displayEnhancedCurationAnalysis = displayEnhancedCurationAnalysis;
window.clearCurationAnalysis = clearCurationAnalysis; 