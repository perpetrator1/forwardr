"""
Quick Reference: Queue Manager Usage
"""

# ==============================================================================
# SETUP (Once at application startup)
# ==============================================================================

from app.queue_manager import get_queue_manager
from app.config import settings

# Initialize queue manager
queue_manager = get_queue_manager(
    db_path="./forwardr.db",
    check_interval=60  # seconds between checks
)

# Start background processor
queue_manager.start_processor()


# ==============================================================================
# QUEUE A POST
# ==============================================================================

from app.media_handler import MediaInfo, MediaHandler
from app.config import ENABLED_PLATFORMS

# Create or parse media info
media_info = MediaInfo(
    type="photo",
    file_id="abc123",
    caption="My post caption #hashtag",
    local_path="./media/photo.jpg"
)

# Queue posts for all enabled platforms (1 hour apart)
job_ids = queue_manager.queue_posts(
    media_info=media_info,
    platforms=ENABLED_PLATFORMS,
    start_delay_minutes=0,     # Start immediately
    interval_minutes=60         # 1 hour between each platform
)

print(f"Queued {len(job_ids)} jobs: {job_ids}")


# ==============================================================================
# QUEUE FOR SPECIFIC PLATFORMS ONLY
# ==============================================================================

# Queue only for specific platforms
job_ids = queue_manager.queue_posts(
    media_info=media_info,
    platforms=["telegram", "twitter"],  # Only these
    start_delay_minutes=5,              # Wait 5 minutes before first
    interval_minutes=10                 # 10 minutes between them
)


# ==============================================================================
# CHECK QUEUE STATUS
# ==============================================================================

status = queue_manager.get_queue_status()

print(f"Pending:   {status['pending']}")
print(f"Completed: {status['completed']}")
print(f"Failed:    {status['failed']}")
print(f"Total:     {status['total']}")


# ==============================================================================
# GET JOB DETAILS
# ==============================================================================

# Get specific job
job = queue_manager.get_job(job_id=1)
if job:
    print(f"Job #{job['id']}: {job['platform']} - {job['status']}")
    print(f"Attempts: {job['attempts']}")
    if job['error_log']:
        print(f"Errors: {job['error_log']}")

# Get recent jobs
jobs = queue_manager.get_all_jobs(limit=10)
for job in jobs:
    print(f"Job #{job['id']}: {job['platform']} - {job['status']}")


# ==============================================================================
# CLEANUP OLD JOBS (Run daily)
# ==============================================================================

# Delete completed jobs older than 7 days
deleted_count = queue_manager.purge_old_jobs(days=7)
print(f"Purged {deleted_count} old jobs")


# ==============================================================================
# FULL WORKFLOW EXAMPLE
# ==============================================================================

async def process_telegram_webhook(telegram_message: dict):
    """Complete workflow from webhook to queue"""
    
    # 1. Parse message
    handler = MediaHandler(
        bot_token=settings.telegram.bot_token,
        media_dir=settings.core.media_path
    )
    media_info = handler.parse_telegram_message(telegram_message)
    
    # 2. Download media
    if media_info.type != "text":
        media_info = await handler.download_telegram_media(media_info)
    
    # 3. Generate platform variants (optional, can be done per-platform later)
    if media_info.local_path:
        variants = handler.get_media_variants(
            media_info, 
            platforms=ENABLED_PLATFORMS
        )
    
    # 4. Queue posts
    job_ids = queue_manager.queue_posts(
        media_info=media_info,
        platforms=ENABLED_PLATFORMS,
        interval_minutes=60
    )
    
    return job_ids


# ==============================================================================
# FASTAPI INTEGRATION EXAMPLE
# ==============================================================================

from fastapi import FastAPI, Request

app = FastAPI()

# Initialize on startup
@app.on_event("startup")
async def startup():
    global queue_manager
    queue_manager = get_queue_manager()
    queue_manager.start_processor()
    print("Queue processor started")

# Shutdown cleanup
@app.on_event("shutdown")
async def shutdown():
    queue_manager.stop_processor()
    print("Queue processor stopped")

# Webhook endpoint
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    update = await request.json()
    message = update.get("message", {})
    
    # Process and queue
    job_ids = await process_telegram_webhook(message)
    
    return {
        "success": True,
        "queued_jobs": len(job_ids),
        "job_ids": job_ids
    }

# Status endpoint
@app.get("/status")
async def get_status():
    return queue_manager.get_queue_status()

# Recent jobs endpoint
@app.get("/jobs")
async def get_jobs(limit: int = 20):
    jobs = queue_manager.get_all_jobs(limit=limit)
    return {"jobs": jobs}


# ==============================================================================
# CONFIGURATION OPTIONS
# ==============================================================================

# Retry settings (in QueueManager.process_job)
MAX_ATTEMPTS = 3           # Maximum retry attempts
RETRY_DELAY_MINUTES = 10   # Delay between retries

# Cleanup settings
CLEANUP_DAYS = 7           # Keep completed jobs for 7 days

# Processor settings
CHECK_INTERVAL_SECONDS = 60  # How often to check for pending jobs


# ==============================================================================
# ERROR HANDLING
# ==============================================================================

# All errors are:
# 1. Logged to console
# 2. Stored in database error_log field
# 3. Used to determine retry behavior
# 4. Available via get_job() or get_all_jobs()

# Check if a job failed
job = queue_manager.get_job(job_id)
if job['status'] == 'failed':
    print(f"Job failed after {job['attempts']} attempts")
    print(f"Errors: {job['error_log']}")


# ==============================================================================
# TESTING
# ==============================================================================

# Run tests:
# python test_queue.py          - Basic queue test
# python test_retry.py          - Retry logic test
# python example_queue_integration.py - Full integration example


# ==============================================================================
# MONITORING
# ==============================================================================

import time

def monitor_queue(duration_seconds=60, interval=5):
    """Monitor queue for a period of time"""
    start = time.time()
    
    while time.time() - start < duration_seconds:
        status = queue_manager.get_queue_status()
        print(f"[{time.strftime('%H:%M:%S')}] "
              f"Pending: {status['pending']}, "
              f"Completed: {status['completed']}, "
              f"Failed: {status['failed']}")
        time.sleep(interval)

# Run monitoring
monitor_queue(duration_seconds=300, interval=10)
