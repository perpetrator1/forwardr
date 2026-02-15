# Forwardr - Social Media Automation System

Automate your social media posting across multiple platforms with a single message to a Telegram bot. Posts are queued and published with a 1-hour delay between each platform.

## Features

- Send media to a Telegram bot to trigger automated posting
- Automatic queuing with 1-hour delay between posts
- Multi-platform support:
  - Telegram Channel
  - Bluesky
  - Mastodon
  - Instagram
  - Threads
  - Twitter/X
  - Reddit
  - YouTube
  - Personal Website
- Automatic retry on failures
- SQLite-based job queue
- Cloudflare Worker webhook receiver
- Deployed on Render.com free tier

## Architecture

```
[Telegram Bot] → [Cloudflare Worker] → [FastAPI Backend on Render]
                                              ↓
                                        [SQLite Queue]
                                              ↓
                                      [Background Worker]
                                              ↓
                                    [Platform Publishers]
```

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

Edit `.env` and fill in your credentials for each platform you want to use. At minimum, you need:

- `TELEGRAM_BOT_TOKEN` - Create a bot via [@BotFather](https://t.me/botfather)
- `API_SECRET_KEY` - Generate a secure random string
- Platform-specific credentials for each service you want to use

### 5. Initialize Database

```bash
python scripts/init_db.py
```

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
wrangler deploy
```

Note the deployed worker URL and add it to your `.env` as `CLOUDFLARE_WORKER_URL`.

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

After deploying to Render, set the webhook for your Telegram bot:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=<YOUR_CLOUDFLARE_WORKER_URL>"
```

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

1. Use your Threads credentials
2. Note: Uses unofficial API; may be subject to rate limits

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

### Personal Website

Still figuring out this part

## Usage

1. Send a photo, video, or document to your Telegram bot
2. Include a caption (optional) - this will be the post text
3. The bot will queue the post for all configured platforms
4. Posts will be published with a 1-hour delay between each platform

## API Endpoints

- `POST /webhook` - Receives webhooks from Cloudflare Worker
- `GET /health` - Health check endpoint
- `GET /queue` - View current job queue (requires API key)
- `GET /jobs/{job_id}` - Get job status (requires API key)

## Database Schema

### `jobs` Table
- `id` - Unique job identifier
- `status` - Job status (pending, processing, completed, failed)
- `platform` - Target platform
- `media_url` - URL to media file
- `caption` - Post caption/text
- `scheduled_time` - When to publish
- `created_at` - Job creation timestamp
- `retries` - Number of retry attempts

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
