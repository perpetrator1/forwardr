"""
Tests for owner-only authentication in the webhook endpoint.
"""
import os
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set required env vars for all tests."""
    monkeypatch.setenv("API_SECRET_KEY", "test-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "111111")
    monkeypatch.setenv("FORWARDR_SKIP_KV_FETCH", "1")


@pytest.fixture
def client():
    # Reimport to pick up env changes
    import importlib
    import app.config
    importlib.reload(app.config)
    import app.main
    importlib.reload(app.main)
    with TestClient(app.main.app) as c:
        yield c


def _make_update(from_id: int, text: str = "", photo: bool = False):
    """Build a minimal Telegram update payload."""
    message = {
        "message_id": 1,
        "from": {"id": from_id, "is_bot": False, "first_name": "Test"},
        "chat": {"id": from_id, "type": "private"},
        "date": 1700000000,
    }
    if photo:
        message["photo"] = [
            {"file_id": "abc123", "file_unique_id": "x", "width": 100, "height": 100, "file_size": 1234}
        ]
        message["caption"] = "test caption"
    else:
        message["text"] = text or "hello"
    return {"update_id": 12345, **{"message": message}}


class TestWebhookAuth:
    """Webhook rejects without valid API key."""

    def test_missing_api_key(self, client):
        resp = client.post("/webhook", json=_make_update(111111))
        assert resp.status_code == 401

    def test_wrong_api_key(self, client):
        resp = client.post(
            "/webhook",
            json=_make_update(111111),
            headers={"X-API-Key": "wrong"},
        )
        assert resp.status_code == 401

    def test_valid_api_key_accepted(self, client):
        resp = client.post(
            "/webhook",
            json=_make_update(111111),
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"


class TestOwnerOnly:
    """Webhook silently ignores messages from non-owner users."""

    @patch("app.main._process_webhook", new_callable=AsyncMock)
    def test_owner_message_processed(self, mock_process, client):
        resp = client.post(
            "/webhook",
            json=_make_update(111111, text="hello"),
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200

    @patch("app.main._process_webhook", new_callable=AsyncMock)
    def test_non_owner_message_ignored(self, mock_process, client):
        """Non-owner update is accepted at HTTP level but _process_webhook
        should skip it (the owner check is inside _process_webhook)."""
        resp = client.post(
            "/webhook",
            json=_make_update(999999, text="hello"),
            headers={"X-API-Key": "test-key"},
        )
        # HTTP-level acceptance (to avoid leaking info)
        assert resp.status_code == 200


class TestProcessQueue:
    """Tests for the /process-queue endpoint."""

    def test_process_queue_requires_api_key(self, client):
        resp = client.post("/process-queue")
        assert resp.status_code == 401

    @patch("app.main._get_qm")
    def test_process_queue_idle(self, mock_qm, client):
        mock_qm.return_value.process_next_job.return_value = {
            "status": "idle",
            "message": "No pending jobs",
        }
        resp = client.post(
            "/process-queue",
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "idle"

    @patch("app.main._get_qm")
    def test_process_queue_processes_job(self, mock_qm, client):
        mock_qm.return_value.process_next_job.return_value = {
            "status": "completed",
            "job_id": 1,
            "platform": "bluesky",
            "message": "Job #1 for bluesky completed",
        }
        resp = client.post(
            "/process-queue",
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["platform"] == "bluesky"
