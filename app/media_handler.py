"""
Media handler for processing Telegram media and optimizing for different platforms
"""
import os
import io
import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from PIL import Image
import httpx
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class MediaInfo:
    """Structured media information"""
    type: str  # photo, video, document, text
    file_id: Optional[str] = None
    caption: Optional[str] = None
    local_path: Optional[str] = None
    mime_type: Optional[str] = None
    duration: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    cloudinary_url: Optional[str] = None
    cloudinary_public_id: Optional[str] = None

    def __init__(self, type: str, **kwargs):
        """Accept (and discard) unknown fields so that jobs stored with
        extra keys like ``scheduled_publish_time`` can still be
        deserialised without crashing."""
        known = {f.name for f in self.__dataclass_fields__.values()}
        self.type = type
        for name in known:
            if name == "type":
                continue
            setattr(self, name, kwargs.get(name, self.__dataclass_fields__[name].default))
        unknown = set(kwargs) - known
        if unknown:
            logger.debug(f"MediaInfo: ignoring unknown fields: {unknown}")

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


class MediaHandler:
    """Handle media download, processing, and optimization"""
    
    def __init__(self, bot_token: str, media_dir: str = "./media", client: Optional[httpx.AsyncClient] = None):
        """
        Initialize media handler
        
        Args:
            bot_token: Telegram bot token for API calls
            media_dir: Directory to store downloaded media
            client: Optional shared httpx.AsyncClient
        """
        self.bot_token = bot_token
        self.media_dir = Path(media_dir)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self._client = client
        
        # Platform-specific limits
        self.platform_limits = {
            "instagram": {
                "max_dimension": 1080,
                "max_size_mb": 8,
                "aspect_ratios": ["1:1", "4:5", "16:9"],  # Square, portrait, landscape
            },
            "twitter": {
                "max_dimension": 4096,
                "max_size_mb": 5,
            },
            "bluesky": {
                "max_dimension": 2048,
                "max_size_mb": 10,
            },
            "mastodon": {
                "max_dimension": 2048,
                "max_size_mb": 8,
            },
            "threads": {
                "max_dimension": 1080,
                "max_size_mb": 8,
            },
            "reddit": {
                "max_dimension": 2048,
                "max_size_mb": 20,
            },
            "default": {
                "max_dimension": 2048,
                "max_size_mb": 10,
            },
        }
    
    def parse_telegram_message(self, message: Dict) -> MediaInfo:
        """
        Parse Telegram message dict into structured MediaInfo
        
        Args:
            message: Raw Telegram message dictionary
            
        Returns:
            MediaInfo object with parsed data
        """
        caption = message.get("caption", "")
        
        # Check for photo
        if "photo" in message:
            # Get highest resolution photo
            photos = message["photo"]
            largest_photo = max(photos, key=lambda p: p.get("file_size", 0))
            
            return MediaInfo(
                type="photo",
                file_id=largest_photo.get("file_id"),
                caption=caption,
                mime_type="image/jpeg",
                width=largest_photo.get("width"),
                height=largest_photo.get("height"),
                file_size=largest_photo.get("file_size"),
            )
        
        # Check for video
        elif "video" in message:
            video = message["video"]
            return MediaInfo(
                type="video",
                file_id=video.get("file_id"),
                caption=caption,
                mime_type=video.get("mime_type", "video/mp4"),
                duration=video.get("duration"),
                width=video.get("width"),
                height=video.get("height"),
                file_size=video.get("file_size"),
            )
        
        # Check for document
        elif "document" in message:
            document = message["document"]
            return MediaInfo(
                type="document",
                file_id=document.get("file_id"),
                caption=caption,
                mime_type=document.get("mime_type"),
                file_size=document.get("file_size"),
            )
        
        # Text only
        else:
            return MediaInfo(
                type="text",
                caption=message.get("text", caption),
            )
    
    async def download_telegram_media(self, media_info: MediaInfo) -> MediaInfo:
        """
        Download media from Telegram and save locally
        
        Args:
            media_info: MediaInfo object with file_id
            
        Returns:
            Updated MediaInfo with local_path filled in
        """
        if media_info.type == "text" or not media_info.file_id:
            logger.info("No media to download (text message)")
            return media_info
        
        client = self._client or httpx.AsyncClient()
        try:
            # Step 1: Get file path from Telegram
            file_info_url = f"https://api.telegram.org/bot{self.bot_token}/getFile"
            params = {"file_id": media_info.file_id}
            
            response = await client.get(file_info_url, params=params)
            response.raise_for_status()
            file_data = response.json()
            
            if not file_data.get("ok"):
                raise Exception(f"Telegram API error: {file_data.get('description')}")
            
            file_path = file_data["result"]["file_path"]
            
            # Step 2: Download the file (streaming)
            download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
            
            # Step 3: Determine file extension
            ext = Path(file_path).suffix
            if not ext and media_info.mime_type:
                # Guess extension from mime type
                mime_to_ext = {
                    "image/jpeg": ".jpg",
                    "image/png": ".png",
                    "image/gif": ".gif",
                    "image/webp": ".webp",
                    "video/mp4": ".mp4",
                    "video/mpeg": ".mpeg",
                }
                ext = mime_to_ext.get(media_info.mime_type, "")
            
            # Step 4: Save to local file using streaming to avoid loading into RAM
            filename = f"{media_info.file_id}{ext}"
            local_path = self.media_dir / filename
            
            async with client.stream("GET", download_url) as response:
                response.raise_for_status()
                with open(local_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
            
            media_info.local_path = str(local_path)
            logger.info(f"Downloaded {media_info.type} to {local_path} (streaming)")
            
            return media_info
                
        except Exception as e:
            logger.error(f"Failed to download media: {e}")
            raise
        finally:
            if client is not self._client:
                await client.aclose()
    
    def cleanup_media(self, media_info: MediaInfo) -> bool:
        """
        Delete local media file
        
        Args:
            media_info: MediaInfo object with local_path
            
        Returns:
            True if deleted successfully
        """
        if not media_info.local_path:
            return False
        
        try:
            path = Path(media_info.local_path)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted {media_info.local_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete media: {e}")
            return False
    
    def _pad_to_aspect_ratio(
        self,
        image: Image.Image,
        target_ratio_str: str = "4:5",
        background_color: Tuple[int, int, int] = (255, 255, 255)
    ) -> Image.Image:
        """
        Pad image to a specific aspect ratio without cropping.
        
        Args:
            image: PIL Image object
            target_ratio_str: Target aspect ratio as "W:H"
            background_color: RGB tuple for padding color
            
        Returns:
            Padded Image
        """
        w, h = image.size
        # Parse ratio
        tw, th = map(int, target_ratio_str.split(":"))
        target_ratio = tw / th
        
        current_ratio = w / h
        
        if current_ratio > target_ratio:
            # Image is wider than target - pad top/bottom
            new_h = int(w / target_ratio)
            new_img = Image.new("RGB", (w, new_h), background_color)
            top = (new_h - h) // 2
            new_img.paste(image, (0, top))
            return new_img
        elif current_ratio < target_ratio:
            # Image is taller than target - pad left/right
            new_w = int(h * target_ratio)
            new_img = Image.new("RGB", (new_w, h), background_color)
            left = (new_w - w) // 2
            new_img.paste(image, (left, 0))
            return new_img
        
        return image

    def _resize_image(
        self, 
        image: Image.Image, 
        max_dimension: int,
        square_crop: bool = False
    ) -> Image.Image:
        """
        Resize image maintaining aspect ratio or crop to square
        
        Args:
            image: PIL Image object
            max_dimension: Maximum width or height
            square_crop: If True, crop to square
            
        Returns:
            Resized/cropped Image
        """
        if square_crop:
            # Crop to square (center crop)
            width, height = image.size
            size = min(width, height)
            
            left = (width - size) // 2
            top = (height - size) // 2
            right = left + size
            bottom = top + size
            
            image = image.crop((left, top, right, bottom))
            
            # Resize to max_dimension
            if size > max_dimension:
                image = image.resize((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        else:
            # Resize maintaining aspect ratio
            width, height = image.size
            
            if width > max_dimension or height > max_dimension:
                if width > height:
                    new_width = max_dimension
                    new_height = int(height * (max_dimension / width))
                else:
                    new_height = max_dimension
                    new_width = int(width * (max_dimension / height))
                
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return image
    
    def _optimize_image_size(
        self, 
        image: Image.Image, 
        max_size_mb: float,
        quality_start: int = 95
    ) -> Tuple[io.BytesIO, int]:
        """
        Optimize image to meet size requirements
        
        Args:
            image: PIL Image object
            max_size_mb: Maximum file size in MB
            quality_start: Starting JPEG quality (will decrease if needed)
            
        Returns:
            Tuple of (BytesIO buffer, final quality used)
        """
        max_bytes = int(max_size_mb * 1024 * 1024)
        quality = quality_start
        
        # Convert RGBA to RGB if needed
        if image.mode == "RGBA":
            # Create white background
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])  # Use alpha channel as mask
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")
        
        while quality > 20:
            with io.BytesIO() as buffer:
                image.save(buffer, format="JPEG", quality=quality, optimize=True)
                size = buffer.tell()
                
                if size <= max_bytes:
                    buffer.seek(0)
                    return io.BytesIO(buffer.getvalue()), quality
            
            quality -= 5
        
        # If still too large, return best effort
        final_buffer = io.BytesIO()
        image.save(final_buffer, format="JPEG", quality=20, optimize=True)
        final_buffer.seek(0)
        return final_buffer, 20
    
    def get_media_variants(
        self, 
        media_info: MediaInfo,
        platforms: Optional[List[str]] = None
    ) -> Dict[str, Dict]:
        """
        Generate platform-specific optimized versions of media
        
        Args:
            media_info: MediaInfo with local_path to original file
            platforms: List of platforms to optimize for (or None for all)
            
        Returns:
            Dictionary mapping platform -> {path, size, dimensions}
        """
        if not media_info.local_path:
            logger.error("No local file to process")
            return {}
        
        if media_info.type not in ["photo", "document"]:
            logger.warning(f"Variant generation not supported for {media_info.type}")
            return {}
        
        original_path = Path(media_info.local_path)
        if not original_path.exists():
            logger.error(f"Original file not found: {original_path}")
            return {}
        
        # Determine which platforms to process
        if platforms is None:
            platforms = ["instagram", "twitter", "bluesky", "mastodon", "threads", "reddit"]
        
        variants = {}
        
        try:
            # Open original image - use a context manager to ensure it's closed
            with Image.open(original_path) as img:
                # Convert to RGB if needed for processing
                if img.mode not in ["RGB", "RGBA"]:
                    img = img.convert("RGB")
                
                for platform in platforms:
                    limits = self.platform_limits.get(platform, self.platform_limits["default"])
                    
                    try:
                        # Special handling for Instagram (square crop option)
                        if platform == "instagram":
                            # Process regular variant
                            with img.copy() as variant_img_regular:
                                variant_img_regular = self._pad_to_aspect_ratio(
                                    variant_img_regular,
                                    "4:5"
                                )
                                variant_img_regular = self._resize_image(
                                    variant_img_regular, 
                                    limits["max_dimension"],
                                    square_crop=False
                                )
                                buffer_regular, quality = self._optimize_image_size(
                                    variant_img_regular,
                                    limits["max_size_mb"]
                                )
                                
                                base_name = original_path.stem
                                regular_path = self.media_dir / f"{base_name}_{platform}.jpg"
                                with open(regular_path, "wb") as f:
                                    f.write(buffer_regular.getbuffer())
                                buffer_regular.close()
                                
                                variants[platform] = {
                                    "path": str(regular_path),
                                    "size_bytes": regular_path.stat().st_size,
                                    "size_mb": round(regular_path.stat().st_size / (1024 * 1024), 2),
                                    "dimensions": variant_img_regular.size,
                                    "ratio": "4:5",
                                    "quality": quality,
                                }
                            
                            # Process square variant separately to keep RAM usage low
                            with img.copy() as variant_img_square:
                                variant_img_square = self._resize_image(
                                    variant_img_square,
                                    limits["max_dimension"],
                                    square_crop=True
                                )
                                buffer_square, quality_sq = self._optimize_image_size(
                                    variant_img_square,
                                    limits["max_size_mb"]
                                )
                                
                                square_path = self.media_dir / f"{base_name}_{platform}_square.jpg"
                                with open(square_path, "wb") as f:
                                    f.write(buffer_square.getbuffer())
                                buffer_square.close()
                                
                                variants[f"{platform}_square"] = {
                                    "path": str(square_path),
                                    "size_bytes": square_path.stat().st_size,
                                    "size_mb": round(square_path.stat().st_size / (1024 * 1024), 2),
                                    "dimensions": variant_img_square.size,
                                    "quality": quality_sq,
                                }
                        else:
                            # Standard resize for other platforms
                            with img.copy() as variant_img:
                                variant_img = self._resize_image(
                                    variant_img,
                                    limits["max_dimension"],
                                    square_crop=False
                                )
                                
                                buffer, quality = self._optimize_image_size(
                                    variant_img,
                                    limits["max_size_mb"]
                                )
                                
                                base_name = original_path.stem
                                variant_path = self.media_dir / f"{base_name}_{platform}.jpg"
                                with open(variant_path, "wb") as f:
                                    f.write(buffer.getbuffer())
                                buffer.close()
                                
                                variants[platform] = {
                                    "path": str(variant_path),
                                    "size_bytes": variant_path.stat().st_size,
                                    "size_mb": round(variant_path.stat().st_size / (1024 * 1024), 2),
                                    "dimensions": variant_img.size,
                                    "quality": quality,
                                }
                            
                        logger.info(f"Created {platform} variant: {variants.get(platform, {}).get('path')}")
                        
                    except Exception as e:
                        logger.error(f"Failed to create {platform} variant: {e}")
                        continue
                
        except Exception as e:
            logger.error(f"Failed to process image: {e}")
            return {}
        
        return variants


# Convenience functions for non-async usage
def create_handler(bot_token: str = "", media_dir: str = "./media") -> MediaHandler:
    """Create a MediaHandler instance"""
    return MediaHandler(bot_token, media_dir)


async def download_and_process(
    message: Dict,
    bot_token: str,
    media_dir: str = "./media"
) -> MediaInfo:
    """
    Parse message, download media, and return MediaInfo
    
    Args:
        message: Telegram message dict
        bot_token: Telegram bot token
        media_dir: Directory to save media
        
    Returns:
        MediaInfo with local_path
    """
    handler = MediaHandler(bot_token, media_dir)
    media_info = handler.parse_telegram_message(message)
    
    if media_info.type != "text":
        media_info = await handler.download_telegram_media(media_info)
    
    return media_info
