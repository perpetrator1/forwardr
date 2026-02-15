#!/usr/bin/env python3
"""
Example usage of the media handler for Telegram message processing
"""
import asyncio
from app.media_handler import MediaHandler, MediaInfo


async def example_telegram_workflow():
    """Example: Process a Telegram message with an image"""
    
    print("=" * 70)
    print("EXAMPLE 1: Processing Telegram Message with Photo")
    print("=" * 70)
    print()
    
    # Simulated Telegram message (what you'd receive from webhook)
    telegram_message = {
        "message_id": 123,
        "from": {"id": 123456789, "first_name": "User"},
        "chat": {"id": -1001234567890},
        "date": 1708012800,
        "photo": [
            {
                "file_id": "AgACAgIAAxkBAAIBY2ZkNzQwMDAwMDAwMDAwMDAwMDA",
                "file_unique_id": "AQADAAA",
                "file_size": 1234,
                "width": 90,
                "height": 67
            },
            {
                "file_id": "AgACAgIAAxkBAAIBZGZkNzQwMDAwMDAwMDAwMDAwMDE",
                "file_unique_id": "AQADAAB",
                "file_size": 12345,
                "width": 320,
                "height": 240
            },
            {
                "file_id": "AgACAgIAAxkBAAIBZWZkNzQwMDAwMDAwMDAwMDAwMDI",
                "file_unique_id": "AQADAAC",
                "file_size": 123456,
                "width": 1280,
                "height": 960
            }
        ],
        "caption": "Check out this amazing photo! #nature #photography"
    }
    
    # Initialize handler with bot token from config
    bot_token = "YOUR_BOT_TOKEN_HERE"  # From config.settings.telegram.bot_token
    handler = MediaHandler(bot_token=bot_token, media_dir="./media")
    
    # Step 1: Parse the message
    media_info = handler.parse_telegram_message(telegram_message)
    
    print(f"Media Type: {media_info.type}")
    print(f"File ID: {media_info.file_id}")
    print(f"Caption: {media_info.caption}")
    print(f"Dimensions: {media_info.width}x{media_info.height}")
    print(f"Size: {media_info.file_size} bytes")
    print()
    
    # Step 2: Download media (would actually download from Telegram)
    # Note: This requires a valid bot token and file_id
    # media_info = await handler.download_telegram_media(media_info)
    # print(f"Downloaded to: {media_info.local_path}")
    
    print("=" * 70)
    print()


def example_local_file_processing():
    """Example: Process a local file and generate variants"""
    
    print("=" * 70)
    print("EXAMPLE 2: Processing Local File")
    print("=" * 70)
    print()
    
    # Create media info from local file
    media_info = MediaInfo(
        type="photo",
        file_id="local_test_image",
        local_path="test_image.jpg",
        caption="Test image for processing"
    )
    
    handler = MediaHandler(bot_token="", media_dir="./media")
    
    # Generate platform-specific variants
    print("Generating platform variants...")
    variants = handler.get_media_variants(media_info)
    
    print(f"\nGenerated {len(variants)} variants:")
    for platform, info in sorted(variants.items()):
        print(f"  • {platform:20} → {info['dimensions'][0]:4}x{info['dimensions'][1]:<4} "
              f"({info['size_mb']} MB, Q{info['quality']})")
    
    print()
    print("=" * 70)
    print()


def example_cleanup():
    """Example: Clean up media files"""
    
    print("=" * 70)
    print("EXAMPLE 3: Cleanup Media")
    print("=" * 70)
    print()
    
    handler = MediaHandler(bot_token="", media_dir="./media")
    
    # Simulate a media_info with local file
    media_info = MediaInfo(
        type="photo",
        file_id="test123",
        local_path="./media/test_file.jpg"
    )
    
    # Clean up the file
    success = handler.cleanup_media(media_info)
    
    if success:
        print(f"Deleted: {media_info.local_path}")
    else:
        print(f"File not found or already deleted: {media_info.local_path}")
    
    print()
    print("=" * 70)
    print()


def example_text_message():
    """Example: Handle text-only message"""
    
    print("=" * 70)
    print("EXAMPLE 4: Text-Only Message")
    print("=" * 70)
    print()
    
    telegram_message = {
        "message_id": 124,
        "from": {"id": 123456789, "first_name": "User"},
        "chat": {"id": -1001234567890},
        "date": 1708012800,
        "text": "This is a text message with no media"
    }
    
    handler = MediaHandler(bot_token="", media_dir="./media")
    media_info = handler.parse_telegram_message(telegram_message)
    
    print(f"Media Type: {media_info.type}")
    print(f"Caption/Text: {media_info.caption}")
    print(f"Has Media: {media_info.file_id is not None}")
    
    print()
    print("=" * 70)
    print()


def main():
    """Run all examples"""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "MEDIA HANDLER USAGE EXAMPLES" + " " * 25 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    # Example 1: Telegram message parsing
    asyncio.run(example_telegram_workflow())
    
    # Example 2: Local file processing
    example_local_file_processing()
    
    # Example 3: Text-only message
    example_text_message()
    
    # Example 4: Cleanup
    # example_cleanup()  # Uncomment to test cleanup
    
    print("\nAll examples completed!\n")


if __name__ == "__main__":
    main()
