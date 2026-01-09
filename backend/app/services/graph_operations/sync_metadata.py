"""
Graph Sync Metadata Manager.

Manages sync timestamps and metadata for incremental synchronization.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Thread pool for running blocking operations
_executor = ThreadPoolExecutor(max_workers=2)


class GraphSyncMetadata:
    """
    Manages sync metadata for incremental synchronization.
    
    Features:
    - Last sync timestamp tracking
    - Sync statistics
    - Multiple sync keys support (crm_sync, email_sync, etc.)
    """
    
    def __init__(self, driver: Any):
        """
        Initialize sync metadata manager.
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
    
    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in the thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, partial(func, *args, **kwargs)
        )
    
    async def get_last_sync_time(self, sync_key: str = "crm_sync") -> Optional[str]:
        """
        Get the last sync timestamp for a given sync key.
        
        Args:
            sync_key: Unique key for this sync type (default: "crm_sync")
            
        Returns:
            ISO 8601 timestamp string or None if never synced
        """
        try:
            result = await self._run_sync(
                self.driver.execute_query,
                """
                MATCH (sys:System {key: $sync_key})
                RETURN sys.last_sync_time as last_sync_time
                """,
                sync_key=sync_key,
                database_="neo4j",
            )
            
            if result and result.records and len(result.records) > 0:
                last_sync = result.records[0].get("last_sync_time")
                if last_sync:
                    # Convert Neo4j DateTime to ISO string
                    iso_string = last_sync.isoformat() if hasattr(last_sync, 'isoformat') else str(last_sync)
                    
                    # CRITICAL: Truncate nanoseconds to milliseconds for Zoho COQL compatibility!
                    # Neo4j stores timestamps with nanosecond precision (9 digits)
                    # Zoho COQL only accepts milliseconds (3 digits) - Standard ISO 8601
                    # Format: YYYY-MM-DDTHH:MM:SS.sss+00:00 (3 digits)
                    if '.' in iso_string and ('+' in iso_string or 'Z' in iso_string):
                        # Split into: datetime part, fractional part, timezone part
                        datetime_part, rest = iso_string.split('.', 1)
                        
                        # Extract fractional seconds and timezone
                        if '+' in rest:
                            fractional, tz = rest.split('+', 1)
                            tz = '+' + tz
                        elif 'Z' in rest:
                            fractional = rest.replace('Z', '')
                            tz = 'Z'
                        else:
                            # No timezone, just fractional
                            fractional = rest
                            tz = ''
                        
                        # Truncate to 3 digits (milliseconds)
                        fractional_ms = fractional[:3].ljust(3, '0')  # Pad with zeros if needed
                        
                        # Reconstruct: datetime.milliseconds+timezone
                        iso_string = f"{datetime_part}.{fractional_ms}{tz}"
                    
                    return iso_string
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get last sync time: {e}")
            return None
    
    async def set_last_sync_time(self, timestamp: Optional[str] = None, sync_key: str = "crm_sync") -> None:
        """
        Set the last sync timestamp for a given sync key.
        
        Args:
            timestamp: ISO 8601 timestamp string or None for current time
            sync_key: Unique key for this sync type (default: "crm_sync")
        """
        try:
            # Use provided timestamp or current time
            if timestamp is None:
                # Format with milliseconds (3 digits) - Zoho COQL doesn't accept nanoseconds!
                # Standard ISO 8601: YYYY-MM-DDTHH:MM:SS.sss+00:00
                now = datetime.now(timezone.utc)
                timestamp = now.strftime('%Y-%m-%dT%H:%M:%S') + f'.{now.microsecond//1000:03d}+00:00'
            
            await self._run_sync(
                self.driver.execute_query,
                """
                MERGE (sys:System {key: $sync_key})
                SET sys.last_sync_time = datetime($timestamp),
                    sys.updated_at = datetime()
                """,
                sync_key=sync_key,
                timestamp=timestamp,
                database_="neo4j",
            )
            
            logger.info(f"✅ Updated last sync time: {timestamp}")
            
        except Exception as e:
            logger.error(f"Failed to set last sync time: {e}")
            raise

