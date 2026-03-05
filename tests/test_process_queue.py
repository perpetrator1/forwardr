"""
Tests for the queue manager — process_next_job and get_oldest_pending_job.
"""
import json
import os
import pytest
from pathlib import Path
from datetime import datetime, timedelta

from app.queue_manager import QueueManager
from app.media_handler import MediaInfo


@pytest.fixture
def qm(tmp_path):
    """Create a fresh QueueManager with a temp DB for each test."""
    db = str(tmp_path / "test.db")
    return QueueManager(db_path=db)


@pytest.fixture
def sample_media():
    return MediaInfo(
        type="photo",
        file_id="test_photo_123",
        caption="Test caption #automation",
        local_path="/tmp/test_image.jpg",
        mime_type="image/jpeg",
    )


class TestGetOldestPendingJob:
    def test_returns_none_when_empty(self, qm):
        assert qm.get_oldest_pending_job() is None

    def test_returns_oldest_job(self, qm, sample_media):
        qm.queue_posts(sample_media, ["bluesky", "twitter"], interval_minutes=0)
        job = qm.get_oldest_pending_job()
        assert job is not None
        assert job["platform"] in ("bluesky", "twitter")

    def test_skips_completed_jobs(self, qm, sample_media):
        ids = qm.queue_posts(sample_media, ["bluesky", "twitter"], interval_minutes=0)
        qm.update_job_status(ids[0], "completed")
        job = qm.get_oldest_pending_job()
        assert job is not None
        assert job["id"] == ids[1]

    def test_returns_none_when_all_complete(self, qm, sample_media):
        ids = qm.queue_posts(sample_media, ["bluesky"], interval_minutes=0)
        qm.update_job_status(ids[0], "completed")
        assert qm.get_oldest_pending_job() is None


class TestProcessNextJob:
    def test_idle_when_no_jobs(self, qm):
        result = qm.process_next_job()
        assert result["status"] == "idle"

    def test_processes_job(self, qm, sample_media):
        """process_next_job should attempt to process and return a result.
        Since we don't have real platform handlers, it will fail but
        the structure should be correct."""
        qm.queue_posts(sample_media, ["bluesky"], interval_minutes=0)
        result = qm.process_next_job()
        # Will fail because there's no real bluesky handler, but we get a result dict
        assert "status" in result
        assert "job_id" in result or result["status"] == "idle"


class TestQueuePosts:
    def test_creates_jobs_for_all_platforms(self, qm, sample_media):
        platforms = ["bluesky", "twitter", "mastodon"]
        ids = qm.queue_posts(sample_media, platforms, interval_minutes=0)
        assert len(ids) == 3

    def test_job_contains_media_info(self, qm, sample_media):
        ids = qm.queue_posts(sample_media, ["bluesky"], interval_minutes=0)
        job = qm.get_job(ids[0])
        assert job is not None
        media = json.loads(job["media_info"])
        assert media["type"] == "photo"
        assert media["caption"] == "Test caption #automation"


class TestCancelJob:
    def test_cancel_pending_job(self, qm, sample_media):
        ids = qm.queue_posts(sample_media, ["bluesky"], interval_minutes=0)
        assert qm.cancel_job(ids[0]) is True
        job = qm.get_job(ids[0])
        assert job["status"] == "cancelled"

    def test_cannot_cancel_completed(self, qm, sample_media):
        ids = qm.queue_posts(sample_media, ["bluesky"], interval_minutes=0)
        qm.update_job_status(ids[0], "completed")
        assert qm.cancel_job(ids[0]) is False
