#!/usr/bin/env python3
"""
Test queue manager - create jobs and process them
"""
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.queue_manager import QueueManager
from app.media_handler import MediaInfo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

logger = logging.getLogger(__name__)


def print_separator(char="=", length=80):
    """Print separator line"""
    print(char * length)


def print_section(title):
    """Print section header"""
    print()
    print_separator()
    print(f"  {title}")
    print_separator()
    print()


def print_status_table(status: dict):
    """Print status in a nice table format"""
    print()
    print("+" + "-" * 38 + "+")
    print("|" + " " * 12 + "QUEUE STATUS" + " " * 14 + "|")
    print("+" + "-" * 38 + "+")
    print(f"|  Pending:   {status['pending']:4d}                    |")
    print(f"|  Completed: {status['completed']:4d}                    |")
    print(f"|  Failed:    {status['failed']:4d}                    |")
    print("+" + "-" * 38 + "+")
    print(f"|  Total:     {status['total']:4d}                    |")
    print("+" + "-" * 38 + "+")
    print()


def create_test_jobs(queue_manager: QueueManager, interval_seconds: int = 5):
    """
    Create test jobs for demonstration
    
    Args:
        queue_manager: QueueManager instance
        interval_seconds: Seconds between job schedules
    """
    print_section("CREATING TEST JOBS")
    
    # Create a test media info
    media_info = MediaInfo(
        type="photo",
        file_id="test_photo_123",
        caption="This is a test post for the queue system! #automation #test",
        local_path="./test_image.jpg",
        mime_type="image/jpeg"
    )
    
    print(f"Media Info:")
    print(f"  Type: {media_info.type}")
    print(f"  File ID: {media_info.file_id}")
    print(f"  Caption: {media_info.caption}")
    print()
    
    # Queue posts for multiple platforms
    platforms = ["telegram", "twitter", "bluesky"]
    
    print(f"Queuing posts for platforms: {', '.join(platforms)}")
    print(f"Schedule interval: {interval_seconds} seconds")
    print()
    
    job_ids = queue_manager.queue_posts(
        media_info=media_info,
        platforms=platforms,
        start_delay_minutes=0,
        interval_minutes=interval_seconds / 60  # Convert seconds to minutes
    )
    
    print(f"Created {len(job_ids)} jobs:")
    for i, (platform, job_id) in enumerate(zip(platforms, job_ids)):
        delay = i * interval_seconds
        print(f"  • Job #{job_id:3d} - {platform:12} (scheduled in {delay}s)")
    
    print()
    return job_ids


def monitor_queue(queue_manager: QueueManager, check_interval: int = 5, max_iterations: int = 20):
    """
    Monitor queue status until all jobs are complete
    
    Args:
        queue_manager: QueueManager instance
        check_interval: Seconds between status checks
        max_iterations: Maximum monitoring iterations
    """
    print_section("MONITORING QUEUE")
    
    print(f"Checking status every {check_interval} seconds...")
    print(f"(Will stop when all jobs are complete or after {max_iterations} checks)")
    print()
    
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        # Get current status
        status = queue_manager.get_queue_status()
        
        # Print status
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Check #{iteration}")
        print_status_table(status)
        
        # Check if all jobs are done
        if status['pending'] == 0 and status['total'] > 0:
            print("All jobs completed!")
            break
        
        # Wait for next check
        if iteration < max_iterations:
            time.sleep(check_interval)
    
    if iteration >= max_iterations:
        print("WARNING: Maximum iterations reached, stopping monitor")
    
    print()


def show_job_details(queue_manager: QueueManager):
    """Show detailed information about all jobs"""
    print_section("JOB DETAILS")
    
    jobs = queue_manager.get_all_jobs(limit=50)
    
    if not jobs:
        print("No jobs found in queue")
        print()
        return
    
    print(f"Total jobs: {len(jobs)}\n")
    
    for job in jobs:
        status_symbol = {
            'pending': '[PENDING]',
            'completed': '[DONE]',
            'failed': '[FAILED]'
        }.get(job['status'], '[UNKNOWN]')
        
        print(f"{status_symbol} Job #{job['id']:3d} - {job['platform']:12} "
              f"[{job['status']:9}] "
              f"(attempts: {job['attempts']})")
        
        if job['post_url']:
            print(f"    URL: {job['post_url']}")
        
        if job['error_log']:
            error_lines = job['error_log'].strip().split('\n')
            last_error = error_lines[-1] if error_lines else ""
            if last_error:
                print(f"    Error: {last_error[:60]}...")
        
        print()


def test_queue_system():
    """Main test function"""
    print()
    print_separator("=", 80)
    print("  QUEUE MANAGER TEST")
    print_separator("=", 80)
    print()
    
    # Initialize queue manager with fast check interval for testing
    db_path = "./test_queue.db"
    check_interval_seconds = 5  # Check every 5 seconds instead of 60
    
    print(f"Database: {db_path}")
    print(f"Check interval: {check_interval_seconds} seconds")
    print()
    
    # Clean up old test database if it exists
    if Path(db_path).exists():
        Path(db_path).unlink()
        print("Removed old test database")
        print()
    
    # Create queue manager
    queue_manager = QueueManager(
        db_path=db_path,
        check_interval=check_interval_seconds
    )
    
    # Create test jobs (scheduled 5 seconds apart)
    job_ids = create_test_jobs(queue_manager, interval_seconds=5)
    
    # Show initial status
    print_section("INITIAL STATUS")
    status = queue_manager.get_queue_status()
    print_status_table(status)
    
    # Start the processor
    print_section("STARTING PROCESSOR")
    print("Starting background processor thread...")
    queue_manager.start_processor()
    print("Processor started")
    print()
    
    # Monitor progress
    try:
        monitor_queue(queue_manager, check_interval=5, max_iterations=20)
        
        # Show final job details
        show_job_details(queue_manager)
        
        # Final status
        print_section("FINAL STATUS")
        final_status = queue_manager.get_queue_status()
        print_status_table(final_status)
        
        # Test purge function
        print_section("TESTING PURGE FUNCTION")
        print("Testing purge of old jobs (simulated)...")
        deleted = queue_manager.purge_old_jobs(days=7)
        print(f"Purge function executed (deleted {deleted} jobs)")
        print()
        
    finally:
        # Stop the processor
        print_section("CLEANUP")
        print("Stopping processor...")
        queue_manager.stop_processor()
        print("Processor stopped")
        print()
    
    print_separator("=", 80)
    print("Test completed successfully!")
    print_separator("=", 80)
    print()


def main():
    """Main entry point"""
    try:
        test_queue_system()
    except KeyboardInterrupt:
        print("\n\nWARNING: Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
