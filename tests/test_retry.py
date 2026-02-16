#!/usr/bin/env python3
"""
Test retry logic - simulate job failures and retries
"""
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.queue_manager import QueueManager
from app.media_handler import MediaInfo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

logger = logging.getLogger(__name__)


class TestQueueManagerWithFailures(QueueManager):
    """Extended QueueManager that simulates failures for testing"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.failure_count = {}  # Track failures per job_id
    
    def process_job(self, job: dict) -> bool:
        """Override to simulate failures"""
        job_id = job['id']
        platform = job['platform']
        
        logger.info(f"Processing job #{job_id} for {platform}")
        
        # Simulate failure for first 2 attempts on job #1
        if job_id == 1 and job['attempts'] < 2:
            logger.warning(f"Simulating failure for job #{job_id} (attempt {job['attempts'] + 1})")
            
            # Call parent's error handling
            error_msg = f"Simulated API error: Rate limit exceeded (attempt {job['attempts'] + 1})"
            
            attempts = job['attempts'] + 1
            max_attempts = 3
            
            if attempts < max_attempts:
                # Reschedule for retry
                self.update_job_status(job_id, 'pending', error_message=error_msg)
                
                # Use shorter retry delay for testing (30 seconds instead of 10 minutes)
                self.reschedule_job(job_id, delay_minutes=0.5)  # 30 seconds
                logger.info(f"Job #{job_id} will retry in 30s (attempt {attempts + 1}/{max_attempts})")
            else:
                # Max attempts reached
                self.update_job_status(job_id, 'failed', error_message=error_msg)
                logger.error(f"Job #{job_id} permanently failed after {attempts} attempts")
            
            return False
        
        # Otherwise, process normally (succeed)
        return super().process_job(job)


def test_retry_logic():
    """Test retry logic with simulated failures"""
    
    print("\n" + "=" * 80)
    print("  RETRY LOGIC TEST")
    print("=" * 80 + "\n")
    
    # Setup
    db_path = "./test_retry.db"
    if Path(db_path).exists():
        Path(db_path).unlink()
    
    queue_manager = TestQueueManagerWithFailures(
        db_path=db_path,
        check_interval=5  # Check every 5 seconds
    )
    
    # Create test jobs
    print("Creating test jobs...")
    print("-" * 80)
    
    media_info = MediaInfo(
        type="text",
        file_id="retry_test",
        caption="Testing retry logic"
    )
    
    # Queue 2 jobs - first will fail twice before succeeding
    job_ids = queue_manager.queue_posts(
        media_info=media_info,
        platforms=["telegram", "twitter"],
        start_delay_minutes=0,
        interval_minutes=0.1  # 6 seconds apart
    )
    
    print(f"Created {len(job_ids)} jobs")
    print(f"  • Job #1 will fail 2 times before succeeding")
    print(f"  • Job #2 will succeed immediately")
    print()
    
    # Start processor
    print("Starting processor...")
    print("-" * 80)
    queue_manager.start_processor()
    print("Processor started\n")
    
    # Monitor for up to 90 seconds (enough time for retries)
    print("Monitoring progress...")
    print("-" * 80)
    
    max_iterations = 18  # 18 * 5 = 90 seconds
    iteration = 0
    
    try:
        while iteration < max_iterations:
            iteration += 1
            time.sleep(5)
            
            status = queue_manager.get_queue_status()
            jobs = queue_manager.get_all_jobs(limit=10)
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{timestamp}] Check #{iteration}")
            print(f"  Status: {status['pending']} pending, "
                  f"{status['completed']} completed, "
                  f"{status['failed']} failed")
            
            # Show job details
            for job in jobs:
                if job['status'] == 'pending':
                    print(f"    Job #{job['id']} ({job['platform']}): "
                          f"Attempt {job['attempts']}, scheduled for {job['scheduled_time'][-8:]}")
                elif job['status'] == 'completed':
                    print(f"    Job #{job['id']} ({job['platform']}): Completed")
                elif job['status'] == 'failed':
                    print(f"    Job #{job['id']} ({job['platform']}): Failed permanently")
            
            # Check if done
            if status['pending'] == 0 and status['total'] > 0:
                print("\nAll jobs completed!")
                break
        
        # Final results
        print("\n" + "=" * 80)
        print("  FINAL RESULTS")
        print("=" * 80 + "\n")
        
        jobs = queue_manager.get_all_jobs(limit=10)
        for job in jobs:
            print(f"Job #{job['id']} - {job['platform']}")
            print(f"  Status: {job['status']}")
            print(f"  Attempts: {job['attempts']}")
            
            if job['error_log']:
                print(f"  Error log:")
                for line in job['error_log'].strip().split('\n'):
                    print(f"    {line}")
            
            if job['post_url']:
                print(f"  Posted: {job['post_url']}")
            
            print()
        
    finally:
        queue_manager.stop_processor()
    
    print("=" * 80)
    print("Retry test completed!\n")


if __name__ == "__main__":
    test_retry_logic()
