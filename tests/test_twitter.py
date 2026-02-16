"""
Test script for Twitter/X posting functionality.
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


def test_text_post() -> bool:
    """Test posting a text tweet."""
    from app.platforms.twitter import post_to_twitter

    logger.info("=" * 60)
    logger.info("Testing Twitter text post...")
    logger.info("=" * 60)

    media_info = {
        "type": "text",
        "text": "Test tweet from forwardr automation system."
    }

    result = post_to_twitter(media_info)

    if result:
        logger.info("Text post SUCCESS")
    else:
        logger.error("Text post FAILED")

    return result


def main() -> None:
    """Run Twitter tests."""
    logger.info("Starting Twitter Integration Test")

    from app.config import settings

    if not settings.twitter.is_complete():
        missing = settings.twitter.get_missing_fields()
        logger.error("Twitter credentials not configured")
        logger.error(f"Missing: {', '.join(missing)}")
        logger.error("Please set these in your .env file")
        return

    logger.info("Credentials found. Running test...")

    result = test_text_post()

    status = "PASS" if result else "FAIL"
    logger.info(f"Test result: {status}")


if __name__ == "__main__":
    main()
