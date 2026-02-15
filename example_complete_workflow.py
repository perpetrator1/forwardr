#!/usr/bin/env python3
"""
Complete Integration Example - Config → Media → Queue → Platform Router
"""
import asyncio
import logging
from pathlib import Path

# Setup
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def complete_workflow_example():
    """
    Demonstrates the complete workflow from receiving a message to posting
    """
    print("\n" + "=" * 80)
    print("  COMPLETE WORKFLOW: Message → Config → Media → Queue → Platforms")
    print("=" * 80 + "\n")
    
    # Step 1: Configuration
    print("Step 1: Load Configuration")
    print("-" * 80)
    
    from app.config import settings, ENABLED_PLATFORMS
    
    print(f"✓ Database: {settings.core.database_url}")
    print(f"✓ Media dir: {settings.core.media_path}")
    print(f"✓ Enabled platforms: {', '.join(ENABLED_PLATFORMS)}")
    print()
    
    # Step 2: Platform Router
    print("Step 2: Initialize Platform Router")
    print("-" * 80)
    
    from app.services.platforms import (
        get_available_platforms,
        get_loaded_handlers
    )
    
    loaded = get_loaded_handlers()
    available = get_available_platforms()
    
    print(f"✓ Loaded handlers: {len(loaded)}")
    print(f"✓ Available platforms: {', '.join(available) if available else 'none'}")
    print()
    
    # Step 3: Parse incoming message
    print("Step 3: Parse Telegram Message")
    print("-" * 80)
    
    # Simulated webhook payload
    telegram_message = {
        "message_id": 12345,
        "from": {"id": 123456, "first_name": "User"},
        "chat": {"id": -1001234567890},
        "date": 1708012800,
        "photo": [
            {
                "file_id": "AgACAgIAAxkBAAIBZWZkNzQwMDAwMDAwMDAwMDAwMDI",
                "file_size": 123456,
                "width": 1280,
                "height": 960
            }
        ],
        "caption": "Check out this amazing sunset! #nature #photography"
    }
    
    from app.media_handler import MediaHandler
    
    handler = MediaHandler(
        bot_token=settings.telegram.bot_token if settings.is_platform_enabled('telegram') else "",
        media_dir=settings.core.media_path
    )
    
    media_info = handler.parse_telegram_message(telegram_message)
    
    print(f"✓ Media type: {media_info.type}")
    print(f"✓ Caption: {media_info.caption}")
    print(f"✓ File ID: {media_info.file_id}")
    print()
    
    # Step 4: Download media (simulated)
    print("Step 4: Download Media")
    print("-" * 80)
    
    # In production: media_info = await handler.download_telegram_media(media_info)
    # For demo, use local file
    media_info.local_path = "./test_image.jpg"
    
    if Path(media_info.local_path).exists():
        print(f"✓ Using local file: {media_info.local_path}")
    else:
        print(f"⚠ Note: {media_info.local_path} not found (would download from Telegram)")
    print()
    
    # Step 5: Determine target platforms
    print("Step 5: Determine Target Platforms")
    print("-" * 80)
    
    from app.services.platforms import determine_platforms
    
    platforms = determine_platforms(media_info.to_dict())
    
    print(f"✓ Media type '{media_info.type}' compatible with:")
    print(f"  All platforms: telegram, bluesky, mastodon, instagram, threads,")
    print(f"                 twitter, reddit, website")
    print(f"  Available now: {', '.join(platforms) if platforms else 'none'}")
    print()
    
    # Step 6: Queue posts
    print("Step 6: Queue Posts")
    print("-" * 80)
    
    from app.queue_manager import get_queue_manager
    
    queue_manager = get_queue_manager(
        db_path="./demo_integration.db",
        check_interval=60
    )
    
    if platforms:
        job_ids = queue_manager.queue_posts(
            media_info=media_info,
            platforms=platforms,
            start_delay_minutes=0,
            interval_minutes=60  # 1 hour between each platform
        )
        
        print(f"✓ Queued {len(job_ids)} jobs:")
        for i, (platform, job_id) in enumerate(zip(platforms, job_ids)):
            hours = i
            print(f"  • Job #{job_id} → {platform} (in {hours}h)")
    else:
        print("⚠ No platforms available to queue")
        print("  Add credentials to .env to enable platforms")
    print()
    
    # Step 7: Background processor
    print("Step 7: Background Processor")
    print("-" * 80)
    
    print("In production:")
    print("  • Start processor once at app startup:")
    print("    queue_manager.start_processor()")
    print()
    print("  • Processor wakes every 60 seconds")
    print("  • Checks for jobs where scheduled_time <= now")
    print("  • Calls platform router to post:")
    print("    from app.services.platforms import post_to_platform")
    print("    success = post_to_platform(platform, media_info)")
    print()
    print("  • Automatic retry on failure (max 3 attempts)")
    print("  • Auto-cleanup of media files when done")
    print()
    
    # Step 8: Workflow summary
    print("Step 8: Workflow Summary")
    print("-" * 80)
    
    status = queue_manager.get_queue_status()
    
    print("Complete workflow:")
    print()
    print("  1. Telegram webhook → FastAPI endpoint")
    print("  2. Parse message → MediaInfo")
    print("  3. Download media → Local file")
    print("  4. Determine platforms → Based on media type + config")
    print("  5. Queue jobs → SQLite database (1h apart)")
    print("  6. Background processor → Picks up ready jobs")
    print("  7. Platform router → Routes to correct handler")
    print("  8. Post to platform → Using platform API")
    print("  9. Update status → completed/failed")
    print(" 10. Cleanup media → Delete local file")
    print()
    print(f"Current queue status:")
    print(f"  • Pending: {status['pending']}")
    print(f"  • Completed: {status['completed']}")
    print(f"  • Failed: {status['failed']}")
    print()
    
    print("=" * 80)
    print("✓ Complete integration workflow demonstrated!")
    print("=" * 80 + "\n")


def production_fastapi_example():
    """Example FastAPI application structure"""
    
    example_code = '''
# main.py - Production FastAPI Application

from fastapi import FastAPI, Request
from app.config import settings
from app.queue_manager import get_queue_manager
from app.media_handler import MediaHandler
from app.services.platforms import determine_platforms

app = FastAPI(title="Forwardr - Social Media Automation")

# Initialize queue manager on startup
@app.on_event("startup")
async def startup():
    global queue_manager, media_handler
    
    queue_manager = get_queue_manager(
        db_path=settings.core.database_url.replace("sqlite+aiosqlite:///", ""),
        check_interval=settings.core.check_interval_seconds
    )
    queue_manager.start_processor()
    
    media_handler = MediaHandler(
        bot_token=settings.telegram.bot_token,
        media_dir=settings.core.media_path
    )
    
    print("✓ Queue processor started")

@app.on_event("shutdown")
async def shutdown():
    queue_manager.stop_processor()
    print("✓ Queue processor stopped")

# Telegram webhook endpoint
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Receive Telegram messages and queue for posting"""
    
    update = await request.json()
    message = update.get("message", {})
    
    # Parse message
    media_info = media_handler.parse_telegram_message(message)
    
    # Download media
    if media_info.type != "text":
        media_info = await media_handler.download_telegram_media(media_info)
    
    # Determine platforms
    platforms = determine_platforms(media_info.to_dict())
    
    # Queue posts
    job_ids = queue_manager.queue_posts(
        media_info=media_info,
        platforms=platforms,
        interval_minutes=60
    )
    
    return {
        "success": True,
        "queued_jobs": len(job_ids),
        "job_ids": job_ids,
        "platforms": platforms
    }

# Status endpoint
@app.get("/status")
async def get_status():
    """Get queue status"""
    return queue_manager.get_queue_status()

# Optional: Manual post endpoint
@app.post("/post")
async def manual_post(request: Request):
    """Manually create a post"""
    
    data = await request.json()
    
    from app.media_handler import MediaInfo
    media_info = MediaInfo(**data)
    
    platforms = determine_platforms(data)
    
    job_ids = queue_manager.queue_posts(
        media_info=media_info,
        platforms=platforms,
        start_delay_minutes=0,  # Post immediately
        interval_minutes=5      # 5 minutes apart for manual posts
    )
    
    return {"queued": len(job_ids), "job_ids": job_ids}

# Run with: uvicorn main:app --reload
'''
    
    print("\n" + "=" * 80)
    print("  PRODUCTION FASTAPI EXAMPLE")
    print("=" * 80)
    print(example_code)
    print("=" * 80 + "\n")


def main():
    """Run examples"""
    
    # Complete workflow
    asyncio.run(complete_workflow_example())
    
    # Production example
    production_fastapi_example()


if __name__ == "__main__":
    main()
