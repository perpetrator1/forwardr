"""
Instagram platform integration via the official Graph API (for Professional accounts).

Requires:
    - An Instagram Professional (Business or Creator) account connected to a Facebook Page.
    - A Facebook App with ``instagram_basic``, ``instagram_content_publish``,
      and ``pages_read_engagement`` permissions.
    - ``INSTAGRAM_ACCESS_TOKEN`` and ``INSTAGRAM_BUSINESS_ACCOUNT_ID`` in ``.env``.

The publishing flow mirrors the container-based approach:
    1. Upload media to a public URL (via Cloudinary).
    2. Create a media container on the Instagram Graph API.
    3. (For videos/reels) Wait for the container to finish processing.
    4. Publish the container.

References:
    https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing
"""
import logging
import time
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.instagram.com/{GRAPH_API_VERSION}"

# Instagram caption limit
CAPTION_MAX_LENGTH = 2200

# Container processing poll settings
_POLL_INTERVAL = 5  # seconds
_POLL_TIMEOUT = 120  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upload_media_to_public_url(local_path: str) -> Optional[str]:
    """Upload a local file to Cloudinary and return its public URL.

    The Instagram Graph API requires media to be hosted at a publicly
    accessible URL. Cloudinary is used as the hosting provider.

    Args:
        local_path: Path to the local media file.

    Returns:
        Public URL of the uploaded media, or ``None`` on failure.
    """
    try:
        from app.utils.cloudinary_config import upload_media

        ext = local_path.rsplit(".", 1)[-1].lower()
        resource_type = "video" if ext in ("mp4", "mov", "avi", "mkv") else "image"
        return upload_media(local_path, resource_type=resource_type)
    except ImportError:
        logger.warning(
            "Instagram: Cloudinary not available — media upload skipped. "
            f"File: {local_path}"
        )
        return None
    except Exception as e:
        logger.error(f"Instagram: Media upload to Cloudinary failed: {e}")
        return None


def _create_media_container(
    account_id: str,
    access_token: str,
    caption: str,
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
) -> Optional[str]:
    """Create an Instagram media container.

    Args:
        account_id: Instagram Business/Creator account ID.
        access_token: Graph API access token.
        caption: Post caption text.
        image_url: Public URL of an image (for photo posts).
        video_url: Public URL of a video (for reel posts).

    Returns:
        Container (creation) ID on success, ``None`` on failure.
    """
    try:
        params: Dict[str, str] = {
            "access_token": access_token,
        }

        if caption:
            params["caption"] = caption[:CAPTION_MAX_LENGTH]

        if image_url:
            params["image_url"] = image_url
        elif video_url:
            params["video_url"] = video_url
            params["media_type"] = "REELS"
        else:
            # Instagram Graph API does not support text-only posts
            logger.error("Instagram: Graph API requires an image or video — text-only posts are not supported")
            return None

        resp = requests.post(
            f"{GRAPH_API_BASE}/{account_id}/media",
            data=params,
            timeout=30,
        )
        resp.raise_for_status()

        container_id = resp.json().get("id")
        if container_id:
            logger.info(f"Instagram: Created media container {container_id}")
            return container_id

        logger.error(f"Instagram: No container ID in response: {resp.json()}")
        return None

    except requests.exceptions.RequestException as e:
        _log_api_error("create media container", e)
        return None
    except Exception as e:
        logger.error(f"Instagram: Unexpected error creating container: {e}")
        return None


def _wait_for_container(account_id: str, access_token: str, container_id: str) -> bool:
    """Poll the container status until it is ``FINISHED`` or an error occurs.

    Args:
        account_id: Instagram Business/Creator account ID.
        access_token: Graph API access token.
        container_id: The creation ID returned by ``_create_media_container``.

    Returns:
        ``True`` if the container is ready for publishing, ``False`` otherwise.
    """
    elapsed = 0
    while elapsed < _POLL_TIMEOUT:
        try:
            resp = requests.get(
                f"{GRAPH_API_BASE}/{container_id}",
                params={
                    "access_token": access_token,
                    "fields": "status_code,status",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status_code", "")

            if status == "FINISHED":
                logger.info(f"Instagram: Container {container_id} is ready")
                return True

            if status in ("ERROR", "EXPIRED"):
                logger.error(
                    f"Instagram: Container processing failed — "
                    f"status={status}, detail={data.get('status', 'unknown')}"
                )
                return False

            logger.debug(f"Instagram: Container status={status}, waiting {_POLL_INTERVAL}s …")

        except Exception as e:
            logger.warning(f"Instagram: Error polling container status: {e}")

        time.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL

    logger.warning(
        f"Instagram: Container not FINISHED after {_POLL_TIMEOUT}s — attempting publish anyway"
    )
    return True


def _publish_container(
    account_id: str, access_token: str, container_id: str
) -> Optional[str]:
    """Publish a previously created media container.

    Args:
        account_id: Instagram Business/Creator account ID.
        access_token: Graph API access token.
        container_id: The creation ID to publish.

    Returns:
        The published media ID on success, ``None`` on failure.
    """
    try:
        resp = requests.post(
            f"{GRAPH_API_BASE}/{account_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": access_token,
            },
            timeout=30,
        )
        resp.raise_for_status()

        media_id = resp.json().get("id")
        if media_id:
            logger.info(f"Instagram: Published media {media_id}")
            return media_id

        logger.error(f"Instagram: No media ID in publish response: {resp.json()}")
        return None

    except requests.exceptions.RequestException as e:
        _log_api_error("publish container", e)
        return None
    except Exception as e:
        logger.error(f"Instagram: Unexpected error publishing: {e}")
        return None


def _get_permalink(access_token: str, media_id: str) -> Optional[str]:
    """Fetch the permalink for a published Instagram media post.

    Args:
        access_token: Graph API access token.
        media_id: Published media ID.

    Returns:
        Permalink URL, or ``None`` if unavailable.
    """
    try:
        resp = requests.get(
            f"{GRAPH_API_BASE}/{media_id}",
            params={"access_token": access_token, "fields": "permalink"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("permalink")
    except Exception as e:
        logger.warning(f"Instagram: Could not fetch permalink: {e}")
        return None


def _cleanup_cloudinary(media_url: str, is_video: bool = False) -> None:
    """Delete an uploaded file from Cloudinary after posting (best-effort)."""
    try:
        from app.utils.cloudinary_config import delete_media

        parts = media_url.split("/upload/")
        if len(parts) != 2:
            return
        # Strip version prefix (v1234567890/) and file extension
        path = "/".join(parts[1].split("/")[1:])
        public_id = path.rsplit(".", 1)[0]
        resource_type = "video" if is_video else "image"

        if delete_media(public_id, resource_type=resource_type):
            logger.info(f"Instagram: Cleaned up Cloudinary media: {public_id}")
        else:
            logger.warning(f"Instagram: Failed to clean up Cloudinary media: {public_id}")
    except Exception as e:
        logger.warning(f"Instagram: Cloudinary cleanup error (non-fatal): {e}")


def _log_api_error(action: str, exc: requests.exceptions.RequestException) -> None:
    """Log an Instagram Graph API error with as much detail as possible."""
    logger.error(f"Instagram: Failed to {action}: {exc}")
    if hasattr(exc, "response") and exc.response is not None:
        try:
            logger.error(f"Instagram API error: {exc.response.json()}")
        except ValueError:
            logger.error(f"Instagram API error: {exc.response.text}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def post(media_info: Dict) -> Optional[str]:
    """Post content to Instagram using the official Graph API.

    Supports:
        - Photo posts (single image with optional caption)
        - Reel posts (single video with optional caption)

    Args:
        media_info: MediaInfo dictionary with keys ``type``, ``caption``,
            and optionally ``local_path``.

    Returns:
        Permalink URL if successful, ``None`` if failed.

    Notes:
        - Instagram Graph API does **not** support text-only posts.
        - Images must be JPEG; max 8 MB.
        - Videos must be MP4; 3–60 s for feed, up to 15 min for Reels.
        - 2 200 character caption limit.
        - 25 API-published posts per 24 h.
        - Requires ``INSTAGRAM_ACCESS_TOKEN`` and
          ``INSTAGRAM_BUSINESS_ACCOUNT_ID`` in ``.env``.
    """
    try:
        from app.config import settings

        ig = settings.instagram
        if not ig.is_complete():
            missing = ig.get_missing_fields()
            logger.error(f"Instagram: Missing credentials — {', '.join(missing)}")
            return None

        access_token = ig.access_token
        account_id = ig.business_account_id

        # --- Prepare content -----------------------------------------------------
        caption = media_info.get("caption", "") or ""
        media_type = media_info.get("type", "text")
        local_path = media_info.get("local_path")

        if len(caption) > CAPTION_MAX_LENGTH:
            logger.warning(
                f"Instagram: Truncating caption from {len(caption)} to {CAPTION_MAX_LENGTH} chars"
            )
            caption = caption[: CAPTION_MAX_LENGTH - 3] + "..."

        # Instagram requires media — skip text-only posts
        if media_type == "text":
            logger.warning("Instagram: Skipping — Graph API requires an image or video")
            return None

        # Use pre-uploaded Cloudinary URL if available (from queue-time upload)
        cloudinary_url = media_info.get("cloudinary_url")

        if not local_path and not cloudinary_url:
            logger.warning("Instagram: Skipping — no local_path or cloudinary_url")
            return None

        logger.info(
            f"Instagram: Preparing to post {media_type} "
            f"({len(caption)} char caption)"
        )

        # --- Upload to public URL ------------------------------------------------
        image_url = video_url = None
        is_video = media_type == "video"

        # Reuse pre-uploaded Cloudinary URL, or upload now if not available
        public_url = cloudinary_url or _upload_media_to_public_url(local_path)
        if not public_url:
            logger.error("Instagram: Failed to get a public URL for media")
            return None

        if is_video:
            video_url = public_url
        else:
            image_url = public_url

        # --- Create → Wait → Publish --------------------------------------------
        container_id = _create_media_container(
            account_id, access_token, caption,
            image_url=image_url, video_url=video_url,
        )
        if not container_id:
            return None

        # Always poll for readiness (videos take longer but images can lag too)
        logger.info("Instagram: Waiting for container to be processed …")
        if not _wait_for_container(account_id, access_token, container_id):
            return None

        media_id = _publish_container(account_id, access_token, container_id)
        if not media_id:
            return None

        # --- Permalink -----------------------------------------------------------
        permalink = _get_permalink(access_token, media_id)
        if permalink:
            logger.info(f"Instagram: Posted successfully — {permalink}")
        else:
            permalink = f"https://www.instagram.com/p/{media_id}"
            logger.info(f"Instagram: Posted successfully — media_id={media_id}")

        # Cloudinary cleanup is handled by QueueManager._cleanup_completed_media()
        # Only clean up here if Instagram did its own upload (no pre-uploaded URL)
        if not cloudinary_url:
            _cleanup_cloudinary(public_url, is_video=is_video)

        return permalink

    except Exception as e:
        logger.error(f"Instagram posting failed: {e}", exc_info=True)
        return None
