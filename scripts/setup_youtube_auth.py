"""
One-time OAuth flow for YouTube uploads.
"""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _resolve_path(path_value: str | None, fallback: str) -> Path:
    root = Path(__file__).resolve().parent.parent
    if not path_value:
        path_value = fallback
    path = Path(path_value)
    if not path.is_absolute():
        path = root / path
    return path


def main() -> None:
    from app.config import settings

    secrets_path = _resolve_path(settings.youtube.client_secrets_file, "")
    if not secrets_path.exists():
        raise FileNotFoundError("YOUTUBE_CLIENT_SECRETS_FILE not found")

    token_path = _resolve_path(settings.youtube.token_file, "youtube_token.json")
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), _SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())

    print("YouTube auth complete")


if __name__ == "__main__":
    main()
