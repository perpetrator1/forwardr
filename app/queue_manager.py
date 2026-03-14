"""
Queue manager for scheduling and processing social media posts.

Supports two backends:
- **Turso** (recommended for production) — set TURSO_DATABASE_URL and
  TURSO_AUTH_TOKEN env vars.  Communicates via Turso's HTTP pipeline API
  so there are **no native dependencies** (uses ``httpx``).
- **Local SQLite** (fallback) — used when the Turso env vars are absent.
"""
import json
import os
import sqlite3
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from dataclasses import asdict
from contextlib import contextmanager
from zoneinfo import ZoneInfo

import httpx

from app.media_handler import MediaInfo, MediaHandler

logger = logging.getLogger(__name__)

# IST timezone (UTC+5:30)
IST = ZoneInfo("Asia/Kolkata")


def _now_ist() -> datetime:
    """Return the current time in IST (Asia/Kolkata), timezone-naive for DB storage."""
    return datetime.now(IST).replace(tzinfo=None)

# ---------------------------------------------------------------------------
# Turso HTTP API helpers
# ---------------------------------------------------------------------------


def _turso_configured() -> bool:
    """Return True when both Turso env vars are present."""
    return bool(
        os.environ.get("TURSO_DATABASE_URL")
        and os.environ.get("TURSO_AUTH_TOKEN")
    )


class _TursoRow:
    """Minimal dict-like row compatible with ``sqlite3.Row``.

    Supports ``row['col']`` access and ``dict(row)`` conversion.
    """

    def __init__(self, columns: List[str], values: List[Any]):
        self._data: Dict[str, Any] = dict(zip(columns, values))

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def __repr__(self) -> str:
        return f"_TursoRow({self._data})"


class _TursoCursor:
    """Minimal cursor returned by :pymethod:`_TursoConnection.execute`."""

    def __init__(
        self,
        columns: List[str],
        rows: List[List[Any]],
        last_insert_rowid: Optional[int],
        affected_row_count: int,
    ):
        self._rows = [_TursoRow(columns, r) for r in rows]
        self.lastrowid = last_insert_rowid
        self.rowcount = affected_row_count
        self._pos = 0

    def fetchone(self) -> Optional[_TursoRow]:
        if self._pos < len(self._rows):
            row = self._rows[self._pos]
            self._pos += 1
            return row
        return None

    def fetchall(self) -> List[_TursoRow]:
        remaining = self._rows[self._pos:]
        self._pos = len(self._rows)
        return remaining


class _TursoConnection:
    """Synchronous connection wrapper around the Turso HTTP pipeline API.

    Each ``execute()`` call sends one HTTP request to
    ``POST <db_url>/v2/pipeline``.  Auto-commit semantics — there is no
    explicit transaction management.

    Designed as a drop-in replacement for ``sqlite3.Connection`` inside
    the ``_get_connection()`` context manager.
    """

    def __init__(self, base_url: str, auth_token: str):
        # Accept libsql:// or https:// URLs
        url = base_url.replace("libsql://", "https://")
        if not url.startswith("https://"):
            url = f"https://{url}"
        self._pipeline_url = f"{url}/v2/pipeline"
        self._auth_token = auth_token
        self._client = httpx.Client(timeout=30.0)
        # Compatibility: the caller sets conn.row_factory — ignored here
        # because _TursoRow already provides dict-like access.
        self.row_factory: Any = None

    # -- execute --------------------------------------------------------------

    def execute(
        self, sql: str, params: Sequence[Any] = ()
    ) -> _TursoCursor:
        args = self._convert_params(params)
        body = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {"sql": sql, "args": args},
                },
                {"type": "close"},
            ]
        }

        resp = self._client.post(
            self._pipeline_url,
            json=body,
            headers={"Authorization": f"Bearer {self._auth_token}"},
        )
        resp.raise_for_status()
        data = resp.json()

        result = data["results"][0]
        if result["type"] == "error":
            msg = result["error"].get("message", "unknown Turso error")
            # Raise sqlite3.OperationalError so existing except-clauses
            # (e.g. the ALTER TABLE migration) keep working.
            raise sqlite3.OperationalError(msg)

        exec_result = result["response"]["result"]
        columns = [c["name"] for c in exec_result.get("cols", [])]
        rows: List[List[Any]] = []
        for row in exec_result.get("rows", []):
            rows.append([self._extract_value(v) for v in row])

        return _TursoCursor(
            columns,
            rows,
            exec_result.get("last_insert_rowid"),
            exec_result.get("affected_row_count", 0),
        )

    # -- param / value conversion --------------------------------------------

    @staticmethod
    def _convert_params(params: Sequence[Any]) -> List[Dict[str, Any]]:
        """Convert Python values to Turso HTTP API arg dicts."""
        args: List[Dict[str, Any]] = []
        for p in params:
            if p is None:
                args.append({"type": "null"})
            elif isinstance(p, bool):
                args.append({"type": "integer", "value": str(int(p))})
            elif isinstance(p, int):
                args.append({"type": "integer", "value": str(p)})
            elif isinstance(p, float):
                args.append({"type": "float", "value": p})
            elif isinstance(p, bytes):
                import base64
                args.append(
                    {"type": "blob", "base64": base64.b64encode(p).decode()}
                )
            else:
                args.append({"type": "text", "value": str(p)})
        return args

    @staticmethod
    def _extract_value(v: Dict[str, Any]) -> Any:
        """Convert a Turso API value dict back to a Python type."""
        vtype = v.get("type")
        if vtype == "null":
            return None
        if vtype == "integer":
            return int(v["value"])
        if vtype == "float":
            return float(v["value"])
        if vtype == "text":
            return v["value"]
        if vtype == "blob":
            import base64
            return base64.b64decode(v["base64"])
        return v.get("value")

    # -- context-manager / lifecycle stubs ------------------------------------

    def commit(self) -> None:
        pass  # Auto-commit per pipeline request

    def rollback(self) -> None:
        pass  # No transaction state to roll back

    def close(self) -> None:
        self._client.close()


class QueueManager:
    """Manage job queue with SQLite backend.
    
    Jobs are processed on-demand via process_next_job() rather than
    a background thread.  The Cloudflare Worker cron calls the
    /process-queue endpoint which invokes this.
    """
    
    def __init__(self, db_path: str = "./forwardr.db", turso_url: str | None = None, turso_token: str | None = None):
        """
        Initialize queue manager.

        Args:
            db_path: Path to local SQLite database (used when Turso is not configured).
            turso_url: Turso/libSQL database URL  (``libsql://…``).
            turso_token: Turso auth token.
        """
        self._lock = threading.Lock()
        self._turso_url = turso_url
        self._turso_token = turso_token

        if self._turso_url:
            # Turso mode — no local file needed
            self.db_path = self._turso_url
            logger.info(f"Using Turso database: {self._turso_url}")
        else:
            # Local SQLite mode
            self.db_path = self._resolve_writable_path(db_path)

        # Initialize database
        self._init_db()

    @staticmethod
    def _resolve_writable_path(db_path: str) -> str:
        """Ensure the parent directory exists and is writable.

        If the configured path can't be used (e.g. Render free tier has no
        persistent disk), fall back to ``./forwardr.db`` in the working
        directory.
        """
        preferred = Path(db_path)
        try:
            preferred.parent.mkdir(parents=True, exist_ok=True)
            # Quick write-test — catches permission issues early
            test_file = preferred.parent / ".db_write_test"
            test_file.touch()
            test_file.unlink()
            logger.info(f"Using database path: {preferred}")
            return str(preferred)
        except OSError as exc:
            fallback = Path("./forwardr.db")
            logger.warning(
                f"Cannot use {preferred} ({exc}). "
                f"Falling back to {fallback.resolve()}"
            )
            fallback.parent.mkdir(parents=True, exist_ok=True)
            return str(fallback)
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager.

        Uses :class:`_TursoConnection` (HTTP pipeline API) for Turso,
        plain ``sqlite3`` otherwise.  Both expose the same
        ``execute / fetchone / fetchall`` interface.
        """
        if self._turso_url:
            conn = _TursoConnection(self._turso_url, self._turso_token)
        else:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
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

            # Metadata table for persisting state across job deletions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Table for deduplicating incoming Telegram updates
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_updates (
                    update_id INTEGER PRIMARY KEY,
                    processed_at TEXT NOT NULL
                )
            """)

            # Migration: add chat_id column for Telegram notifications
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN chat_id TEXT")
                logger.info("Added chat_id column to jobs table")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            logger.info("Database initialized")
    
    def is_update_processed(self, update_id: int) -> bool:
        """
        Check if a Telegram update has already been processed.
        
        Args:
            update_id: The Telegram update_id
            
        Returns:
            True if processed, False otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM processed_updates WHERE update_id = ?",
                (update_id,)
            )
            return cursor.fetchone() is not None

    def mark_update_processed(self, update_id: int) -> None:
        """
        Mark a Telegram update as processed.
        
        Args:
            update_id: The Telegram update_id
        """
        now = _now_ist().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_updates (update_id, processed_at) VALUES (?, ?)",
                (update_id, now)
            )

    def queue_posts(
        self, 
        media_info: MediaInfo, 
        platforms: List[str],
        interval_hours: float = 5.0,
        chat_id: Optional[str] = None,
    ) -> Tuple[List[int], datetime]:
        """
        Queue posts for multiple platforms with interval-based scheduling.
        
        Scheduling logic:
        - If no recent posts exist: schedule for now (immediate)
        - Otherwise: schedule for (latest_scheduled_time + interval_hours)
        - All platforms for the same submission share one scheduled time
        
        Args:
            media_info: MediaInfo object with content to post
            platforms: List of platform names
            interval_hours: Hours between each submission (0 = always immediate)
            chat_id: Telegram chat ID for sending notifications
            
        Returns:
            Tuple of (list of job IDs, scheduled datetime)
        """
        job_ids = []
        now = _now_ist()


        with self._get_connection() as conn:
            # Check pending jobs first, then fall back to the persisted
            # last_scheduled_time (which survives completed-job deletion).
            cursor = conn.execute("""
                SELECT MAX(scheduled_time) as latest
                FROM jobs 
                WHERE status = 'pending'
            """)
            row = cursor.fetchone()
            latest = row['latest'] if row and row['latest'] else None

            if not latest:
                # No pending jobs — check metadata for the last time we
                # actually scheduled something (persists after deletion).
                cursor = conn.execute(
                    "SELECT value FROM metadata WHERE key = 'last_scheduled_time'"
                )
                meta = cursor.fetchone()
                if meta and interval_hours > 0:
                    meta_dt = datetime.fromisoformat(meta['value'])
                    # Only use it if it's recent enough to matter for spacing.
                    # If the interval has already fully elapsed, discard it —
                    # no point keeping stale data.
                    if now < meta_dt + timedelta(hours=interval_hours):
                        latest = meta['value']
                    else:
                        # Stale — clean it up
                        conn.execute(
                            "DELETE FROM metadata WHERE key = 'last_scheduled_time'"
                        )
            
            if latest and interval_hours > 0:
                latest_dt = datetime.fromisoformat(latest)
                next_slot = latest_dt + timedelta(hours=interval_hours)
                # Only schedule in the future; if enough time has passed, go now
                scheduled_time = max(now, next_slot)
            else:
                # No previous jobs or interval is 0 — post immediately
                scheduled_time = now
            
            for platform in platforms:
                cursor = conn.execute("""
                    INSERT INTO jobs (
                        platform, media_info, scheduled_time, 
                        status, attempts, created_at, file_id, chat_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    platform,
                    json.dumps(media_info.to_dict()),
                    scheduled_time.isoformat(),
                    'pending',
                    0,
                    now.isoformat(),
                    media_info.file_id,
                    chat_id,
                ))
                
                job_id = cursor.lastrowid
                job_ids.append(job_id)
                
                logger.info(
                    f"Queued job #{job_id} for {platform} "
                    f"at {scheduled_time.isoformat()}"
                )

            # Persist the scheduled time so interval logic survives job deletion
            conn.execute("""
                INSERT INTO metadata (key, value) VALUES ('last_scheduled_time', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (scheduled_time.isoformat(),))
        
        return job_ids, scheduled_time
    
    def get_pending_jobs(self) -> List[Dict]:
        """
        Get all pending jobs that are ready to process
        
        Returns:
            List of job dictionaries
        """
        now = _now_ist().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM jobs 
                WHERE status = 'pending' 
                AND scheduled_time <= ?
                ORDER BY scheduled_time ASC
            """, (now,))
            
            jobs = [dict(row) for row in cursor.fetchall()]
            
        return jobs

    def get_oldest_pending_job(self) -> Optional[Dict]:
        """
        Get the single oldest pending job that is ready to process.
        Used by the /process-queue endpoint for cron-driven processing.
        
        Returns:
            Job dictionary or None
        """
        now = _now_ist().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM jobs 
                WHERE status = 'pending' 
                AND scheduled_time <= ?
                ORDER BY scheduled_time ASC
                LIMIT 1
            """, (now,))
            
            row = cursor.fetchone()
        
        return dict(row) if row else None

    def process_next_job(self) -> Dict:
        """
        Get and process the oldest pending job.
        
        Returns:
            Result dict with status, job_id, platform, and message
        """
        job = self.get_oldest_pending_job()
        
        if not job:
            self._cleanup_completed_media()
            return {"status": "idle", "message": "No pending jobs"}
        
        success = self.process_job(job)
        
        # Read the updated job BEFORE cleanup deletes it from the DB
        updated = self.get_job(job["id"])
        self._cleanup_completed_media()
        
        return {
            "status": "completed" if success else "failed",
            "job_id": job["id"],
            "platform": job["platform"],
            "chat_id": job.get("chat_id"),
            "post_url": updated.get("post_url", "") if updated else "",
            "message": f"Job #{job['id']} for {job['platform']} {'completed' if success else 'failed'}",
        }

    def process_all_due_jobs(self) -> List[Dict]:
        """
        Process ALL pending jobs that are due right now.
        
        Returns:
            List of result dicts: [{job_id, platform, chat_id, success, post_url}]
        """
        results = []
        
        while True:
            job = self.get_oldest_pending_job()
            if not job:
                break
            
            success = self.process_job(job)
            updated = self.get_job(job["id"])
            
            results.append({
                "job_id": job["id"],
                "platform": job["platform"],
                "chat_id": job.get("chat_id"),
                "success": success,
                "post_url": updated.get("post_url", "") if updated else "",
            })
        
        self._cleanup_completed_media()
        return results

    def get_next_scheduled_time(self) -> Optional[str]:
        """
        Get the earliest scheduled time among pending jobs.
        
        Returns:
            ISO timestamp string, or None if no pending jobs.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT MIN(scheduled_time) as next_time
                FROM jobs 
                WHERE status = 'pending'
            """)
            row = cursor.fetchone()
            return row['next_time'] if row and row['next_time'] else None
    
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
        now = _now_ist().isoformat()
        
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
                timestamp = _now_ist().strftime("%Y-%m-%d %H:%M:%S")
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
        new_time = _now_ist() + timedelta(minutes=delay_minutes)
        
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE jobs 
                SET scheduled_time = ?, status = 'pending', updated_at = ?
                WHERE id = ?
            """, (new_time.isoformat(), _now_ist().isoformat(), job_id))
            
        logger.info(f"Job #{job_id} rescheduled for {new_time.isoformat()}")

    def _ensure_media_downloaded(self, media_info: MediaInfo) -> MediaInfo:
        """Re-download media if the local file is missing.

        Tries in order:
        1. Cloudinary URL (persistent, no expiration)
        2. Telegram file_id (valid ~1 hour after original message)

        Returns an updated :class:`MediaInfo` with ``local_path`` set.
        """
        import asyncio
        from app.config import settings

        # Try Cloudinary first (more reliable)
        if media_info.cloudinary_url:
            try:
                local_path = self._download_from_cloudinary(media_info)
                if local_path:
                    media_info.local_path = local_path
                    logger.info(f"Re-downloaded media from Cloudinary to {local_path}")
                    return media_info
            except Exception as e:
                logger.warning(f"Cloudinary download failed, trying Telegram: {e}")

        # Fall back to Telegram file_id
        bot_token = settings.telegram.bot_token
        if not bot_token:
            raise RuntimeError("Cannot re-download media: Telegram bot token missing")

        handler = MediaHandler(bot_token, settings.core.media_path)

        # download_telegram_media is async — run it from sync context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an existing event loop (e.g. FastAPI background task).
            # Create a new thread to run the coroutine.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                media_info = pool.submit(
                    asyncio.run, handler.download_telegram_media(media_info)
                ).result(timeout=60)
        else:
            media_info = asyncio.run(handler.download_telegram_media(media_info))

        logger.info(f"Re-downloaded media from Telegram to {media_info.local_path}")
        return media_info

    def _download_from_cloudinary(self, media_info: MediaInfo) -> Optional[str]:
        """Download media from Cloudinary URL to local path."""
        import httpx
        from app.config import settings

        url = media_info.cloudinary_url
        if not url:
            return None

        # Determine filename from URL or file_id
        ext = url.rsplit('.', 1)[-1].split('?')[0]  # Handle query params
        if not ext or len(ext) > 5:
            ext = 'jpg' if media_info.type == 'photo' else 'mp4'
        filename = f"{media_info.file_id or 'cloudinary'}.{ext}"

        media_dir = Path(settings.core.media_path)
        media_dir.mkdir(parents=True, exist_ok=True)
        local_path = media_dir / filename

        with httpx.Client(timeout=60.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            with open(local_path, 'wb') as f:
                f.write(resp.content)

        return str(local_path)
    
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

            # Re-download media if the local file is missing
            # (Render free tier wipes the filesystem on spin-down)
            if media_info.type != "text" and media_info.file_id:
                needs_download = (
                    not media_info.local_path
                    or not Path(media_info.local_path).exists()
                )
                if needs_download:
                    media_info = self._ensure_media_downloaded(media_info)
            
            # Import platform router
            from app.services.platforms import post_to_platform
            
            # Post to platform using router
            logger.info(f"Posting to {platform}: {media_info.caption[:50] if media_info.caption else 'No caption'}")
            
            post_url = post_to_platform(platform, media_info.to_dict())
            
            if post_url:
                # Mark as completed with real URL
                self.update_job_status(job_id, 'completed', post_url=post_url)
                return True
            else:
                # Platform returned None/empty
                raise Exception(f"Platform {platform} returned no URL")
            
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
    
    def _cleanup_completed_media(self):
        """
        Clean up media files for jobs where all platforms are complete or cancelled.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, media_info
                FROM jobs
                WHERE status IN ('completed', 'cancelled')
            """)
            finished_rows = list(cursor.fetchall())
            
            if not finished_rows:
                return
                
            # Check what's still in use by pending jobs
            cursor = conn.execute("""
                SELECT media_info
                FROM jobs
                WHERE status = 'pending'
            """)
            in_use_rows = list(cursor.fetchall())

        in_use_cloudinary_ids = set()
        in_use_local_paths = set()
        
        for row in in_use_rows:
            try:
                info_dict = json.loads(row['media_info'])
                if info_dict.get('cloudinary_public_id'):
                    in_use_cloudinary_ids.add(info_dict['cloudinary_public_id'])
                if info_dict.get('local_path'):
                    in_use_local_paths.add(info_dict['local_path'])
            except Exception:
                pass

        for row in finished_rows:
            try:
                job_id = row['id']
                info_dict = json.loads(row['media_info'])
                media_info = MediaInfo(**info_dict)
                
                # Clean up local file
                local_path = info_dict.get('local_path')
                if local_path and local_path not in in_use_local_paths:
                    if Path(local_path).exists():
                        handler = MediaHandler(bot_token="", media_dir="./media")
                        handler.cleanup_media(media_info)
                        logger.info(f"Cleaned up local media for job {job_id}")
                    # Remove from our tracked set so we don't try to delete it again
                    in_use_local_paths.add(local_path)
                        
                # Clean up Cloudinary
                cloud_id = info_dict.get('cloudinary_public_id')
                if cloud_id and cloud_id not in in_use_cloudinary_ids:
                    try:
                        from app.utils.cloudinary_config import delete_media, CLOUDINARY_AVAILABLE
                        if CLOUDINARY_AVAILABLE:
                            resource_type = 'video' if media_info.type == 'video' else 'image'
                            if delete_media(cloud_id, resource_type):
                                logger.info(f"Deleted from Cloudinary: {cloud_id}")
                            else:
                                logger.warning(f"Failed to delete from Cloudinary: {cloud_id}")
                        # Remove from our tracked set so we don't try to delete it again
                        in_use_cloudinary_ids.add(cloud_id)
                    except Exception as ce:
                        logger.warning(f"Cloudinary cleanup failed for {cloud_id}: {ce}")
                        
            except Exception as e:
                logger.error(f"Failed to cleanup media for job {row['id']}: {e}")

        # Delete finished jobs from the database after media cleanup
        self._delete_finished_jobs()

    def _delete_finished_jobs(self):
        """Delete all completed and cancelled jobs from the database."""
        with self._get_connection() as conn:
            # Capture latest completed time to persist as a watermark
            cursor = conn.execute("SELECT MAX(scheduled_time) as latest FROM jobs WHERE status = 'completed'")
            row = cursor.fetchone()
            if row and row['latest']:
                conn.execute("""
                    INSERT INTO metadata (key, value) VALUES ('last_completion_time', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """, (row['latest'],))

            cursor = conn.execute("""
                DELETE FROM jobs
                WHERE status IN ('completed', 'cancelled')
            """)
            deleted = cursor.rowcount
        if deleted:
            logger.info(f"Deleted {deleted} finished (completed/cancelled) jobs from queue")
    
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
                'cancelled': 0,
                'total': 0
            }
            
            for row in cursor.fetchall():
                status = row['status']
                count = row['count']
                status_counts[status] = count
                status_counts['total'] += count
        
        return status_counts

    def cancel_job(self, job_id: int) -> bool:
        """
        Cancel a pending job

        Args:
            job_id: Job ID

        Returns:
            True if cancelled, False otherwise
        """
        now = _now_ist().isoformat()

        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT status FROM jobs WHERE id = ?",
                (job_id,)
            )
            row = cursor.fetchone()
            if not row:
                logger.error(f"Job #{job_id} not found")
                return False

            if row['status'] != 'pending':
                logger.warning(f"Job #{job_id} is not pending and cannot be cancelled")
                return False

            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                ('cancelled', now, job_id),
            )

        logger.info(f"Job #{job_id} cancelled")
        self._delete_finished_jobs()

        # Recalculate metadata so a cancelled future-schedule doesn't
        # block the next submission from going out immediately.
        self._recalculate_last_scheduled()
        return True

    def cancel_all_jobs(self) -> int:
        """
        Cancel ALL pending jobs.

        Returns:
            Number of jobs cancelled
        """
        now = _now_ist().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE jobs SET status = 'cancelled', updated_at = ? WHERE status = 'pending'",
                (now,)
            )
            cancelled_count = cursor.rowcount

        if cancelled_count > 0:
            logger.info(f"Cancelled {cancelled_count} pending jobs")
            self._delete_finished_jobs()
            self._recalculate_last_scheduled()

        return cancelled_count

    def _recalculate_last_scheduled(self):
        """Update 'last_scheduled_time' in metadata based on remaining pending jobs and last completion."""
        with self._get_connection() as conn:
            # Get max from pending jobs
            cursor = conn.execute("""
                SELECT MAX(scheduled_time) as latest
                FROM jobs WHERE status = 'pending'
            """)
            row = cursor.fetchone()
            pending_latest = row['latest'] if row and row['latest'] else None

            # Get last known completion time
            cursor = conn.execute("SELECT value FROM metadata WHERE key = 'last_completion_time'")
            row = cursor.fetchone()
            completion_latest = row['value'] if row else None

            # New watermark is the max of the two
            watermark = None
            if pending_latest and completion_latest:
                watermark = max(pending_latest, completion_latest)
            else:
                watermark = pending_latest or completion_latest

            if watermark:
                conn.execute("""
                    INSERT INTO metadata (key, value) VALUES ('last_scheduled_time', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """, (watermark,))
            else:
                # Truly empty slate
                conn.execute("DELETE FROM metadata WHERE key = 'last_scheduled_time'")
    
    def purge_old_jobs(self, days: int = 7) -> int:
        """
        Delete failed jobs older than specified days.
        
        Completed and cancelled jobs are deleted immediately after
        processing, so this only targets failed jobs that accumulate
        over time.
        
        Args:
            days: Number of days to keep failed jobs
            
        Returns:
            Number of jobs deleted
        """
        cutoff_date = _now_ist() - timedelta(days=days)
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM jobs
                WHERE status = 'failed'
                AND updated_at < ?
            """, (cutoff_date.isoformat(),))
            
            deleted_count = cursor.rowcount
        
        if deleted_count > 0:
            logger.info(f"Purged {deleted_count} old failed jobs")
        
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

    def update_job_media_info(self, job_id: int, media_info: Dict) -> bool:
        """
        Update the media_info of a job.
        
        Args:
            job_id: Job ID
            media_info: New media_info dictionary
            
        Returns:
            True if successful, False otherwise
        """
        now = _now_ist().isoformat()
        with self._get_connection() as conn:
            # Only allow updating pending jobs
            cursor = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row or row['status'] != 'pending':
                return False

            conn.execute(
                "UPDATE jobs SET media_info = ?, updated_at = ? WHERE id = ?",
                (json.dumps(media_info), now, job_id)
            )
        return True

    def set_platform_setting(self, platform: str, key: str, value: str):
        """Set a platform-specific setting in the metadata table."""
        meta_key = f"setting:{platform}:{key}"
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO metadata (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (meta_key, value))

    def get_platform_setting(self, platform: str, key: str) -> Optional[str]:
        """Get a platform-specific setting from the metadata table."""
        meta_key = f"setting:{platform}:{key}"
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM metadata WHERE key = ?",
                (meta_key,)
            )
            row = cursor.fetchone()
            return row['value'] if row else None

    def get_all_platform_settings(self, key: str) -> Dict[str, str]:
        """Get all platform settings for a specific key (e.g., 'caption_adder')."""
        prefix = f"setting:%:{key}"
        results = {}
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT key, value FROM metadata WHERE key LIKE ?",
                (prefix,)
            )
            for row in cursor.fetchall():
                # Extract platform from "setting:platform:key"
                parts = row['key'].split(':')
                if len(parts) == 3:
                    results[parts[1]] = row['value']
        return results


# Singleton instance
_queue_manager = None


def _default_db_path() -> str:
    """Return the local database path from env or a sensible default."""
    return os.environ.get("DATABASE_PATH", "./forwardr.db")


def get_queue_manager(
    db_path: str | None = None,
) -> QueueManager:
    """Get or create queue manager singleton.

    When TURSO_DATABASE_URL and TURSO_AUTH_TOKEN are set, the manager
    connects to Turso.  Otherwise it falls back to local SQLite.
    """
    global _queue_manager

    if _queue_manager is None:
        turso_url = os.environ.get("TURSO_DATABASE_URL")
        turso_token = os.environ.get("TURSO_AUTH_TOKEN")

        resolved = db_path or _default_db_path()
        if turso_url and turso_token:
            logger.info(f"Initialising QueueManager with Turso: {turso_url}")
            _queue_manager = QueueManager(
                db_path=resolved,
                turso_url=turso_url,
                turso_token=turso_token,
            )
        else:
            resolved_abs = str(Path(resolved).resolve())
            logger.info(f"Initialising QueueManager with local SQLite: {resolved} (resolved: {resolved_abs})")
            _queue_manager = QueueManager(db_path=resolved)

    return _queue_manager
