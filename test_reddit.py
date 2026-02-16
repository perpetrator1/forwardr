"""
Test script for Reddit posting functionality.
"""
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def test_text_post() -> bool:
    """Test posting a text submission to Reddit."""
    from app.platforms.reddit import post_to_reddit

    logger.info("=" * 60)
    logger.info("Testing Reddit text post...")
    logger.info("=" * 60)

    media_info = {
        "type": "text",
        "caption": "Forwardr test post\n\nThis is a test text submission from the automation system.",
    }

    result = post_to_reddit(media_info)

    if result:
        logger.info("Text post SUCCESS")
    else:
        logger.error("Text post FAILED")

    return result


def main() -> None:
    """Run Reddit tests."""
    logger.info("Starting Reddit Integration Test")

    from app.config import settings

    if not settings.reddit.is_complete():
        missing = settings.reddit.get_missing_fields()
        logger.error("Reddit credentials not configured")
        logger.error(f"Missing: {', '.join(missing)}")
        logger.error("Please set these in your .env file")
        return

    logger.info("Credentials found. Running test...")

    result = test_text_post()
    status = "PASS" if result else "FAIL"
    logger.info(f"Test result: {status}")


if __name__ == "__main__":
    main()
