"""
Instagram posting via instagrapi.
"""
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple

from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, LoginRequired, TwoFactorRequired

logger = logging.getLogger(__name__)

_client: Optional[Client] = None
_client_username: Optional[str] = None
_client_password: Optional[str] = None
_client_session_path: Optional[Path] = None


def _get_session_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    session_name = os.getenv("INSTAGRAM_SESSION_FILE", "instagram_session.json")
    session_path = Path(session_name)
    if not session_path.is_absolute():
        session_path = root / session_path
    session_path.parent.mkdir(parents=True, exist_ok=True)
    return session_path


def _get_client(username: str, password: str, session_path: Path) -> Client:
    global _client, _client_username, _client_password, _client_session_path

    if (
        _client is None
        or _client_username != username
        or _client_password != password
        or _client_session_path != session_path
    ):
        client = Client()

        if session_path.exists():
            try:
                client.load_settings(str(session_path))
            except Exception as exc:
                logger.warning(f"Failed to load Instagram session: {exc}")

        client.login(username, password)

        try:
            client.dump_settings(str(session_path))
        except Exception as exc:
            logger.warning(f"Failed to save Instagram session: {exc}")

        _client = client
        _client_username = username
        _client_password = password
        _client_session_path = session_path

    return _client


def _prepare_image(local_path: str) -> Tuple[Optional[Path], bool]:
    """Resize and crop image to fit Instagram requirements."""
    try:
        from PIL import Image
    except ImportError:
        logger.error("Pillow is required for image processing.")
        return None, False

    path = Path(local_path)
    if not path.exists():
        logger.error(f"Photo file not found: {local_path}")
        return None, False

    with Image.open(path) as image:
        image = image.convert("RGB")
        width, height = image.size

        min_ratio = 4 / 5
        max_ratio = 1.91

        ratio = width / height
        if ratio < min_ratio:
            target_height = int(width / min_ratio)
            if target_height < height:
                top = (height - target_height) // 2
                image = image.crop((0, top, width, top + target_height))
                width, height = image.size
        elif ratio > max_ratio:
            target_width = int(height * max_ratio)
            if target_width < width:
                left = (width - target_width) // 2
                image = image.crop((left, 0, left + target_width, height))
                width, height = image.size

        max_dim = max(width, height)
        min_dim = min(width, height)

        scale = 1.0
        if max_dim > 1080:
            scale = 1080 / max_dim
        elif min_dim < 320:
            scale = 320 / min_dim

        if scale != 1.0:
            new_size = (int(width * scale), int(height * scale))
            image = image.resize(new_size, Image.LANCZOS)

        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".jpg",
            prefix="ig_",
            dir=path.parent,
        )
        temp_path = Path(temp_file.name)
        temp_file.close()
        image.save(temp_path, format="JPEG", quality=95)

    return temp_path, True


def post_to_instagram(media_info: Dict) -> bool:
    """
    Post content to Instagram.

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

    username = settings.instagram.username
    password = settings.instagram.password

    if not username or not password:
        logger.error("Instagram credentials missing. Check INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD.")
        return False

    if not isinstance(media_info, dict):
        logger.error("media_info must be a dict")
        return False

    media_type = (media_info.get("type") or "text").lower()
    caption = media_info.get("caption") or ""
    local_path = media_info.get("local_path")

    if media_type not in {"photo", "video"}:
        logger.info(f"Skipping unsupported media type for Instagram: {media_type}")
        return False

    try:
        session_path = _get_session_path()
        client = _get_client(username, password, session_path)

        if media_type == "photo":
            if not local_path:
                logger.error("Photo post missing local_path")
                return False

            processed_path, should_delete = _prepare_image(local_path)
            if not processed_path:
                return False

            try:
                client.photo_upload(str(processed_path), caption=caption)
                logger.info(f"Successfully posted photo to Instagram: {processed_path}")
            finally:
                if should_delete:
                    try:
                        processed_path.unlink()
                    except Exception:
                        logger.warning(f"Failed to delete temp image: {processed_path}")
            return True

        if media_type == "video":
            if not local_path:
                logger.error("Video post missing local_path")
                return False

            path = Path(local_path)
            if not path.exists():
                logger.error(f"Video file not found: {local_path}")
                return False

            client.clip_upload(str(path), caption=caption)
            logger.info(f"Successfully posted video to Instagram: {local_path}")
            return True

        return False

    except ChallengeRequired as exc:
        logger.error(
            "Instagram login challenge required. "
            "Please complete the challenge in the app and try again.",
            exc_info=True,
        )
        return False
    except TwoFactorRequired:
        logger.error(
            "Instagram login requires two-factor authentication. "
            "Please disable or provide a session file.",
            exc_info=True,
        )
        return False
    except LoginRequired:
        logger.error("Instagram login failed. Check credentials.", exc_info=True)
        return False
    except Exception as exc:
        logger.error(f"Failed to post to Instagram: {exc}", exc_info=True)
        return False
