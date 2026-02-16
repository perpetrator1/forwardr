"""
Reddit posting via praw.
"""
import logging
import time
from pathlib import Path
from typing import Dict

import praw

logger = logging.getLogger(__name__)


def _split_caption(caption: str, default_title: str) -> tuple[str, str]:
    lines = [line.strip() for line in caption.splitlines()]
    lines = [line for line in lines if line != ""]

    if not lines:
        return default_title, ""

    title = lines[0]
    body = "\n".join(lines[1:]).strip()
    if not title:
        title = default_title
    return title, body


def post_to_reddit(media_info: Dict) -> bool:
    """
    Post content to Reddit.

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

    reddit_settings = settings.reddit

    if not reddit_settings.is_complete():
        logger.error("Reddit credentials missing. Check REDDIT_* environment variables.")
        return False

    if not isinstance(media_info, dict):
        logger.error("media_info must be a dict")
        return False

    media_type = (media_info.get("type") or "text").lower()
    caption = media_info.get("caption") or ""

    try:
        reddit = praw.Reddit(
            client_id=reddit_settings.client_id,
            client_secret=reddit_settings.client_secret,
            username=reddit_settings.username,
            password=reddit_settings.password,
            user_agent=reddit_settings.user_agent,
        )

        subreddit_name = reddit_settings.subreddit
        if not subreddit_name:
            logger.error("REDDIT_SUBREDDIT is not set")
            return False

        subreddit = reddit.subreddit(subreddit_name)
        title, body = _split_caption(caption, reddit_settings.default_title)

        time.sleep(2)

        if media_type == "photo":
            local_path = media_info.get("local_path")
            if not local_path:
                logger.error("Photo post missing local_path")
                return False

            path = Path(local_path)
            if not path.exists():
                logger.error(f"Photo file not found: {local_path}")
                return False

            subreddit.submit_image(title=title, image_path=str(path))
            logger.info(f"Successfully posted photo to Reddit: {local_path}")
            return True

        if media_type == "video":
            local_path = media_info.get("local_path")
            if not local_path:
                logger.error("Video post missing local_path")
                return False

            path = Path(local_path)
            if not path.exists():
                logger.error(f"Video file not found: {local_path}")
                return False

            subreddit.submit_video(title=title, video_path=str(path))
            logger.info(f"Successfully posted video to Reddit: {local_path}")
            return True

        if media_type == "text":
            text = media_info.get("text") or caption
            title, body = _split_caption(text, reddit_settings.default_title)
            subreddit.submit(title=title, selftext=body)
            logger.info("Successfully posted text to Reddit")
            return True

        logger.info(f"Skipping unsupported media type for Reddit: {media_type}")
        return False

    except Exception as exc:
        logger.error(f"Failed to post to Reddit: {exc}", exc_info=True)
        return False
