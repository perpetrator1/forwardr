"""
Queue manager for scheduling and processing social media posts
"""
import json
import sqlite3
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict
from contextlib import contextmanager

from app.media_handler import MediaInfo, MediaHandler

logger = logging.getLogger(__name__)


class QueueManager:
    """Manage job queue with SQLite backend"""
    
    def __init__(self, db_path: str = "./forwardr.db", check_interval: int = 60):
        """
        Initialize queue manager
        
        Args:
            db_path: Path to SQLite database
            check_interval: Seconds between queue checks
        """
        self.db_path = db_path
        self.check_interval = check_interval
        self._processor_thread = None
        self._processor_running = False
        self._lock = threading.Lock()
        
        # Initialize database
        self._init_db()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    media_info TEXT NOT NULL,
                    scheduled_time TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER DEFAULT 0,
                    error_log TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    completed_at TEXT,
                    file_id TEXT,
                    post_url TEXT
                )
            """)
            
            # Create indices for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status_scheduled 
                ON jobs(status, scheduled_time)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_id 
                ON jobs(file_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON jobs(created_at)
            """)
            
            logger.info("Database initialized")
    
    def queue_posts(
        self, 
        media_info: MediaInfo, 
        platforms: List[str],
        start_delay_minutes: int = 0,
        interval_minutes: int = 60
    ) -> List[int]:
        """
        Queue posts for multiple platforms
        
        Args:
            media_info: MediaInfo object with content to post
            platforms: List of platform names
            start_delay_minutes: Minutes to wait before first post
            interval_minutes: Minutes between each platform post
            
        Returns:
            List of job IDs created
        """
        job_ids = []
        now = datetime.utcnow()
        
        with self._get_connection() as conn:
            for i, platform in enumerate(platforms):
                # Calculate scheduled time
                delay = start_delay_minutes + (i * interval_minutes)
                scheduled_time = now + timedelta(minutes=delay)
                
                # Insert job
                cursor = conn.execute("""
                    INSERT INTO jobs (
                        platform, media_info, scheduled_time, 
                        status, attempts, created_at, file_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    platform,
                    json.dumps(media_info.to_dict()),
                    scheduled_time.isoformat(),
                    'pending',
                    0,
                    now.isoformat(),
                    media_info.file_id
                ))
                
                job_id = cursor.lastrowid
                job_ids.append(job_id)
                
                logger.info(
                    f"Queued job #{job_id} for {platform} "
                    f"at {scheduled_time.isoformat()}"
                )
        
        return job_ids
    
    def get_pending_jobs(self) -> List[Dict]:
        """
        Get all pending jobs that are ready to process
        
        Returns:
            List of job dictionaries
        """
        now = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM jobs 
                WHERE status = 'pending' 
                AND scheduled_time <= ?
                ORDER BY scheduled_time ASC
            """, (now,))
            
            jobs = [dict(row) for row in cursor.fetchall()]
            
        return jobs
    
    def update_job_status(
        self, 
        job_id: int, 
        status: str,
        error_message: Optional[str] = None,
        post_url: Optional[str] = None
    ):
        """
        Update job status
        
        Args:
            job_id: Job ID
            status: New status (pending/completed/failed)
            error_message: Error message if failed
            post_url: URL of posted content if successful
        """
        now = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            # Get current job info
            cursor = conn.execute(
                "SELECT attempts, error_log FROM jobs WHERE id = ?",
                (job_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                logger.error(f"Job #{job_id} not found")
                return
            
            attempts = row['attempts'] + 1
            error_log = row['error_log'] or ""
            
            # Append error message if provided
            if error_message:
                timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                error_log += f"\n[{timestamp}] Attempt {attempts}: {error_message}"
            
            # Update job
            if status == 'completed':
                conn.execute("""
                    UPDATE jobs 
                    SET status = ?, attempts = ?, updated_at = ?, 
                        completed_at = ?, post_url = ?
                    WHERE id = ?
                """, (status, attempts, now, now, post_url, job_id))
            else:
                conn.execute("""
                    UPDATE jobs 
                    SET status = ?, attempts = ?, updated_at = ?, error_log = ?
                    WHERE id = ?
                """, (status, attempts, now, error_log, job_id))
            
            logger.info(f"Job #{job_id} updated to {status} (attempt {attempts})")
    
    def reschedule_job(self, job_id: int, delay_minutes: int = 10):
        """
        Reschedule a failed job for retry
        
        Args:
            job_id: Job ID to reschedule
            delay_minutes: Minutes to wait before retry
        """
        new_time = datetime.utcnow() + timedelta(minutes=delay_minutes)
        
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE jobs 
                SET scheduled_time = ?, status = 'pending', updated_at = ?
                WHERE id = ?
            """, (new_time.isoformat(), datetime.utcnow().isoformat(), job_id))
            
        logger.info(f"Job #{job_id} rescheduled for {new_time.isoformat()}")
    
    def process_job(self, job: Dict) -> bool:
        """
        Process a single job
        
        Args:
            job: Job dictionary from database
            
        Returns:
            True if successful, False if failed
        """
        job_id = job['id']
        platform = job['platform']
        
        logger.info(f"Processing job #{job_id} for {platform}")
        
        try:
            # Parse media info
            media_info_dict = json.loads(job['media_info'])
            media_info = MediaInfo(**media_info_dict)
            
            # Import platform router
            from app.services.platforms import post_to_platform
            
            # Post to platform using router
            logger.info(f"Posting to {platform}: {media_info.caption[:50] if media_info.caption else 'No caption'}")
            
            result = post_to_platform(platform, media_info.to_dict())
            
            if result:
                # Mark as completed
                post_url = f"https://{platform}.com/post/{job_id}"  # TODO: Get real URL from platform response
                self.update_job_status(job_id, 'completed', post_url=post_url)
                return True
            else:
                # Platform returned False
                raise Exception(f"Platform {platform} returned False")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Job #{job_id} failed: {error_msg}")
            
            # Check retry attempts
            attempts = job['attempts'] + 1
            max_attempts = 3
            
            if attempts < max_attempts:
                # Reschedule for retry
                self.update_job_status(job_id, 'pending', error_message=error_msg)
                self.reschedule_job(job_id, delay_minutes=10)
                logger.info(f"Job #{job_id} will retry (attempt {attempts + 1}/{max_attempts})")
            else:
                # Max attempts reached, mark as failed
                self.update_job_status(job_id, 'failed', error_message=error_msg)
                logger.error(f"Job #{job_id} permanently failed after {attempts} attempts")
            
            return False
    
    def _processor_loop(self):
        """Background processor loop"""
        logger.info("Queue processor started")
        
        while self._processor_running:
            try:
                # Get pending jobs
                jobs = self.get_pending_jobs()
                
                if jobs:
                    logger.info(f"Found {len(jobs)} pending jobs to process")
                    
                    for job in jobs:
                        if not self._processor_running:
                            break
                        
                        self.process_job(job)
                
                # Check for cleanup
                self._cleanup_completed_media()
                
            except Exception as e:
                logger.error(f"Error in processor loop: {e}")
            
            # Sleep for check interval
            time.sleep(self.check_interval)
        
        logger.info("Queue processor stopped")
    
    def _cleanup_completed_media(self):
        """
        Clean up media files for jobs where all platforms are complete
        """
        with self._get_connection() as conn:
            # Find file_ids where all jobs are completed or failed
            cursor = conn.execute("""
                SELECT DISTINCT file_id
                FROM jobs
                WHERE file_id IS NOT NULL
                AND file_id NOT IN (
                    SELECT DISTINCT file_id
                    FROM jobs
                    WHERE status = 'pending'
                    AND file_id IS NOT NULL
                )
            """)
            
            completed_file_ids = [row['file_id'] for row in cursor.fetchall()]
            
        for file_id in completed_file_ids:
            try:
                # Check if we already cleaned this up
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT media_info FROM jobs 
                        WHERE file_id = ? 
                        LIMIT 1
                    """, (file_id,))
                    
                    row = cursor.fetchone()
                    if not row:
                        continue
                    
                    media_info_dict = json.loads(row['media_info'])
                    media_info = MediaInfo(**media_info_dict)
                    
                    if media_info.local_path and Path(media_info.local_path).exists():
                        # Clean up the file
                        handler = MediaHandler(bot_token="", media_dir="./media")
                        handler.cleanup_media(media_info)
                        logger.info(f"Cleaned up media for file_id: {file_id}")
                        
            except Exception as e:
                logger.error(f"Failed to cleanup file_id {file_id}: {e}")
    
    def start_processor(self):
        """Start the background processor thread"""
        if self._processor_running:
            logger.warning("Processor already running")
            return
        
        self._processor_running = True
        self._processor_thread = threading.Thread(
            target=self._processor_loop,
            daemon=True,
            name="QueueProcessor"
        )
        self._processor_thread.start()
        logger.info("Queue processor thread started")
    
    def stop_processor(self):
        """Stop the background processor thread"""
        if not self._processor_running:
            logger.warning("Processor not running")
            return
        
        logger.info("Stopping queue processor...")
        self._processor_running = False
        
        if self._processor_thread:
            self._processor_thread.join(timeout=10)
        
        logger.info("Queue processor stopped")
    
    def get_queue_status(self) -> Dict[str, int]:
        """
        Get queue status counts
        
        Returns:
            Dictionary with pending/completed/failed counts
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    status,
                    COUNT(*) as count
                FROM jobs
                GROUP BY status
            """)
            
            status_counts = {
                'pending': 0,
                'completed': 0,
                'failed': 0,
                'total': 0
            }
            
            for row in cursor.fetchall():
                status = row['status']
                count = row['count']
                status_counts[status] = count
                status_counts['total'] += count
        
        return status_counts
    
    def purge_old_jobs(self, days: int = 7) -> int:
        """
        Delete completed jobs older than specified days
        
        Args:
            days: Number of days to keep completed jobs
            
        Returns:
            Number of jobs deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM jobs
                WHERE status = 'completed'
                AND completed_at < ?
            """, (cutoff_date.isoformat(),))
            
            deleted_count = cursor.rowcount
        
        if deleted_count > 0:
            logger.info(f"Purged {deleted_count} old completed jobs")
        
        return deleted_count
    
    def get_all_jobs(self, limit: int = 100) -> List[Dict]:
        """
        Get all jobs (for debugging/monitoring)
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            List of job dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM jobs
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            jobs = [dict(row) for row in cursor.fetchall()]
        
        return jobs
    
    def get_job(self, job_id: int) -> Optional[Dict]:
        """
        Get a specific job by ID
        
        Args:
            job_id: Job ID
            
        Returns:
            Job dictionary or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM jobs WHERE id = ?
            """, (job_id,))
            
            row = cursor.fetchone()
            
        return dict(row) if row else None


# Singleton instance
_queue_manager = None


def get_queue_manager(
    db_path: str = "./forwardr.db", 
    check_interval: int = 60
) -> QueueManager:
    """Get or create queue manager singleton"""
    global _queue_manager
    
    if _queue_manager is None:
        _queue_manager = QueueManager(db_path, check_interval)
    
    return _queue_manager
