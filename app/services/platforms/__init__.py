"""
Platform integration services - Central router for posting to social media platforms
"""
import logging
from typing import Dict, List, Optional, Callable
from app.config import settings, ENABLED_PLATFORMS

logger = logging.getLogger(__name__)

# Platform module registry - maps platform name to posting function
_platform_handlers: Dict[str, Callable] = {}
_import_errors: Dict[str, str] = {}


def _safe_import_platform(platform_name: str, module_name: str) -> bool:
    """
    Safely import a platform module and register its post function
    
    Args:
        platform_name: Name of the platform (e.g., 'telegram')
        module_name: Module to import (e.g., 'telegram')
        
    Returns:
        True if import succeeded, False otherwise
    """
    try:
        # Import the platform module
        module = __import__(
            f"app.services.platforms.{module_name}",
            fromlist=['post']
        )
        
        # Get the post function
        if hasattr(module, 'post'):
            _platform_handlers[platform_name] = module.post
            logger.debug(f"✓ Loaded platform handler: {platform_name}")
            return True
        else:
            error = f"Module missing 'post' function"
            _import_errors[platform_name] = error
            logger.warning(f"✗ {platform_name}: {error}")
            return False
            
    except ImportError as e:
        error = f"Import error: {str(e)}"
        _import_errors[platform_name] = error
        logger.warning(f"✗ Failed to import {platform_name}: {error}")
        return False
    except Exception as e:
        error = f"Unexpected error: {str(e)}"
        _import_errors[platform_name] = error
        logger.error(f"✗ Error loading {platform_name}: {error}")
        return False


# Initialize all platform imports
_PLATFORM_MODULES = {
    'telegram': 'telegram',
    'bluesky': 'bluesky',
    'mastodon': 'mastodon',
    'instagram': 'instagram',
    'threads': 'threads',
    'twitter': 'twitter',
    'reddit': 'reddit',
    'youtube': 'youtube',
}

# Attempt to import all platforms
logger.info("Loading platform handlers...")
for platform_name, module_name in _PLATFORM_MODULES.items():
    _safe_import_platform(platform_name, module_name)


def get_available_platforms() -> List[str]:
    """
    Get list of platforms that are both configured AND imported successfully
    
    Returns:
        List of available platform names
    """
    available = []
    
    for platform in ENABLED_PLATFORMS:
        # Check if platform handler was imported successfully
        if platform in _platform_handlers:
            available.append(platform)
        else:
            logger.debug(
                f"Platform '{platform}' has credentials but handler not available: "
                f"{_import_errors.get(platform, 'Unknown error')}"
            )
    
    return available


def determine_platforms(media_info: Dict) -> List[str]:
    """
    Determine which platforms to post to based on media type
    
    Routing logic:
    - photo → telegram, bluesky, mastodon, instagram, threads, twitter, reddit
    - video → telegram, bluesky, mastodon, youtube, twitter
    - text  → telegram, bluesky, mastodon, twitter, reddit
    - document → telegram
    
    Args:
        media_info: MediaInfo dictionary with 'type' field
        
    Returns:
        List of platform names that support this media type and are available
    """
    media_type = media_info.get('type', 'text')
    
    # Define platform support by media type
    platform_support = {
        'photo': [
            'telegram', 'bluesky', 'mastodon', 'instagram', 
            'threads', 'twitter', 'reddit'
        ],
        'video': [
            'telegram', 'bluesky', 'mastodon', 'youtube', 
            'twitter'
        ],
        'text': [
            'telegram', 'bluesky', 'mastodon', 'twitter', 
            'reddit'
        ],
        'document': [
            'telegram'
        ],
    }
    
    # Get platforms that support this media type
    supported_platforms = platform_support.get(media_type, [])
    
    # Filter to only include available platforms
    available = get_available_platforms()
    
    # Return intersection of supported and available
    platforms = [p for p in supported_platforms if p in available]
    
    logger.info(
        f"Media type '{media_type}' → {len(platforms)} available platforms: "
        f"{', '.join(platforms) if platforms else 'none'}"
    )
    
    return platforms


def post_to_platform(platform: str, media_info: Dict) -> bool:
    """
    Post to a specific platform
    
    Args:
        platform: Platform name (e.g., 'telegram', 'twitter')
        media_info: MediaInfo dictionary with content to post
        
    Returns:
        True if post succeeded, False if failed
    """
    # Check if platform handler exists
    if platform not in _platform_handlers:
        logger.error(
            f"Platform '{platform}' not available. "
            f"Reason: {_import_errors.get(platform, 'Not imported')}"
        )
        return False
    
    # Check if platform is configured
    if platform not in ENABLED_PLATFORMS:
        logger.error(
            f"Platform '{platform}' not configured (missing credentials)"
        )
        return False
    
    try:
        # Get the platform's post function
        post_func = _platform_handlers[platform]
        
        logger.info(f"Posting to {platform}...")
        
        # Call the platform's post function
        result = post_func(media_info)
        
        if result:
            logger.info(f"✓ Successfully posted to {platform}")
            return True
        else:
            logger.warning(f"✗ Failed to post to {platform} (returned False)")
            return False
            
    except Exception as e:
        logger.error(f"✗ Exception posting to {platform}: {str(e)}", exc_info=True)
        return False


def get_platform_errors() -> Dict[str, str]:
    """
    Get import errors for platforms that failed to load
    
    Returns:
        Dictionary mapping platform name to error message
    """
    return _import_errors.copy()


def get_loaded_handlers() -> List[str]:
    """
    Get list of platform handlers that loaded successfully
    
    Returns:
        List of platform names with loaded handlers
    """
    return list(_platform_handlers.keys())


# Export public API
__all__ = [
    'post_to_platform',
    'get_available_platforms',
    'determine_platforms',
    'get_platform_errors',
    'get_loaded_handlers',
]
