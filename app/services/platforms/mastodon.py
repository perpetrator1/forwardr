"""
Mastodon platform integration
"""
import logging
from typing import Dict, Optional
from mastodon import Mastodon

logger = logging.getLogger(__name__)


def post(media_info: Dict) -> Optional[str]:
    """
    Post content to Mastodon
    
    Args:
        media_info: MediaInfo dictionary
        
    Returns:
        Post URL if successful, None if failed
    """
    try:
        from app.config import settings
        
        # Initialize Mastodon client
        mastodon = Mastodon(
            access_token=settings.mastodon.access_token,
            api_base_url=settings.mastodon.instance_url
        )
        
        # Get the text content
        text = media_info.get('caption', '')
        
        # Post with media if available
        if media_info['type'] in ['photo', 'video'] and media_info.get('local_path'):
            logger.info(f"Mastodon: Uploading {media_info['type']} from {media_info['local_path']}")
            media = mastodon.media_post(media_info['local_path'])
            status = mastodon.status_post(
                text,
                media_ids=[media['id']]
            )
        else:
            # Text-only post
            logger.info(f"Mastodon: Posting text: {text[:50]}...")
            status = mastodon.status_post(text)
        
        post_url = status.get('url', '')
        logger.info(f"Mastodon: Posted successfully - {post_url}")
        return post_url
        
    except Exception as e:
        logger.error(f"Mastodon posting failed: {e}", exc_info=True)
        return None
