"""
FastAPI application entry point.

The server is designed for Render's free tier spin-up/spin-down lifecycle:
- /webhook     receives Telegram updates forwarded by the Cloudflare Worker
- /process-queue  processes the oldest pending job (called by CF Worker cron)
- /health, /queue  monitoring endpoints
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from app.config import settings, ENABLED_PLATFORMS
from app.media_handler import MediaHandler
from app.queue_manager import get_queue_manager
from app.services.platforms import determine_platforms, get_loaded_handlers

logger = logging.getLogger(__name__)

_queue_manager = None


def _get_expected_api_key() -> str:
	return settings.core.api_key or os.getenv("API_SECRET_KEY", "")


def _get_qm():
	"""Get or initialise the queue manager singleton."""
	global _queue_manager
	if _queue_manager is None:
		_queue_manager = get_queue_manager()
	return _queue_manager


def _validate_api_key(x_api_key: Optional[str]) -> None:
	"""Raise 401 if the API key doesn't match."""
	expected_key = _get_expected_api_key()
	if not expected_key or x_api_key != expected_key:
		raise HTTPException(status_code=401, detail="Unauthorized")


def _validate_config() -> None:
	if not _get_expected_api_key():
		logger.warning("API key is not configured. Set API_SECRET_KEY or api_key.")
	if not settings.telegram.bot_token:
		logger.warning("Telegram bot token is missing. Webhook processing will fail.")
	if not ENABLED_PLATFORMS:
		logger.warning("No platforms enabled. Check platform credentials.")


async def _process_webhook(update: Dict) -> None:
	try:
		bot_token = settings.telegram.bot_token
		if not bot_token:
			logger.error("Cannot process webhook without Telegram bot token")
			return

		message = (
			update.get("message")
			or update.get("edited_message")
			or update.get("channel_post")
			or update.get("edited_channel_post")
		)
		if not message:
			logger.error("Webhook payload missing Telegram message")
			return

		# Owner-only check (defence-in-depth — CF Worker already filters)
		owner_id = settings.telegram.owner_id or os.getenv("TELEGRAM_OWNER_ID", "")
		if owner_id:
			sender_id = str(message.get("from", {}).get("id", ""))
			if sender_id and sender_id != owner_id:
				logger.warning(f"Ignoring message from non-owner: {sender_id}")
				return

		# Skip bot commands — those are handled by the CF Worker
		text = message.get("text", "")
		if text.startswith("/"):
			logger.info(f"Skipping bot command (handled by CF Worker): {text}")
			return

		handler = MediaHandler(bot_token, settings.core.media_path)
		media_info = handler.parse_telegram_message(message)

		if media_info.type != "text":
			media_info = await handler.download_telegram_media(media_info)

		platforms = determine_platforms(media_info.to_dict())
		if not platforms:
			logger.warning("No available platforms for this media type")
			return

		qm = _get_qm()
		# Queue with no delay — the cron will process them one at a time
		qm.queue_posts(
			media_info, 
			platforms,
			start_delay_minutes=0,
			interval_minutes=0
		)
	except Exception as exc:
		logger.error(f"Webhook processing failed: {exc}", exc_info=True)


@asynccontextmanager
async def _lifespan(application: FastAPI):
	"""Startup / shutdown lifecycle."""
	_validate_config()
	logger.info(f"Enabled platforms: {', '.join(ENABLED_PLATFORMS) if ENABLED_PLATFORMS else 'none'}")
	logger.info(f"Loaded handlers: {', '.join(get_loaded_handlers())}")
	yield


app = FastAPI(title="Forwardr", lifespan=_lifespan)


@app.post("/webhook")
async def webhook(
	request: Request,
	background_tasks: BackgroundTasks,
	x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
	_validate_api_key(x_api_key)
	update = await request.json()

	# Process asynchronously to return quickly to the webhook sender.
	background_tasks.add_task(_process_webhook, update)

	return {"status": "accepted"}


@app.post("/process-queue")
async def process_queue(
	x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
	"""
	Process the oldest pending job in the queue.
	Called by the Cloudflare Worker cron trigger every 5 hours.
	"""
	_validate_api_key(x_api_key)

	qm = _get_qm()
	result = qm.process_next_job()

	logger.info(f"process-queue result: {result}")
	return result


@app.get("/health")
def health() -> Dict:
	qm = _get_qm()
	status_counts = qm.get_queue_status()
	return {
		"status": "ok",
		"queue": status_counts,
		"enabled_platforms": ENABLED_PLATFORMS,
	}


@app.get("/queue")
def queue_list() -> Dict:
	qm = _get_qm()
	jobs = qm.get_all_jobs()
	return {"jobs": jobs}


@app.delete("/queue/{job_id}")
def queue_cancel(job_id: int) -> Dict:
	qm = _get_qm()
	success = qm.cancel_job(job_id)
	if not success:
		raise HTTPException(status_code=400, detail="Job not pending or not found")
	return {"status": "cancelled", "job_id": job_id}
