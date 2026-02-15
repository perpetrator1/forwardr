# Queue Manager - Feature Summary

## Implemented Features

### 1. Database Schema (SQLite)
```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    media_info TEXT NOT NULL,              -- JSON serialized MediaInfo
    scheduled_time TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending/completed/failed
    attempts INTEGER DEFAULT 0,
    error_log TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    completed_at TEXT,
    file_id TEXT,
    post_url TEXT
)
```

**Indexes:**
- `idx_status_scheduled` - Fast lookup of pending jobs
- `idx_file_id` - Group jobs by file for cleanup
- `idx_created_at` - Efficient purging of old jobs

### 2. Core Functions

#### `queue_posts(media_info, platforms, start_delay_minutes, interval_minutes)`
- Takes MediaInfo and list of platforms
- Schedules jobs with configurable spacing
- Default: 1 hour apart (60 minutes)
- Returns list of created job IDs

#### `start_processor()`
- Starts background thread
- Wakes every 60 seconds (configurable)
- Processes jobs where `scheduled_time <= now` and `status = 'pending'`
- Runs as daemon thread

#### `process_job(job)`
- Processes a single job
- Updates status to completed/failed
- Handles errors with logging

### 3. Retry Logic
- **Max attempts:** 3 per job
- **Backoff:** 10 minutes between retries (configurable)
- **Error tracking:** All errors logged in `error_log` field
- **Status flow:** pending → failed (retry) → pending → ... → failed (permanent)

### 4. Automatic Cleanup
- **Trigger:** After all jobs for a `file_id` are complete/failed
- **Action:** Calls `MediaHandler.cleanup_media()` to delete local files
- **Smart detection:** Only cleans when NO pending jobs remain for that file

### 5. Monitoring Functions

#### `get_queue_status()`
Returns:
```python
{
    'pending': 5,
    'completed': 120,
    'failed': 3,
    'total': 128
}
```

#### `get_all_jobs(limit=100)`
Returns list of job dictionaries for monitoring/debugging

#### `get_job(job_id)`
Get specific job details

### 6. Maintenance

#### `purge_old_jobs(days=7)`
- Deletes completed jobs older than specified days
- Returns count of deleted jobs
- Should be run periodically (e.g., daily cron job)

## Test Results

### Test 1: Basic Queue Processing
```
Created: 3 jobs (telegram, twitter, bluesky)
Schedule: 5 seconds apart
Result: All 3 jobs completed successfully
Cleanup: test_image.jpg deleted automatically
Time: ~20 seconds total
```

### Test 2: Platform Integration
```
Config integration: Works with settings.enabled_platforms
Media handler: Integrates with MediaInfo
Database: Created with proper schema
Background processor: Starts/stops cleanly
```

### Test 3: Retry Logic
```
Job #1: Simulated failures (2x) → Success on attempt 3
Job #2: Success on first attempt
Retry delay: 30 seconds (configurable)
Error logging: All attempts tracked
```

## Workflow Example

1. **Receive Telegram message**
   ```python
   media_info = handler.parse_telegram_message(telegram_msg)
   media_info = await handler.download_telegram_media(media_info)
   ```

2. **Generate platform variants**
   ```python
   variants = handler.get_media_variants(media_info, platforms=ENABLED_PLATFORMS)
   ```

3. **Queue posts**
   ```python
   job_ids = queue_manager.queue_posts(
       media_info=media_info,
       platforms=ENABLED_PLATFORMS,
       interval_minutes=60
   )
   ```

4. **Background processor handles posting**
   - Checks every 60 seconds
   - Processes ready jobs
   - Retries failures (max 3 attempts)
   - Logs all errors

5. **Automatic cleanup**
   - When all platform posts complete
   - Deletes local media file
   - Frees disk space

## Files Created

1. **app/queue_manager.py** (530 lines)
   - QueueManager class
   - Database operations
   - Background processor
   - Retry logic
   - Cleanup automation

2. **test_queue.py** (200 lines)
   - Creates 3 test jobs
   - Starts processor
   - Monitors status every 5 seconds
   - Shows completion

3. **example_queue_integration.py** (250 lines)
   - Full workflow example
   - Config integration
   - Monitoring examples
   - Cleanup demonstration

4. **test_retry.py** (150 lines)
   - Simulates failures
   - Tests retry logic
   - Validates error logging

## Production Usage

### Application Startup
```python
from app.queue_manager import get_queue_manager
from app.config import settings

# Initialize and start processor once
queue_manager = get_queue_manager(
    db_path=settings.core.database_url,
    check_interval=settings.core.check_interval_seconds
)
queue_manager.start_processor()
```

### Webhook Handler
```python
@app.post("/webhook/telegram")
async def telegram_webhook(update: dict):
    message = update.get("message", {})
    
    # Parse and download
    media_info = handler.parse_telegram_message(message)
    media_info = await handler.download_telegram_media(media_info)
    
    # Queue for all enabled platforms
    job_ids = queue_manager.queue_posts(
        media_info=media_info,
        platforms=ENABLED_PLATFORMS,
        interval_minutes=60
    )
    
    return {"queued": len(job_ids), "job_ids": job_ids}
```

### Periodic Cleanup (Cron)
```python
# Run daily at midnight
queue_manager.purge_old_jobs(days=7)
```

## Key Features

- **Thread-safe** - Uses SQLite with proper locking  
- **Resilient** - Automatic retries with backoff  
- **Clean** - Auto-deletes media after posting  
- **Monitored** - Status tracking and error logging  
- **Efficient** - Indexed queries, minimal overhead  
- **Configurable** - Intervals, retries, purge settings  
- **Tested** - Multiple test scripts verify functionality  

## Performance

- **Database:** SQLite with WAL mode (concurrent reads)
- **Memory:** Minimal - processes jobs one at a time
- **Disk:** Auto-cleanup prevents accumulation
- **CPU:** Low - sleeps between checks (60s default)
- **Scalability:** Suitable for 100s of posts/day

## Error Handling

All errors are:
1. Logged to console with timestamps
2. Stored in database `error_log` field
3. Used to determine retry behavior
4. Available via monitoring API

## Summary

The queue manager provides a robust, production-ready system for scheduling and processing social media posts across multiple platforms with automatic retries, error handling, and cleanup.
