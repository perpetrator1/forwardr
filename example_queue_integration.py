#!/usr/bin/env python3
"""
Integration example - how to use queue manager with media handler and config
"""
import asyncio
import logging
from pathlib import Path

from app.config import settings, ENABLED_PLATFORMS
from app.media_handler import MediaHandler, MediaInfo
from app.queue_manager import get_queue_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

logger = logging.getLogger(__name__)


async def process_telegram_message_example(telegram_message: dict):
    """
    Example: Full workflow from Telegram message to queued posts
    
    This shows how all components work together:
    1. Parse Telegram message
    2. Download media
    3. Generate platform-specific variants
    4. Queue posts for enabled platforms
    5. Background processor handles posting
    """
    
    print("\n" + "=" * 70)
    print("INTEGRATION EXAMPLE: Telegram Message → Queue → Social Media")
    print("=" * 70 + "\n")
    
    # Step 1: Initialize components with config
    print("Step 1: Initialize components")
    print("-" * 70)
    
    media_handler = MediaHandler(
        bot_token=settings.telegram.bot_token if settings.is_platform_enabled('telegram') else "",
        media_dir=settings.core.media_path
    )
    
    queue_manager = get_queue_manager(
        db_path=settings.core.database_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", ""),
        check_interval=settings.core.check_interval_seconds
    )
    
    print(f"✓ Media handler initialized (media dir: {settings.core.media_path})")
    print(f"✓ Queue manager initialized (check interval: {settings.core.check_interval_seconds}s)")
    print(f"✓ Enabled platforms: {', '.join(ENABLED_PLATFORMS)}")
    print()
    
    # Step 2: Parse Telegram message
    print("Step 2: Parse Telegram message")
    print("-" * 70)
    
    media_info = media_handler.parse_telegram_message(telegram_message)
    
    print(f"Media type: {media_info.type}")
    print(f"Caption: {media_info.caption}")
    if media_info.file_id:
        print(f"File ID: {media_info.file_id}")
    print()
    
    # Step 3: Download media (if not text-only)
    if media_info.type != "text" and media_info.file_id:
        print("Step 3: Download media from Telegram")
        print("-" * 70)
        
        # In production, this would actually download:
        # media_info = await media_handler.download_telegram_media(media_info)
        # print(f"✓ Downloaded to: {media_info.local_path}")
        
        # For this example, use local test file
        media_info.local_path = "./test_image.jpg"
        print(f"✓ Using test file: {media_info.local_path}")
        print()
        
        # Step 4: Generate platform-specific variants (optional, can be done per-platform)
        print("Step 4: Generate platform-specific variants")
        print("-" * 70)
        
        if Path(media_info.local_path).exists():
            variants = media_handler.get_media_variants(
                media_info,
                platforms=ENABLED_PLATFORMS
            )
            
            print(f"✓ Generated {len(variants)} platform variants")
            for platform, info in sorted(variants.items()):
                print(f"  • {platform}: {info['dimensions'][0]}x{info['dimensions'][1]}, {info['size_mb']} MB")
        else:
            print("⚠ Test file not found, skipping variant generation")
        print()
    
    # Step 5: Queue posts for enabled platforms
    print("Step 5: Queue posts for all enabled platforms")
    print("-" * 70)
    
    if ENABLED_PLATFORMS:
        job_ids = queue_manager.queue_posts(
            media_info=media_info,
            platforms=ENABLED_PLATFORMS,
            start_delay_minutes=0,
            interval_minutes=60  # 1 hour between posts
        )
        
        print(f"✓ Queued {len(job_ids)} posts:")
        for i, (platform, job_id) in enumerate(zip(ENABLED_PLATFORMS, job_ids)):
            delay_hours = i
            print(f"  • Job #{job_id} → {platform} (in {delay_hours}h)")
    else:
        print("⚠ No platforms enabled, skipping queue")
    print()
    
    # Step 6: Start background processor (if not already running)
    print("Step 6: Background processor")
    print("-" * 70)
    
    # In production, start this once at app startup:
    # queue_manager.start_processor()
    print("💡 In production, start processor once at app startup:")
    print("   queue_manager.start_processor()")
    print()
    
    # Step 7: Monitor status
    print("Step 7: Check queue status")
    print("-" * 70)
    
    status = queue_manager.get_queue_status()
    print(f"Queue status:")
    print(f"  • Pending:   {status['pending']}")
    print(f"  • Completed: {status['completed']}")
    print(f"  • Failed:    {status['failed']}")
    print(f"  • Total:     {status['total']}")
    print()
    
    print("=" * 70)
    print("✓ Integration example completed!")
    print("=" * 70 + "\n")


def webhook_handler_example():
    """
    Example: Webhook handler for receiving Telegram messages
    
    This is how you'd integrate everything in a FastAPI webhook endpoint
    """
    
    # Simulated Telegram webhook payload
    webhook_payload = {
        "update_id": 123456789,
        "message": {
            "message_id": 42,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "John",
                "username": "johndoe"
            },
            "chat": {
                "id": -1001234567890,
                "title": "My Channel",
                "type": "channel"
            },
            "date": 1708012800,
            "photo": [
                {
                    "file_id": "AgACAgIAAxkBAAIBZWZkNzQwMDAwMDAwMDAwMDAwMDI",
                    "file_unique_id": "AQADAAC",
                    "file_size": 123456,
                    "width": 1280,
                    "height": 960
                }
            ],
            "caption": "Amazing sunset! 🌅 #nature #photography"
        }
    }
    
    # Extract message
    message = webhook_payload.get("message", {})
    
    # Process it
    asyncio.run(process_telegram_message_example(message))


def cleanup_example():
    """Example: Periodic cleanup of old jobs"""
    
    print("\n" + "=" * 70)
    print("CLEANUP EXAMPLE")
    print("=" * 70 + "\n")
    
    queue_manager = get_queue_manager()
    
    print("Purging old completed jobs (older than 7 days)...")
    deleted = queue_manager.purge_old_jobs(days=7)
    print(f"✓ Deleted {deleted} old jobs")
    print()
    
    print("=" * 70 + "\n")


def monitoring_example():
    """Example: Get detailed job information for monitoring/debugging"""
    
    print("\n" + "=" * 70)
    print("MONITORING EXAMPLE")
    print("=" * 70 + "\n")
    
    queue_manager = get_queue_manager()
    
    # Get recent jobs
    jobs = queue_manager.get_all_jobs(limit=10)
    
    print(f"Recent jobs (last {len(jobs)}):\n")
    
    for job in jobs:
        status_emoji = {
            'pending': '⏳',
            'completed': '✅',
            'failed': '❌'
        }.get(job['status'], '❓')
        
        print(f"{status_emoji} Job #{job['id']}")
        print(f"   Platform: {job['platform']}")
        print(f"   Status: {job['status']} (attempt {job['attempts']})")
        print(f"   Scheduled: {job['scheduled_time']}")
        
        if job['completed_at']:
            print(f"   Completed: {job['completed_at']}")
        
        if job['post_url']:
            print(f"   URL: {job['post_url']}")
        
        if job['error_log']:
            print(f"   Errors: {job['error_log'][:100]}...")
        
        print()
    
    print("=" * 70 + "\n")


def main():
    """Run all examples"""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "QUEUE INTEGRATION EXAMPLES" + " " * 27 + "║")
    print("╚" + "═" * 68 + "╝")
    
    # Example 1: Full workflow
    webhook_handler_example()
    
    # Example 2: Cleanup
    cleanup_example()
    
    # Example 3: Monitoring
    monitoring_example()
    
    print("\n✓ All examples completed!\n")


if __name__ == "__main__":
    main()
