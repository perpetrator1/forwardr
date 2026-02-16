"""
Test script for Instagram posting functionality.
"""
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def test_image_post() -> bool:
    """Test posting an image to Instagram."""
    from app.platforms.instagram import post_to_instagram

    logger.info("=" * 60)
    logger.info("Testing Instagram image post...")
    logger.info("=" * 60)

    media_dir = Path(__file__).parent.parent / "media"
    test_image = None

    if media_dir.exists():
        for ext in ["*.jpg", "*.jpeg", "*.png"]:
            images = list(media_dir.glob(ext))
            if images:
                test_image = images[0]
                break

    if not test_image:
        media_dir.mkdir(exist_ok=True)
        test_image = media_dir / "test_instagram.jpg"
        try:
            from PIL import Image

            image = Image.new("RGB", (1080, 1080), color=(40, 80, 120))
            image.save(test_image)
            logger.info(f"Created test image: {test_image}")
        except ImportError:
            logger.error("Pillow not installed. Cannot create test image.")
            return False

    media_info = {
        "type": "photo",
        "caption": "Test image post from forwardr automation.",
        "local_path": str(test_image),
    }

    result = post_to_instagram(media_info)

    if result:
        logger.info("Image post SUCCESS")
    else:
        logger.error("Image post FAILED")

    return result


def main() -> None:
    """Run Instagram tests."""
    logger.info("Starting Instagram Integration Test")

    from app.config import settings

    if not settings.instagram.is_complete():
        missing = settings.instagram.get_missing_fields()
        logger.error("Instagram credentials not configured")
        logger.error(f"Missing: {', '.join(missing)}")
        logger.error("Please set these in your .env file")
        return

    logger.info("Credentials found. Running test...")

    result = test_image_post()
    status = "PASS" if result else "FAIL"
    logger.info(f"Test result: {status}")


if __name__ == "__main__":
    main()
