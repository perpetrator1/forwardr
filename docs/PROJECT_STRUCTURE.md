# Project Structure

Complete folder and file structure for the Forwardr social media automation system.

```
forwardr/
│
├── .env.example                          # Environment variables template
├── .gitignore                            # Git ignore rules
├── README.md                             # Project documentation and setup guide
├── render.yaml                           # Render.com deployment config
├── requirements.txt                      # Python dependencies (pinned versions)
│
├── app/                                  # Main application
│   ├── __init__.py
│   ├── main.py                           # FastAPI entry point (webhook, health, queue endpoints)
│   ├── config.py                         # Configuration (Pydantic Settings, loads .env)
│   ├── database.py                       # Database connection and session management
│   ├── media_handler.py                  # Telegram media download and processing
│   ├── queue_manager.py                  # SQLite-backed job queue with background processor
│   │
│   ├── api/                              # API layer
│   │   ├── __init__.py
│   │   ├── webhook.py                    # Webhook endpoint
│   │   └── admin.py                      # Admin/monitoring endpoints
│   │
│   ├── models/                           # Database models
│   │   ├── __init__.py
│   │   ├── job.py                        # Job queue model
│   │   └── post.py                       # Post data model
│   │
│   ├── platforms/                        # Direct platform posting modules
│   │   ├── __init__.py
│   │   ├── bluesky.py                    # Bluesky via atproto
│   │   ├── instagram.py                  # Instagram via instagrapi
│   │   ├── mastodon.py                   # Mastodon via Mastodon.py
│   │   ├── reddit.py                     # Reddit via praw
│   │   ├── telegram_channel.py           # Telegram via Bot API
│   │   ├── threads.py                    # Threads via Graph API
│   │   ├── twitter.py                    # Twitter/X via tweepy
│   │   └── youtube.py                    # YouTube via google-api-python-client
│   │
│   ├── services/                         # Business logic layer
│   │   ├── __init__.py
│   │   ├── queue.py                      # Queue management logic
│   │   ├── scheduler.py                  # Post scheduling and timing
│   │   │
│   │   └── platforms/                    # Platform router and service wrappers
│   │       ├── __init__.py               # Central router (determine_platforms, post_to_platform)
│   │       ├── bluesky.py
│   │       ├── instagram.py
│   │       ├── mastodon.py
│   │       ├── reddit.py
│   │       ├── telegram.py
│   │       ├── threads.py
│   │       ├── twitter.py
│   │       └── youtube.py
│   │
│   ├── utils/                            # Utility functions
│   │   ├── __init__.py
│   │   ├── media.py                      # Media processing utilities
│   │   └── logger.py                     # Logging configuration
│   │
│   └── workers/                          # Background workers
│       ├── __init__.py
│       └── poster.py                     # Background job processor
│
├── cloudflare-worker/                    # Cloudflare Worker (webhook proxy)
│   ├── index.js                          # Worker script with KV retry
│   ├── worker.js                         # Legacy worker stub
│   ├── wrangler.toml                     # Wrangler config (KV bindings, secrets)
│   ├── package.json                      # NPM config
│   └── README.md                         # Worker setup docs
│
├── tests/                                # All tests
│   ├── __init__.py
│   ├── test_bluesky.py                   # Bluesky integration test
│   ├── test_config.py                    # Config/credentials status check
│   ├── test_e2e.py                       # End-to-end integration test
│   ├── test_instagram.py                 # Instagram integration test
│   ├── test_mastodon.py                  # Mastodon integration test
│   ├── test_media_handler.py             # Media handler test
│   ├── test_platform_router.py           # Platform router logic test
│   ├── test_queue.py                     # Queue manager test
│   ├── test_reddit.py                    # Reddit integration test
│   ├── test_retry.py                     # Retry logic test
│   ├── test_router_quick.py              # Quick router smoke test
│   ├── test_telegram.py                  # Telegram integration test
│   └── test_twitter.py                   # Twitter integration test
│
├── examples/                             # Usage examples and references
│   ├── complete_workflow.py              # Full config → media → queue → post flow
│   ├── media_usage.py                    # Media handler usage examples
│   ├── queue_integration.py              # Queue manager integration example
│   └── queue_quick_reference.py          # Quick-reference code snippets
│
├── scripts/                              # Utility scripts
│   ├── __init__.py
│   ├── init_db.py                        # Database initialisation
│   ├── migrate.py                        # Database migrations
│   └── setup_youtube_auth.py             # One-time YouTube OAuth flow
│
├── docs/                                 # Documentation
│   ├── PLATFORM_ROUTER_SUMMARY.md        # Platform router feature summary
│   ├── PROJECT_STRUCTURE.md              # This file
│   ├── QUEUE_MANAGER_SUMMARY.md          # Queue manager feature summary
│   └── RENDER_DEPLOYMENT.md              # Render.com deployment guide
│
├── media/                                # Temporary media storage (persistent disk on Render)
│
└── logs/                                 # Application logs
```

## File Purposes

### Root Level Files

- **`.env.example`**: Template for environment variables with detailed comments explaining each variable
- **`.gitignore`**: Specifies files and directories to exclude from version control
- **`README.md`**: Complete project documentation, setup instructions, and usage guide
- **`requirements.txt`**: All Python dependencies with pinned versions for reproducibility

### Application Layer (`app/`)

#### Core Files
- **`main.py`**: FastAPI entry point — webhook, health, queue, and cancel endpoints. Lazy processor start for Render cold boot.
- **`config.py`**: Centralized configuration using Pydantic Settings with per-platform env_prefix classes. Singleton `settings` object.
- **`database.py`**: Database connection and session management.
- **`media_handler.py`**: Downloads media from Telegram Bot API by file_id, determines type (photo/video/document).
- **`queue_manager.py`**: SQLite-backed persistent job queue. Statuses: pending → completed / failed / cancelled. Background processor thread.

#### API Layer (`app/api/`)
- **`webhook.py`**: Receives webhook payloads from Cloudflare Worker (Telegram messages)
- **`admin.py`**: Administrative endpoints for queue monitoring and manual operations

#### Data Models (`app/models/`)
- **`job.py`**: Job queue model (status, platform, timing, retries)
- **`post.py`**: Post data model (media, caption, metadata)

#### Services Layer (`app/services/`)
- **`queue.py`**: Queue management logic (add jobs, update status, handle retries)
- **`scheduler.py`**: Calculate post times, manage 1-hour delays between platforms

##### Platform Router (`app/services/platforms/`)
Central routing layer that maps content types to target platforms:
- **`__init__.py`**: `determine_platforms()` (content type → platform list), `post_to_platform()` dispatcher
- **`telegram.py`**: Telegram Channel posting
- **`bluesky.py`**: Bluesky (AT Protocol) posting
- **`mastodon.py`**: Mastodon posting
- **`instagram.py`**: Instagram posting
- **`threads.py`**: Threads (Meta Graph API) posting
- **`twitter.py`**: Twitter/X posting
- **`reddit.py`**: Reddit posting
- **`youtube.py`**: YouTube posting

#### Direct Platform Modules (`app/platforms/`)
Low-level posting clients (each with `post()` function):
- **`bluesky.py`**: atproto Client, 300 char limit, image blob upload
- **`telegram_channel.py`**: Telegram Bot API via requests
- **`mastodon.py`**: Mastodon.py, 500 char limit, media + status flow
- **`twitter.py`**: Dual-client — tweepy.API (v1.1 media upload) + tweepy.Client (v2 tweet)
- **`instagram.py`**: instagrapi, session persistence, PIL image resize (320–1080px, aspect 4:5–1.91:1)
- **`threads.py`**: Meta Graph API v19.0, container create → poll → publish, ImgBB for public URLs
- **`reddit.py`**: praw script OAuth, 2s rate limit, first line = title
- **`youtube.py`**: google-api-python-client, OAuth2, resumable upload

#### Utilities (`app/utils/`)
- **`media.py`**: Media processing utilities
- **`logger.py`**: Logging configuration

#### Workers (`app/workers/`)
- **`poster.py`**: Background worker that processes the job queue and posts to platforms

### Cloudflare Worker (`cloudflare-worker/`)

- **`index.js`**: Main worker — validates update_id, wakes Render via GET, forwards webhook with X-API-Key, stores failures in KV
- **`worker.js`**: Legacy worker stub
- **`wrangler.toml`**: Worker config with KV namespace binding (FAILED_UPDATES)
- **`package.json`**: NPM config
- **`README.md`**: Worker setup and deployment instructions

### Tests (`tests/`)

Per-platform and per-component integration tests. Run from project root: `python -m pytest tests/`
- **`test_bluesky.py`** — Bluesky posting test
- **`test_config.py`** — Credential status check
- **`test_e2e.py`** — End-to-end test (supports `--platform` and `--dry-run`)
- **`test_instagram.py`** — Instagram posting test
- **`test_mastodon.py`** — Mastodon posting test
- **`test_media_handler.py`** — Media handler test
- **`test_platform_router.py`** — Platform router logic test
- **`test_queue.py`** — Queue manager test
- **`test_reddit.py`** — Reddit posting test
- **`test_retry.py`** — Retry logic test
- **`test_router_quick.py`** — Quick router smoke test
- **`test_telegram.py`** — Telegram posting test
- **`test_twitter.py`** — Twitter posting test

### Examples (`examples/`)

Reference code showing how to use libraries and subsystems:
- **`complete_workflow.py`** — Full config → media → queue → post flow
- **`media_usage.py`** — Media handler usage
- **`queue_integration.py`** — Queue manager integration
- **`queue_quick_reference.py`** — Quick-reference code snippets

### Scripts (`scripts/`)

- **`init_db.py`**: Create database tables and initial setup
- **`migrate.py`**: Apply database schema migrations
- **`setup_youtube_auth.py`**: One-time YouTube OAuth2 token generation

### Documentation (`docs/`)

- **`PROJECT_STRUCTURE.md`**: This file
- **`PLATFORM_ROUTER_SUMMARY.md`**: Platform router feature overview
- **`QUEUE_MANAGER_SUMMARY.md`**: Queue manager feature overview
- **`RENDER_DEPLOYMENT.md`**: Step-by-step Render.com deployment guide

### Storage Directories

- **`media/`**: Temporary storage for downloaded media files (auto-cleaned after posting)
- **`logs/`**: Application log files (rotated automatically)

## Data Flow

```
1. User sends media to Telegram bot
   ↓
2. Telegram sends webhook to Cloudflare Worker
   ↓
3. Cloudflare Worker forwards to FastAPI backend (/webhook endpoint)
   ↓
4. Backend downloads media, creates jobs for each platform
   ↓
5. Jobs are scheduled with 1-hour delay between each
   ↓
6. Background worker processes jobs at scheduled times
   ↓
7. Platform-specific services post content
   ↓
8. Job status updated (completed/failed)
   ↓
9. Failed jobs are retried (max 3 attempts)
```

## Configuration Files

### `.env` Requirements
See `.env.example` for a complete list. Required variables include:
- API keys for each platform
- Database path
- Media storage path
- Cloudflare Worker URL
- Scheduling parameters

### `requirements.txt`
All Python dependencies with pinned versions:
- FastAPI and Uvicorn (web framework)
- SQLAlchemy and aiosqlite (database)
- APScheduler (task scheduling)
- Platform-specific SDKs (Telegram, Bluesky, Mastodon, etc.)
- Pillow and python-magic (media processing)
- Loguru (logging)

## Development Workflow

1. Copy `.env.example` to `.env` and fill in credentials
2. Install dependencies: `pip install -r requirements.txt`
3. Initialize database: `python scripts/init_db.py`
4. Run locally: `uvicorn app.main:app --reload`
5. Deploy Cloudflare Worker: `cd cloudflare-worker && wrangler deploy`
6. Deploy to Render.com
7. Set Telegram webhook to Cloudflare Worker URL

## Status

All core components are implemented:

- **8 platform integrations**: Telegram, Bluesky, Mastodon, Instagram, Threads, Twitter/X, Reddit, YouTube
- **FastAPI server** with webhook, health, queue, and cancel endpoints
- **Cloudflare Worker** with KV-backed retry for failed forwards
- **SQLite job queue** with background processor and cancellation support
- **Render.com deployment** config with persistent disk
- **End-to-end test** with `--platform` and `--dry-run` flags
- **Per-platform tests** for each integration
