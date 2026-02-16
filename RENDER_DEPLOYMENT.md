**Pre-Deploy Checklist**
- Run `python setup_youtube_auth.py` locally to generate `youtube_token.json` and keep it safe.
- Set all environment variables in Render (use the list in render.yaml; set `MEDIA_STORAGE_PATH` to `/media`).
- Deploy the Cloudflare Worker first and confirm it returns 200 for test requests.
- Register the Telegram webhook last to point at the Worker URL.

**Post-Deploy Test Sequence**
- Health check: open `https://<your-render-app>.onrender.com/health` and confirm status is ok and queue counts are present.
- Send a test Telegram message to your bot and watch Render logs for the webhook receipt and queued job IDs.
- Check `GET /queue` and confirm the new job appears with `pending` status.
- Wait for the configured delay and verify the job transitions to `completed` or `failed` in logs and the queue.

**Common Render Free Tier Issues and Fixes**
- Cold start delays: expect the first webhook to take several seconds; the Worker wake-up and async processing handle this. If you see missed updates, use the Worker `/retry` endpoint.
- Disk persistence: only files under `/media` persist across deploys; ensure `MEDIA_STORAGE_PATH=/media` and avoid writing elsewhere.
- Memory limits with large video files: reduce file sizes, increase compression, or move large uploads to external storage; avoid concurrent large uploads.
