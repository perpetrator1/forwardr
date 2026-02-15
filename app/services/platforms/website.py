"""
Personal website integration
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def post(media_info: Dict) -> bool:
    """
    Post content to website via webhook
    
    Args:
        media_info: MediaInfo dictionary
        
    Returns:
        True if post succeeded
    """
    try:
        from app.config import settings
        
        # TODO: Implement webhook posting
        # import httpx
        # 
        # payload = {
        #     'type': media_info.get('type'),
        #     'caption': media_info.get('caption'),
        #     'file_url': media_info.get('local_path'),  # Or upload to CDN first
        # }
        # 
        # headers = {}
        # if settings.website.api_key:
        #     headers['Authorization'] = f'Bearer {settings.website.api_key}'
        # 
        # response = httpx.post(
        #     settings.website.webhook_url,
        #     json=payload,
        #     headers=headers,
        #     timeout=30
        # )
        # response.raise_for_status()
        
        logger.info(f"Website: Would post {media_info.get('type')} to webhook")
        return True
        
    except Exception as e:
        logger.error(f"Website posting failed: {e}")
        return False
