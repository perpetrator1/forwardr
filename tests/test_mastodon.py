"""
Test script for Mastodon posting functionality.
"""
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def test_text_post():
    """Test posting a text status to Mastodon."""
    from app.platforms.mastodon import post_to_mastodon
    
    logger.info("=" * 60)
    logger.info("Testing Mastodon text post...")
    logger.info("=" * 60)
    
    media_info = {
        "type": "text",
        "text": "🤖 Test post from forwardr automation system! This is a test of the Mastodon integration."
    }
    
    result = post_to_mastodon(media_info)
    
    if result:
        logger.info("✅ Text post SUCCESS")
    else:
        logger.error("❌ Text post FAILED")
    
    return result


def test_image_post():
    """Test posting an image to Mastodon."""
    from app.platforms.mastodon import post_to_mastodon
    
    logger.info("=" * 60)
    logger.info("Testing Mastodon image post...")
    logger.info("=" * 60)
    
    # Try to find a test image in media directory
    media_dir = Path(__file__).parent.parent / "media"
    test_image = None
    
    if media_dir.exists():
        # Look for common image extensions
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.gif"]:
            images = list(media_dir.glob(ext))
            if images:
                test_image = images[0]
                break
    
    if not test_image:
        logger.warning("No test image found in media/ directory")
        logger.info("Creating a simple test image...")
        
        # Create media directory if it doesn't exist
        media_dir.mkdir(exist_ok=True)
        test_image = media_dir / "test_image.png"
        
        # Create a simple colored image using PIL
        try:
            from PIL import Image
            img = Image.new('RGB', (400, 300), color=(73, 109, 137))
            img.save(test_image)
            logger.info(f"Created test image: {test_image}")
        except ImportError:
            logger.error("PIL/Pillow not installed. Cannot create test image.")
            logger.info("Install with: pip install Pillow")
            return False
    
    logger.info(f"Using test image: {test_image}")
    
    media_info = {
        "type": "photo",
        "caption": "📸 Test image post from forwardr! Testing Mastodon photo upload functionality.",
        "local_path": str(test_image)
    }
    
    result = post_to_mastodon(media_info)
    
    if result:
        logger.info("✅ Image post SUCCESS")
    else:
        logger.error("❌ Image post FAILED")
    
    return result


def main():
    """Run all Mastodon tests."""
    logger.info("\n🚀 Starting Mastodon Integration Tests\n")
    
    # Check for credentials
    from app.config import settings
    
    if not settings.mastodon.is_complete():
        missing = settings.mastodon.get_missing_fields()
        logger.error("❌ Mastodon credentials not configured")
        logger.error(f"Missing: {', '.join(missing)}")
        logger.error("Please set these in your .env file")
        return
    
    logger.info(f"✅ Mastodon instance: {settings.mastodon.instance_url}")
    logger.info("")
    
    # Run tests
    results = []
    
    # Test 1: Text post
    results.append(("Text Post", test_text_post()))
    
    print()  # Spacing between tests
    
    # Test 2: Image post
    results.append(("Image Post", test_image_post()))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name}: {status}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
