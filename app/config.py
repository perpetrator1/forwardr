"""
Configuration management using Pydantic Settings
"""
import os
from pathlib import Path
from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import logging

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
    """Instagram configuration"""
    model_config = SettingsConfigDict(env_prefix="INSTAGRAM_")
    
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    
    def is_complete(self) -> bool:
        """Check if all required credentials are present"""
        return bool(self.username and self.password)
    
    def get_missing_fields(self) -> List[str]:
        """Return list of missing required fields"""
        missing = []
        if not self.username:
            missing.append("INSTAGRAM_USERNAME")
        if not self.password:
            missing.append("INSTAGRAM_PASSWORD")
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
    
    def is_complete(self) -> bool:
        """Check if all required credentials are present"""
        return bool(
            self.client_id and 
            self.client_secret and 
            self.username and 
            self.password
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
        return missing


class YouTubeSettings(BaseSettings):
    """YouTube configuration"""
    model_config = SettingsConfigDict(env_prefix="YOUTUBE_")
    
    client_secrets_file: Optional[str] = Field(default=None)
    credentials_file: Optional[str] = Field(default=None)
    
    def is_complete(self) -> bool:
        """Check if all required credentials are present"""
        return bool(self.client_secrets_file)
    
    def get_missing_fields(self) -> List[str]:
        """Return list of missing required fields"""
        missing = []
        if not self.client_secrets_file:
            missing.append("YOUTUBE_CLIENT_SECRETS_FILE")
        return missing


class WebsiteSettings(BaseSettings):
    """Website/webhook configuration"""
    model_config = SettingsConfigDict(env_prefix="WEBSITE_")
    
    webhook_url: Optional[str] = Field(default=None)
    api_key: Optional[str] = Field(default=None)
    
    def is_complete(self) -> bool:
        """Check if all required credentials are present"""
        return bool(self.webhook_url)
    
    def get_missing_fields(self) -> List[str]:
        """Return list of missing required fields"""
        missing = []
        if not self.webhook_url:
            missing.append("WEBSITE_WEBHOOK_URL")
        return missing


# Main Settings Class
class Settings:
    """Main settings container with platform validation"""
    
    def __init__(self):
        # Initialize core settings
        self.core = CoreSettings()
        
        # Initialize platform settings
        self.telegram = TelegramSettings()
        self.bluesky = BlueskySettings()
        self.mastodon = MastodonSettings()
        self.instagram = InstagramSettings()
        self.threads = ThreadsSettings()
        self.twitter = TwitterSettings()
        self.reddit = RedditSettings()
        self.youtube = YouTubeSettings()
        self.website = WebsiteSettings()
        
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
            "website": self.website,
        }
        
        # Validate and set enabled platforms
        self.enabled_platforms = self._validate_platforms()
    
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
            logger.warning("No platforms are configured! Please add credentials to .env file")
        else:
            logger.info(f"Total enabled platforms: {len(enabled)}/{len(self._platforms)}")
        
        return enabled
    
    def is_platform_enabled(self, platform: str) -> bool:
        """Check if a specific platform is enabled"""
        return platform.lower() in self.enabled_platforms
    
    def get_platform_config(self, platform: str):
        """Get configuration for a specific platform"""
        return self._platforms.get(platform.lower())


# Create singleton settings instance
settings = Settings()

# Export enabled platforms list for easy access
ENABLED_PLATFORMS = settings.enabled_platforms


# Export for easy importing
__all__ = ["settings", "ENABLED_PLATFORMS"]
