#!/usr/bin/env python3
"""
Test platform router - demonstrates routing logic and error handling
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.platforms import (
    post_to_platform,
    get_available_platforms,
    determine_platforms,
    get_platform_errors,
    get_loaded_handlers
)
from app.config import ENABLED_PLATFORMS
from app.media_handler import MediaInfo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s"
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


def test_platform_loading():
    """Test which platforms loaded successfully"""
    print_section("PLATFORM LOADING STATUS")
    
    loaded = get_loaded_handlers()
    errors = get_platform_errors()
    
    print("Loaded platform handlers:")
    if loaded:
        for platform in sorted(loaded):
            print(f"  ✓ {platform}")
    else:
        print("  (none)")
    
    print()
    
    if errors:
        print("Failed to load:")
        for platform, error in sorted(errors.items()):
            print(f"  ✗ {platform}: {error}")
    else:
        print("All platforms loaded successfully!")
    
    print()


def test_available_platforms():
    """Test which platforms are both configured AND loaded"""
    print_section("AVAILABLE PLATFORMS")
    
    print(f"Configured platforms (from .env): {', '.join(ENABLED_PLATFORMS) if ENABLED_PLATFORMS else 'none'}")
    print()
    
    available = get_available_platforms()
    print(f"Available platforms (configured + loaded): {', '.join(available) if available else 'none'}")
    print()
    
    if available:
        print(f"✓ {len(available)} platform(s) ready to use")
    else:
        print("⚠ No platforms available - add credentials to .env file")
    
    print()


def test_media_routing():
    """Test routing logic for different media types"""
    print_section("MEDIA TYPE ROUTING")
    
    media_types = [
        {
            'type': 'photo',
            'caption': 'A beautiful photo',
            'local_path': './test_image.jpg',
            'file_id': 'photo_123'
        },
        {
            'type': 'video',
            'caption': 'An amazing video',
            'local_path': './test_video.mp4',
            'file_id': 'video_456'
        },
        {
            'type': 'text',
            'caption': 'Just a text post',
            'file_id': 'text_789'
        },
        {
            'type': 'document',
            'caption': 'A document file',
            'local_path': './test_doc.pdf',
            'file_id': 'doc_012'
        },
    ]
    
    for media_info in media_types:
        media_type = media_info['type']
        platforms = determine_platforms(media_info)
        
        print(f"{media_type.upper():10} → {len(platforms)} platform(s): {', '.join(platforms) if platforms else 'none'}")
    
    print()


def test_posting():
    """Test posting to platforms"""
    print_section("POSTING TEST")
    
    # Create test media info
    media_info = MediaInfo(
        type='photo',
        file_id='test_photo_999',
        caption='Test post from platform router! 🚀 #automation',
        local_path='./test_image.jpg'
    ).to_dict()
    
    print("Test media info:")
    print(f"  Type: {media_info['type']}")
    print(f"  Caption: {media_info['caption']}")
    print()
    
    # Get platforms to post to
    platforms = determine_platforms(media_info)
    
    if not platforms:
        print("No platforms available for posting")
        return
    
    print(f"Attempting to post to {len(platforms)} platform(s)...\n")
    
    # Try posting to each platform
    results = {}
    for platform in platforms:
        print(f"Posting to {platform}...")
        success = post_to_platform(platform, media_info)
        results[platform] = success
        print()
    
    # Summary
    print_separator("-")
    successful = sum(1 for v in results.values() if v)
    failed = len(results) - successful
    
    print(f"\nResults: {successful} succeeded, {failed} failed")
    
    for platform, success in sorted(results.items()):
        status = "✓" if success else "✗"
        print(f"  {status} {platform}")
    
    print()


def test_error_handling():
    """Test error handling for invalid platforms"""
    print_section("ERROR HANDLING TEST")
    
    media_info = {'type': 'text', 'caption': 'Test'}
    
    # Test posting to non-existent platform
    print("1. Posting to non-existent platform...")
    result = post_to_platform('nonexistent', media_info)
    print(f"   Result: {result} (expected False)")
    print()
    
    # Test posting to non-configured platform
    print("2. Posting to non-configured platform (twitter)...")
    result = post_to_platform('twitter', media_info)
    print(f"   Result: {result}")
    print()


def main():
    """Run all tests"""
    print()
    print_separator("=", 80)
    print("  PLATFORM ROUTER TEST")
    print_separator("=", 80)
    
    # Test 1: Platform loading
    test_platform_loading()
    
    # Test 2: Available platforms
    test_available_platforms()
    
    # Test 3: Media routing
    test_media_routing()
    
    # Test 4: Posting
    test_posting()
    
    # Test 5: Error handling
    test_error_handling()
    
    print_separator("=", 80)
    print("✓ All tests completed!")
    print_separator("=", 80)
    print()


if __name__ == "__main__":
    main()
