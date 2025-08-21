import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    """Manages caching of analysis results and metadata to avoid repeated API calls."""
    
    def __init__(self, cache_dir: str = "cache", db_path: str = "cache/analysis_cache.db"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database for caching analysis results."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create tables if they don't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    pmid TEXT PRIMARY KEY,
                    analysis_data TEXT,
                    metadata TEXT,
                    timestamp TEXT,
                    source TEXT,
                    confidence REAL,
                    curation_ready BOOLEAN
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metadata_cache (
                    pmid TEXT PRIMARY KEY,
                    metadata TEXT,
                    timestamp TEXT,
                    source TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fulltext_cache (
                    pmid TEXT PRIMARY KEY,
                    fulltext TEXT,
                    timestamp TEXT,
                    source TEXT
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_analysis_timestamp ON analysis_cache(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metadata_timestamp ON metadata_cache(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_fulltext_timestamp ON fulltext_cache(timestamp)')
            
            conn.commit()
            conn.close()
            logger.info("Cache database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize cache database: {str(e)}")
    
    def store_analysis_result(self, pmid: str, analysis_data: Dict, metadata: Dict, 
                            source: str = "gemini", confidence: float = 0.0, 
                            curation_ready: bool = False) -> bool:
        """Store analysis results in the cache database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO analysis_cache 
                (pmid, analysis_data, metadata, timestamp, source, confidence, curation_ready)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                pmid,
                json.dumps(analysis_data, ensure_ascii=False),
                json.dumps(metadata, ensure_ascii=False),
                datetime.now().isoformat(),
                source,
                confidence,
                curation_ready
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Stored analysis result for PMID {pmid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store analysis result for PMID {pmid}: {str(e)}")
            return False
    
    def get_analysis_result(self, pmid: str) -> Optional[Dict]:
        """Retrieve analysis results from cache."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT analysis_data, metadata, timestamp, source, confidence, curation_ready
                FROM analysis_cache 
                WHERE pmid = ?
            ''', (pmid,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                analysis_data, metadata, timestamp, source, confidence, curation_ready = result
                return {
                    "analysis_data": json.loads(analysis_data),
                    "metadata": json.loads(metadata),
                    "timestamp": timestamp,
                    "source": source,
                    "confidence": confidence,
                    "curation_ready": curation_ready,
                    "cached": True
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve analysis result for PMID {pmid}: {str(e)}")
            return None
    
    def store_metadata(self, pmid: str, metadata: Dict, source: str = "pubmed") -> bool:
        """Store paper metadata in cache."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO metadata_cache 
                (pmid, metadata, timestamp, source)
                VALUES (?, ?, ?, ?)
            ''', (
                pmid,
                json.dumps(metadata, ensure_ascii=False),
                datetime.now().isoformat(),
                source
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Stored metadata for PMID {pmid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store metadata for PMID {pmid}: {str(e)}")
            return False
    
    def get_metadata(self, pmid: str) -> Optional[Dict]:
        """Retrieve paper metadata from cache."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT metadata, timestamp, source
                FROM metadata_cache 
                WHERE pmid = ?
            ''', (pmid,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                metadata, timestamp, source = result
                return {
                    "metadata": json.loads(metadata),
                    "timestamp": timestamp,
                    "source": source,
                    "cached": True
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve metadata for PMID {pmid}: {str(e)}")
            return None
    
    def store_fulltext(self, pmid: str, fulltext: str, source: str = "pmc") -> bool:
        """Store full text in cache."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO fulltext_cache 
                (pmid, fulltext, timestamp, source)
                VALUES (?, ?, ?, ?)
            ''', (
                pmid,
                fulltext,
                datetime.now().isoformat(),
                source
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Stored fulltext for PMID {pmid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store fulltext for PMID {pmid}: {str(e)}")
            return False
    
    def get_fulltext(self, pmid: str) -> Optional[Dict]:
        """Retrieve full text from cache."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT fulltext, timestamp, source
                FROM fulltext_cache 
                WHERE pmid = ?
            ''', (pmid,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                fulltext, timestamp, source = result
                return {
                    "fulltext": fulltext,
                    "timestamp": timestamp,
                    "source": source,
                    "cached": True
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve fulltext for PMID {pmid}: {str(e)}")
            return None
    
    def is_cache_valid(self, timestamp: str, max_age_hours: int = 24) -> bool:
        """Check if cached data is still valid based on age."""
        try:
            cache_time = datetime.fromisoformat(timestamp)
            current_time = datetime.now()
            age = current_time - cache_time
            
            return age < timedelta(hours=max_age_hours)
            
        except Exception as e:
            logger.warning(f"Failed to check cache validity: {str(e)}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics and information."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get counts for each table
            cursor.execute('SELECT COUNT(*) FROM analysis_cache')
            analysis_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM metadata_cache')
            metadata_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM fulltext_cache')
            fulltext_count = cursor.fetchone()[0]
            
            # Get recent activity
            cursor.execute('''
                SELECT COUNT(*) FROM analysis_cache 
                WHERE timestamp > datetime('now', '-24 hours')
            ''')
            recent_analysis = cursor.fetchone()[0]
            
            # Get curation readiness stats
            cursor.execute('SELECT COUNT(*) FROM analysis_cache WHERE curation_ready = 1')
            ready_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM analysis_cache WHERE curation_ready = 0')
            not_ready_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "analysis_cache_count": analysis_count,
                "metadata_cache_count": metadata_count,
                "fulltext_cache_count": fulltext_count,
                "recent_analysis_24h": recent_analysis,
                "curation_ready_count": ready_count,
                "curation_not_ready_count": not_ready_count,
                "total_curation_analyzed": ready_count + not_ready_count,
                "curation_readiness_rate": ready_count / (ready_count + not_ready_count) if (ready_count + not_ready_count) > 0 else 0.0
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {str(e)}")
            return {}

    def get_all_analysis_results(self) -> List[Dict[str, Any]]:
        """Get all analysis results from the cache for statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT pmid, analysis_data, metadata, timestamp, source, confidence, curation_ready
                FROM analysis_cache
                ORDER BY timestamp DESC
            ''')
            
            results = []
            for row in cursor.fetchall():
                pmid, analysis_data, metadata, timestamp, source, confidence, curation_ready = row
                try:
                    results.append({
                        "pmid": pmid,
                        "analysis_data": json.loads(analysis_data) if analysis_data else {},
                        "metadata": json.loads(metadata) if metadata else {},
                        "timestamp": timestamp,
                        "source": source,
                        "confidence": confidence,
                        "curation_ready": bool(curation_ready)
                    })
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse cached data for PMID {pmid}")
                    continue
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Failed to get all analysis results: {str(e)}")
            return []
    
    def _get_cache_size_mb(self) -> float:
        """Get the size of the cache database in MB."""
        try:
            if self.db_path.exists():
                size_bytes = self.db_path.stat().st_size
                return round(size_bytes / (1024 * 1024), 2)
            return 0.0
        except Exception:
            return 0.0
    
    def clear_old_cache(self, max_age_hours: int = 168) -> int:
        """Clear cache entries older than specified age. Returns number of cleared entries."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
            
            # Clear old entries
            cursor.execute('DELETE FROM analysis_cache WHERE timestamp < ?', (cutoff_time,))
            analysis_cleared = cursor.rowcount
            
            cursor.execute('DELETE FROM metadata_cache WHERE timestamp < ?', (cutoff_time,))
            metadata_cleared = cursor.rowcount
            
            cursor.execute('DELETE FROM fulltext_cache WHERE timestamp < ?', (cutoff_time,))
            fulltext_cleared = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            total_cleared = analysis_cleared + metadata_cleared + fulltext_cleared
            logger.info(f"Cleared {total_cleared} old cache entries")
            
            return total_cleared
            
        except Exception as e:
            logger.error(f"Failed to clear old cache: {str(e)}")
            return 0
    
    def search_cache(self, query: str, search_type: str = "all") -> List[Dict]:
        """Search cache for papers matching the query."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if search_type == "analysis":
                cursor.execute('''
                    SELECT pmid, analysis_data, metadata, timestamp, confidence, curation_ready
                    FROM analysis_cache 
                    WHERE analysis_data LIKE ? OR metadata LIKE ?
                    ORDER BY timestamp DESC
                ''', (f'%{query}%', f'%{query}%'))
            elif search_type == "metadata":
                cursor.execute('''
                    SELECT pmid, metadata, timestamp
                    FROM metadata_cache 
                    WHERE metadata LIKE ?
                    ORDER BY timestamp DESC
                ''', (f'%{query}%',))
            else:
                # Search all tables
                cursor.execute('''
                    SELECT DISTINCT pmid FROM (
                        SELECT pmid FROM analysis_cache WHERE analysis_data LIKE ? OR metadata LIKE ?
                        UNION
                        SELECT pmid FROM metadata_cache WHERE metadata LIKE ?
                        UNION
                        SELECT pmid FROM fulltext_cache WHERE fulltext LIKE ?
                    )
                ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))
            
            results = cursor.fetchall()
            conn.close()
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search cache: {str(e)}")
            return [] 