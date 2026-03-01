"""
Bluesky (AT Protocol) platform integration
"""
import logging
from typing import Dict, Optional
import httpx
from atproto import Client
from atproto_client.request import Request

logger = logging.getLogger(__name__)


def post(media_info: Dict) -> Optional[str]:
    """
    Post content to Bluesky
    
    Args:
        media_info: MediaInfo dictionary
        
    Returns:
        Post URL if successful, None if failed
    """
    try:
        from app.config import settings
        
        # Initialize Bluesky client with extended timeout for video uploads
        request = Request(timeout=httpx.Timeout(120.0, connect=30.0))
        client = Client(request=request)
        
        # Login with handle or username
        handle = settings.bluesky.handle or settings.bluesky.username
        if not handle or not settings.bluesky.password:
            logger.error("Bluesky: Missing credentials")
            return None
        
        logger.info(f"Bluesky: Logging in as {handle}")
        client.login(handle, settings.bluesky.password)
        
        # Get the text content
        text = media_info.get('caption', '')
        
        # Post with media if available
        if media_info['type'] == 'photo' and media_info.get('local_path'):
            logger.info(f"Bluesky: Uploading photo from {media_info['local_path']}")
            with open(media_info['local_path'], 'rb') as f:
                image_data = f.read()
            
            # Send post with image
            response = client.send_image(
                text=text,
                image=image_data,
                image_alt=text[:100] if text else "Image"  # Alt text from caption
            )
        elif media_info['type'] == 'video' and media_info.get('local_path'):
            logger.info(f"Bluesky: Uploading video from {media_info['local_path']}")
            with open(media_info['local_path'], 'rb') as f:
                video_data = f.read()
            
            # Build aspect ratio if dimensions are available
            video_aspect_ratio = None
            if media_info.get('width') and media_info.get('height'):
                from atproto import models
                video_aspect_ratio = models.AppBskyEmbedDefs.AspectRatio(
                    width=media_info['width'],
                    height=media_info['height'],
                )
            
            # Send post with video
            response = client.send_video(
                text=text,
                video=video_data,
                video_alt=text[:100] if text else "Video",
                video_aspect_ratio=video_aspect_ratio,
            )
        else:
            # Text-only post
            logger.info(f"Bluesky: Posting text: {text[:50]}...")
            response = client.send_post(text=text)
        
        # Construct post URL from response
        if response and hasattr(response, 'uri'):
            # Extract post ID from AT URI (at://did:plc:.../app.bsky.feed.post/...)
            uri_parts = response.uri.split('/')
            post_id = uri_parts[-1] if uri_parts else ''
            
            # Get user's handle from profile
            profile = client.get_profile(handle)
            user_handle = profile.handle if profile else handle
            
            post_url = f"https://bsky.app/profile/{user_handle}/post/{post_id}"
            logger.info(f"Bluesky: Posted successfully - {post_url}")
            return post_url
        
        logger.warning("Bluesky: Post succeeded but no URI returned")
        return "https://bsky.app"
        
    except Exception as e:
        logger.error(f"Bluesky posting failed: {e}", exc_info=True)
        return None
