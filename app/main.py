"""
FastAPI application entry point.

The server is designed for Render's free tier spin-up/spin-down lifecycle:
- /webhook     receives Telegram updates forwarded by the Cloudflare Worker
- /process-queue  processes the oldest pending job (called by CF Worker cron)
- /health, /queue  monitoring endpoints

A lightweight background loop also processes due jobs every 60 seconds so
scheduled posts are picked up even if the CF Worker cron fails to reach the
server.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from app.config import settings
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
	if not settings.enabled_platforms:
		logger.warning("No platforms enabled. Check platform credentials.")


async def _send_telegram_msg(bot_token: str, chat_id: str, text: str) -> None:
	"""Send a notification message back to the user via Telegram."""
	if not bot_token or not chat_id:
		return
	try:
		url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
		async with httpx.AsyncClient() as client:
			await client.post(url, json={
				"chat_id": chat_id,
				"text": text,
				"parse_mode": "HTML",
			}, timeout=10)
	except Exception as e:
		logger.warning(f"Telegram notification failed: {e}")


def _format_results(results: List[Dict], header: str = "\U0001f4ca <b>Results:</b>") -> str:
	"""Format a list of job results into a single Telegram message."""
	lines = [header]
	for r in results:
		platform = r.get("platform", "unknown")
		if r.get("success"):
			url_text = f"\n   {r['post_url']}" if r.get("post_url") else ""
			lines.append(f"\u2705 <b>{platform}</b>{url_text}")
		else:
			lines.append(f"\u274c <b>{platform}</b> \u2014 failed (will retry)")
	return "\n".join(lines)


async def _process_webhook(update: Dict) -> None:
	try:
		# Refresh credentials from KV so newly-added platforms are picked up
		await settings.refresh_async()

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

		# Extract chat_id for sending notifications back
		chat_id = str(message.get("chat", {}).get("id", ""))

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

			# Upload to Cloudinary for persistent storage (survives container restarts)
			if media_info.local_path:
				try:
					from app.utils.cloudinary_config import upload_media_with_id, CLOUDINARY_AVAILABLE
					if CLOUDINARY_AVAILABLE:
						ext = media_info.local_path.rsplit('.', 1)[-1].lower()
						resource_type = 'video' if ext in ('mp4', 'mov', 'avi', 'mkv') else 'image'
						result = upload_media_with_id(media_info.local_path, resource_type)
						if result:
							media_info.cloudinary_url = result["url"]
							media_info.cloudinary_public_id = result["public_id"]
							logger.info(f"Media uploaded to Cloudinary: {result['public_id']}")
				except Exception as e:
					logger.warning(f"Cloudinary upload failed (will use local): {e}")

		platforms = determine_platforms(media_info.to_dict())
		if not platforms:
			logger.warning("No available platforms for this media type")
			await _send_telegram_msg(bot_token, chat_id,
				"\u26a0\ufe0f No platforms configured for this media type.\n"
				"Use /getcreds to check your setup.")
			return

		qm = _get_qm()
		interval_hours = settings.post_interval_hours

		job_ids, scheduled_time = qm.queue_posts(
			media_info,
			platforms,
			interval_hours=interval_hours,
			chat_id=chat_id,
		)

		now = datetime.utcnow()
		is_immediate = (scheduled_time - now).total_seconds() < 60

		if is_immediate:
			platform_list = ", ".join(platforms)
			await _send_telegram_msg(bot_token, chat_id,
				f"\U0001f4e4 <b>Posting now</b> to {platform_list}...")

			# Process all due jobs (the just-queued ones + any previously scheduled)
			results = qm.process_all_due_jobs()

			if results:
				summary = _format_results(results)
				await _send_telegram_msg(bot_token, chat_id, summary)
		else:
			# Scheduled for later — notify user
			time_str = scheduled_time.strftime("%b %d, %H:%M UTC")
			platform_list = ", ".join(platforms)
			await _send_telegram_msg(bot_token, chat_id,
				f"\U0001f4cb <b>Queued for posting</b>\n"
				f"Platforms: {platform_list}\n"
				f"\u23f0 Scheduled: {time_str}\n\n"
				f"Use /status to check queue status.")

			# Still process any OTHER jobs that are due from earlier schedules
			results = qm.process_all_due_jobs()
			if results:
				summary = _format_results(results,
					header="\U0001f4ca <b>Also processed from queue:</b>")
				await _send_telegram_msg(bot_token, chat_id, summary)

	except Exception as exc:
		logger.error(f"Webhook processing failed: {exc}", exc_info=True)


_QUEUE_POLL_INTERVAL = int(os.getenv("QUEUE_POLL_INTERVAL", "60"))  # seconds


async def _queue_processing_loop():
	"""Periodically process due jobs in the background.

	This ensures scheduled posts are picked up even when the external
	CF Worker cron trigger is unavailable (e.g. local dev, cold-start
	races).  The interval is intentionally short (default 60 s) so that
	posts go out close to their scheduled time.
	"""
	while True:
		await asyncio.sleep(_QUEUE_POLL_INTERVAL)
		try:
			await settings.refresh_async()
			qm = _get_qm()
			results = qm.process_all_due_jobs()

			# Notify users via Telegram for jobs processed in the background
			bot_token = settings.telegram.bot_token
			if bot_token and results:
				by_chat: Dict[str, list] = {}
				for r in results:
					cid = r.get("chat_id") or ""
					by_chat.setdefault(cid, []).append(r)
				for cid, chat_results in by_chat.items():
					if not cid:
						continue
					summary = _format_results(
						chat_results,
						header="\U0001f4ca <b>Scheduled posts processed:</b>",
					)
					await _send_telegram_msg(bot_token, cid, summary)

			if results:
				logger.info(f"Background loop processed {len(results)} jobs")
		except Exception as exc:
			logger.error(f"Background queue loop error: {exc}", exc_info=True)


@asynccontextmanager
async def _lifespan(application: FastAPI):
	"""Startup / shutdown lifecycle."""
	_validate_config()
	logger.info(f"Enabled platforms: {', '.join(settings.enabled_platforms) if settings.enabled_platforms else 'none'}")
	logger.info(f"Loaded handlers: {', '.join(get_loaded_handlers())}")

	# Launch the background queue-processing loop
	task = asyncio.create_task(_queue_processing_loop())
	logger.info(f"Background queue processor started (interval={_QUEUE_POLL_INTERVAL}s)")

	yield

	# Shutdown: cancel the background task
	task.cancel()
	try:
		await task
	except asyncio.CancelledError:
		pass


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
	Process all pending jobs that are due.
	Called by the Cloudflare Worker cron trigger.
	"""
	_validate_api_key(x_api_key)

	# Refresh credentials so newly-configured platforms are recognised
	await settings.refresh_async()

	qm = _get_qm()
	results = qm.process_all_due_jobs()

	# Send Telegram notifications grouped by chat_id
	bot_token = settings.telegram.bot_token
	if bot_token and results:
		by_chat: Dict[str, list] = {}
		for r in results:
			cid = r.get("chat_id") or ""
			by_chat.setdefault(cid, []).append(r)

		for cid, chat_results in by_chat.items():
			if not cid:
				continue
			summary = _format_results(chat_results,
				header="\U0001f4ca <b>Scheduled posts processed:</b>")
			await _send_telegram_msg(bot_token, cid, summary)

	next_scheduled = qm.get_next_scheduled_time()

	logger.info(f"process-queue: processed {len(results)} jobs, next_scheduled={next_scheduled}")
	return {
		"processed": len(results),
		"results": results,
		"next_scheduled": next_scheduled,
	}


@app.get("/health")
def health() -> Dict:
	try:
		qm = _get_qm()
		status_counts = qm.get_queue_status()
		next_scheduled = qm.get_next_scheduled_time()
	except Exception as exc:
		logger.error(f"Health check: DB unavailable: {exc}")
		return {
			"status": "degraded",
			"error": str(exc),
			"enabled_platforms": settings.enabled_platforms,
			"post_interval_hours": settings.post_interval_hours,
		}
	return {
		"status": "ok",
		"queue": status_counts,
		"next_scheduled": next_scheduled,
		"enabled_platforms": settings.enabled_platforms,
		"post_interval_hours": settings.post_interval_hours,
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
