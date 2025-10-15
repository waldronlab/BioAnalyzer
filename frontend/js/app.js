// ---------------------------
// Global variables
// ---------------------------
window.chatHistory = [];
window.ws = null;
window.isConnected = false;
window.latestResults = [];

// ---------------------------
// Offline caching
// ---------------------------
const CACHE_KEY = 'bioanalyzer_cached_results';

const saveCache = () => {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(window.latestResults || []));
  } catch (e) {
    console.warn('Failed to save cache:', e);
  }
};

const loadCache = () => {
  try {
    const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || '[]');
    if (Array.isArray(cached) && cached.length) {
      window.latestResults = cached;
      displayResults(cached);
    }
  } catch (e) {
    console.warn('Failed to load cache:', e);
  }
};

// Load cached results on page load
document.addEventListener('DOMContentLoaded', () => loadCache());

// ---------------------------
// Default configuration
// ---------------------------
const appConfig = {
  frontend: {
    apiBaseUrl: '/api/v1',
    analysisTimeout: 60000,
    model: { hidden_size: 768, num_hidden_layers: 6, num_attention_heads: 12, intermediate_size: 3072 },
  },
  timeouts: { frontend: 60000, gemini: 30000, analysis: 45000 },
};

// ---------------------------
// Fetch and merge backend configuration
// ---------------------------
async function fetchConfig() {
  try {
    const response = await fetch('/api/v1/config');
    if (!response.ok) return console.warn('Config fetch failed:', response.status), appConfig;
    const config = await response.json();
    appConfig.frontend = { ...appConfig.frontend, ...(config.frontend || {}) };
    if (config.timeouts) {
      appConfig.timeouts = {
        frontend: (config.timeouts.frontend || appConfig.timeouts.frontend / 1000) * 1000,
        gemini: (config.timeouts.gemini || appConfig.timeouts.gemini / 1000) * 1000,
        analysis: (config.timeouts.analysis || appConfig.timeouts.analysis / 1000) * 1000,
      };
    }
    console.log('Configuration loaded:', appConfig);
    return appConfig;
  } catch (error) {
    console.warn('Config load failed, using defaults:', error);
    return appConfig;
  }
}

// ---------------------------
// Event listeners
// ---------------------------
const handleChatKeyPress = e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
};

document.addEventListener('DOMContentLoaded', async () => {
  console.log('DOM loaded, setting up event listeners...');
  await fetchConfig();
  const analyzeButton = document.getElementById('analyze-btn');
  const pmidInput = document.getElementById('singlePmid');
  
  console.log('Button found:', !!analyzeButton);
  console.log('PMID input found:', !!pmidInput);
  
  if (analyzeButton && pmidInput) {
    console.log('Setting up analyze button click handler...');
    analyzeButton.addEventListener('click', async () => {
      console.log('Analyze button clicked!');
      const pmid = pmidInput.value.trim();
      console.log('PMID entered:', pmid);
      
      if (!pmid) {
        console.log('No PMID entered, showing warning');
        return showAlert('Please enter a valid PubMed ID.', 'warning');
      }
      
      console.log('Starting analysis for PMID:', pmid);
      showLoading();
      try {
        const results = await handleSinglePmid(pmid);
        console.log('Analysis completed, results:', results);
        displayResults(results);
      } catch (e) {
        console.error('Analysis error:', e);
        showError(`Analysis failed: ${e.message}`);
      } finally {
        hideLoading();
      }
    });
  } else {
    console.error('Required elements not found:', { analyzeButton: !!analyzeButton, pmidInput: !!pmidInput });
  }

  const messageInput = document.getElementById('chat-input');
  if (messageInput) {
    messageInput.addEventListener('keydown', handleChatKeyPress);
  }

  document.querySelectorAll('.nav-tabs .nav-link').forEach(tab => {
    tab.addEventListener('click', e => {
      e.preventDefault();
      document.querySelectorAll('.nav-tabs .nav-link, .tab-pane').forEach(el => el.classList.remove('active', 'show'));
      tab.classList.add('active');
      document.querySelector(tab.getAttribute('data-bs-target'))?.classList.add('active', 'show');
    });
  });
});

// Clean up on unload
window.addEventListener('beforeunload', () => {
  if (window.ws) window.ws.close();
  const messageInput = document.getElementById('chat-input');
  if (messageInput) messageInput.removeEventListener('keydown', handleChatKeyPress);
});

// ---------------------------
// Utility functions
// ---------------------------
const showAlert = (message, type = 'info') => {
  const alertBox = document.getElementById('alert-box');
  if (alertBox) {
    alertBox.innerHTML = `<div class="alert ${type}"><strong>${type.toUpperCase()}:</strong> ${message}</div>`;
  } else {
    alert(message);
  }
};

const showLoading = () => {
  const loading = document.getElementById('loading');
  if (loading) {
    loading.innerHTML = `<div class="text-center"><div class="spinner-border text-primary mb-3" role="status"><span class="visually-hidden">Loading...</span></div><p class="text-muted">Initializing analysis...</p><p class="text-muted small">This may take up to 60 seconds for complex papers</p></div>`;
    loading.style.display = 'block';
  }
  ['empty-state', 'results-content'].forEach(id => document.getElementById(id)?.style.display = 'none');
};

const hideLoading = () => document.getElementById('loading')?.style.display = 'none';

const showError = message => {
  const resultsContent = document.getElementById('results-content');
  if (resultsContent) {
    resultsContent.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i><div style="white-space: pre-line; font-family: monospace; font-size: 0.9em;">${escapeHtml(message).replace(/\n/g, '<br>')}</div></div>`;
    resultsContent.style.display = 'block';
  }
  document.getElementById('empty-state')?.style.display = 'none';
};

const showProgress = (message, percentage) => {
  const loading = document.getElementById('loading');
  if (loading) {
    const timeEstimate = percentage < 50 ? 'Estimated time: 30-45 seconds' : 
                        percentage < 80 ? 'Estimated time: 10-20 seconds' : 
                        'Almost done...';
    loading.innerHTML = `<div class="text-center"><div class="spinner-border text-primary mb-3" role="status"><span class="visually-hidden">Loading...</span></div><div class="progress mb-3" style="height: 20px;"><div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: ${percentage}%" aria-valuenow="${percentage}" aria-valuemin="0" aria-valuemax="100">${percentage}%</div></div><p class="text-muted">${message}</p><p class="text-muted small">${timeEstimate}</p></div>`;
    loading.style.display = 'block';
  }
};

const escapeHtml = str => String(str).replace(/[&<>"'\/]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;', '/': '&#x2F;' }[c]));

// ---------------------------
// Core analysis functions
// ---------------------------
window.analyzePapers = async () => {
  const fileInput = document.getElementById('fileInput');
  const singlePmid = document.getElementById('singlePmid').value.trim();
  const batchPmids = document.getElementById('batchPmids').value.trim();
  if (!fileInput.files.length && !singlePmid && !batchPmids) return showError('Please provide input: upload a file, enter a PMID, or provide a list of PMIDs');
  await fetchConfig();
  showLoading();
  try {
    let results = [];
    if (fileInput.files.length) {
      showProgress('Processing file...', 10);
      results = await handleFileUpload(fileInput.files[0]);
    } else if (singlePmid) {
      showProgress('Starting analysis...', 10);
      results = await handleSinglePmid(singlePmid);
    } else if (batchPmids) {
      showProgress('Processing batch...', 10);
      results = await analyzeBatchStreaming(batchPmids.split(/[,\n]/).map(p => p.trim()).filter(Boolean));
    }
    displayResults(results);
  } catch (error) {
    console.error('Analysis error:', error);
    let errorMessage = 'Analysis failed. Please try again.';
    
    if (error.message.includes('timeout') || error.message.includes('AbortError')) {
      errorMessage = 'Analysis timed out. The paper may be complex or the service is busy. Please try again.';
    } else if (error.message.includes('404')) {
      errorMessage = 'Paper not found. Please verify the PMID is correct.';
    } else if (error.message.includes('500')) {
      errorMessage = 'Server error occurred. Please try again later or contact support.';
    } else if (error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
      errorMessage = 'Network error. Please check your connection and try again.';
    } else if (error.message) {
      errorMessage = `Analysis failed: ${error.message}`;
    }
    
    showError(errorMessage);
  } finally {
    hideLoading();
  }
};

// ---------------------------
// File upload handler
// ---------------------------
async function handleFileUpload(file) {
  if (!file) throw new Error('No file selected');
  const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
  if (!['.csv', '.xls', '.xlsx'].includes(ext)) throw new Error('Please select a CSV or Excel file');
  const maxSize = ext === '.csv' ? 5 * 1024 * 1024 : 10 * 1024 * 1024;
  if (file.size > maxSize) throw new Error(`File size must be less than ${maxSize / (1024 * 1024)}MB`);
  const formData = new FormData();
  formData.append('file', file);
  try {
    const response = await fetch('/api/v1/upload_csv', { method: 'POST', body: formData });
    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage = `Upload failed (${response.status})`;
      try {
        const errorData = JSON.parse(errorText);
        if (errorData.detail) errorMessage = errorData.detail;
      } catch {}
      throw new Error(errorMessage);
    }
    const data = await response.json();
    if (data.error) throw new Error(data.error);
    const pmids = Array.isArray(data.pmids) ? data.pmids : [];
    if (pmids.length) {
      showProgress('Starting batch analysis...', 15);
      return await analyzeBatchStreaming(pmids);
    }
    return [];
  } catch (error) {
    console.error('File upload error:', error);
    throw error;
  }
}

// ---------------------------
// Single PMID handler
// ---------------------------
async function handleSinglePmid(pmid, retryCount = 0) {
  console.log(`Starting analysis for PMID: ${pmid}, retry: ${retryCount}`);
  await fetchConfig();
  const timeout = appConfig.frontend.analysisTimeout || appConfig.timeouts.analysis || 60000;
  const maxRetries = 2;
  
  console.log(`Using timeout: ${timeout}ms`);
  showProgress('Retrieving paper metadata...', 25);
  const controller = new AbortController();
  let timeoutId, progressInterval;
  
  try {
    timeoutId = setTimeout(() => {
      console.log('Request timed out, aborting...');
      controller.abort();
    }, timeout);
    const startTime = Date.now();
    progressInterval = setInterval(() => {
      const currentProgress = Math.min(75, 25 + ((Date.now() - startTime) / (timeout * 0.75)) * 50);
      showProgress('Analyzing paper content...', Math.round(currentProgress));
    }, 2000);
    
    console.log(`Making API request to: /api/v1/analyze/${pmid}`);
    const response = await fetch(`/api/v1/analyze/${pmid}`, { 
      signal: controller.signal, 
      headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' } 
    });
    
    console.log(`API response status: ${response.status}`);
    
    clearTimeout(timeoutId);
    clearInterval(progressInterval);
    
    if (!response.ok) {
      if (response.status === 500 && retryCount < maxRetries) {
        showProgress(`Retrying analysis (attempt ${retryCount + 2}/${maxRetries + 1})...`, 10);
        await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds before retry
        return handleSinglePmid(pmid, retryCount + 1);
      }
      throw new Error(response.status === 408 ? 'Request timed out.' : response.status === 404 ? 'Paper not found.' : response.status === 500 ? 'Server error.' : `HTTP error: ${response.status}`);
    }
    
    showProgress('Analysis complete!', 100);
    const data = await response.json();
    if (data.error) throw new Error(data.error_type && data.debug_info ? formatDetailedError(data.error, data.error_type, data.debug_info) : data.error);
    return [{ pmid, title: data.title || 'N/A', enhanced_analysis: data.fields || data }];
  } catch (error) {
    clearTimeout(timeoutId);
    clearInterval(progressInterval);
    
    if (error.name === 'AbortError') {
      showAlert(`Analysis timed out after ${timeout / 1000} seconds. The paper may be complex or the service is busy. Please try again.`, 'warning');
      throw new Error('Analysis timed out');
    }
    
    // Retry on network errors
    if ((error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) && retryCount < maxRetries) {
      showProgress(`Retrying analysis (attempt ${retryCount + 2}/${maxRetries + 1})...`, 10);
      await new Promise(resolve => setTimeout(resolve, 2000));
      return handleSinglePmid(pmid, retryCount + 1);
    }
    
    showAlert(`Analysis failed: ${error.message}`, 'error');
    throw error;
  }
}

// ---------------------------
// Batch PMID handler (with streaming & live progress)
// ---------------------------
const analyzeBatchStreaming = pmids => new Promise((resolve, reject) => {
  const results = [];
  const total = pmids.length;
  let processed = 0;

  const es = new EventSource(`/api/v1/enhanced_analysis_batch_stream?pmids=${encodeURIComponent(pmids.join(','))}&max_concurrent=1`);
  
  es.onmessage = event => {
    try {
      const data = JSON.parse(event.data);
      if (data?.pmid) {
        appendResult(data);
        results.push(data);
        processed += 1;

        // Update progress dynamically
        const percent = Math.min(100, Math.round((processed / total) * 100));
        showProgress(`Analyzing batch (${processed}/${total})`, percent);

        // Save cache after each item
        saveCache();
      }
    } catch (e) {
      console.warn('Failed to parse streaming event:', e);
    }
  };

  es.addEventListener('done', () => {
    es.close();
    showProgress('Batch analysis complete!', 100);
    resolve(results);
  });

  es.onerror = err => {
    console.warn('Streaming error:', err);
    try { es.close(); } catch {}
    resolve(results);
  };
});

// ---------------------------
// Append result & save cache
// ---------------------------
const appendResult = result => {
  const resultsContent = document.getElementById('results-content');
  const emptyState = document.getElementById('empty-state');
  const loading = document.getElementById('loading');
  if (emptyState) emptyState.style.display = 'none';
  if (loading) loading.style.display = 'none';
  if (resultsContent && resultsContent.style.display !== 'block') {
    resultsContent.innerHTML = `
      <div class="d-flex justify-content-between align-items-center mb-4">
        <h4 class="mb-0"><i class="fas fa-chart-bar me-2"></i>Analysis Results</h4>
        <div>
          <button class="btn btn-outline-success btn-sm me-2" onclick="exportResults()"><i class="fas fa-download me-2"></i>Export CSV</button>
          <button class="btn btn-outline-secondary btn-sm" onclick="clearResults()"><i class="fas fa-trash me-2"></i>Clear</button>
        </div>
      </div>
      <div class="row"><div class="col-md-12"><div class="card bg-light"><div class="card-body text-center"><h5 class="card-title">Papers Analyzed</h5><h2 class="text-primary" id="results-count">0</h2></div></div></div></div>`;
    resultsContent.style.display = 'block';
  }
  resultsContent.innerHTML += renderResultCard(result);
  window.latestResults = [...(window.latestResults || []), result];

  // Save cache
  saveCache();

  const countEl = document.getElementById('results-count');
  if (countEl) countEl.textContent = String((parseInt(countEl.textContent || '0', 10) || 0) + 1);
};

// ---------------------------
// Display results
// ---------------------------
const displayResults = results => {
  window.latestResults = Array.isArray(results) ? results.slice() : [];
  if (!results?.length) return showError('No results to display');
  const resultsContent = document.getElementById('results-content');
  if (!resultsContent) return console.error('Results content element not found');
  let html = `
    <div class="d-flex justify-content-between align-items-center mb-4">
      <h4 class="mb-0"><i class="fas fa-chart-bar me-2"></i>Analysis Results</h4>
      <div>
        <button class="btn btn-outline-success btn-sm me-2" onclick="exportResults()"><i class="fas fa-download me-2"></i>Export CSV</button>
        <button class="btn btn-outline-secondary btn-sm" onclick="clearResults()"><i class="fas fa-trash me-2"></i>Clear</button>
      </div>
    </div>
    <div class="row"><div class="col-md-12"><div class="card bg-light"><div class="card-body text-center"><h5 class="card-title">Papers Analyzed</h5><h2 class="text-primary">${results.length}</h2></div></div></div></div>`;
  results.forEach(r => html += renderResultCard(r));
  resultsContent.innerHTML = html;
  resultsContent.style.display = 'block';
  document.getElementById('empty-state')?.style.display = 'none';
};

// ---------------------------
// Export & Clear Results
// ---------------------------
window.exportResults = () => {
  try {
    const rows = window.latestResults || [];
    if (!rows.length) return showAlert('No results to export.', 'warning');
    const header = ['pmid', 'title', 'host_species.value', 'host_species.status', 'host_species.confidence', 'body_site.value', 'body_site.status', 'body_site.confidence', 'condition.value', 'condition.status', 'condition.confidence', 'sequencing_type.value', 'sequencing_type.status', 'sequencing_type.confidence', 'taxa_level.value', 'taxa_level.status', 'taxa_level.confidence', 'sample_size.value', 'sample_size.status', 'sample_size.confidence'];
    const esc = s => {
      const x = String(s ?? '');
      return /[,"\n]/.test(x) ? `"${x.replace(/"/g, '""')}"` : x;
    };
    const lines = [header.join(',')];
    for (const r of rows) {
      const a = r?.enhanced_analysis || {};
      lines.push([
        esc(r.pmid), esc(r.title),
        esc(a.host_species?.value ?? ''),
        esc(a.host_species?.status ?? ''), esc(a.host_species?.confidence ?? ''),
        esc(a.body_site?.value ?? ''),
        esc(a.body_site?.status ?? ''), esc(a.body_site?.confidence ?? ''),
        esc(a.condition?.value ?? ''),
        esc(a.condition?.status ?? ''), esc(a.condition?.confidence ?? ''),
        esc(a.sequencing_type?.value ?? ''),
        esc(a.sequencing_type?.status ?? ''), esc(a.sequencing_type?.confidence ?? ''),
        esc(a.taxa_level?.value ?? ''),
        esc(a.taxa_level?.status ?? ''), esc(a.taxa_level?.confidence ?? ''),
        esc(a.sample_size?.value ?? ''),
        esc(a.sample_size?.status ?? ''), esc(a.sample_size?.confidence ?? '')
      ].join(','));
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'bioanalyzer_results.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (e) {
    console.error('Export failed:', e);
    showAlert('Failed to export results', 'error');
  }
};

window.clearResults = () => {
  document.getElementById('results-content').style.display = 'none';
  document.getElementById('empty-state').style.display = 'block';
  ['fileInput', 'singlePmid', 'batchPmids'].forEach(id => document.getElementById(id).value = '');
  window.latestResults = [];
  localStorage.removeItem(CACHE_KEY);
};

// ---------------------------
// Chat functions
// ---------------------------
const sendMessage = () => {
  const input = document.getElementById('chat-input');
  if (!input?.value.trim()) return;
  displayChatMessage(input.value.trim(), 'user');
  input.value = '';
  setTimeout(() => displayChatMessage('Thank you for your message. The assistant is being configured.', 'assistant'), 1000);
};

const displayChatMessage = (message, role) => {
  const chatMessages = document.getElementById('chat-messages');
  if (!chatMessages) return;
  const div = document.createElement('div');
  div.className = `mb-3 ${role === 'user' ? 'text-end' : 'text-start'}`;
  const bubble = document.createElement('div');
  bubble.className = `d-inline-block p-2 rounded ${role === 'user' ? 'bg-primary text-white' : 'bg-light'}`;
  bubble.style.maxWidth = '70%';
  bubble.textContent = message;
  div.appendChild(bubble);
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
};

// ---------------------------
// Render result card
// ---------------------------
const renderResultCard = result => {
  const a = result?.enhanced_analysis || {};
  const fields = [
    { icon: 'dna', name: 'Host Species', key: 'host_species', value: a.host_species?.value || 'Not found' },
    { icon: 'map-marker-alt', name: 'Body Site', key: 'body_site', value: a.body_site?.value || 'Not found' },
    { icon: 'stethoscope', name: 'Condition', key: 'condition', value: a.condition?.value || 'Not found' },
    { icon: 'microscope', name: 'Sequencing Type', key: 'sequencing_type', value: a.sequencing_type?.value || 'Not found' },
    { icon: 'sitemap', name: 'Taxa Level', key: 'taxa_level', value: a.taxa_level?.value || 'Not found' },
    { icon: 'hashtag', name: 'Sample Size', key: 'sample_size', value: a.sample_size?.value || 'Not found' },
  ];
  return `
    <div class="card mt-3">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h6 class="mb-0"><strong>PMID ${result.pmid || ''}</strong> - ${escapeHtml(result.title || 'N/A')}</h6>
      </div>
      <div class="card-body">
        ${fields.map((f, i) => `
          <div class="col-md-6${i % 2 ? '' : ' mt-3 mt-md-0'}">
            <div class="field-card">
              <h6><i class="fas fa-${f.icon} me-2"></i>${f.name}</h6>
              <p class="mb-1"><strong>Value:</strong> ${f.value}</p>
              <p class="mb-1"><strong>Status:</strong> <span class="status-${a[f.key]?.status?.toLowerCase() || 'absent'}">${a[f.key]?.status || 'ABSENT'}</span></p>
              <p class="mb-1"><strong>Confidence:</strong> ${(a[f.key]?.confidence || 0).toFixed(2)}</p>
              ${a[f.key]?.reason_if_missing ? `<p class="mb-1"><strong>Note:</strong> ${a[f.key].reason_if_missing}</p>` : ''}
            </div>
          </div>
        `).reduce((rows, field, i) => {
          if (i % 2 === 0) rows.push([]);
          rows[rows.length - 1].push(field);
          return rows;
        }, []).map(row => `<div class="row">${row.join('')}</div>`).join('')}
        ${a.missing_fields?.length ? `
          <div class="alert alert-warning mt-3">
            <h6><i class="fas fa-exclamation-triangle me-2"></i>Missing Fields</h6>
            <p class="mb-1"><strong>Fields to review:</strong> ${a.missing_fields.join(', ')}</p>
            <p class="mb-0"><strong>Summary:</strong> ${a.curation_preparation_summary || 'Review required'}</p>
          </div>
        ` : ''}
        ${a.error ? `
          <div class="alert alert-danger mt-3">
            <h6><i class="fas fa-exclamation-circle me-2"></i>Analysis Error</h6>
            <p class="mb-1"><strong>Error Type:</strong> ${a.error_type || 'Unknown'}</p>
            <p class="mb-1"><strong>Error:</strong> ${a.error}</p>
            ${a.debug_info ? `
              <details class="mt-2">
                <summary><strong>Debug Information</strong></summary>
                <div class="mt-2 p-2 bg-light rounded" style="font-family: monospace; font-size: 0.8em;">
                  ${Object.entries(a.debug_info).map(([k, v]) => `<div><strong>${k}:</strong> ${v}</div>`).join('')}
                </div>
              </details>
            ` : ''}
          </div>
        ` : ''}
      </div>
    </div>`;
};

// ---------------------------
// Format error messages
// ---------------------------
const formatDetailedError = (error, errorType, debugInfo) => {
  let msg = `🚨 ${error}\n\n`;
  if (errorType) msg += `📋 Error Type: ${errorType}\n`;
  if (debugInfo) {
    if (debugInfo.issue) msg += `🔍 Issue: ${debugInfo.issue}\n`;
    if (debugInfo.solution) msg += `💡 Solution: ${debugInfo.solution}\n`;
    if (debugInfo.suggestions?.length) msg += `💡 Suggestions:\n${debugInfo.suggestions.map(s => `   • ${s}`).join('\n')}\n`;
    if (debugInfo.timestamp) msg += `⏰ Timestamp: ${debugInfo.timestamp}\n`;
  }
  if (errorType?.includes('API') || errorType?.includes('Gemini')) {
    msg += `\n🔧 Troubleshooting:\n   1. Check Gemini API key\n   2. Verify IP restrictions\n   3. Check API quota\n   4. Ensure API permissions\n   5. Check network connectivity\n`;
  }
  return msg;
};

// ---------------------------
// Legacy compatibility
// ---------------------------
window.analyzeSinglePaper = window.analyzePapers;
window.analyzeBatchPapers = window.analyzePapers;
window.showLoading = showLoading;
window.hideLoading = hideLoading;
window.showError = showError;
window.displayResults = displayResults;