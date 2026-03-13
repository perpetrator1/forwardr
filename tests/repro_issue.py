#!/usr/bin/env python3
import sys
import os
import json
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.queue_manager import QueueManager
from app.media_handler import MediaInfo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_merging_success():
    db_path = "./repro_test.db"
    if Path(db_path).exists():
        Path(db_path).unlink()
    
    qm = QueueManager(db_path=db_path)
    chat_id = "12345"
    
    # Platform list
    platforms = ["bluesky", "mastodon"]
    
    # 1. Text message arrives first (caption)
    text_info = MediaInfo(type="text", caption="This is a caption")
    logger.info("Queuing text-only post...")
    job_ids, scheduled_time = qm.queue_posts(text_info, platforms, interval_hours=0, chat_id=chat_id)
    
    # Verify it has a 5s delay
    now = datetime.now() # Approximate but fine for test
    diff = (scheduled_time - now).total_seconds()
    logger.info(f"Scheduled for {scheduled_time} (diff={diff}s)")
    if 4 <= diff <= 6:
        logger.info("SUCCESS: 5s delay applied correctly.")
    else:
        logger.error(f"FAILURE: 5s delay NOT applied correctly. Diff={diff}s")

    # 2. Media message arrives second (within 1 second)
    logger.info("Queuing media post immediately (should merge with caption)...")
    media_info = MediaInfo(type="photo", file_id="p123", caption=None)
    qm.queue_posts(media_info, platforms, interval_hours=0, chat_id=chat_id)
    
    # 3. Final check
    jobs = qm.get_all_jobs()
    logger.info(f"Total jobs: {len(jobs)}")
    
    pending_jobs = [j for j in jobs if j['status'] == 'pending']
    cancelled_jobs = [j for j in jobs if j['status'] == 'cancelled']
    
    logger.info(f"Pending jobs: {len(pending_jobs)}")
    logger.info(f"Cancelled jobs: {len(cancelled_jobs)}")

    if len(pending_jobs) == len(platforms):
        m = json.loads(pending_jobs[0]['media_info'])
        if m.get('caption') == "This is a caption":
            logger.info("SUCCESS: Merging worked! Caption inherited.")
        else:
            logger.error(f"FAILURE: Merging failed to get caption. Caption={m.get('caption')}")
    else:
        logger.error(f"FAILURE: Wrong number of pending jobs. Found {len(pending_jobs)} instead of {len(platforms)}")

if __name__ == "__main__":
    test_merging_success()
