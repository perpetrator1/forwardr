# Project Structure

Complete folder and file structure for the Forwardr social media automation system.

```
forwardr/
│
├── .env.example                          # Environment variables template with comments
├── .gitignore                            # Git ignore rules
├── README.md                             # Project documentation and setup guide
├── requirements.txt                      # Python dependencies with pinned versions
│
├── app/                                  # Main application directory
│   ├── __init__.py                       # App package initialization
│   ├── main.py                           # FastAPI application entry point
│   ├── config.py                         # Configuration management (Pydantic Settings)
│   ├── database.py                       # Database connection and session management
│   │
│   ├── api/                              # API endpoints
│   │   ├── __init__.py
│   │   ├── webhook.py                    # Webhook endpoints (receives from Cloudflare)
│   │   └── admin.py                      # Admin/monitoring endpoints
│   │
│   ├── models/                           # Database models (SQLAlchemy)
│   │   ├── __init__.py
│   │   ├── job.py                        # Job queue model
│   │   └── post.py                       # Post data model
│   │
│   ├── services/                         # Business logic layer
│   │   ├── __init__.py
│   │   ├── queue.py                      # Job queue management
│   │   ├── scheduler.py                  # Post scheduling and timing
│   │   │
│   │   └── platforms/                    # Platform-specific integrations
│   │       ├── __init__.py
│   │       ├── telegram.py               # Telegram Channel posting
│   │       ├── bluesky.py                # Bluesky (AT Protocol) posting
│   │       ├── mastodon.py               # Mastodon posting
│   │       ├── instagram.py              # Instagram posting
│   │       ├── threads.py                # Threads (Meta) posting
│   │       ├── twitter.py                # Twitter/X posting
│   │       ├── reddit.py                 # Reddit posting
│   │       ├── youtube.py                # YouTube posting
│   │       └── website.py                # Personal website posting
│   │
│   ├── utils/                            # Utility functions
│   │   ├── __init__.py
│   │   ├── media.py                      # Media download/processing utilities
│   │   └── logger.py                     # Logging configuration
│   │
│   └── workers/                          # Background workers
│       ├── __init__.py
│       └── poster.py                     # Background job processor
│
├── cloudflare-worker/                    # Cloudflare Worker for webhook receiving
│   ├── worker.js                         # Worker script (receives Telegram webhooks)
│   ├── wrangler.toml                     # Cloudflare Worker configuration
│   ├── package.json                      # NPM package configuration
│   └── README.md                         # Worker-specific documentation
│
├── tests/                                # Test suite
│   ├── __init__.py
│   ├── test_api.py                       # API endpoint tests
│   ├── test_services.py                  # Service layer tests
│   └── test_platforms.py                 # Platform integration tests
│
├── scripts/                              # Utility scripts
│   ├── __init__.py
│   ├── init_db.py                        # Database initialization
│   └── migrate.py                        # Database migrations
│
├── media/                                # Temporary media storage
│   └── .gitkeep                          # Keep directory in git
│
└── logs/                                 # Application logs
    └── .gitkeep                          # Keep directory in git
```

## File Purposes

### Root Level Files

- **`.env.example`**: Template for environment variables with detailed comments explaining each variable
- **`.gitignore`**: Specifies files and directories to exclude from version control
- **`README.md`**: Complete project documentation, setup instructions, and usage guide
- **`requirements.txt`**: All Python dependencies with pinned versions for reproducibility

### Application Layer (`app/`)

#### Core Files
- **`main.py`**: FastAPI application initialization, middleware, and route registration
- **`config.py`**: Centralized configuration using Pydantic Settings (loads from .env)
- **`database.py`**: SQLAlchemy database setup, session management, and connection handling

#### API Layer (`app/api/`)
- **`webhook.py`**: Receives webhook payloads from Cloudflare Worker (Telegram messages)
- **`admin.py`**: Administrative endpoints for queue monitoring and manual operations

#### Data Models (`app/models/`)
- **`job.py`**: SQLAlchemy model for job queue (status, platform, timing, retries)
- **`post.py`**: SQLAlchemy model for post data (media, caption, metadata)

#### Services Layer (`app/services/`)
- **`queue.py`**: Queue management logic (add jobs, update status, handle retries)
- **`scheduler.py`**: Calculate post times, manage 1-hour delays between platforms

##### Platform Integrations (`app/services/platforms/`)
Each file contains platform-specific posting logic:
- **`telegram.py`**: Post to Telegram Channel using python-telegram-bot
- **`bluesky.py`**: Post to Bluesky using AT Protocol SDK
- **`mastodon.py`**: Post to Mastodon using Mastodon.py
- **`instagram.py`**: Post to Instagram using instagrapi
- **`threads.py`**: Post to Threads using threads-api
- **`twitter.py`**: Post to Twitter/X using tweepy
- **`reddit.py`**: Post to Reddit using praw
- **`youtube.py`**: Upload to YouTube using Google API client
- **`website.py`**: Post to personal website via custom API

#### Utilities (`app/utils/`)
- **`media.py`**: Download media from Telegram, process images/videos, manage storage
- **`logger.py`**: Configure structured logging with loguru

#### Workers (`app/workers/`)
- **`poster.py`**: Background worker that processes the job queue and posts to platforms

### Cloudflare Worker (`cloudflare-worker/`)

- **`worker.js`**: Receives Telegram webhooks and forwards to FastAPI backend
- **`wrangler.toml`**: Cloudflare Worker configuration (name, environment variables)
- **`package.json`**: NPM dependencies and scripts
- **`README.md`**: Worker-specific setup and deployment instructions

### Tests (`tests/`)

- **`test_api.py`**: Test webhook endpoints and admin API
- **`test_services.py`**: Test queue management and scheduling logic
- **`test_platforms.py`**: Test each platform integration (mock API calls)

### Scripts (`scripts/`)

- **`init_db.py`**: Create database tables and initial setup
- **`migrate.py`**: Apply database schema migrations

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

## Next Steps

After the scaffold is complete, the following logic needs to be implemented:

1. **FastAPI application** (`app/main.py`)
2. **Database models** (`app/models/`)
3. **Configuration management** (`app/config.py`)
4. **API endpoints** (`app/api/`)
5. **Queue and scheduling services** (`app/services/`)
6. **Platform integrations** (`app/services/platforms/`)
7. **Background worker** (`app/workers/poster.py`)
8. **Cloudflare Worker logic** (`cloudflare-worker/worker.js`)
9. **Database initialization** (`scripts/init_db.py`)
10. **Tests** (`tests/`)
