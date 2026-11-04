"""Real-world mess. Each function damages a copy of the data the way real systems do.

Rates are deliberately small, like production: most records are fine, a few are not,
and the few are what break integrations.
"""

from __future__ import annotations

import random
from datetime import date, datetime

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def sis_date(d: date | None) -> str:
    """Legacy SIS (Oracle-style) date: 04-NOV-2026."""
    return "" if d is None else f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year}"


def finance_date(d: date | datetime | None) -> str:
    """Finance export date: UK format 04/11/2026."""
    return "" if d is None else d.strftime("%d/%m/%Y")


def money(pounds: int | float) -> str:
    """Finance export money: '9,535.00' (thousands separator, as a string)."""
    return f"{pounds:,.2f}"


def maybe_trailing_space(value: str, rng: random.Random, rate: float = 0.02) -> str:
    return value + " " if value and rng.random() < rate else value


def maybe_blank(value, rng: random.Random, rate: float = 0.02):
    return None if rng.random() < rate else value


def typo_email(email: str, rng: random.Random) -> str:
    """A second application from the same person often has a slightly different email."""
    local, _, domain = email.partition("@")
    options = [
        f"{local}@{domain.replace('.com', '.co')}" if ".com" in domain else f"{local}1@{domain}",
        f"{local.replace('.', '')}@{domain}",
        f"{local.upper()}@{domain}",
        f"{local}{rng.randint(1, 99)}@{domain}",
    ]
    return rng.choice(options)


def variant_name(first: str, last: str, rng: random.Random) -> tuple[str, str]:
    """Same person, typed differently: case, spaces, missing accents, hyphens."""
    choice = rng.randint(0, 4)
    if choice == 0:
        return first.lower(), last.upper()
    if choice == 1:
        return f" {first}", f"{last} "
    if choice == 2:
        strip = str.maketrans("ëéèçãáàíóúüöäñłšřøåŁÓÁ", "eeecaaaiouuoanlsroaLOA")
        return first.translate(strip), last.translate(strip)
    if choice == 3:
        return first, last.replace("-", " ").replace("'", "")
    return first[:1].upper() + first[1:], last


def invalid_email(email: str, rng: random.Random) -> str:
    return rng.choice([email.replace("@", ""), email.replace(".", ",", 1), email + "."])
