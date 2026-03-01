"""Cloudinary integration for hosting media that Threads requires at public URLs.

Setup:
    1. Sign up at https://cloudinary.com/ (free tier available)
    2. Add ``CLOUDINARY_CLOUD_NAME``, ``CLOUDINARY_API_KEY``, and
       ``CLOUDINARY_API_SECRET`` to your ``.env`` file.
"""
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Ensure .env is loaded so Cloudinary credentials are in os.environ.
_ENV_PATH = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

# Check if cloudinary is installed.
try:
    import cloudinary
    import cloudinary.uploader
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False
    logger.warning(
        "Cloudinary not available. Install with: pip install cloudinary\n"
        "Media posts to Threads will be text-only."
    )


def configure_cloudinary() -> bool:
    """Configure Cloudinary from environment variables.

    Returns:
        ``True`` if configured successfully, ``False`` otherwise.
    """
    if not CLOUDINARY_AVAILABLE:
        return False

    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    api_key = os.getenv('CLOUDINARY_API_KEY')
    api_secret = os.getenv('CLOUDINARY_API_SECRET')
    
    if not all([cloud_name, api_key, api_secret]):
        logger.warning(
            "Cloudinary credentials not fully configured. "
            "Add CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and "
            "CLOUDINARY_API_SECRET to .env file"
        )
        return False
    
    try:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        logger.info("Cloudinary configured successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to configure Cloudinary: {e}")
        return False


def upload_media(file_path: str, resource_type: str = 'auto') -> Optional[str]:
    """
    Upload media to Cloudinary and get public URL
    
    Args:
        file_path: Local path to the media file
        resource_type: 'image', 'video', or 'auto' (default)
        
    Returns:
        Public HTTPS URL of the uploaded media, or None if upload failed
        
    Example:
        >>> url = upload_media('/path/to/image.jpg')
        >>> print(url)
        'https://res.cloudinary.com/your-cloud/image/upload/v1234567890/abc123.jpg'
    """
    if not CLOUDINARY_AVAILABLE:
        logger.error("Cloudinary not available - cannot upload media")
        return None
    
    try:
        # Configure if not already done
        if not cloudinary.config().cloud_name:
            if not configure_cloudinary():
                return None
        
        # Upload the file
        logger.info(f"Uploading {file_path} to Cloudinary...")
        result = cloudinary.uploader.upload(
            file_path,
            resource_type=resource_type,
            folder='threads',  # Organize in a folder
            transformation={
                'quality': 'auto',  # Auto-optimize quality
                'fetch_format': 'auto'  # Auto-select best format
            }
        )
        
        public_url = result.get('secure_url')
        
        if public_url:
            logger.info(f"Media uploaded successfully: {public_url}")
            return public_url
        else:
            logger.error("Upload succeeded but no URL returned")
            return None
            
    except Exception as e:
        logger.error(f"Failed to upload media to Cloudinary: {e}")
        return None


def delete_media(public_id: str, resource_type: str = 'image') -> bool:
    """
    Delete media from Cloudinary (optional cleanup)
    
    Args:
        public_id: The public ID of the resource (from upload result)
        resource_type: 'image' or 'video'
        
    Returns:
        True if deleted successfully, False otherwise
    """
    if not CLOUDINARY_AVAILABLE:
        return False
    
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        return result.get('result') == 'ok'
    except Exception as e:
        logger.error(f"Failed to delete media from Cloudinary: {e}")
        return False


# Auto-configure on import if credentials are available
if CLOUDINARY_AVAILABLE:
    configure_cloudinary()
