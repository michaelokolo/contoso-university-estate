import hashlib
import hmac

MAX_AGE_SECONDS = 300


def parse_signature(header: str) -> tuple[int, str] | None:
    try:
        parts = dict(item.split("=", 1) for item in header.split(","))
        return int(parts["t"]), parts["v1"]
    except (KeyError, ValueError):
        return None

def is_valid(body: bytes, header: str, secret: str, now: float) -> bool:
    parsed = parse_signature(header)
    if parsed is None:
        return False
    timestamp, received = parsed
    if abs(now - timestamp) > MAX_AGE_SECONDS:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)
