# Performance Optimization Guide

## Overview

This document outlines the performance improvements implemented to resolve slow PMID query issues in BioAnalyzer.

## Issues Identified

### 1. Synchronous API Calls
- **Problem**: PubMed and PMC API calls were blocking the entire request
- **Impact**: Requests could hang indefinitely waiting for external APIs
- **Solution**: Added async support with timeout handling

### 2. No Timeout Handling
- **Problem**: API calls had no timeout limits
- **Impact**: Requests could hang for minutes or hours
- **Solution**: Implemented configurable timeouts for all API operations

### 3. Inefficient Caching
- **Problem**: Database connections were created/destroyed for each operation
- **Impact**: High overhead for cache operations
- **Solution**: Implemented connection pooling and async cache operations

### 4. Large Prompt Processing
- **Problem**: Very long prompts sent to Gemini API
- **Impact**: Slow AI analysis responses
- **Solution**: Optimized prompts and added timeout handling

## Performance Improvements Implemented

### 1. Async Operations

#### Data Retrieval Service
```python
# Before: Synchronous calls
metadata = retriever.get_paper_metadata(pmid)
full_text = retriever.get_pmc_fulltext(pmid)

# After: Concurrent async calls
metadata_task = retriever.get_paper_metadata_async(pmid)
full_text_task = retriever.get_pmc_fulltext_async(pmid)
metadata, full_text = await asyncio.gather(metadata_task, full_text_task)
```

#### Cache Manager
```python
# Before: Synchronous database operations
cached_result = cache_manager.get_analysis_result(pmid)

# After: Async operations with connection pooling
cached_result = await cache_manager.get_analysis_result_async(pmid)
```

### 2. Timeout Configuration

#### Environment Variables
```bash
# API timeouts (seconds)
API_TIMEOUT=30
ANALYSIS_TIMEOUT=45
GEMINI_TIMEOUT=30
FRONTEND_TIMEOUT=60

# Rate limiting
NCBI_RATE_LIMIT_DELAY=0.34
MAX_CONCURRENT_REQUESTS=3
```

#### Timeout Implementation
```python
# Data retrieval timeout
metadata, full_text = await asyncio.wait_for(
    asyncio.gather(metadata_task, full_text_task, return_exceptions=True),
    timeout=45.0  # 45 second timeout for entire operation
)

# Gemini API timeout
response = await asyncio.wait_for(
    loop.run_in_executor(None, model.generate_content, prompt),
    timeout=30.0  # 30 second timeout for AI analysis
)
```

### 3. Connection Pooling

#### Database Connections
```python
class CacheManager:
    def __init__(self):
        self._connection_pool = []
        self._max_connections = 5
    
    def _get_connection(self):
        if self._connection_pool:
            return self._connection_pool.pop()
        return sqlite3.connect(self.db_path)
    
    def _return_connection(self, conn):
        if len(self._connection_pool) < self._max_connections:
            self._connection_pool.append(conn)
        else:
            conn.close()
```

### 4. Frontend Improvements

#### Progress Indicators
```javascript
// Show detailed progress during analysis
showProgress('Retrieving paper metadata...', 25);
showProgress('Analyzing paper content...', 75);
showProgress('Analysis complete!', 100);
```

#### Timeout Handling
```javascript
// 60 second timeout with AbortController
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 60000);

const response = await fetch(`/enhanced_analysis/${pmid}`, {
    signal: controller.signal
});
```

## Configuration

### Environment Variables
Create a `.env` file in your project root:

```bash
# Performance Settings
API_TIMEOUT=30
ANALYSIS_TIMEOUT=45
GEMINI_TIMEOUT=30
FRONTEND_TIMEOUT=60

# Cache Settings
CACHE_VALIDITY_HOURS=24
MAX_CACHE_SIZE=1000

# Rate Limiting
NCBI_RATE_LIMIT_DELAY=0.34
MAX_CONCURRENT_REQUESTS=3

# Logging
LOG_LEVEL=INFO
```

### API Configuration
The system automatically uses these settings for:
- PubMed API calls
- PMC full-text retrieval
- Gemini AI analysis
- Cache operations

## Monitoring and Debugging

### Health Check Endpoint
```bash
curl http://localhost:8000/health
```

Response includes:
- System status
- Cache statistics
- Service availability

### Metrics Endpoint
```bash
curl http://localhost:8000/metrics
```

Response includes:
- Cache performance metrics
- Analysis statistics
- Recent activity

### Performance Monitor Script
```bash
# Test single PMID
python scripts/performance_monitor.py --pmid 12345

# Test multiple PMIDs
python scripts/performance_monitor.py --pmids 12345 67890 11111

# Test from file
python scripts/performance_monitor.py --file pmids.txt
```

## Expected Performance Improvements

### Before Optimization
- **Typical PMID query**: 2-5 minutes
- **Timeout issues**: Common
- **Cache misses**: Slow fallback
- **User experience**: Poor with long loading times

### After Optimization
- **Typical PMID query**: 15-45 seconds
- **Timeout handling**: Graceful with user feedback
- **Cache performance**: Fast retrieval for repeated queries
- **User experience**: Progress indicators and clear feedback

## Troubleshooting

### Common Issues

#### 1. Still Experiencing Slow Queries
- Check if the PMID exists in PubMed
- Verify network connectivity to NCBI APIs
- Check cache status: `/health` endpoint
- Review logs for specific error messages

#### 2. Timeout Errors
- Increase timeout values in environment variables
- Check if external APIs are responding slowly
- Verify Gemini API key and quota

#### 3. Cache Not Working
- Check database permissions
- Verify cache directory exists and is writable
- Check cache statistics: `/metrics` endpoint

### Debug Commands
```bash
# Check system health
curl http://localhost:8000/health

# Monitor performance
python scripts/performance_monitor.py --pmid 12345

# Check logs
tail -f logs/bioanalyzer.log

# Test specific endpoints
curl http://localhost:8000/enhanced_analysis/12345
```

## Best Practices

### 1. Use Caching
- First-time queries will be slower
- Subsequent queries for the same PMID will be much faster
- Cache is automatically managed and cleaned up

### 2. Monitor Performance
- Use the performance monitor script regularly
- Check health and metrics endpoints
- Monitor log files for errors

### 3. Optimize for Your Use Case
- Adjust timeout values based on your network conditions
- Modify cache settings based on your storage constraints
- Configure rate limiting based on your API quotas

## Future Improvements

### Planned Enhancements
1. **Background Processing**: Queue long-running analyses
2. **Distributed Caching**: Redis integration for better performance
3. **API Response Caching**: Cache external API responses
4. **Load Balancing**: Multiple worker processes
5. **Real-time Monitoring**: WebSocket-based progress updates

### Contributing
To contribute to performance improvements:
1. Identify bottlenecks using the performance monitor
2. Implement optimizations following the async pattern
3. Add appropriate timeout handling
4. Update this documentation
5. Test with various PMIDs and scenarios
