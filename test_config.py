#!/usr/bin/env python3
"""
Test configuration script - displays platform status and missing credentials
"""
import sys
import logging
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)

from app.config import settings, ENABLED_PLATFORMS


def print_separator(char="=", length=70):
    """Print a separator line"""
    print(char * length)


def print_section(title):
    """Print a section header"""
    print()
    print_separator()
    print(f"  {title}")
    print_separator()
    print()


def print_platform_status():
    """Print detailed status for each platform"""
    print_section("PLATFORM CONFIGURATION STATUS")
    
    # Get all platforms
    all_platforms = [
        "telegram", "bluesky", "mastodon", "instagram", 
        "threads", "twitter", "reddit", "youtube"
    ]
    
    enabled_count = 0
    disabled_count = 0
    
    for platform in all_platforms:
        platform_config = settings.get_platform_config(platform)
        is_enabled = platform_config.is_complete()
        
        if is_enabled:
            enabled_count += 1
            status = "ENABLED"
            status_color = "\033[92m"  # Green
        else:
            disabled_count += 1
            status = "DISABLED"
            status_color = "\033[91m"  # Red
        
        reset_color = "\033[0m"
        
        print(f"{status_color}{platform.upper():12} - {status}{reset_color}")
        
        # Show missing fields for disabled platforms
        if not is_enabled:
            missing = platform_config.get_missing_fields()
            print(f"             Missing: {', '.join(missing)}")
        
        print()
    
    return enabled_count, disabled_count


def print_summary(enabled_count, disabled_count):
    """Print summary statistics"""
    print_section("SUMMARY")
    
    total = enabled_count + disabled_count
    percentage = (enabled_count / total * 100) if total > 0 else 0
    
    print(f"Enabled Platforms:  {enabled_count}/{total} ({percentage:.0f}%)")
    print(f"Disabled Platforms: {disabled_count}/{total}")
    print()
    
    if enabled_count > 0:
        print("Ready to use:", ", ".join(ENABLED_PLATFORMS))
    else:
        print("\033[93mWARNING: No platforms are configured!\033[0m")
        print("Please add credentials to your .env file to enable platforms.")
    
    print()


def print_core_settings():
    """Print core application settings"""
    print_section("CORE SETTINGS")
    
    print(f"Database URL:     {settings.core.database_url}")
    print(f"Media Path:       {settings.core.media_path}")
    print(f"Logs Path:        {settings.core.logs_path}")
    print(f"API Host:         {settings.core.api_host}:{settings.core.api_port}")
    print(f"Check Interval:   {settings.core.check_interval_seconds}s")
    
    if settings.core.api_key:
        print(f"API Key:          {'*' * 8}{settings.core.api_key[-4:] if len(settings.core.api_key) > 4 else '****'}")
    else:
        print(f"API Key:          \033[93m(not set)\033[0m")
    
    print()


def print_env_file_status():
    """Check and print .env file status"""
    print_section("ENVIRONMENT FILE")
    
    env_path = Path(__file__).parent / ".env"
    env_example_path = Path(__file__).parent / ".env.example"
    
    if env_path.exists():
        print(f".env file found: {env_path}")
        file_size = env_path.stat().st_size
        print(f"  Size: {file_size} bytes")
    else:
        print(f"\033[91m.env file not found: {env_path}\033[0m")
        if env_example_path.exists():
            print(f"  Hint: Copy {env_example_path} to {env_path} and fill in your credentials")
    
    print()


def main():
    """Main test function"""
    print()
    print_separator("=", 70)
    print("  FORWARDR - Configuration Test")
    print_separator("=", 70)
    
    # Print environment file status
    print_env_file_status()
    
    # Print core settings
    print_core_settings()
    
    # Print platform status
    enabled_count, disabled_count = print_platform_status()
    
    # Print summary
    print_summary(enabled_count, disabled_count)
    
    print_separator("=", 70)
    print()
    
    # Exit code based on configuration
    if enabled_count == 0:
        sys.exit(1)  # Error if no platforms configured
    else:
        sys.exit(0)  # Success


if __name__ == "__main__":
    main()
