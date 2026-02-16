"""
Threads (Meta) posting via Graph API.
"""
import base64
import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

_API_BASE_URL = "https://graph.facebook.com/v19.0"


def _threads_request(
    method: str,
    path: str,
    access_token: str,
    params: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, str]] = None,
) -> Optional[Dict]:
    url = f"{_API_BASE_URL}{path}"
    params = params or {}
    data = data or {}

    if method.upper() == "GET":
        params.setdefault("access_token", access_token)
    else:
        data.setdefault("access_token", access_token)

    try:
        response = requests.request(method, url, params=params, data=data, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error(f"Threads API request failed: {exc}")
        return None

    try:
        payload = response.json()
    except ValueError:
        logger.error(
            "Threads API returned non-JSON response: "
            f"status={response.status_code} body={response.text}"
        )
        return None

    if "error" in payload:
        logger.error(f"Threads API error: {payload['error']}")
        return None

    return payload


def _upload_image_to_imgbb(local_path: str) -> Optional[str]:
    api_key = os.getenv("IMGBB_API_KEY")
    if not api_key:
        logger.error(
            "IMGBB_API_KEY is not set. Upload the image to a public host "
            "(Cloudflare R2 or ImgBB) and pass media_info['public_url']."
        )
        return None

    path = Path(local_path)
    if not path.exists():
        logger.error(f"Photo file not found: {local_path}")
        return None

    with path.open("rb") as file_handle:
        encoded = base64.b64encode(file_handle.read()).decode("ascii")

    try:
        response = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": api_key, "image": encoded},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error(f"ImgBB upload failed: {exc}")
        return None

    try:
        payload = response.json()
    except ValueError:
        logger.error("ImgBB returned non-JSON response")
        return None

    if not payload.get("success"):
        logger.error(f"ImgBB upload error: {payload}")
        return None

    data = payload.get("data") or {}
    return data.get("url") or data.get("display_url")


def _get_public_image_url(media_info: Dict) -> Optional[str]:
    public_url = media_info.get("public_url") or media_info.get("image_url") or media_info.get("url")
    if public_url:
        return public_url

    local_path = media_info.get("local_path")
    if not local_path:
        logger.error("Photo post missing public_url or local_path")
        return None

    # Threads requires a publicly accessible URL; it does not accept direct file uploads.
    return _upload_image_to_imgbb(local_path)


def _wait_for_container(access_token: str, creation_id: str) -> bool:
    for attempt in range(1, 11):
        payload = _threads_request(
            "GET",
            f"/{creation_id}",
            access_token,
            params={"fields": "status"},
        )
        if not payload:
            return False

        status = (payload.get("status") or "").upper()
        if status == "FINISHED":
            return True
        if status in {"ERROR", "FAILED"}:
            logger.error(f"Threads container failed with status: {status}")
            return False

        logger.info(f"Threads container status {status or 'PENDING'} (attempt {attempt}/10)")
        time.sleep(5)

    logger.error("Threads container did not become ready in time")
    return False


def _publish_container(access_token: str, user_id: str, creation_id: str) -> bool:
    payload = _threads_request(
        "POST",
        f"/{user_id}/threads_publish",
        access_token,
        data={"creation_id": creation_id},
    )
    if not payload:
        return False

    if not payload.get("id"):
        logger.error(f"Threads publish failed: {payload}")
        return False

    return True


def post_to_threads(media_info: Dict) -> bool:
    """
    Post content to Threads.

    Args:
        media_info: Dict with keys like type, caption, local_path, public_url

    Returns:
        True if post succeeded, False otherwise
    """
    try:
        from app.config import settings
    except Exception as exc:
        logger.error(f"Failed to load app settings: {exc}")
        return False

    access_token = settings.threads.access_token
    user_id = settings.threads.user_id

    if not access_token or not user_id:
        logger.error("Threads credentials missing. Check THREADS_ACCESS_TOKEN and THREADS_USER_ID.")
        return False

    if not isinstance(media_info, dict):
        logger.error("media_info must be a dict")
        return False

    media_type = (media_info.get("type") or "text").lower()
    caption = media_info.get("caption") or ""

    if media_type == "text":
        text = media_info.get("text") or caption
        if not text:
            logger.error("Text post missing content")
            return False

        payload = _threads_request(
            "POST",
            f"/{user_id}/threads",
            access_token,
            data={"media_type": "TEXT", "text": text},
        )
        if not payload or not payload.get("id"):
            logger.error(f"Threads create container failed: {payload}")
            return False

        creation_id = payload["id"]
        if not _wait_for_container(access_token, creation_id):
            return False

        if not _publish_container(access_token, user_id, creation_id):
            return False

        logger.info("Successfully posted text to Threads")
        return True

    if media_type == "photo":
        public_url = _get_public_image_url(media_info)
        if not public_url:
            return False

        payload = _threads_request(
            "POST",
            f"/{user_id}/threads",
            access_token,
            data={"media_type": "IMAGE", "image_url": public_url, "text": caption},
        )
        if not payload or not payload.get("id"):
            logger.error(f"Threads create container failed: {payload}")
            return False

        creation_id = payload["id"]
        if not _wait_for_container(access_token, creation_id):
            return False

        if not _publish_container(access_token, user_id, creation_id):
            return False

        logger.info("Successfully posted photo to Threads")
        return True

    if media_type == "video":
        public_url = media_info.get("public_url") or media_info.get("video_url") or media_info.get("url")
        if not public_url:
            logger.error(
                "Video post requires a public URL. Upload the video to a public host "
                "and pass media_info['public_url']."
            )
            return False

        payload = _threads_request(
            "POST",
            f"/{user_id}/threads",
            access_token,
            data={"media_type": "VIDEO", "video_url": public_url, "text": caption},
        )
        if not payload or not payload.get("id"):
            logger.error(f"Threads create container failed: {payload}")
            return False

        creation_id = payload["id"]
        if not _wait_for_container(access_token, creation_id):
            return False

        if not _publish_container(access_token, user_id, creation_id):
            return False

        logger.info("Successfully posted video to Threads")
        return True

    logger.info(f"Skipping unsupported media type for Threads: {media_type}")
    return False
