"""
End-to-end integration test for Forwardr.
"""
import argparse
import json
import logging
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
import uvicorn

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _create_test_image(media_dir: Path) -> Path:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for this test") from exc

    media_dir.mkdir(parents=True, exist_ok=True)
    image_path = media_dir / "test_e2e.jpg"
    image = Image.new("RGB", (800, 800), color=(32, 64, 128))
    image.save(image_path)
    return image_path


def _build_telegram_payload(caption: str, file_id: str) -> Dict:
    now = int(time.time())
    return {
        "update_id": now,
        "message": {
            "message_id": 1,
            "date": now,
            "chat": {"id": 12345, "type": "private"},
            "photo": [
                {
                    "file_id": file_id,
                    "file_size": 1000,
                    "width": 800,
                    "height": 800,
                }
            ],
            "caption": caption,
        },
    }


def _wait_for_health(url: str, timeout: int = 20) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return
        except requests.RequestException:
            time.sleep(0.5)
    raise RuntimeError("Server did not become healthy in time")


def _wait_for_jobs(queue_manager, timeout: int = 30) -> List[Dict]:
    start = time.time()
    while time.time() - start < timeout:
        jobs = queue_manager.get_all_jobs(limit=200)
        if jobs:
            return jobs
        time.sleep(0.5)
    raise RuntimeError("Jobs were not queued in time")


def _wait_for_completion(queue_manager, timeout: int = 120) -> List[Dict]:
    start = time.time()
    while time.time() - start < timeout:
        jobs = queue_manager.get_all_jobs(limit=200)
        if jobs and all(job["status"] != "pending" for job in jobs):
            return jobs
        time.sleep(1)
    raise RuntimeError("Jobs did not complete in time")


def _summarize_jobs(jobs: List[Dict]) -> Dict[str, List[str]]:
    summary = {"completed": [], "failed": [], "pending": [], "cancelled": []}
    for job in jobs:
        status = job.get("status") or "pending"
        platform = job.get("platform") or "unknown"
        if status not in summary:
            summary[status] = []
        summary[status].append(platform)
    return summary


def _start_server(app, port: int) -> uvicorn.Server:
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Forwardr end-to-end test")
    parser.add_argument("--platform", help="Test a single platform")
    parser.add_argument("--dry-run", action="store_true", help="Mock platform calls")
    args = parser.parse_args()

    _configure_logging()

    temp_dir = Path(tempfile.mkdtemp(prefix="forwardr-e2e-"))
    db_path = temp_dir / "forwardr_test.db"
    media_dir = temp_dir / "media"
    image_path = _create_test_image(media_dir)

    os.environ["API_SECRET_KEY"] = "test-secret"
    os.environ["TELEGRAM_BOT_TOKEN"] = "test-telegram-token"

    try:
        from app.queue_manager import QueueManager
        from app import main as app_main
        from app import media_handler
        from app import services
        from app.services import platforms as platforms_module

        queue_manager = QueueManager(db_path=str(db_path), check_interval=1)

        def queue_posts_fast(media_info, platforms, start_delay_minutes=0, interval_minutes=60):
            return QueueManager.queue_posts(
                queue_manager,
                media_info,
                platforms,
                start_delay_minutes=0,
                interval_minutes=0.05,
            )

        queue_manager.queue_posts = queue_posts_fast
        app_main._queue_manager = queue_manager
        app_main.get_queue_manager = lambda: queue_manager

        async def fake_download(self, media_info_obj):
            media_info_obj.local_path = str(image_path)
            return media_info_obj

        media_handler.MediaHandler.download_telegram_media = fake_download

        if args.platform:
            def forced_platforms(_media_info: Dict) -> List[str]:
                return [args.platform]

            app_main.determine_platforms = forced_platforms
        elif args.dry_run:
            def all_platforms(_media_info: Dict) -> List[str]:
                return [
                    "telegram",
                    "bluesky",
                    "mastodon",
                    "instagram",
                    "threads",
                    "twitter",
                    "reddit",
                    "website",
                ]

            app_main.determine_platforms = all_platforms

        results: Dict[str, bool] = {}

        if args.dry_run:
            def mock_post_to_platform(platform: str, _media_info: Dict) -> bool:
                results[platform] = True
                return True

            platforms_module.post_to_platform = mock_post_to_platform

        server = _start_server(app_main.app, port=8001)
        _wait_for_health("http://127.0.0.1:8001/health")

        payload = _build_telegram_payload("Forwardr e2e test\nSecond line", "test-file-id")
        response = requests.post(
            "http://127.0.0.1:8001/webhook",
            headers={"X-API-Key": "test-secret"},
            data=json.dumps(payload),
            timeout=10,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Webhook failed: {response.status_code} {response.text}")

        jobs = _wait_for_jobs(queue_manager)
        logger.info(f"Queued {len(jobs)} job(s)")

        jobs = _wait_for_completion(queue_manager)
        summary = _summarize_jobs(jobs)

        logger.info("Job results:")
        for status, platforms in summary.items():
            if platforms:
                logger.info(f"  {status}: {', '.join(platforms)}")

    finally:
        try:
            if 'server' in locals():
                server.should_exit = True
        except Exception:
            pass

        try:
            queue_manager.stop_processor()
        except Exception:
            pass

        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
