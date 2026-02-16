"""
Twitter/X posting via tweepy.
"""
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import tweepy

logger = logging.getLogger(__name__)

_client_v2: Optional[tweepy.Client] = None
_api_v1: Optional[tweepy.API] = None
_client_creds: Optional[Tuple[str, str, str, str]] = None


def _get_clients(
    api_key: str,
    api_secret: str,
    access_token: str,
    access_token_secret: str,
) -> Tuple[tweepy.Client, tweepy.API]:
    """Get or create tweepy v2 client and v1.1 API objects."""
    global _client_v2, _api_v1, _client_creds

    creds = (api_key, api_secret, access_token, access_token_secret)
    if _client_v2 is None or _api_v1 is None or _client_creds != creds:
        _client_v2 = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        auth = tweepy.OAuth1UserHandler(
            api_key,
            api_secret,
            access_token,
            access_token_secret,
        )
        _api_v1 = tweepy.API(auth)
        _client_creds = creds

    return _client_v2, _api_v1


def _truncate_caption(text: str) -> str:
    if len(text) <= 280:
        return text
    return text[:280]


def post_to_twitter(media_info: Dict) -> bool:
    """
    Post content to Twitter/X using tweepy.

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

    api_key = settings.twitter.api_key
    api_secret = settings.twitter.api_secret
    access_token = settings.twitter.access_token
    access_token_secret = settings.twitter.access_token_secret

    if not api_key or not api_secret or not access_token or not access_token_secret:
        logger.error(
            "Twitter credentials missing. Check TWITTER_API_KEY, TWITTER_API_SECRET, "
            "TWITTER_ACCESS_TOKEN, and TWITTER_ACCESS_TOKEN_SECRET."
        )
        return False

    if not isinstance(media_info, dict):
        logger.error("media_info must be a dict")
        return False

    media_type = (media_info.get("type") or "text").lower()
    caption = media_info.get("caption") or ""
    caption = _truncate_caption(caption)

    try:
        client_v2, api_v1 = _get_clients(
            api_key,
            api_secret,
            access_token,
            access_token_secret,
        )

        if media_type == "text":
            text = media_info.get("text") or caption
            text = _truncate_caption(text)
            if not text:
                logger.error("Text post missing content")
                return False
            client_v2.create_tweet(text=text)
            logger.info("Successfully posted text to Twitter")
            return True

        if media_type in {"photo", "video"}:
            local_path = media_info.get("local_path")
            if not local_path:
                logger.error(f"{media_type} post missing local_path")
                return False

            path = Path(local_path)
            if not path.exists():
                logger.error(f"{media_type} file not found: {local_path}")
                return False

            media = api_v1.media_upload(str(path))
            media_id = media.media_id_string

            client_v2.create_tweet(
                text=caption,
                media_ids=[media_id],
            )
            logger.info(f"Successfully posted {media_type} to Twitter: {local_path}")
            return True

        logger.error(f"Unsupported media type for Twitter: {media_type}")
        return False

    except Exception as exc:
        logger.error(f"Twitter posting failed: {exc}", exc_info=True)
        return False
