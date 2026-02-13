# Cloudflare Worker

This directory contains the Cloudflare Worker that receives Telegram webhooks and forwards them to the FastAPI backend.

## Setup

1. Install Wrangler CLI:
```bash
npm install -g wrangler
```

2. Login to Cloudflare:
```bash
wrangler login
```

3. Update `wrangler.toml` with your settings:
   - Set your worker name
   - Configure environment variables

4. Set secrets:
```bash
wrangler secret put API_SECRET_KEY
wrangler secret put FASTAPI_BACKEND_URL
```

5. Deploy:
```bash
wrangler deploy
```

## Environment Variables

- `FASTAPI_BACKEND_URL`: URL of your FastAPI backend on Render.com
- `API_SECRET_KEY`: Secret key for authenticating requests to the backend

## Testing Locally

```bash
wrangler dev
```

This will start a local development server for testing the worker.
