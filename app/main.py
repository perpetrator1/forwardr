"""
FastAPI application entry point.
"""
import asyncio
import logging
import os
import threading
from typing import Dict, Optional

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from app.config import settings, ENABLED_PLATFORMS
from app.media_handler import MediaHandler
from app.queue_manager import get_queue_manager
from app.services.platforms import determine_platforms, get_loaded_handlers

logger = logging.getLogger(__name__)

app = FastAPI(title="Forwardr")

_queue_manager = None
_processor_lock = threading.Lock()


def _get_expected_api_key() -> str:
	return settings.core.api_key or os.getenv("API_SECRET_KEY", "")


def _ensure_processor_running() -> None:
	global _queue_manager
	if _queue_manager is None:
		_queue_manager = get_queue_manager()
	if _queue_manager._processor_running:
		return

	with _processor_lock:
		if not _queue_manager._processor_running:
			_queue_manager.start_processor()


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

		handler = MediaHandler(bot_token, settings.core.media_path)
		media_info = handler.parse_telegram_message(message)

		if media_info.type != "text":
			media_info = await handler.download_telegram_media(media_info)

		platforms = determine_platforms(media_info.to_dict())
		if not platforms:
			logger.warning("No available platforms for this media type")
			return

		_ensure_processor_running()
		_queue_manager.queue_posts(media_info, platforms)
	except Exception as exc:
		logger.error(f"Webhook processing failed: {exc}", exc_info=True)


@app.on_event("startup")
async def on_startup() -> None:
	_validate_config()
	logger.info(f"Enabled platforms: {', '.join(ENABLED_PLATFORMS) if ENABLED_PLATFORMS else 'none'}")
	logger.info(f"Loaded handlers: {', '.join(get_loaded_handlers())}")
	_ensure_processor_running()


@app.on_event("shutdown")
async def on_shutdown() -> None:
	if _queue_manager is not None:
		_queue_manager.stop_processor()


@app.post("/webhook")
async def webhook(
	request: Request,
	background_tasks: BackgroundTasks,
	x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
	expected_key = _get_expected_api_key()
	if not expected_key or x_api_key != expected_key:
		raise HTTPException(status_code=401, detail="Unauthorized")

	update = await request.json()

	# Process asynchronously to return quickly to the webhook sender.
	background_tasks.add_task(_process_webhook, update)

	return {"status": "accepted"}


@app.get("/health")
def health() -> Dict:
	_ensure_processor_running()
	status_counts = _queue_manager.get_queue_status()
	return {
		"status": "ok",
		"queue": status_counts,
		"enabled_platforms": ENABLED_PLATFORMS,
	}


@app.get("/queue")
def queue_list() -> Dict:
	_ensure_processor_running()
	jobs = _queue_manager.get_all_jobs()
	return {"jobs": jobs}


@app.delete("/queue/{job_id}")
def queue_cancel(job_id: int) -> Dict:
	_ensure_processor_running()
	success = _queue_manager.cancel_job(job_id)
	if not success:
		raise HTTPException(status_code=400, detail="Job not pending or not found")
	return {"status": "cancelled", "job_id": job_id}
