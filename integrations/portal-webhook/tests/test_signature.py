import hashlib
import hmac

from signature import is_valid

SECRET = "test-secret"
BODY = b'{"id":"evt_1","type":"application.submitted"}'
NOW = 1_800_000_000


def sign(secret, timestamp, body):
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={mac}"


def test_valid_signature_is_accepted():
    assert is_valid(BODY, sign(SECRET, NOW, BODY), SECRET, NOW)


def test_wrong_secret_is_rejected():
    assert not is_valid(BODY, sign("wrong-secret", NOW, BODY), SECRET, NOW)


def test_changed_body_is_rejected():
    header = sign(SECRET, NOW, BODY)
    assert not is_valid(BODY + b" ", header, SECRET, NOW)


def test_old_timestamp_is_rejected():
    old = NOW - 301
    assert not is_valid(BODY, sign(SECRET, old, BODY), SECRET, NOW)


def test_malformed_headers_are_rejected():
    assert not is_valid(BODY, "", SECRET, NOW)
    assert not is_valid(BODY, "garbage", SECRET, NOW)
    assert not is_valid(BODY, "t=abc,v1=123", SECRET, NOW)
