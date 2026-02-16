#!/usr/bin/env python3
"""
Platform Router - Quick Integration Test
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

print("\n" + "=" * 70)
print("  PLATFORM ROUTER - QUICK TEST")
print("=" * 70 + "\n")

# Test 1: Import the router
print("1. Importing platform router...")
try:
    from app.services.platforms import (
        post_to_platform,
        get_available_platforms,
        determine_platforms,
        get_loaded_handlers
    )
    print("   ✓ Import successful\n")
except Exception as e:
    print(f"   ✗ Import failed: {e}\n")
    sys.exit(1)

# Test 2: Check loaded handlers
print("2. Loaded platform handlers:")
handlers = get_loaded_handlers()
for handler in sorted(handlers):
    print(f"   ✓ {handler}")
print()

# Test 3: Check available platforms
print("3. Available platforms (configured + loaded):")
available = get_available_platforms()
if available:
    for platform in available:
        print(f"   ✓ {platform}")
else:
    print("   (none - add credentials to .env)")
print()

# Test 4: Test routing logic
print("4. Routing logic test:")
test_cases = [
    ('photo', ['telegram', 'bluesky', 'mastodon', 'instagram', 'threads', 'twitter', 'reddit']),
    ('video', ['telegram', 'bluesky', 'mastodon', 'youtube', 'twitter']),
    ('text', ['telegram', 'bluesky', 'mastodon', 'twitter', 'reddit']),
    ('document', ['telegram']),
]

for media_type, expected_platforms in test_cases:
    media_info = {'type': media_type}
    result = determine_platforms(media_info)
    # Only shows platforms that are available
    print(f"   {media_type:10} → {', '.join(result) if result else '(none available)'}")
print()

# Test 5: Test posting
print("5. Test posting:")
if available:
    platform = available[0]
    media_info = {
        'type': 'text',
        'caption': 'Test post from router',
        'file_id': 'test123'
    }
    
    print(f"   Posting to {platform}...")
    result = post_to_platform(platform, media_info)
    
    if result:
        print(f"   ✓ Post succeeded")
    else:
        print(f"   ✗ Post failed")
else:
    print("   (skipped - no platforms available)")

print()
print("=" * 70)
print("✓ Tests completed!")
print("=" * 70 + "\n")
