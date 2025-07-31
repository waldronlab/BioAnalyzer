# BugSigDB Curation Criteria Fixes

## Problem Identified

The paper PMID: 29469650 "Prenatal androgen exposure causes hypertension and gut microbiota dysbiosis" was incorrectly classified as "NOT READY FOR CURATION" despite containing clear microbial signatures that make it suitable for BugSigDB curation.

## Root Cause Analysis

The issue was in multiple components of the system:

1. **LLM Prompt Too Generic**: The Gemini QA prompt didn't provide specific criteria for what constitutes a curatable microbial signature
2. **Backend Logic Too Restrictive**: The backend curation criteria were overly strict and didn't properly utilize LLM analysis results
3. **Confidence Threshold Too High**: The BugSigDB analyzer used a confidence threshold of 0.4, which was too restrictive

## Fixes Implemented

### 1. Enhanced LLM Prompt (`models/gemini_qa.py`)

**Before:**
- Generic prompt without clear criteria
- No specific guidance on what makes a paper curatable

**After:**
- Added specific criteria for READY FOR CURATION:
  - Differential abundance of specific microbial taxa
  - Microbial community composition changes
  - Specific bacterial/fungal/viral taxa identification
  - Metagenomic or 16S sequencing results
  - Microbial signatures associated with health outcomes
- Clear criteria for NOT READY FOR CURATION:
  - Only if purely review article with no original research
  - Only if contains NO microbial data or sequencing results
  - Only if mentions "microbiome" in passing without specific findings

### 2. Improved Backend Logic (`web/app.py`)

**Before:**
```python
elif has_signature and has_citation and has_microbiome_keyword:
    curation_status = "ready"
```

**After:**
```python
# More comprehensive microbiome keyword detection
microbiome_keywords = [
    'microbiome', 'microbiota', 'microbial', 'bacteria', 'bacterial',
    'dysbiosis', 'abundance', 'taxonomic', 'community', 'sequencing',
    '16s', 'metagenomic', 'shotgun', 'amplicon'
]

# Check if LLM analysis indicates readiness
curation_analysis = analysis.get('curation_analysis', {})
llm_readiness = curation_analysis.get('readiness', 'UNKNOWN')

if llm_readiness == "READY":
    curation_status = "ready"
elif has_signature and has_citation and has_microbiome_keyword:
    curation_status = "ready"
elif llm_readiness == "NOT_READY":
    curation_status = "not_ready"
```

### 3. Lowered Confidence Threshold (`utils/bugsigdb_analyzer.py`)

**Before:**
```python
has_signatures = (
    confidence > 0.4 and
    len(found_terms['general']) >= 1 and
    len(found_terms['methods']) >= 1
)
```

**After:**
```python
has_signatures = (
    confidence > 0.2 and  # Lowered from 0.4 to 0.2
    len(found_terms['general']) >= 1 and
    (len(found_terms['methods']) >= 1 or len(found_terms['analysis']) >= 1)  # More flexible
)
```

## Expected Results

With these fixes, papers like PMID: 29469650 should now be correctly identified as "READY FOR CURATION" because they contain:

1. **Specific microbial taxa identification**: "Nocardiaceae and Clostridiaceae", "Akkermansia, Bacteroides, Lactobacillus, Clostridium"
2. **Differential abundance data**: "higher relative abundance", "lower abundance"
3. **Health outcome associations**: Links to hypertension and cardiometabolic function
4. **Experimental design**: Well-controlled study with proper methodology

## Testing Recommendations

1. Test the paper PMID: 29469650 to verify it's now classified as "READY FOR CURATION"
2. Test other papers with similar characteristics to ensure consistency
3. Monitor the system to ensure the changes don't create false positives
4. Consider adding unit tests for the curation criteria

## Impact

These changes will:
- Improve accuracy of curation readiness assessment
- Reduce false negatives (papers incorrectly marked as not ready)
- Provide more comprehensive microbial signature detection
- Better utilize LLM analysis capabilities
- Make the system more inclusive for papers with valid microbial signatures 