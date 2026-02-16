#!/usr/bin/env python3
"""
Send a test text message and image to Bluesky.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from app.platforms.bluesky import post_to_bluesky

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


def ensure_test_image() -> Path:
    """Ensure a test image exists and return its path."""
    image_path = Path("./large_test_image.jpg")
    if image_path.exists():
        return image_path

    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("Pillow is required to generate a test image")

    image = Image.new("RGB", (800, 450), (30, 120, 200))
    image.save(image_path)
    return image_path


def main() -> int:
    if not settings.bluesky.is_complete():
        missing = settings.bluesky.get_missing_fields()
        logger.error(f"Bluesky credentials missing: {', '.join(missing)}")
        return 1

    logger.info("Sending test text post...")
    text_ok = post_to_bluesky(
        {
            "type": "text",
            "caption": "Forwardr test: Bluesky text post",
        }
    )

    logger.info("Sending test image post...")
    try:
        image_path = ensure_test_image()
    except RuntimeError as exc:
        logger.error(str(exc))
        return 1

    image_ok = post_to_bluesky(
        {
            "type": "photo",
            "caption": "Forwardr test: Bluesky image post",
            "local_path": str(image_path),
            "alt_text": "",
        }
    )

    if text_ok and image_ok:
        logger.info("Bluesky test completed successfully")
        return 0

    logger.error("Bluesky test failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
