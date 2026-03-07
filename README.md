# Forwardr - Social Media Automation System

Automate your social media posting across multiple platforms with a single message to a Telegram bot. Posts are queued and published via a cron-triggered schedule.

## Features

- Send media to a Telegram bot to trigger automated posting
- **Owner-only** — only your Telegram account can use the bot
- **Cron-based queue** — Cloudflare Worker wakes the server hourly; background loop also processes every 60s
- **Telegram credential management** — set platform credentials via bot commands, stored in Cloudflare KV
- Multi-platform support:
  - Telegram Channel
  - Bluesky
  - Mastodon
  - Instagram
  - Threads
  - Twitter/X
  - Reddit
  - YouTube
- Automatic retry on failures
- Turso-backed persistent job queue (with local SQLite fallback)
- Cloudinary media storage (survives container restarts)
- Cloudflare Worker webhook receiver
- Deployed on Render.com free tier

## Architecture

```
                          ┌───────────────────────┐
                          │   Cloudflare Worker    │
                          │                       │
[Telegram Bot] ──webhook──▶  • Owner-only filter  │
                          │  • Bot commands        │──────▶ Cloudflare KV
                          │    (/setcred, /help…) │         (credentials)
                          │  • Forward media       │
                          │  • Cron trigger        │
                          └──────┬────────────┬────┘
                                 │            │
                          /webhook      /process-queue
                                 │            │
                          ┌──────▼────────────▼────┐
                          │  FastAPI on Render.com  │
                          │                        │
                          │  • Download media       │
                          │  • Upload to Cloudinary │──▶ Cloudinary (media CDN)
                          │  • Queue jobs (Turso)   │──▶ Turso (persistent DB)
                          │  • Background loop 60s  │
                          │  • Post to platforms    │
                          └────────────────────────┘
```

**Flow:**
1. You send a photo/video/text to the Telegram bot
2. Cloudflare Worker checks you're the owner, forwards to Render
3. FastAPI downloads the media, uploads it to Cloudinary, and queues jobs in Turso for all enabled platforms
4. The background loop (every 60s) or CF Worker cron processes due jobs
5. At processing time, media is fetched from Cloudinary if the local file is gone (ephemeral container)
6. After all platforms finish posting for a submission, Cloudinary media is deleted automatically

## Prerequisites

- Python 3.11+
- Cloudflare account (free tier)
- Render.com account (free tier)
- API credentials for each platform you want to use

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd forwardr
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials. At minimum, you need:

- `TELEGRAM_BOT_TOKEN` - Create a bot via [@BotFather](https://t.me/botfather)
- `TELEGRAM_OWNER_ID` - Your Telegram user ID (send `/start` to [@userinfobot](https://t.me/userinfobot))
- `API_SECRET_KEY` - Generate a secure random string
- `CLOUDFLARE_WORKER_URL` - Your deployed worker URL

### 5. Set Up Turso Database (Production)

```bash
# Install Turso CLI
curl -sSfL https://get.tur.so/install.sh | bash
turso auth login

# Create database and get credentials
turso db create forwardr
turso db show forwardr --url    # → TURSO_DATABASE_URL
turso db tokens create forwardr  # → TURSO_AUTH_TOKEN
```

Add `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` to your Render environment variables. Without them, the app falls back to local SQLite.

### 6. Run Locally (Development)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### 7. Deploy Cloudflare Worker

```bash
cd cloudflare-worker
npm install -g wrangler
wrangler login

# Create the KV namespaces
wrangler kv namespace create FAILED_UPDATES
wrangler kv namespace create CREDENTIALS

# Update wrangler.toml with the returned KV IDs, then:
wrangler deploy
```

Set secrets (not stored in `wrangler.toml`):
```bash
wrangler secret put RENDER_URL        # Your Render service URL
wrangler secret put API_KEY           # Same as API_SECRET_KEY
wrangler secret put TELEGRAM_OWNER_ID # Your numeric Telegram user ID
wrangler secret put TELEGRAM_BOT_TOKEN # Your bot token
```

### 8. Deploy to Render.com

1. Create a new Web Service on [Render.com](https://render.com)
2. Connect your GitHub repository
3. Configure the service:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add all environment variables from `.env` to Render's Environment Variables
5. Deploy

### 9. Set Up Telegram Bot Webhook

After deploying, point the Telegram webhook to your CF Worker:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=<YOUR_CLOUDFLARE_WORKER_URL>"
```

## Telegram Bot Commands

Once the bot is running, send these commands via Telegram:

| Command | Description |
|---------|-------------|
| `/setcred <platform> <key> <value>` | Save a platform credential |
| `/delcred <platform> <key>` | Delete a credential |
| `/getcreds` | List configured platforms & missing fields |
| `/status` | Show server & queue status |
| `/help` | Show all commands |

**Example — setting up Bluesky:**
```
/setcred bluesky handle your-handle.bsky.social
/setcred bluesky password xxxx-xxxx-xxxx-xxxx
```

Credentials are stored in Cloudflare KV (persistent, encrypted at rest by Cloudflare). Environment variables in `.env` or Render always take precedence over KV values.

## Platform Setup Guides

### Telegram

1. Create a bot: [@BotFather](https://t.me/botfather)
2. Get your API credentials: [my.telegram.org](https://my.telegram.org)
3. Create a channel and add your bot as an administrator

### Bluesky

1. Create an account at [bsky.app](https://bsky.app)
2. Generate an app password: Settings → App Passwords → Add App Password

### Mastodon

1. Create an account on any Mastodon instance
2. Go to Settings → Development → New Application
3. Grant required permissions and create the app
4. Copy the access token

### Instagram

1. Convert your Instagram account to a Professional Account (if not already):
   - Go to Settings → Account → Switch to Professional Account
2. Create a Facebook Page and link it to your Instagram Professional Account
3. Set up a Facebook App in [Facebook Developers](https://developers.facebook.com):
   - Create a new app → Business type
   - Add Instagram Graph API product
   - Configure Instagram Basic Display
4. Generate a long-lived access token for the Instagram Graph API
5. Get your Instagram Business Account ID

### Threads

**Official Meta API Integration** (Safe & Recommended)

1. Create a Meta Developer app at [developers.facebook.com](https://developers.facebook.com)
2. Add Threads API product to your app
3. Generate a long-lived access token with `threads_basic` and `threads_content_publish` permissions
4. Get your Threads User ID

#### Get Cloudinary (Free) - 2 min

1. Sign up → https://cloudinary.com/
2. Dashboard → Copy credentials
3. Add to `.env`:

```bash
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_key
CLOUDINARY_API_SECRET=your_secret
```

**Rate Limits:** 250 posts per 24 hours, 500 character limit per post

### Twitter/X

1. Apply for developer access: [developer.twitter.com](https://developer.twitter.com)
2. Create a new app and generate API keys
3. Ensure you have read/write permissions

### Reddit

1. Create an app: [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
2. Select "script" as the app type
3. Copy the client ID and secret

### YouTube

1. Create a project in [Google Cloud Console](https://console.cloud.google.com)
2. Enable YouTube Data API v3
3. Create OAuth 2.0 credentials
4. Download the client configuration

## Usage

1. Send a photo, video, or document to your Telegram bot
2. Include a caption (optional) — this will be the post text
3. The bot will queue the post for all configured platforms
4. The cron trigger processes one queued post every 5 hours

## API Endpoints

- `POST /webhook` - Receives webhooks from Cloudflare Worker
- `POST /process-queue` - Process the oldest pending job (cron-triggered)
- `GET /health` - Health check endpoint
- `GET /queue` - View current job queue
- `DELETE /queue/{job_id}` - Cancel a pending job

## Database Schema

### `jobs` Table
- `id` - Unique job identifier
- `status` - Job status (pending, processing, completed, failed)
- `platform` - Target platform
- `media_info` - Serialised media info JSON
- `scheduled_time` - When to publish
- `created_at` - Job creation timestamp
- `attempts` - Number of retry attempts
- `error_log` - Error messages from failed attempts
- `file_id` - Telegram file ID (for cleanup tracking)
- `post_url` - URL of the published post

## Configuration

Edit `app/config.py` to customize:
- Post delay duration
- Retry attempts
- Enabled platforms
- Media file size limits

## Project Structure

```
forwardr/
├── app/                      # Main application code
│   ├── api/                  # API endpoints
│   ├── models/               # Database models
│   ├── services/             # Business logic
│   │   └── platforms/        # Platform-specific integrations
│   ├── utils/                # Utility functions
│   └── workers/              # Background workers
├── cloudflare-worker/        # Cloudflare Worker code
├── scripts/                  # Database and utility scripts
├── tests/                    # Test files
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Contributing

any sort of help is welcome :)

## License

MIT License - feel free to use this project for personal or commercial purposes.
