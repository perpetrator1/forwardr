"""
Bluesky posting via atproto.
"""
import logging
from pathlib import Path
from typing import Dict, Optional

from atproto import Client

logger = logging.getLogger(__name__)

_client: Optional[Client] = None
_client_username: Optional[str] = None
_client_password: Optional[str] = None


def _get_client(username: str, password: str) -> Client:
    global _client, _client_username, _client_password

    if _client is None or _client_username != username or _client_password != password:
        client = Client()
        client.login(username, password)
        _client = client
        _client_username = username
        _client_password = password

    return _client


def _truncate_caption(text: str) -> str:
    if len(text) <= 300:
        return text
    return text[:300]


def post_to_bluesky(media_info: Dict) -> bool:
    """
    Post content to Bluesky using the atproto client.

    Args:
        media_info: Dict with keys like type, caption, local_path

    Returns:
        True if post succeeded, False otherwise
    """
    try:
        from app.config import settings
    except Exception as exc:
        logger.error(f"Failed to load app settings: {exc}")
        return False

    username = settings.bluesky.username or settings.bluesky.handle
    password = settings.bluesky.password

    if not username or not password:
        logger.error("Bluesky credentials missing. Check BLUESKY_USERNAME and BLUESKY_PASSWORD.")
        return False

    if not isinstance(media_info, dict):
        logger.error("media_info must be a dict")
        return False

    media_type = (media_info.get("type") or "text").lower()
    caption = media_info.get("caption") or ""
    caption = _truncate_caption(caption)

    try:
        client = _get_client(username, password)

        if media_type == "text":
            text = media_info.get("text") or caption
            text = _truncate_caption(text)
            if not text:
                logger.error("Text post missing content")
                return False
            client.send_post(text=text)
            return True

        if media_type == "photo":
            local_path = media_info.get("local_path")
            if not local_path:
                logger.error("Photo post missing local_path")
                return False

            path = Path(local_path)
            if not path.exists():
                logger.error(f"Photo file not found: {local_path}")
                return False

            alt_text = media_info.get("alt_text") or media_info.get("alt") or ""

            with path.open("rb") as file_handle:
                image_data = file_handle.read()

            upload = client.upload_blob(image_data)
            embed = client.app.bsky.embed.images.main(
                images=[
                    client.app.bsky.embed.images.image(
                        alt=alt_text,
                        image=upload.blob,
                    )
                ]
            )

            client.send_post(text=caption, embed=embed)
            return True

        if media_type == "video":
            link = media_info.get("url") or media_info.get("link")
            text = caption
            if link:
                text = f"{caption}\n{link}" if caption else link
                text = _truncate_caption(text)
            if not text:
                logger.error("Video post missing caption or link")
                return False
            client.send_post(text=text)
            return True

        logger.error(f"Unsupported media type for Bluesky: {media_type}")
        return False

    except Exception as exc:
        logger.error(f"Bluesky posting failed: {exc}")
        return False
