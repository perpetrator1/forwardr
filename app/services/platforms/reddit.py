"""
Reddit platform integration

TODO: Implement actual posting using praw.
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def post(media_info: Dict) -> Optional[str]:
    """
    Post content to Reddit.

    Args:
        media_info: MediaInfo dictionary.

    Returns:
        Post URL if successful, None if failed.
    """
    try:
        from app.config import settings

        # TODO: Implement Reddit posting with praw
        subreddit = settings.reddit.subreddit or "unknown"
        logger.info(f"Reddit: Would post {media_info.get('type')} to r/{subreddit}")
        return f"https://reddit.com/r/{subreddit}"

    except Exception as e:
        logger.error(f"Reddit posting failed: {e}")
        return None
