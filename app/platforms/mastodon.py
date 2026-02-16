"""
Mastodon posting via Mastodon.py library.
"""
import logging
from pathlib import Path
from typing import Dict

from mastodon import Mastodon

logger = logging.getLogger(__name__)

_client = None
_client_instance_url = None
_client_access_token = None


def _get_client(instance_url: str, access_token: str) -> Mastodon:
    """Get or create Mastodon client instance."""
    global _client, _client_instance_url, _client_access_token

    if _client is None or _client_instance_url != instance_url or _client_access_token != access_token:
        _client = Mastodon(
            access_token=access_token,
            api_base_url=instance_url
        )
        _client_instance_url = instance_url
        _client_access_token = access_token

    return _client


def _truncate_caption(text: str) -> str:
    """Truncate caption to Mastodon's 500 character limit."""
    if len(text) <= 500:
        return text
    return text[:500]


def post_to_mastodon(media_info: Dict) -> bool:
    """
    Post content to Mastodon.

    Args:
        media_info: Dict with keys like type, caption, local_path, text

    Returns:
        True if post succeeded, False otherwise
    """
    try:
        from app.config import settings
    except Exception as exc:
        logger.error(f"Failed to load app settings: {exc}")
        return False

    instance_url = settings.mastodon.instance_url
    access_token = settings.mastodon.access_token

    if not instance_url or not access_token:
        logger.error("Mastodon credentials missing. Check MASTODON_INSTANCE_URL and MASTODON_ACCESS_TOKEN.")
        return False

    if not isinstance(media_info, dict):
        logger.error("media_info must be a dict")
        return False

    media_type = (media_info.get("type") or "text").lower()
    caption = media_info.get("caption") or ""
    caption = _truncate_caption(caption)

    try:
        client = _get_client(instance_url, access_token)

        # Handle text-only posts
        if media_type == "text":
            text = media_info.get("text") or caption
            text = _truncate_caption(text)
            if not text:
                logger.error("Text post missing content")
                return False
            
            client.status_post(
                status=text,
                visibility='public'
            )
            logger.info("Successfully posted text to Mastodon")
            return True

        # Handle photo posts
        if media_type == "photo":
            local_path = media_info.get("local_path")
            if not local_path:
                logger.error("Photo post missing local_path")
                return False

            path = Path(local_path)
            if not path.exists():
                logger.error(f"Photo file not found: {local_path}")
                return False

            # Upload media first
            media_dict = client.media_post(str(path))
            media_id = media_dict['id']

            # Post status with media
            client.status_post(
                status=caption,
                media_ids=[media_id],
                visibility='public'
            )
            logger.info(f"Successfully posted photo to Mastodon: {local_path}")
            return True

        # Handle video posts
        if media_type == "video":
            local_path = media_info.get("local_path")
            if not local_path:
                logger.error("Video post missing local_path")
                return False

            path = Path(local_path)
            if not path.exists():
                logger.error(f"Video file not found: {local_path}")
                return False

            # Upload media first
            media_dict = client.media_post(str(path))
            media_id = media_dict['id']

            # Post status with media
            client.status_post(
                status=caption,
                media_ids=[media_id],
                visibility='public'
            )
            logger.info(f"Successfully posted video to Mastodon: {local_path}")
            return True

        logger.error(f"Unsupported media type: {media_type}")
        return False

    except Exception as exc:
        logger.error(f"Failed to post to Mastodon: {exc}", exc_info=True)
        return False
