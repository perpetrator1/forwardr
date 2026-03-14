
import os
import asyncio
import logging
import sys
from pathlib import Path
from PIL import Image
import httpx
import time
import resource
import shutil

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.media_handler import MediaHandler, MediaInfo

# Configure logging to flush immediately
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def get_memory_usage():
    """Returns memory usage in MB."""
    # resource.getrusage(resource.RUSAGE_SELF).ru_maxrss is in KB on Linux
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

async def verify_image_processing():
    logger.info("--- Starting Image Processing Verification ---")
    initial_mem = get_memory_usage()
    logger.info(f"Initial Memory: {initial_mem:.2f} MB")
    
    # Create a large test image (4000x3000 ~ 12MP) - still large enough to test spikes
    test_image_path = Path("test_large_image.jpg")
    logger.info("Generating test image (4000x3000)...")
    img = Image.new('RGB', (4000, 3000), color=(73, 109, 137))
    img.save(test_image_path, "JPEG", quality=95)
    logger.info(f"Test image saved: {test_image_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    test_media_dir = Path("./test_media")
    if test_media_dir.exists():
        shutil.rmtree(test_media_dir)
    test_media_dir.mkdir(parents=True, exist_ok=True)
    
    handler = MediaHandler("test_token", str(test_media_dir))
    
    platforms = ["instagram", "threads", "bluesky", "mastodon", "twitter"]
    
    # Create MediaInfo object
    media_info = MediaInfo(type="photo", local_path=str(test_image_path))
    
    # Measure memory before processing
    pre_process_mem = get_memory_usage()
    logger.info(f"Memory before processing: {pre_process_mem:.2f} MB")
    
    start_time = time.time()
    logger.info(f"Processing variants for platforms: {platforms}")
    variants = handler.get_media_variants(media_info, platforms)
    end_time = time.time()
    
    # Measure memory after processing
    post_process_mem = get_memory_usage()
    logger.info(f"Memory after processing: {post_process_mem:.2f} MB")
    logger.info(f"Memory Delta: {post_process_mem - pre_process_mem:.2f} MB")
    logger.info(f"Time taken: {end_time - start_time:.2f} s")
    
    logger.info(f"Created {len(variants)} variants")
    for name, info in variants.items():
        logger.info(f" - {name}: {info['dimensions']} @ {info.get('size_mb', 0):.2f} MB")
    
    # Cleanup
    if test_image_path.exists():
        test_image_path.unlink()
    for name, info in variants.items():
        p = Path(info['path'])
        if p.exists():
            p.unlink()
    if test_media_dir.exists():
        shutil.rmtree(test_media_dir)

    logger.info("--- Image Processing Verification Completed ---")

if __name__ == "__main__":
    asyncio.run(verify_image_processing())
