"""Threads (Meta) platform integration via the official Graph API."""
import logging
import time
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

# Threads Graph API
GRAPH_API_VERSION = "v1.0"
GRAPH_API_BASE = f"https://graph.threads.net/{GRAPH_API_VERSION}"

# Cache the resolved numeric user ID so we only look it up once per process.
_cached_numeric_user_id: Optional[str] = None


def _resolve_user_id(user_id: str, access_token: str) -> Optional[str]:
    """Return a numeric Threads user ID, resolving via ``/me`` if necessary.

    The result is cached for the lifetime of the process so subsequent posts
    don't make an extra API call.
    """
    global _cached_numeric_user_id
    if _cached_numeric_user_id:
        return _cached_numeric_user_id

    if user_id.isdigit():
        _cached_numeric_user_id = user_id
        return user_id

    try:
        resp = requests.get(
            f"{GRAPH_API_BASE}/me",
            params={"access_token": access_token, "fields": "id,username"},
            timeout=15,
        )
        resp.raise_for_status()
        numeric_id = resp.json().get("id")
        if numeric_id:
            logger.info(f"Threads: Resolved '{user_id}' → numeric ID {numeric_id}")
            _cached_numeric_user_id = numeric_id
            return numeric_id
        logger.error(f"Threads: /me response missing 'id': {resp.json()}")
        return None
    except Exception as e:
        logger.error(f"Threads: Failed to resolve user ID '{user_id}': {e}")
        return None


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
        from app.utils.cloudinary_config import upload_media

        ext = local_path.rsplit('.', 1)[-1].lower()
        resource_type = 'video' if ext in ('mp4', 'mov', 'avi', 'mkv') else 'image'
        return upload_media(local_path, resource_type=resource_type)
    except ImportError:
        logger.warning(
            f"Threads: Cloudinary not available — media upload skipped. "
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
        data = {
            "media_type": "TEXT",
            "text": text[:500],
            "access_token": access_token,
        }
        if image_url:
            data.update(media_type="IMAGE", image_url=image_url)
        elif video_url:
            data.update(media_type="VIDEO", video_url=video_url)

        resp = requests.post(
            f"{GRAPH_API_BASE}/{user_id}/threads", data=data, timeout=30
        )
        resp.raise_for_status()

        container_id = resp.json().get("id")
        if container_id:
            logger.info(f"Threads: Created media container {container_id}")
            return container_id

        logger.error(f"Threads: No container ID in response: {resp.json()}")
        return None
    except requests.exceptions.RequestException as e:
        _log_api_error("create media container", e)
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
        resp = requests.post(
            f"{GRAPH_API_BASE}/{user_id}/threads_publish",
            data={"creation_id": container_id, "access_token": access_token},
            timeout=30,
        )
        resp.raise_for_status()

        post_id = resp.json().get("id")
        if post_id:
            logger.info(f"Threads: Published post {post_id}")
            return post_id

        logger.error(f"Threads: No post ID in response: {resp.json()}")
        return None
    except requests.exceptions.RequestException as e:
        _log_api_error("publish container", e)
        return None
    except Exception as e:
        logger.error(f"Threads: Unexpected error publishing: {e}")
        return None


def _log_api_error(action: str, exc: requests.exceptions.RequestException) -> None:
    """Log a Threads API error with as much detail as possible."""
    logger.error(f"Threads: Failed to {action}: {exc}")
    if hasattr(exc, 'response') and exc.response is not None:
        try:
            logger.error(f"Threads API error: {exc.response.json()}")
        except ValueError:
            logger.error(f"Threads API error: {exc.response.text}")


def _wait_for_container(user_id: str, access_token: str, container_id: str, timeout: int = 90) -> bool:
    """Poll the Threads container status until it's FINISHED, or timeout.

    Returns True if the container is ready (or status unknown), False on error.
    """
    for _ in range(timeout // 5):
        try:
            resp = requests.get(
                f"{GRAPH_API_BASE}/{container_id}",
                params={"access_token": access_token, "fields": "status,error_message"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "")
            if status == "FINISHED":
                logger.info(f"Threads: Container {container_id} is ready")
                return True
            if status in ("ERROR", "EXPIRED"):
                logger.error(
                    f"Threads: Container processing failed — status={status}, "
                    f"error={data.get('error_message', 'unknown')}"
                )
                return False
            logger.debug(f"Threads: Container status={status}, waiting 5s...")
            time.sleep(5)
        except Exception as e:
            logger.warning(f"Threads: Error polling container status: {e}")
            time.sleep(5)
    logger.warning(f"Threads: Container not FINISHED after {timeout}s, attempting publish anyway")
    return True


def _cleanup_cloudinary(media_url: str, is_video: bool = False) -> None:
    """Delete an uploaded file from Cloudinary after posting (best-effort)."""
    try:
        from app.utils.cloudinary_config import delete_media

        # URL format: https://res.cloudinary.com/.../upload/v123/threads/abc.jpg
        parts = media_url.split('/upload/')
        if len(parts) != 2:
            return
        # Strip version prefix (v1234567890/) and file extension
        path = '/'.join(parts[1].split('/')[1:])  # remove version segment
        public_id = path.rsplit('.', 1)[0]
        resource_type = 'video' if is_video else 'image'

        if delete_media(public_id, resource_type=resource_type):
            logger.info(f"Threads: Cleaned up Cloudinary media: {public_id}")
        else:
            logger.warning(f"Threads: Failed to clean up Cloudinary media: {public_id}")
    except Exception as e:
        logger.warning(f"Threads: Cloudinary cleanup error (non-fatal): {e}")


def post(media_info: Dict) -> Optional[str]:
    """Post content to Threads using the official Meta Graph API.

    Args:
        media_info: MediaInfo dictionary with keys ``type``, ``caption``,
            and optionally ``local_path``.

    Returns:
        Post URL if successful, ``None`` if failed.

    Notes:
        - 500-character limit per post.
        - 250 posts / 24 h rate limit.
        - Media must be publicly accessible (uploaded via Cloudinary).
        - Requires ``THREADS_ACCESS_TOKEN`` and ``THREADS_USER_ID`` in ``.env``.
    """
    try:
        from app.config import settings

        if not settings.threads.access_token or not settings.threads.user_id:
            logger.error("Threads: Missing credentials (access_token or user_id)")
            return None

        access_token = settings.threads.access_token
        user_id = _resolve_user_id(settings.threads.user_id, access_token)
        if not user_id:
            logger.error("Threads: Could not resolve numeric user ID")
            return None

        # --- Text ----------------------------------------------------------------
        text = media_info.get('caption', '') or ''
        media_type = media_info.get('type', 'text')
        local_path = media_info.get('local_path')
        # Only require text for text-only posts; media posts can have empty captions
        if not text and media_type == 'text' and not local_path:
            logger.error("Threads: No text content provided for text-only post")
            return None
        if len(text) > 500:
            logger.warning(f"Threads: Truncating text from {len(text)} to 500 chars")
            text = text[:497] + "..."

        logger.info(f"Threads: Preparing to post ({len(text)} chars)")

        # --- Media ---------------------------------------------------------------
        image_url = video_url = None

        if media_type == 'photo' and local_path:
            image_url = _upload_media_to_public_url(local_path)
            if not image_url:
                logger.warning("Threads: Media upload failed, falling back to text-only post")
                if not text:
                    logger.error("Threads: Cannot fall back to text-only — caption is empty")
                    return None
        elif media_type == 'video' and local_path:
            video_url = _upload_media_to_public_url(local_path)
            if not video_url:
                logger.warning("Threads: Media upload failed, falling back to text-only post")
                if not text:
                    logger.error("Threads: Cannot fall back to text-only — caption is empty")
                    return None

        # --- Create → (wait) → Publish ------------------------------------------
        container_id = _create_media_container(
            user_id, access_token, text,
            image_url=image_url, video_url=video_url,
        )
        if not container_id:
            return None

        if image_url or video_url:
            logger.info("Threads: Waiting for media to be processed by Threads...")
            _wait_for_container(user_id, access_token, container_id)

        post_id = _publish_container(user_id, access_token, container_id)
        if not post_id:
            return None

        post_url = f"https://www.threads.net/t/{post_id}"
        logger.info(f"Threads: Posted successfully — {post_url}")

        # --- Cleanup Cloudinary --------------------------------------------------
        if image_url:
            _cleanup_cloudinary(image_url, is_video=False)
        elif video_url:
            _cleanup_cloudinary(video_url, is_video=True)

        return post_url

    except Exception as e:
        logger.error(f"Threads posting failed: {e}", exc_info=True)
        return None
