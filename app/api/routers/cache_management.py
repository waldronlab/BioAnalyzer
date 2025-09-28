"""
Cache management endpoints for analysis data.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime, timedelta
import pytz

from app.services.cache_manager import CacheManager
from app.api.models.api_models import CacheStatsResponse
from app.api.utils.api_utils import get_current_timestamp

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Cache Management"])

# Initialize cache manager
cache_manager = CacheManager()


@router.delete("/cache/analysis/{pmid}")
async def delete_analysis_cache(pmid: str):
    """
    **Delete cached analysis results for a specific PMID.**
    
    This endpoint removes cached analysis results for a specific paper,
    forcing a fresh analysis on the next request.
    
    **Parameters:**
    - `pmid`: PubMed ID of the paper to clear from cache
    
    **Response:**
    Returns confirmation of cache deletion.
    """
    try:
        success = cache_manager.delete_analysis(pmid)
        
        if success:
            return {
                "pmid": pmid,
                "cache_type": "analysis",
                "status": "deleted",
                "timestamp": get_current_timestamp()
            }
        else:
            return {
                "pmid": pmid,
                "cache_type": "analysis",
                "status": "not_found",
                "timestamp": get_current_timestamp()
            }
            
    except Exception as e:
        logger.error(f"Error deleting analysis cache for PMID {pmid}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting analysis cache: {str(e)}")


@router.delete("/cache/metadata/{pmid}")
async def delete_metadata_cache(pmid: str):
    """
    **Delete cached metadata for a specific PMID.**
    
    This endpoint removes cached paper metadata for a specific paper,
    forcing a fresh metadata retrieval on the next request.
    
    **Parameters:**
    - `pmid`: PubMed ID of the paper to clear from cache
    
    **Response:**
    Returns confirmation of cache deletion.
    """
    try:
        success = cache_manager.delete_metadata(pmid)
        
        if success:
            return {
                "pmid": pmid,
                "cache_type": "metadata",
                "status": "deleted",
                "timestamp": get_current_timestamp()
            }
        else:
            return {
                "pmid": pmid,
                "cache_type": "metadata",
                "status": "not_found",
                "timestamp": get_current_timestamp()
            }
            
    except Exception as e:
        logger.error(f"Error deleting metadata cache for PMID {pmid}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting metadata cache: {str(e)}")


@router.delete("/cache/fulltext/{pmid}")
async def delete_fulltext_cache(pmid: str):
    """
    **Delete cached full text for a specific PMID.**
    
    This endpoint removes cached full text content for a specific paper,
    forcing a fresh text retrieval on the next request.
    
    **Parameters:**
    - `pmid`: PubMed ID of the paper to clear from cache
    
    **Response:**
    Returns confirmation of cache deletion.
    """
    try:
        success = cache_manager.delete_fulltext(pmid)
        
        if success:
            return {
                "pmid": pmid,
                "cache_type": "fulltext",
                "status": "deleted",
                "timestamp": get_current_timestamp()
            }
        else:
            return {
                "pmid": pmid,
                "cache_type": "fulltext",
                "status": "not_found",
                "timestamp": get_current_timestamp()
            }
            
    except Exception as e:
        logger.error(f"Error deleting fulltext cache for PMID {pmid}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting fulltext cache: {str(e)}")


@router.delete("/cache/all")
async def clear_all_cache():
    """
    **Clear all cached data.**
    
    This endpoint removes all cached data from the system,
    including analysis results, metadata, and full text content.
    
    **Response:**
    Returns confirmation of cache clearing with statistics.
    """
    try:
        # Get cache stats before clearing
        stats_before = cache_manager.get_cache_stats()
        
        # Clear all cache
        success = cache_manager.clear_all_cache()
        
        if success:
            return {
                "status": "cleared",
                "entries_cleared": stats_before.get('total_entries', 0),
                "cache_size_cleared_mb": stats_before.get('cache_size_mb', 0),
                "timestamp": get_current_timestamp()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to clear cache")
            
    except Exception as e:
        logger.error(f"Error clearing all cache: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")


@router.get("/cache/stats")
async def get_cache_stats():
    """
    **Get cache statistics and information.**
    
    This endpoint provides detailed statistics about the cache system,
    including entry counts, size, and performance metrics.
    
    **Response:**
    Returns comprehensive cache statistics.
    """
    try:
        stats = cache_manager.get_cache_stats()
        
        return CacheStatsResponse(
            total_entries=stats.get('total_entries', 0),
            analysis_cache_entries=stats.get('analysis_cache_entries', 0),
            metadata_cache_entries=stats.get('metadata_cache_entries', 0),
            fulltext_cache_entries=stats.get('fulltext_cache_entries', 0),
            cache_size_mb=stats.get('cache_size_mb', 0.0),
            oldest_entry=stats.get('oldest_entry'),
            newest_entry=stats.get('newest_entry')
        )
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting cache stats: {str(e)}")


@router.post("/cache/clear")
async def clear_old_cache(max_age_hours: int = Query(168, description="Maximum age in hours")):
    """
    **Clear old cache entries.**
    
    This endpoint removes cache entries older than the specified age,
    helping to manage cache size and ensure data freshness.
    
    **Parameters:**
    - `max_age_hours`: Maximum age in hours (default: 168 = 1 week)
    
    **Response:**
    Returns statistics about cleared entries.
    """
    try:
        if max_age_hours < 1:
            raise HTTPException(status_code=400, detail="max_age_hours must be at least 1")
        
        # Calculate cutoff time
        cutoff_time = datetime.now(pytz.UTC) - timedelta(hours=max_age_hours)
        
        # Get cache stats before clearing
        stats_before = cache_manager.get_cache_stats()
        
        # Clear old entries
        cleared_count = cache_manager.clear_old_entries(cutoff_time)
        
        # Get cache stats after clearing
        stats_after = cache_manager.get_cache_stats()
        
        return {
            "status": "cleared",
            "max_age_hours": max_age_hours,
            "cutoff_time": cutoff_time.isoformat(),
            "entries_cleared": cleared_count,
            "entries_before": stats_before.get('total_entries', 0),
            "entries_after": stats_after.get('total_entries', 0),
            "size_before_mb": stats_before.get('cache_size_mb', 0.0),
            "size_after_mb": stats_after.get('cache_size_mb', 0.0),
            "timestamp": get_current_timestamp()
        }
        
    except Exception as e:
        logger.error(f"Error clearing old cache: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing old cache: {str(e)}")


@router.get("/cache/search")
async def search_cache(
    query: str = Query(..., description="Search query"),
    search_type: str = Query("all", description="Type of cache to search")
):
    """
    **Search cache for papers matching the query.**
    
    This endpoint searches through cached data to find papers
    matching the specified query criteria.
    
    **Parameters:**
    - `query`: Search query string
    - `search_type`: Type of cache to search (all, analysis, metadata, fulltext)
    
    **Response:**
    Returns list of matching papers with their cache information.
    """
    try:
        if search_type not in ["all", "analysis", "metadata", "fulltext"]:
            raise HTTPException(
                status_code=400, 
                detail="search_type must be one of: all, analysis, metadata, fulltext"
            )
        
        # Perform search
        results = cache_manager.search_cache(query, search_type)
        
        return {
            "query": query,
            "search_type": search_type,
            "results_count": len(results),
            "results": results,
            "timestamp": get_current_timestamp()
        }
        
    except Exception as e:
        logger.error(f"Error searching cache: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching cache: {str(e)}")


@router.get("/cache/health")
async def cache_health_check():
    """
    **Check cache system health.**
    
    This endpoint performs a health check on the cache system,
    verifying connectivity and basic functionality.
    
    **Response:**
    Returns cache system health status.
    """
    try:
        # Test cache operations
        test_pmid = "test_health_check"
        
        # Test write
        test_data = {"test": "data", "timestamp": get_current_timestamp()}
        write_success = cache_manager.cache_analysis(test_pmid, test_data)
        
        # Test read
        read_data = cache_manager.get_analysis(test_pmid)
        read_success = read_data is not None
        
        # Test delete
        delete_success = cache_manager.delete_analysis(test_pmid)
        
        # Get cache stats
        stats = cache_manager.get_cache_stats()
        
        health_status = "healthy" if all([write_success, read_success, delete_success]) else "unhealthy"
        
        return {
            "status": health_status,
            "write_test": write_success,
            "read_test": read_success,
            "delete_test": delete_success,
            "cache_stats": stats,
            "timestamp": get_current_timestamp()
        }
        
    except Exception as e:
        logger.error(f"Error in cache health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": get_current_timestamp()
        }


@router.get("/cache/export")
async def export_cache_data(
    cache_type: str = Query("all", description="Type of cache to export"),
    format: str = Query("json", description="Export format (json, csv)")
):
    """
    **Export cache data for backup or analysis.**
    
    This endpoint exports cached data in the specified format
    for backup purposes or further analysis.
    
    **Parameters:**
    - `cache_type`: Type of cache to export (all, analysis, metadata, fulltext)
    - `format`: Export format (json, csv)
    
    **Response:**
    Returns exported cache data.
    """
    try:
        if cache_type not in ["all", "analysis", "metadata", "fulltext"]:
            raise HTTPException(
                status_code=400, 
                detail="cache_type must be one of: all, analysis, metadata, fulltext"
            )
        
        if format not in ["json", "csv"]:
            raise HTTPException(
                status_code=400, 
                detail="format must be one of: json, csv"
            )
        
        # Export cache data
        export_data = cache_manager.export_cache_data(cache_type, format)
        
        return {
            "cache_type": cache_type,
            "format": format,
            "data": export_data,
            "timestamp": get_current_timestamp()
        }
        
    except Exception as e:
        logger.error(f"Error exporting cache data: {e}")
        raise HTTPException(status_code=500, detail=f"Error exporting cache data: {str(e)}")
