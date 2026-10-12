"""Lire ce que tape l'utilisateur : texte -> date, moment, minutes.

Chaque erreur de format devient une InvalidError avec une phrase claire.
"""

from datetime import date, datetime

from deauville.errors import InvalidError


def parse_day(text: str) -> date:
    """Texte -> journée, ou InvalidError avec une phrase."""
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise InvalidError(f"{text!r} is not a day, use YYYY-MM-DD.") from None


def parse_moment(text: str) -> datetime:
    """Texte -> moment, ou InvalidError avec une phrase."""
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise InvalidError(f"{text!r} is not a moment, use YYYY-MM-DDTHH:MM.") from None


def parse_minutes(text: str) -> int:
    """Texte -> nombre de minutes, ou InvalidError avec une phrase."""
    try:
        return int(text)
    except ValueError:
        raise InvalidError(f"{text!r} is not a number of minutes.") from None
