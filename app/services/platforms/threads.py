import logging
import time
from typing import Dict, Optional
import requests

logger = logging.getLogger(__name__)

# Meta Graph API endpoints for Threads
GRAPH_API_VERSION = "v18.0"
GRAPH_API_BASE = f"https://graph.threads.net/{GRAPH_API_VERSION}"


def _upload_media_to_public_url(local_path: str) -> Optional[str]:
    """
    Upload media to a public URL so Threads can access it.
    
    Note: Threads API requires media to be publicly accessible.
    This function uses Cloudinary if configured, otherwise returns None.
    
    Args:
        local_path: Local file path
        
    Returns:
        Public URL of the media, or None if upload failed
    """
    try:
        # Try to use Cloudinary helper if available
        try:
            from app.utils.cloudinary_config import upload_media
            
            # Determine resource type from file extension
            ext = local_path.lower().split('.')[-1]
            resource_type = 'video' if ext in ['mp4', 'mov', 'avi', 'mkv'] else 'image'
            
            public_url = upload_media(local_path, resource_type=resource_type)
            if public_url:
                return public_url
        except ImportError:
            pass
        
        # If Cloudinary is not configured, log warning
        logger.warning(
            f"Threads: Media upload not configured. "
            f"Configure Cloudinary to post media. "
            f"File: {local_path}"
        )
        return None
        
    except Exception as e:
        logger.error(f"Threads: Media upload failed: {e}")
        return None


def _create_media_container(
    user_id: str,
    access_token: str,
    text: str,
    image_url: Optional[str] = None,
    video_url: Optional[str] = None
) -> Optional[str]:
    """
    Create a Threads media container
    
    Args:
        user_id: Threads user ID
        access_token: Access token
        text: Post text/caption
        image_url: Public URL of image (optional)
        video_url: Public URL of video (optional)
        
    Returns:
        Container ID if successful, None otherwise
    """
    try:
        url = f"{GRAPH_API_BASE}/{user_id}/threads"
        
        # Build request data
        data = {
            "media_type": "TEXT",
            "text": text[:500],  # Threads has a 500 character limit
            "access_token": access_token
        }
        
        # Add media if provided
        if image_url:
            data["media_type"] = "IMAGE"
            data["image_url"] = image_url
        elif video_url:
            data["media_type"] = "VIDEO"
            data["video_url"] = video_url
        
        # Create container
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        container_id = result.get("id")
        
        if container_id:
            logger.info(f"Threads: Created media container {container_id}")
            return container_id
        else:
            logger.error(f"Threads: No container ID in response: {result}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Threads: Failed to create media container: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                logger.error(f"Threads API error: {error_data}")
            except:
                logger.error(f"Threads API error: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Threads: Unexpected error creating container: {e}")
        return None


def _publish_container(
    user_id: str,
    access_token: str,
    container_id: str
) -> Optional[str]:
    """
    Publish a Threads media container
    
    Args:
        user_id: Threads user ID
        access_token: Access token
        container_id: Container ID from _create_media_container
        
    Returns:
        Post ID if successful, None otherwise
    """
    try:
        url = f"{GRAPH_API_BASE}/{user_id}/threads_publish"
        
        data = {
            "creation_id": container_id,
            "access_token": access_token
        }
        
        # Publish the container
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        post_id = result.get("id")
        
        if post_id:
            logger.info(f"Threads: Published post {post_id}")
            return post_id
        else:
            logger.error(f"Threads: No post ID in response: {result}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Threads: Failed to publish container: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                logger.error(f"Threads API error: {error_data}")
            except:
                logger.error(f"Threads API error: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Threads: Unexpected error publishing: {e}")
        return None


def post(media_info: Dict) -> Optional[str]:
    """
    Post content to Threads using the official Meta Graph API
    
    Args:
        media_info: MediaInfo dictionary containing:
            - type: 'photo', 'video', 'text', etc.
            - caption: Text content to post
            - local_path: Path to media file (optional)
            
    Returns:
        Post URL if successful, None if failed
        
    Notes:
        - Threads has a 500 character limit
        - Rate limit: 250 posts per 24 hours
        - Media must be publicly accessible via URL
        - Requires THREADS_ACCESS_TOKEN and THREADS_USER_ID in .env
    """
    try:
        from app.config import settings
        
        # Check credentials
        if not settings.threads.access_token or not settings.threads.user_id:
            logger.error("Threads: Missing credentials (access_token or user_id)")
            return None
        
        access_token = settings.threads.access_token
        user_id = settings.threads.user_id
        
        # Get text content (truncate to 500 chars)
        text = media_info.get('caption', '')
        if not text:
            logger.error("Threads: No text content provided")
            return None
        
        if len(text) > 500:
            logger.warning(f"Threads: Truncating text from {len(text)} to 500 characters")
            text = text[:497] + "..."
        
        logger.info(f"Threads: Preparing to post ({len(text)} chars)")
        
        # Handle media if present
        image_url = None
        video_url = None
        
        if media_info['type'] == 'photo' and media_info.get('local_path'):
            logger.info(f"Threads: Uploading photo from {media_info['local_path']}")
            image_url = _upload_media_to_public_url(media_info['local_path'])
            if not image_url:
                logger.warning("Threads: Continuing with text-only post (media upload not configured)")
        
        elif media_info['type'] == 'video' and media_info.get('local_path'):
            logger.info(f"Threads: Uploading video from {media_info['local_path']}")
            video_url = _upload_media_to_public_url(media_info['local_path'])
            if not video_url:
                logger.warning("Threads: Continuing with text-only post (media upload not configured)")
        
        # Step 1: Create media container
        container_id = _create_media_container(
            user_id=user_id,
            access_token=access_token,
            text=text,
            image_url=image_url,
            video_url=video_url
        )
        
        if not container_id:
            logger.error("Threads: Failed to create media container")
            return None
        
        # Step 2: Wait a moment (recommended by Meta for media processing)
        if image_url or video_url:
            logger.info("Threads: Waiting for media processing...")
            time.sleep(2)
        
        # Step 3: Publish the container
        post_id = _publish_container(
            user_id=user_id,
            access_token=access_token,
            container_id=container_id
        )
        
        if not post_id:
            logger.error("Threads: Failed to publish container")
            return None
        
        # Construct post URL
        post_url = f"https://www.threads.net/t/{post_id}"
        logger.info(f"Threads: Posted successfully - {post_url}")
        
        return post_url
        
    except Exception as e:
        logger.error(f"Threads posting failed: {e}", exc_info=True)
        return None
