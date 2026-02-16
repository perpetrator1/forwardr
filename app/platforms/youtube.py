"""
YouTube posting via google-api-python-client.
"""
import logging
from pathlib import Path
from typing import Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _resolve_path(path_value: Optional[str], fallback: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    if not path_value:
        path_value = fallback
    path = Path(path_value)
    if not path.is_absolute():
        path = root / path
    return path


def _get_credentials(client_secrets_file: Optional[str], token_file: Optional[str]) -> Optional[Credentials]:
    token_path = _resolve_path(token_file, "youtube_token.json")
    creds: Optional[Credentials] = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:
                logger.error(f"Failed to refresh YouTube credentials: {exc}")
                creds = None
        if not creds:
            secrets_path = _resolve_path(client_secrets_file, "") if client_secrets_file else None
            if not secrets_path or not secrets_path.exists():
                logger.error("Missing YOUTUBE_CLIENT_SECRETS_FILE for OAuth flow")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), _SCOPES)
            creds = flow.run_local_server(port=0)

        try:
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json())
        except Exception as exc:
            logger.error(f"Failed to save YouTube token file: {exc}")

    return creds


def _split_title(caption: str) -> str:
    for line in caption.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return "Forwardr upload"


def post_to_youtube(media_info: Dict) -> bool:
    """
    Post content to YouTube.

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

    if not isinstance(media_info, dict):
        logger.error("media_info must be a dict")
        return False

    media_type = (media_info.get("type") or "text").lower()
    if media_type != "video":
        logger.info(f"Skipping unsupported media type for YouTube: {media_type}")
        return False

    local_path = media_info.get("local_path")
    if not local_path:
        logger.error("Video post missing local_path")
        return False

    path = Path(local_path)
    if not path.exists():
        logger.error(f"Video file not found: {local_path}")
        return False

    caption = media_info.get("caption") or ""
    title = _split_title(caption)
    description = caption

    try:
        creds = _get_credentials(settings.youtube.client_secrets_file, settings.youtube.token_file)
        if not creds:
            return False

        youtube = build("youtube", "v3", credentials=creds)

        media = MediaFileUpload(str(path), resumable=True)
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "categoryId": "22",
                },
                "status": {"privacyStatus": "public"},
            },
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logger.info(f"YouTube upload progress: {progress}%")

        if response and response.get("id"):
            logger.info(f"Successfully uploaded video to YouTube: {response['id']}")
            return True

        logger.error(f"YouTube upload failed: {response}")
        return False

    except Exception as exc:
        logger.error(f"Failed to post to YouTube: {exc}", exc_info=True)
        return False
