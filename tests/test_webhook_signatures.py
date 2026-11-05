import hashlib
import hmac
import time

from common.webhooks import sign


def verify(secret: str, header: str, body: bytes, tolerance: int = 300) -> bool:
    """The check a receiver (e.g. an Azure Function) must do."""
    parts = dict(p.split("=", 1) for p in header.split(","))
    ts = int(parts["t"])
    if abs(time.time() - ts) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])


def test_valid_signature_verifies():
    body = b'{"id":"evt_1"}'
    assert verify("s3cret", sign("s3cret", int(time.time()), body), body)


def test_wrong_secret_fails():
    body = b'{"id":"evt_1"}'
    assert not verify("s3cret", sign("other", int(time.time()), body), body)


def test_tampered_body_fails():
    header = sign("s3cret", int(time.time()), b'{"amount":"500.00"}')
    assert not verify("s3cret", header, b'{"amount":"5000.00"}')


def test_old_timestamp_fails():
    body = b'{"id":"evt_1"}'
    assert not verify("s3cret", sign("s3cret", int(time.time()) - 3600, body), body)
