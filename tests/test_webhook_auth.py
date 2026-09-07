import hashlib
import hmac
import time

from app.api.webhooks import _verify_slack_signature
from app.config import settings


def _sign(body: bytes, timestamp: str, secret: str) -> str:
    base_string = f"v0:{timestamp}:{body.decode('utf-8')}"
    return "v0=" + hmac.new(secret.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha256).hexdigest()


def test_valid_signature_is_accepted(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", "test-secret")
    body = b"text=hello&channel_id=C123"
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp, "test-secret")

    assert _verify_slack_signature(body, timestamp, signature) is True


def test_wrong_secret_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", "test-secret")
    body = b"text=hello"
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp, "wrong-secret")

    assert _verify_slack_signature(body, timestamp, signature) is False


def test_stale_timestamp_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", "test-secret")
    body = b"text=hello"
    old_timestamp = str(int(time.time()) - 60 * 10)  # 10 minutes old
    signature = _sign(body, old_timestamp, "test-secret")

    assert _verify_slack_signature(body, old_timestamp, signature) is False


def test_missing_signing_secret_rejects_everything(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", None)
    body = b"text=hello"
    timestamp = str(int(time.time()))

    assert _verify_slack_signature(body, timestamp, "v0=anything") is False
