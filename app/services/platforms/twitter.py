"""
Twitter/X platform integration using Tweepy (API v2 + v1.1 media upload).
"""
import logging
import time
from typing import Dict, Optional

import tweepy

logger = logging.getLogger(__name__)

# Twitter character limit
TWEET_MAX_LENGTH = 280

# Media processing poll interval / max wait
_MEDIA_POLL_INTERVAL = 5  # seconds
_MEDIA_MAX_WAIT = 120  # seconds


def _get_clients():
    """
    Build and return (tweepy.Client, tweepy.API) using the configured credentials.

    - ``Client`` is the v2 API client used for creating tweets.
    - ``API`` is the v1.1 client needed for media uploads (not yet in v2).

    Returns:
        Tuple of (client_v2, api_v1) or (None, None) on failure.
    """
    from app.config import settings

    tw = settings.twitter
    if not tw.is_complete():
        missing = tw.get_missing_fields()
        logger.error(f"Twitter: Missing credentials — {', '.join(missing)}")
        return None, None

    try:
        # v2 client for tweet creation
        client = tweepy.Client(
            consumer_key=tw.api_key,
            consumer_secret=tw.api_secret,
            access_token=tw.access_token,
            access_token_secret=tw.access_token_secret,
        )

        # v1.1 API for media uploads
        auth = tweepy.OAuth1UserHandler(
            consumer_key=tw.api_key,
            consumer_secret=tw.api_secret,
            access_token=tw.access_token,
            access_token_secret=tw.access_token_secret,
        )
        api = tweepy.API(auth, wait_on_rate_limit=True)

        return client, api
    except Exception as e:
        logger.error(f"Twitter: Failed to initialise clients: {e}", exc_info=True)
        return None, None


def _upload_media(api: tweepy.API, local_path: str, media_type: str) -> Optional[int]:
    """
    Upload a photo or video via the v1.1 media/upload endpoint.

    For videos the upload uses chunked mode and waits for server-side
    processing to complete before returning.

    Args:
        api: Authenticated tweepy v1.1 API instance.
        local_path: Path to the local media file.
        media_type: ``'photo'`` or ``'video'``.

    Returns:
        ``media_id`` (int) on success, ``None`` on failure.
    """
    try:
        if media_type == "video":
            logger.info(f"Twitter: Uploading video (chunked) — {local_path}")
            media = api.media_upload(
                filename=local_path,
                media_category="tweet_video",
                chunked=True,
            )
            # Wait for async processing to finish
            _wait_for_media_processing(api, media.media_id)
        else:
            logger.info(f"Twitter: Uploading image — {local_path}")
            media = api.media_upload(filename=local_path)

        logger.info(f"Twitter: Media uploaded — media_id={media.media_id}")
        return media.media_id

    except tweepy.TweepyException as e:
        logger.error(f"Twitter: Media upload failed: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Twitter: Unexpected error during media upload: {e}", exc_info=True)
        return None


def _wait_for_media_processing(api: tweepy.API, media_id: int) -> None:
    """
    Poll ``media/upload`` STATUS until the video is processed or we time out.
    """
    elapsed = 0
    while elapsed < _MEDIA_MAX_WAIT:
        try:
            status = api.get_media_upload_status(media_id)
            state = status.processing_info.get("state") if hasattr(status, "processing_info") and status.processing_info else None

            if state is None or state == "succeeded":
                logger.info(f"Twitter: Media {media_id} processing complete")
                return

            if state == "failed":
                error = (
                    status.processing_info.get("error", {}).get("message", "unknown")
                    if status.processing_info
                    else "unknown"
                )
                logger.error(f"Twitter: Media processing failed — {error}")
                return

            wait = status.processing_info.get("check_after_secs", _MEDIA_POLL_INTERVAL)
            logger.debug(f"Twitter: Media processing state={state}, retrying in {wait}s")
            time.sleep(wait)
            elapsed += wait

        except Exception as e:
            logger.warning(f"Twitter: Error checking media status: {e}")
            time.sleep(_MEDIA_POLL_INTERVAL)
            elapsed += _MEDIA_POLL_INTERVAL

    logger.warning(f"Twitter: Media processing not confirmed after {_MEDIA_MAX_WAIT}s — proceeding anyway")


def post(media_info: Dict) -> Optional[str]:
    """
    Post content to Twitter/X.

    Supports:
    - Text-only tweets
    - Photo tweets (with or without caption)
    - Video tweets (with or without caption)

    Args:
        media_info: MediaInfo dictionary with keys ``type``, ``caption``,
            and optionally ``local_path``.

    Returns:
        Tweet URL if successful, ``None`` if failed.
    """
    try:
        client, api = _get_clients()
        if client is None:
            return None

        text = media_info.get("caption", "") or ""
        media_type = media_info.get("type", "text")
        local_path = media_info.get("local_path")

        # Truncate to Twitter's limit
        if len(text) > TWEET_MAX_LENGTH:
            logger.warning(f"Twitter: Truncating text from {len(text)} to {TWEET_MAX_LENGTH} chars")
            text = text[: TWEET_MAX_LENGTH - 3] + "..."

        # Text is required for text-only tweets
        if not text and media_type == "text":
            logger.error("Twitter: No text content for text-only tweet")
            return None

        # --- Media upload --------------------------------------------------------
        media_ids = None

        if media_type in ("photo", "video") and local_path:
            media_id = _upload_media(api, local_path, media_type)
            if media_id:
                media_ids = [media_id]
            else:
                logger.warning("Twitter: Media upload failed — falling back to text-only")

        # --- Create tweet --------------------------------------------------------
        logger.info(
            f"Twitter: Creating tweet ({len(text)} chars"
            f"{', with media' if media_ids else ''})"
        )

        # text can be empty when posting media-only tweets
        tweet_text = text if text else None

        response = client.create_tweet(text=tweet_text, media_ids=media_ids)

        if response and response.data:
            tweet_id = response.data.get("id")
            if tweet_id:
                # Fetch the authenticated user's username for the URL
                tweet_url = _build_tweet_url(client, tweet_id)
                logger.info(f"Twitter: Posted successfully — {tweet_url}")
                return tweet_url

        logger.warning("Twitter: Tweet created but no ID returned")
        return "https://x.com"

    except tweepy.TweepyException as e:
        logger.error(f"Twitter posting failed (Tweepy): {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Twitter posting failed: {e}", exc_info=True)
        return None


def _build_tweet_url(client: tweepy.Client, tweet_id: str) -> str:
    """Construct the tweet URL from the authenticated user's handle."""
    try:
        me = client.get_me()
        if me and me.data:
            return f"https://x.com/{me.data.username}/status/{tweet_id}"
    except Exception as e:
        logger.debug(f"Twitter: Could not fetch username for URL: {e}")
    return f"https://x.com/i/status/{tweet_id}"
