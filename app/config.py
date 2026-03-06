"""
Configuration management using Pydantic Settings.

Credentials are resolved in this order (higher wins):
1. Environment variables / .env file
2. Cloudflare Worker KV (fetched via CLOUDFLARE_WORKER_URL/credentials)
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import logging

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)


# Core Settings
class CoreSettings(BaseSettings):
    """Core application settings"""
    model_config = SettingsConfigDict(env_prefix="")
    
    # Database
    database_url: str = Field(default="sqlite+aiosqlite:///./forwardr.db")
    
    # API
    api_key: str = Field(default="")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    
    # Paths
    media_path: str = Field(default="./media")
    logs_path: str = Field(default="./logs")
    
    # Scheduling
    check_interval_seconds: int = Field(default=60)


# Platform Settings
class TelegramSettings(BaseSettings):
    """Telegram platform configuration"""
    model_config = SettingsConfigDict(env_prefix="TELEGRAM_")
    
    bot_token: Optional[str] = Field(default=None)
    chat_id: Optional[str] = Field(default=None)
    owner_id: Optional[str] = Field(default=None)
    
    def is_complete(self) -> bool:
        """Check if all required credentials are present"""
        return bool(self.bot_token and self.chat_id)
    
    def get_missing_fields(self) -> List[str]:
        """Return list of missing required fields"""
        missing = []
        if not self.bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        return missing


class BlueskySettings(BaseSettings):
    """Bluesky (AT Protocol) configuration"""
    model_config = SettingsConfigDict(env_prefix="BLUESKY_")
    
    username: Optional[str] = Field(default=None)
    handle: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    
    def is_complete(self) -> bool:
        """Check if all required credentials are present"""
        return bool((self.username or self.handle) and self.password)
    
    def get_missing_fields(self) -> List[str]:
        """Return list of missing required fields"""
        missing = []
        if not (self.username or self.handle):
            missing.append("BLUESKY_USERNAME")
        if not self.password:
            missing.append("BLUESKY_PASSWORD")
        return missing


class MastodonSettings(BaseSettings):
    """Mastodon configuration"""
    model_config = SettingsConfigDict(env_prefix="MASTODON_")
    
    instance_url: Optional[str] = Field(default=None)
    access_token: Optional[str] = Field(default=None)
    
    def is_complete(self) -> bool:
        """Check if all required credentials are present"""
        return bool(self.instance_url and self.access_token)
    
    def get_missing_fields(self) -> List[str]:
        """Return list of missing required fields"""
        missing = []
        if not self.instance_url:
            missing.append("MASTODON_INSTANCE_URL")
        if not self.access_token:
            missing.append("MASTODON_ACCESS_TOKEN")
        return missing


class InstagramSettings(BaseSettings):
    """Instagram configuration (Graph API for Professional accounts)"""
    model_config = SettingsConfigDict(env_prefix="INSTAGRAM_")
    
    access_token: Optional[str] = Field(default=None)
    business_account_id: Optional[str] = Field(default=None)
    
    def is_complete(self) -> bool:
        """Check if all required credentials are present"""
        return bool(self.access_token and self.business_account_id)
    
    def get_missing_fields(self) -> List[str]:
        """Return list of missing required fields"""
        missing = []
        if not self.access_token:
            missing.append("INSTAGRAM_ACCESS_TOKEN")
        if not self.business_account_id:
            missing.append("INSTAGRAM_BUSINESS_ACCOUNT_ID")
        return missing


class ThreadsSettings(BaseSettings):
    """Threads (Meta) configuration"""
    model_config = SettingsConfigDict(env_prefix="THREADS_")

    access_token: Optional[str] = Field(default=None)
    user_id: Optional[str] = Field(default=None)

    def is_complete(self) -> bool:
        """Check if all required credentials are present"""
        return bool(self.access_token and self.user_id)

    def get_missing_fields(self) -> List[str]:
        """Return list of missing required fields"""
        missing = []
        if not self.access_token:
            missing.append("THREADS_ACCESS_TOKEN")
        if not self.user_id:
            missing.append("THREADS_USER_ID")
        return missing


class TwitterSettings(BaseSettings):
    """Twitter/X configuration"""
    model_config = SettingsConfigDict(env_prefix="TWITTER_")
    
    api_key: Optional[str] = Field(default=None)
    api_secret: Optional[str] = Field(default=None)
    access_token: Optional[str] = Field(default=None)
    access_token_secret: Optional[str] = Field(default=None)
    bearer_token: Optional[str] = Field(default=None)
    
    def is_complete(self) -> bool:
        """Check if all required credentials are present"""
        return bool(
            self.api_key and 
            self.api_secret and 
            self.access_token and 
            self.access_token_secret
        )
    
    def get_missing_fields(self) -> List[str]:
        """Return list of missing required fields"""
        missing = []
        if not self.api_key:
            missing.append("TWITTER_API_KEY")
        if not self.api_secret:
            missing.append("TWITTER_API_SECRET")
        if not self.access_token:
            missing.append("TWITTER_ACCESS_TOKEN")
        if not self.access_token_secret:
            missing.append("TWITTER_ACCESS_TOKEN_SECRET")
        return missing


class RedditSettings(BaseSettings):
    """Reddit configuration"""
    model_config = SettingsConfigDict(env_prefix="REDDIT_")
    
    client_id: Optional[str] = Field(default=None)
    client_secret: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default="forwardr/1.0")
    subreddit: Optional[str] = Field(default=None)
    default_title: str = Field(default="Forwardr update")
    
    def is_complete(self) -> bool:
        """Check if all required credentials are present"""
        return bool(
            self.client_id and 
            self.client_secret and 
            self.username and 
            self.password and
            self.subreddit
        )
    
    def get_missing_fields(self) -> List[str]:
        """Return list of missing required fields"""
        missing = []
        if not self.client_id:
            missing.append("REDDIT_CLIENT_ID")
        if not self.client_secret:
            missing.append("REDDIT_CLIENT_SECRET")
        if not self.username:
            missing.append("REDDIT_USERNAME")
        if not self.password:
            missing.append("REDDIT_PASSWORD")
        if not self.subreddit:
            missing.append("REDDIT_SUBREDDIT")
        return missing


class YouTubeSettings(BaseSettings):
    """YouTube configuration"""
    model_config = SettingsConfigDict(env_prefix="YOUTUBE_")
    
    client_secrets_file: Optional[str] = Field(default=None)
    token_file: Optional[str] = Field(default=None)
    
    def is_complete(self) -> bool:
        """Check if all required credentials are present"""
        return bool(self.client_secrets_file)
    
    def get_missing_fields(self) -> List[str]:
        """Return list of missing required fields"""
        missing = []
        if not self.client_secrets_file:
            missing.append("YOUTUBE_CLIENT_SECRETS_FILE")
        return missing


# ---------------------------------------------------------------------------
# KV credential fetching
# ---------------------------------------------------------------------------

# Maps KV key names → Pydantic field names for each platform.
# KV stores e.g. cred:bluesky:handle → value  and the Pydantic field is `handle`.
_KV_FIELD_MAP: Dict[str, Dict[str, str]] = {
    "telegram": {"bot_token": "bot_token", "chat_id": "chat_id"},
    "bluesky": {"handle": "handle", "password": "password", "username": "username"},
    "mastodon": {"instance_url": "instance_url", "access_token": "access_token"},
    "instagram": {"access_token": "access_token", "business_account_id": "business_account_id"},
    "threads": {"access_token": "access_token", "user_id": "user_id"},
    "twitter": {
        "api_key": "api_key", "api_secret": "api_secret",
        "access_token": "access_token", "access_token_secret": "access_token_secret",
        "bearer_token": "bearer_token",
    },
    "reddit": {
        "client_id": "client_id", "client_secret": "client_secret",
        "username": "username", "password": "password",
        "user_agent": "user_agent", "subreddit": "subreddit",
        "default_title": "default_title",
    },
    "youtube": {"client_secrets_file": "client_secrets_file", "token_file": "token_file"},
}


def _kv_fetch_params():
    """Return (url, headers) for the KV credentials endpoint, or (None, None) if not configured."""
    if os.getenv("FORWARDR_SKIP_KV_FETCH", ""):
        return None, None
    worker_url = os.getenv("CLOUDFLARE_WORKER_URL", "").rstrip("/")
    api_key = os.getenv("API_SECRET_KEY", "")
    if not worker_url or not api_key:
        logger.debug("No CLOUDFLARE_WORKER_URL or API_SECRET_KEY — skipping KV fetch")
        return None, None
    return f"{worker_url}/credentials", {"X-API-Key": api_key}


_KV_TIMEOUT = 15          # seconds — Render free-tier outbound can be slow
_KV_RETRIES = 2           # total attempts
_KV_RETRY_DELAY = 2       # seconds between retries


def _fetch_kv_credentials() -> Dict[str, Dict[str, str]]:
    """
    Fetch credentials from the Cloudflare Worker /credentials endpoint.
    Returns {platform: {key: value}} or empty dict on failure.

    Set FORWARDR_SKIP_KV_FETCH=1 in tests to skip the network call.
    """
    url, headers = _kv_fetch_params()
    if not url:
        return {}

    if httpx is None:
        logger.debug("httpx not installed — skipping KV credential fetch")
        return {}

    import time as _time
    last_err = None
    for attempt in range(1, _KV_RETRIES + 1):
        try:
            logger.info(f"KV fetch attempt {attempt}/{_KV_RETRIES} → {url}")
            resp = httpx.get(url, headers=headers, timeout=_KV_TIMEOUT)
            if resp.status_code != 200:
                logger.warning(f"KV credential fetch returned {resp.status_code}")
                last_err = f"HTTP {resp.status_code}"
            else:
                logger.info("KV credentials fetched successfully")
                return resp.json()
        except Exception as e:
            last_err = e
            logger.warning(f"KV fetch attempt {attempt} failed: {e}")
        if attempt < _KV_RETRIES:
            _time.sleep(_KV_RETRY_DELAY)

    logger.warning(f"All KV fetch attempts failed. Last error: {last_err}")
    return {}


async def _fetch_kv_credentials_async() -> Dict[str, Dict[str, str]]:
    """
    Async variant of _fetch_kv_credentials — used inside async webhook processing
    so it doesn't block the event loop.
    """
    url, headers = _kv_fetch_params()
    if not url:
        return {}

    if httpx is None:
        logger.debug("httpx not installed — skipping async KV credential fetch")
        return {}

    import asyncio
    last_err = None
    for attempt in range(1, _KV_RETRIES + 1):
        try:
            logger.info(f"Async KV fetch attempt {attempt}/{_KV_RETRIES} → {url}")
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=_KV_TIMEOUT)
            if resp.status_code != 200:
                logger.warning(f"KV credential fetch returned {resp.status_code}")
                last_err = f"HTTP {resp.status_code}"
            else:
                logger.info("KV credentials fetched successfully (async)")
                return resp.json()
        except Exception as e:
            last_err = e
            logger.warning(f"Async KV fetch attempt {attempt} failed: {e}")
        if attempt < _KV_RETRIES:
            await asyncio.sleep(_KV_RETRY_DELAY)

    logger.warning(f"All async KV fetch attempts failed. Last error: {last_err}")
    return {}


# Maps KV cloudinary keys → environment variable names
_CLOUDINARY_ENV_MAP = {
    "cloud_name": "CLOUDINARY_CLOUD_NAME",
    "api_key": "CLOUDINARY_API_KEY",
    "api_secret": "CLOUDINARY_API_SECRET",
}


def _inject_cloudinary_from_kv(kv_creds: Dict) -> None:
    """Set Cloudinary env vars from KV so cloudinary_config.py can read them."""
    cloud_kv = kv_creds.get("cloudinary", {})
    if not cloud_kv:
        return
    injected = []
    for kv_key, env_var in _CLOUDINARY_ENV_MAP.items():
        value = cloud_kv.get(kv_key)
        if value and not os.getenv(env_var):
            os.environ[env_var] = value
            injected.append(env_var)
    if injected:
        logger.info(f"Injected Cloudinary env vars from KV: {', '.join(injected)}")
        # Re-configure Cloudinary so it picks up the new env vars
        try:
            from app.utils.cloudinary_config import configure_cloudinary
            configure_cloudinary()
        except Exception as e:
            logger.warning(f"Cloudinary re-configuration failed: {e}")


def _merge_kv_into_settings(platform_obj: Any, kv_creds: Dict[str, str], field_map: Dict[str, str]) -> None:
    """
    For each key in kv_creds, if the corresponding Pydantic field is
    currently empty/None, set it from KV.  Env vars always win.
    """
    for kv_key, field_name in field_map.items():
        kv_value = kv_creds.get(kv_key)
        if not kv_value:
            continue
        current = getattr(platform_obj, field_name, None)
        if not current:  # Only fill if env didn't already set it
            setattr(platform_obj, field_name, kv_value)
            logger.debug(f"Set {field_name} from KV")


# ---------------------------------------------------------------------------
# Main Settings Class
# ---------------------------------------------------------------------------

class Settings:
    """Main settings container with platform validation"""
    
    def __init__(self):
        # Initialize core settings
        self.core = CoreSettings()
        
        # Initialize platform settings (from env/.env)
        self.telegram = TelegramSettings()
        self.bluesky = BlueskySettings()
        self.mastodon = MastodonSettings()
        self.instagram = InstagramSettings()
        self.threads = ThreadsSettings()
        self.twitter = TwitterSettings()
        self.reddit = RedditSettings()
        self.youtube = YouTubeSettings()
        
        # Platform registry
        self._platforms = {
            "telegram": self.telegram,
            "bluesky": self.bluesky,
            "mastodon": self.mastodon,
            "instagram": self.instagram,
            "threads": self.threads,
            "twitter": self.twitter,
            "reddit": self.reddit,
            "youtube": self.youtube,
        }
        
        # Scheduling
        self.post_interval_hours: float = 5.0  # default; overridden by KV config
        
        # Merge in credentials from Cloudflare KV (env vars take precedence)
        self._merge_kv_credentials()
        
        # Validate and set enabled platforms
        self.enabled_platforms = self._validate_platforms()
    
    def _merge_kv_credentials(self) -> None:
        """Fetch credentials from CF Worker KV and fill in any blanks."""
        kv_creds = _fetch_kv_credentials()
        if not kv_creds:
            return
        
        # Extract config section (added by CF Worker alongside credentials)
        config = kv_creds.pop("_config", {})
        if config:
            interval = config.get("post_interval_hours")
            if interval is not None:
                self.post_interval_hours = float(interval)
                logger.info(f"Post interval from KV: {self.post_interval_hours} hours")
        
        logger.info(f"Merging KV credentials for platforms: {', '.join(kv_creds.keys())}")
        
        for platform_name, platform_obj in self._platforms.items():
            platform_kv = kv_creds.get(platform_name, {})
            field_map = _KV_FIELD_MAP.get(platform_name, {})
            if platform_kv and field_map:
                _merge_kv_into_settings(platform_obj, platform_kv, field_map)
        
        # Cloudinary has no Pydantic model — inject into os.environ
        _inject_cloudinary_from_kv(kv_creds)
    
    def _validate_platforms(self) -> List[str]:
        """
        Validate platform credentials and return list of enabled platforms.
        Logs warnings for platforms with missing credentials.
        """
        enabled = []
        
        for platform_name, platform_config in self._platforms.items():
            if platform_config.is_complete():
                enabled.append(platform_name)
                logger.info(f"{platform_name.capitalize()} platform enabled")
            else:
                missing = platform_config.get_missing_fields()
                logger.warning(
                    f"{platform_name.capitalize()} platform disabled - "
                    f"missing: {', '.join(missing)}"
                )
        
        if not enabled:
            logger.warning("No platforms are configured! Add credentials via /setcred or .env")
        else:
            logger.info(f"Total enabled platforms: {len(enabled)}/{len(self._platforms)}")
        
        return enabled
    
    def is_platform_enabled(self, platform: str) -> bool:
        """Check if a specific platform is enabled"""
        return platform.lower() in self.enabled_platforms
    
    def get_platform_config(self, platform: str):
        """Get configuration for a specific platform"""
        return self._platforms.get(platform.lower())

    def _reinit_platforms(self) -> None:
        """Re-create all platform settings from env vars and update the registry."""
        self.telegram = TelegramSettings()
        self.bluesky = BlueskySettings()
        self.mastodon = MastodonSettings()
        self.instagram = InstagramSettings()
        self.threads = ThreadsSettings()
        self.twitter = TwitterSettings()
        self.reddit = RedditSettings()
        self.youtube = YouTubeSettings()
        self._platforms = {
            "telegram": self.telegram,
            "bluesky": self.bluesky,
            "mastodon": self.mastodon,
            "instagram": self.instagram,
            "threads": self.threads,
            "twitter": self.twitter,
            "reddit": self.reddit,
            "youtube": self.youtube,
        }
        self.post_interval_hours = 5.0

    def _apply_kv_and_validate(self, kv_creds: Dict) -> None:
        """Merge a pre-fetched KV dict into settings and recalculate enabled platforms."""
        if kv_creds:
            config = kv_creds.pop("_config", {})
            if config:
                interval = config.get("post_interval_hours")
                if interval is not None:
                    self.post_interval_hours = float(interval)
                    logger.info(f"Post interval from KV: {self.post_interval_hours} hours")
            logger.info(f"Merging KV credentials for platforms: {', '.join(kv_creds.keys())}")
            for platform_name, platform_obj in self._platforms.items():
                platform_kv = kv_creds.get(platform_name, {})
                field_map = _KV_FIELD_MAP.get(platform_name, {})
                if platform_kv and field_map:
                    _merge_kv_into_settings(platform_obj, platform_kv, field_map)

            # Cloudinary has no Pydantic model — inject into os.environ so
            # cloudinary_config.configure_cloudinary() can pick them up.
            _inject_cloudinary_from_kv(kv_creds)

        self.enabled_platforms = self._validate_platforms()
        global ENABLED_PLATFORMS
        ENABLED_PLATFORMS = self.enabled_platforms

    def refresh(self) -> None:
        """Re-fetch KV credentials and recalculate enabled platforms (sync).
        
        Call this before operations that need the latest credentials,
        since users may add/delete credentials via /setcred or /delcred at any time.
        
        This completely reinitializes platform settings from env vars, then
        overlays KV credentials — ensuring deleted KV creds actually disappear.
        """
        self._reinit_platforms()
        kv_creds = _fetch_kv_credentials()
        self._apply_kv_and_validate(kv_creds)
        logger.info(f"Config refreshed (sync). Enabled platforms: {', '.join(self.enabled_platforms) or 'none'}")

    async def refresh_async(self) -> None:
        """Async version of refresh() — avoids blocking the event loop."""
        self._reinit_platforms()
        kv_creds = await _fetch_kv_credentials_async()
        self._apply_kv_and_validate(kv_creds)
        logger.info(f"Config refreshed (async). Enabled platforms: {', '.join(self.enabled_platforms) or 'none'}")


# Create singleton settings instance
settings = Settings()

# Export enabled platforms list for easy access
ENABLED_PLATFORMS = settings.enabled_platforms


# Export for easy importing
__all__ = ["settings", "ENABLED_PLATFORMS"]
