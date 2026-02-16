"""
Telegram channel posting via Bot API using requests.
"""
import logging
from pathlib import Path
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)


def _send_telegram_request(
    method: str,
    token: str,
    data: Dict[str, str],
    files: Optional[Dict[str, object]] = None,
) -> bool:
    url = f"https://api.telegram.org/bot{token}/{method}"

    try:
        response = requests.post(url, data=data, files=files, timeout=30)
    except requests.RequestException as exc:
        logger.error(f"Telegram API request failed: {exc}")
        return False

    try:
        payload = response.json()
    except ValueError:
        logger.error(
            "Telegram API returned non-JSON response: "
            f"status={response.status_code} body={response.text}"
        )
        return False

    if not payload.get("ok"):
        description = payload.get("description") or "Unknown Telegram API error"
        logger.error(f"Telegram API error: {description}")
        return False

    return True


def post_to_telegram_channel(media_info: Dict) -> bool:
    """
    Post content to a Telegram channel using the Bot API.

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

    bot_token = settings.telegram.bot_token
    chat_id = settings.telegram.chat_id

    if not bot_token or not chat_id:
        logger.error("Telegram credentials missing. Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
        return False

    if not isinstance(media_info, dict):
        logger.error("media_info must be a dict")
        return False

    media_type = (media_info.get("type") or "text").lower()
    caption = media_info.get("caption") or ""
    local_path = media_info.get("local_path")

    if media_type == "text":
        text = media_info.get("text") or caption
        if not text:
            logger.error("Text post missing content")
            return False
        data = {"chat_id": chat_id, "text": text}
        return _send_telegram_request("sendMessage", bot_token, data)

    if media_type in {"photo", "video", "document"}:
        if not local_path:
            logger.error(f"{media_type} post missing local_path")
            return False

        path = Path(local_path)
        if not path.exists():
            logger.error(f"{media_type} file not found: {local_path}")
            return False

        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption

        method_map = {
            "photo": "sendPhoto",
            "video": "sendVideo",
            "document": "sendDocument",
        }
        file_field_map = {
            "photo": "photo",
            "video": "video",
            "document": "document",
        }

        method = method_map[media_type]
        file_field = file_field_map[media_type]

        with path.open("rb") as file_handle:
            files = {file_field: file_handle}
            return _send_telegram_request(method, bot_token, data, files)

    logger.error(f"Unsupported media type for Telegram: {media_type}")
    return False
