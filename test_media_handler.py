#!/usr/bin/env python3
"""
Test media handler - process image and generate platform-specific variants
"""
import sys
import logging
from pathlib import Path
from tabulate import tabulate

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.media_handler import MediaHandler, MediaInfo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s"
)


def print_separator(char="=", length=80):
    """Print separator line"""
    print(char * length)


def print_section(title):
    """Print section header"""
    print()
    print_separator()
    print(f"  {title}")
    print_separator()
    print()


def format_size(size_bytes):
    """Format file size in human-readable format"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def test_media_handler(image_path: str):
    """
    Test media handler with a local image file
    
    Args:
        image_path: Path to input image file
    """
    input_path = Path(image_path)
    
    # Validate input file
    if not input_path.exists():
        print(f"❌ Error: File not found: {input_path}")
        sys.exit(1)
    
    if not input_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
        print(f"⚠ Warning: File may not be a valid image: {input_path}")
    
    print_section("MEDIA HANDLER TEST")
    
    # Display input file info
    file_size = input_path.stat().st_size
    print(f"Input file: {input_path}")
    print(f"File size:  {format_size(file_size)}")
    print()
    
    # Create MediaInfo from local file
    media_info = MediaInfo(
        type="photo",
        file_id=input_path.stem,  # Use filename as file_id
        local_path=str(input_path),
        mime_type="image/jpeg",
    )
    
    # Create handler
    handler = MediaHandler(bot_token="", media_dir="./media")
    
    print("🔄 Generating platform-specific variants...\n")
    
    # Generate variants for all platforms
    variants = handler.get_media_variants(media_info)
    
    if not variants:
        print("❌ Failed to generate variants!")
        sys.exit(1)
    
    # Display results
    print_section("GENERATED VARIANTS")
    
    # Prepare table data
    table_data = []
    for platform, info in sorted(variants.items()):
        table_data.append([
            platform.upper(),
            Path(info["path"]).name,
            format_size(info["size_bytes"]),
            f"{info['dimensions'][0]}x{info['dimensions'][1]}",
            f"{info['quality']}%",
        ])
    
    # Print table
    headers = ["Platform", "Filename", "Size", "Dimensions", "Quality"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print()
    
    # Summary statistics
    total_size = sum(v["size_bytes"] for v in variants.values())
    print_section("SUMMARY")
    
    print(f"Total variants created: {len(variants)}")
    print(f"Total storage used:     {format_size(total_size)}")
    print(f"Original file size:     {format_size(file_size)}")
    print(f"Size reduction:         {((file_size - total_size) / file_size * 100):.1f}%")
    print()
    
    # List all created files
    print("Created files:")
    for platform, info in sorted(variants.items()):
        print(f"  ✓ {info['path']}")
    print()
    
    print_separator()
    print()


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python test_media_handler.py <image_file>")
        print()
        print("Example:")
        print("  python test_media_handler.py sample.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    test_media_handler(image_path)


if __name__ == "__main__":
    main()
