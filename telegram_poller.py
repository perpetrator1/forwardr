#!/usr/bin/env python3
"""
Telegram Polling Script - Get messages from Telegram and forward to local webhook

This is for LOCAL TESTING ONLY. It polls Telegram for updates and sends them
to your local webhook endpoint, simulating what would happen in production.

In production, you'd use a real webhook with a public URL.
"""
import time
import requests
from datetime import datetime
from app.config import settings

API_URL = "http://localhost:8000"
API_KEY = settings.core.api_key or "test-api-key-change-in-production"
BOT_TOKEN = settings.telegram.bot_token

if not BOT_TOKEN:
    print("❌ Error: TELEGRAM_BOT_TOKEN not configured in .env")
    exit(1)

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def get_bot_info():
    """Get bot information"""
    response = requests.get(f"{TELEGRAM_API}/getMe")
    data = response.json()
    if data.get("ok"):
        bot = data["result"]
        return bot
    return None


def delete_webhook():
    """Delete any existing webhook"""
    response = requests.post(f"{TELEGRAM_API}/deleteWebhook")
    data = response.json()
    return data.get("ok", False)


def get_updates(offset=None):
    """
    Get updates from Telegram
    
    Args:
        offset: Update ID to start from
        
    Returns:
        List of updates
    """
    params = {
        "timeout": 30,  # Long polling
        "allowed_updates": ["message", "edited_message", "channel_post", "edited_channel_post"]
    }
    
    if offset:
        params["offset"] = offset
    
    try:
        response = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=35)
        data = response.json()
        
        if data.get("ok"):
            return data.get("result", [])
        else:
            print(f"❌ Telegram API error: {data.get('description')}")
            return []
    
    except requests.exceptions.Timeout:
        # Timeout is normal for long polling
        return []
    except Exception as e:
        print(f"❌ Error getting updates: {e}")
        return []


def forward_to_webhook(update):
    """
    Forward update to local webhook
    
    Args:
        update: Telegram update object
    """
    try:
        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{API_URL}/webhook",
            json=update,
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            return True
        else:
            print(f"❌ Webhook error: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"❌ Error forwarding to webhook: {e}")
        return False


def process_update(update):
    """
    Process a single update
    
    Args:
        update: Telegram update dictionary
    """
    update_id = update.get("update_id")
    
    # Get the message
    message = (
        update.get("message") or 
        update.get("edited_message") or
        update.get("channel_post") or
        update.get("edited_channel_post")
    )
    
    if not message:
        return
    
    # Extract message info
    msg_type = "text"
    content = message.get("text", "")
    
    if "photo" in message:
        msg_type = "photo"
        content = message.get("caption", "(no caption)")
    elif "video" in message:
        msg_type = "video"
        content = message.get("caption", "(no caption)")
    elif "document" in message:
        msg_type = "document"
        content = message.get("caption", "(no caption)")
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    print(f"\n[{timestamp}] 📨 New {msg_type} message (ID: {update_id})")
    if content:
        print(f"   {content[:80]}{'...' if len(content) > 80 else ''}")
    
    # Forward to webhook
    if forward_to_webhook(update):
        print(f"   ✅ Forwarded to webhook")
    else:
        print(f"   ❌ Failed to forward")


def main():
    """Main polling loop"""
    print("=" * 70)
    print("🤖 Telegram Polling Bot")
    print("=" * 70)
    
    # Get bot info
    bot = get_bot_info()
    if not bot:
        print("❌ Error: Could not get bot info")
        return
    
    print(f"\n✅ Bot: @{bot['username']} ({bot['first_name']})")
    
    # Delete webhook if exists
    print("\n🗑️  Deleting any existing webhook...")
    if delete_webhook():
        print("   ✅ Webhook deleted")
    else:
        print("   ⚠️  Could not delete webhook (might not exist)")
    
    # Check server health
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        health = response.json()
        print(f"\n💚 Server health: {health['status']}")
        print(f"   Enabled platforms: {', '.join(health['enabled_platforms'])}")
    except Exception as e:
        print(f"\n❌ Error: Cannot connect to local server at {API_URL}")
        print(f"   Make sure the server is running: uvicorn app.main:app --reload")
        return
    
    print("\n" + "=" * 70)
    print("🎯 Ready! Send messages to your bot on Telegram")
    print("=" * 70)
    print(f"\n   Bot username: @{bot['username']}")
    print(f"   Listening for messages...")
    print(f"\n   Press Ctrl+C to stop\n")
    
    offset = None
    
    try:
        while True:
            # Get updates
            updates = get_updates(offset)
            
            # Process each update
            for update in updates:
                process_update(update)
                
                # Update offset to mark this update as processed
                offset = update["update_id"] + 1
            
            # Small delay if no updates (long polling already waits)
            if not updates:
                time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\n\n👋 Stopping poller...")
        print("=" * 70)


if __name__ == "__main__":
    main()
