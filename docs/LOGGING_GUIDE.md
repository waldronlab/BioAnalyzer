# Logging Guide for BioAnalyzer

## Overview

BioAnalyzer now includes a comprehensive logging system that tracks all PMID queries, API calls, cache operations, and performance metrics. This system will help you troubleshoot performance issues and monitor system health.

## Log Files

The system creates several specialized log files in the `logs/` directory:

### 1. **bioanalyzer.log** - Main Application Log
- General application events
- System startup/shutdown
- General errors and warnings
- User requests and responses

### 2. **performance.log** - Performance Metrics
- PMID query start/end times
- API call durations and success rates
- Cache operation performance
- Analysis step timing
- Detailed performance metrics

### 3. **errors.log** - Error Tracking
- Detailed error information
- Stack traces
- Error context and PMID information
- System failures and exceptions

### 4. **api_calls.log** - External API Calls
- PubMed API calls
- PMC API calls
- Gemini API calls
- Success/failure rates and timing

## Log Format

All log entries follow a consistent format:

```
TIMESTAMP - LOGGER_NAME - LEVEL - FUNCTION:LINE - MESSAGE
```

### Performance Log Format

```
PMID_QUERY_START - PMID: 12345 | User-Agent: Mozilla/5.0... | IP: 192.168.1.100 | Timestamp: 2024-01-15T10:30:00
PMID_QUERY_END - PMID: 12345 | Status: SUCCESS | Duration: 25.34s | Cache: FRESH | Error: None | Timestamp: 2024-01-15T10:30:25
API_CALL - Service: PubMed | Operation: efetch | PMID: 12345 | Duration: 2.45s | Status: SUCCESS | Error: None | Timestamp: 2024-01-15T10:30:02
CACHE_OP - Operation: STORE | PMID: 12345 | Type: analysis | Duration: 0.023s | Status: SUCCESS | Timestamp: 2024-01-15T10:30:25
ANALYSIS_STEP - PMID: 12345 | Step: data_retrieval | Duration: 3.12s | Details: {"metadata_success": true, "fulltext_success": true} | Timestamp: 2024-01-15T10:30:03
```

## Monitoring Tools

### 1. **Real-time Log Viewer**
```bash
# Monitor all logs in real-time
python scripts/log_viewer.py

# Monitor specific log types
python scripts/log_viewer.py --logs performance errors

# Filter logs for specific patterns
python scripts/log_viewer.py --filter "PMID.*12345"

# Highlight important patterns
python scripts/log_viewer.py --highlight "ERROR|FAILED|TIMEOUT"
```

### 2. **Performance Dashboard**
```bash
# Start real-time dashboard
python scripts/log_dashboard.py

# Custom refresh interval
python scripts/log_dashboard.py --refresh 10
```

### 3. **Log Cleanup and Management**
```bash
# Show log information
python scripts/log_cleanup.py --info

# Clean up old logs (older than 7 days)
python scripts/log_cleanup.py --cleanup 7

# Rotate logs manually
python scripts/log_cleanup.py --rotate

# Compress old logs
python scripts/log_cleanup.py --compress

# Reset all logs (clear content)
python scripts/log_cleanup.py --reset
```

## Performance Analysis

### Understanding Performance Logs

#### Query Lifecycle
1. **PMID_QUERY_START** - Query begins
2. **CACHE_OP GET** - Check cache (if applicable)
3. **API_CALL** - External API requests
4. **ANALYSIS_STEP** - Processing steps
5. **CACHE_OP STORE** - Store results
6. **PMID_QUERY_END** - Query completes

#### Performance Metrics
- **Duration**: Total time for PMID analysis
- **Cache Status**: Whether result was served from cache
- **API Performance**: Individual API call timing
- **Step Timing**: Time for each analysis phase

### Identifying Bottlenecks

#### High Duration Issues
```bash
# Find slow queries (>30 seconds)
grep "Duration: [3-9][0-9]\." logs/performance.log

# Find very slow queries (>60 seconds)
grep "Duration: [6-9][0-9]\." logs/performance.log
```

#### API Performance Issues
```bash
# Find slow PubMed API calls
grep "Service: PubMed.*Duration: [2-9]" logs/performance.log

# Find failed API calls
grep "Status: FAILED" logs/performance.log
```

#### Cache Performance
```bash
# Check cache hit rate
grep "Cache: CACHED" logs/performance.log | wc -l
grep "Cache: FRESH" logs/performance.log | wc -l
```

## Troubleshooting Common Issues

### 1. **Slow PMID Queries**

#### Check Performance Logs
```bash
# Find the specific PMID
grep "PMID: 12345" logs/performance.log

# Look for timing breakdown
grep -A 5 -B 5 "PMID: 12345" logs/performance.log
```

#### Check API Performance
```bash
# Look for slow API calls
grep "Duration: [5-9]" logs/api_calls.log

# Check for API failures
grep "Status: FAILED" logs/api_calls.log
```

### 2. **Cache Issues**

#### Check Cache Operations
```bash
# Look for cache failures
grep "Status: FAILED" logs/performance.log | grep "CACHE_OP"

# Check cache timing
grep "CACHE_OP" logs/performance.log | grep "Duration: [0-9]"
```

### 3. **Error Investigation**

#### Find Error Details
```bash
# Get full error context
grep -A 10 "PMID: 12345" logs/errors.log

# Search for specific error types
grep "TimeoutError" logs/errors.log
grep "ConnectionError" logs/errors.log
```

## Log Configuration

### Environment Variables
```bash
# Log level (DEBUG, INFO, WARNING, ERROR)
export LOG_LEVEL=INFO

# Log directory
export LOG_DIR=logs

# Log rotation settings
export MAX_LOG_SIZE=10485760  # 10MB
export MAX_LOG_FILES=5
```

### Log Rotation
The system automatically rotates logs when they reach 10MB and keeps 5 rotated files:
- `bioanalyzer.log` (current)
- `bioanalyzer.log.1` (previous)
- `bioanalyzer.log.2` (older)
- etc.

## Best Practices

### 1. **Regular Monitoring**
- Use the dashboard for real-time monitoring
- Check performance logs daily
- Monitor error logs for issues

### 2. **Log Maintenance**
- Clean up old logs weekly
- Compress rotated logs monthly
- Monitor disk space usage

### 3. **Performance Analysis**
- Track average response times
- Monitor cache hit rates
- Identify slow queries

### 4. **Error Tracking**
- Investigate failed queries
- Monitor API failure rates
- Track timeout occurrences

## Example Workflows

### Daily Health Check
```bash
# Start dashboard
python scripts/log_dashboard.py --refresh 30

# Check for errors
grep "Status: FAILED" logs/performance.log | tail -10

# Check performance
grep "Duration:" logs/performance.log | tail -20
```

### Weekly Performance Review
```bash
# Generate performance report
python scripts/log_cleanup.py --info

# Clean up old logs
python scripts/log_cleanup.py --cleanup 7

# Compress rotated logs
python scripts/log_cleanup.py --compress
```

### Troubleshooting Specific PMID
```bash
# Get full query lifecycle
grep -A 20 -B 5 "PMID: 12345" logs/performance.log

# Check for errors
grep "PMID: 12345" logs/errors.log

# Check API calls
grep "PMID: 12345" logs/api_calls.log
```

## Integration with Monitoring

### Health Check Endpoint
```bash
# Check system health
curl http://localhost:8000/health

# Get performance metrics
curl http://localhost:8000/metrics
```

### Log Aggregation
The logs are structured to work with log aggregation tools like:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Splunk
- Graylog
- Fluentd

## Support and Troubleshooting

If you encounter issues with the logging system:

1. **Check log file permissions** - Ensure the `logs/` directory is writable
2. **Verify disk space** - Logs can grow quickly
3. **Check Python dependencies** - Ensure all required packages are installed
4. **Review log rotation** - Check if logrotate is properly configured

The comprehensive logging system should now give you full visibility into PMID query performance and help identify any remaining bottlenecks in your system.
