#!/usr/bin/env python3
"""
Credential verification script for all configured platforms.

Tests each platform's credentials by making lightweight, read-only API calls
(no content is posted). Prints a summary at the end.

Usage:
    python test_credentials.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ANSI colours for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

results: dict[str, str] = {}  # platform -> status message


def header(name: str) -> None:
    print(f"\n{BOLD}{CYAN}{'─' * 50}")
    print(f"  Testing {name}")
    print(f"{'─' * 50}{RESET}")


def ok(platform: str, detail: str = "") -> None:
    msg = f"{GREEN}✓ {platform}: OK{RESET}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    results[platform] = f"OK — {detail}" if detail else "OK"


def fail(platform: str, detail: str) -> None:
    msg = f"{RED}✗ {platform}: FAILED{RESET}  ({detail})"
    print(msg)
    results[platform] = f"FAILED — {detail}"


def skip(platform: str, reason: str) -> None:
    msg = f"{YELLOW}⊘ {platform}: SKIPPED{RESET}  ({reason})"
    print(msg)
    results[platform] = f"SKIPPED — {reason}"


# ──────────────────────────────────────────────────────────────────────────────
# 1. Telegram
# ──────────────────────────────────────────────────────────────────────────────
def test_telegram() -> None:
    header("Telegram")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        skip("Telegram", "TELEGRAM_BOT_TOKEN not set")
        return
    try:
        import requests
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getMe", timeout=15
        )
        data = resp.json()
        if data.get("ok"):
            bot = data["result"]
            ok("Telegram", f"Bot @{bot.get('username', '?')} (id={bot.get('id')})")
        else:
            fail("Telegram", data.get("description", "Unknown error"))
    except Exception as e:
        fail("Telegram", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# 2. Bluesky
# ──────────────────────────────────────────────────────────────────────────────
def test_bluesky() -> None:
    header("Bluesky")
    handle = os.getenv("BLUESKY_HANDLE") or os.getenv("BLUESKY_USERNAME")
    password = os.getenv("BLUESKY_PASSWORD")
    if not handle or not password:
        skip("Bluesky", "BLUESKY_HANDLE / BLUESKY_PASSWORD not set")
        return
    try:
        from atproto import Client
        client = Client()
        profile = client.login(handle, password)
        ok("Bluesky", f"Logged in as {profile.handle} (did={profile.did})")
    except Exception as e:
        fail("Bluesky", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# 3. Mastodon
# ──────────────────────────────────────────────────────────────────────────────
def test_mastodon() -> None:
    header("Mastodon")
    instance_url = os.getenv("MASTODON_INSTANCE_URL")
    access_token = os.getenv("MASTODON_ACCESS_TOKEN")
    if not instance_url or not access_token:
        skip("Mastodon", "MASTODON_INSTANCE_URL / MASTODON_ACCESS_TOKEN not set")
        return
    try:
        from mastodon import Mastodon
        client = Mastodon(access_token=access_token, api_base_url=instance_url)
        acct = client.account_verify_credentials()
        ok("Mastodon", f"@{acct['acct']}@{instance_url.replace('https://', '')}")
    except Exception as e:
        fail("Mastodon", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# 4. Instagram (Graph API)
# ──────────────────────────────────────────────────────────────────────────────
def test_instagram() -> None:
    header("Instagram")
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    if not access_token or not account_id:
        skip("Instagram", "INSTAGRAM_ACCESS_TOKEN / INSTAGRAM_BUSINESS_ACCOUNT_ID not set")
        return
    try:
        import requests
        resp = requests.get(
            f"https://graph.instagram.com/v21.0/{account_id}",
            params={
                "access_token": access_token,
                "fields": "id,username,name,followers_count",
            },
            timeout=15,
        )
        data = resp.json()
        if "error" in data:
            fail("Instagram", data["error"].get("message", str(data["error"])))
        else:
            username = data.get("username", data.get("name", "unknown"))
            followers = data.get("followers_count", "?")
            ok("Instagram", f"@{username} (followers: {followers})")
    except Exception as e:
        fail("Instagram", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# 5. Threads (Graph API)
# ──────────────────────────────────────────────────────────────────────────────
def test_threads() -> None:
    header("Threads")
    access_token = os.getenv("THREADS_ACCESS_TOKEN")
    user_id = os.getenv("THREADS_USER_ID")
    if not access_token:
        skip("Threads", "THREADS_ACCESS_TOKEN not set")
        return
    try:
        import requests
        resp = requests.get(
            "https://graph.threads.net/v1.0/me",
            params={
                "access_token": access_token,
                "fields": "id,username",
            },
            timeout=15,
        )
        data = resp.json()
        if "error" in data:
            fail("Threads", data["error"].get("message", str(data["error"])))
        else:
            username = data.get("username", "unknown")
            numeric_id = data.get("id", "?")
            ok("Threads", f"@{username} (id={numeric_id})")
    except Exception as e:
        fail("Threads", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# 6. Twitter / X
# ──────────────────────────────────────────────────────────────────────────────
def test_twitter() -> None:
    header("Twitter / X")
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
    if not all([api_key, api_secret, access_token, access_secret]):
        skip("Twitter", "One or more TWITTER_* credentials not set")
        return
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret,
        )
        me = client.get_me()
        if me and me.data:
            ok("Twitter", f"@{me.data.username} (id={me.data.id})")
        else:
            fail("Twitter", "get_me() returned no data")
    except Exception as e:
        fail("Twitter", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# 7. Reddit
# ──────────────────────────────────────────────────────────────────────────────
def test_reddit() -> None:
    header("Reddit")
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    username = os.getenv("REDDIT_USERNAME")
    password = os.getenv("REDDIT_PASSWORD")
    user_agent = os.getenv("REDDIT_USER_AGENT", "forwardr/1.0")
    if not client_id or not client_secret or not username or not password:
        skip("Reddit", "REDDIT_CLIENT_ID / CLIENT_SECRET / USERNAME / PASSWORD not set")
        return
    # Skip if still placeholder values
    if "your-client-id" in (client_id or "") or "your_username" in (username or ""):
        skip("Reddit", "Credentials contain placeholder values")
        return
    try:
        import praw
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=user_agent,
        )
        user = reddit.user.me()
        ok("Reddit", f"u/{user.name} (karma: {user.link_karma + user.comment_karma})")
    except Exception as e:
        fail("Reddit", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# 8. YouTube
# ──────────────────────────────────────────────────────────────────────────────
def test_youtube() -> None:
    header("YouTube")
    secrets_file = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE")
    token_file = os.getenv("YOUTUBE_TOKEN_FILE", "./youtube_token.json")
    if not secrets_file:
        skip("YouTube", "YOUTUBE_CLIENT_SECRETS_FILE not set")
        return
    if not Path(secrets_file).exists():
        skip("YouTube", f"Client secrets file not found: {secrets_file}")
        return
    if not Path(token_file).exists():
        skip("YouTube", f"Token file not found: {token_file} (run setup_youtube_auth.py first)")
        return
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(token_file)
        yt = build("youtube", "v3", credentials=creds)
        resp = yt.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items", [])
        if items:
            title = items[0]["snippet"]["title"]
            ok("YouTube", f"Channel: {title}")
        else:
            fail("YouTube", "No channel found for authenticated user")
    except Exception as e:
        fail("YouTube", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# 9. Cloudinary
# ──────────────────────────────────────────────────────────────────────────────
def test_cloudinary() -> None:
    header("Cloudinary")
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    if not all([cloud_name, api_key, api_secret]):
        skip("Cloudinary", "CLOUDINARY_CLOUD_NAME / API_KEY / API_SECRET not set")
        return
    try:
        import cloudinary
        import cloudinary.api
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )
        # Lightweight ping — fetch usage/quota info
        usage = cloudinary.api.usage()
        plan = usage.get("plan", "unknown")
        used_pct = usage.get("credits", {}).get("used_percent", "?")
        ok("Cloudinary", f"Plan: {plan}, credits used: {used_pct}%")
    except Exception as e:
        fail("Cloudinary", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    print(f"\n{BOLD}{'═' * 50}")
    print("  Forwardr — Credential Verification")
    print(f"{'═' * 50}{RESET}")

    test_telegram()
    test_bluesky()
    test_mastodon()
    test_instagram()
    test_threads()
    test_twitter()
    test_reddit()
    test_youtube()
    test_cloudinary()

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'═' * 50}")
    print("  Summary")
    print(f"{'═' * 50}{RESET}")

    passed = failed = skipped = 0
    for platform, status in results.items():
        if status.startswith("OK"):
            symbol = f"{GREEN}✓{RESET}"
            passed += 1
        elif status.startswith("FAILED"):
            symbol = f"{RED}✗{RESET}"
            failed += 1
        else:
            symbol = f"{YELLOW}⊘{RESET}"
            skipped += 1
        print(f"  {symbol} {platform:<14} {status}")

    print(f"\n  {GREEN}Passed: {passed}{RESET}  "
          f"{RED}Failed: {failed}{RESET}  "
          f"{YELLOW}Skipped: {skipped}{RESET}\n")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
