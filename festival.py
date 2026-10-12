"""Le festival : lecture, sauvegarde, calculs et règles.

Ce module ne fait aucun print : il est partagé par main.py (ligne de commande)
et api.py (serveur web).
"""

import json
import unicodedata
from datetime import date, datetime, timedelta

DATA_FILE = "data/festival.json"

# Règle du festival : une journée se termine à 06:00. Un spectacle à 1 h du
# matin appartient donc à la journée de la veille.
FESTIVAL_DAY_CHANGE = timedelta(hours=6)

# Règles du brief pour programmer un spectacle.
MIN_DURATION = 1  # minutes
MAX_DURATION = 360  # minutes
GAP = timedelta(minutes=30)  # battement entre deux spectacles (salle ou artiste)


def load_festival(path: str) -> dict:
    """Lit le fichier JSON et le transforme en dict Python.

    Lève ValueError avec une phrase claire si le fichier manque ou est abîmé.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise ValueError(f"the data file {path} does not exist.") from None
    except json.JSONDecodeError as error:
        raise ValueError(
            f"the data file {path} is damaged (line {error.lineno})."
        ) from None


def save_festival(festival: dict, path: str) -> None:
    """Réécrit le fichier JSON avec les données à jour."""
    with open(path, "w", encoding="utf-8") as f:
        # ensure_ascii=False garde "é" lisible, indent=2 garde le fichier lisible.
        json.dump(festival, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_day(text: str) -> date:
    """Texte -> journée, ou ValueError avec une phrase."""
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{text!r} is not a day, use YYYY-MM-DD.") from None


def parse_moment(text: str) -> datetime:
    """Texte -> moment, ou ValueError avec une phrase."""
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{text!r} is not a moment, use YYYY-MM-DDTHH:MM.") from None


def parse_minutes(text: str) -> int:
    """Texte -> nombre de minutes, ou ValueError avec une phrase."""
    try:
        return int(text)
    except ValueError:
        raise ValueError(f"{text!r} is not a number of minutes.") from None


def slugify(name: str) -> str:
    """Transforme un nom en identifiant.

    "Théâtre des Planches" -> "theatre-des-planches"
    """
    # NFKD sépare "é" en "e" + accent, puis l'encodage ASCII supprime l'accent.
    decomposed = unicodedata.normalize("NFKD", name)
    plain = decomposed.encode("ascii", "ignore").decode("ascii")
    # On garde lettres et chiffres, et un seul tiret pour tout le reste.
    slug = ""
    for char in plain.lower():
        if char.isalnum():
            slug += char
        elif not slug.endswith("-"):
            slug += "-"
    return slug.strip("-")


def find_venue(festival: dict, slug: str) -> dict | None:
    """Renvoie la salle qui a cet identifiant, ou None si elle n'existe pas."""
    for venue in festival["venues"]:
        if slugify(venue["name"]) == slug:
            return venue
    return None


def find_artist(festival: dict, slug: str) -> dict | None:
    """Renvoie l'artiste qui a cet identifiant, ou None s'il n'existe pas."""
    for artist in festival["artists"]:
        if slugify(artist["name"]) == slug:
            return artist
    return None


def start_of(performance: dict) -> datetime:
    """Le moment où commence un spectacle (texte -> vraie date et heure)."""
    return datetime.fromisoformat(performance["start"])


def end_of(performance: dict) -> datetime:
    """Le moment où se termine un spectacle : début + durée."""
    return start_of(performance) + timedelta(minutes=performance["duration_minutes"])


def festival_day_of(performance: dict) -> date:
    """La journée de festival d'un spectacle : son début moins 6 heures."""
    return (start_of(performance) - FESTIVAL_DAY_CHANGE).date()


def festival_days(festival: dict) -> list[date]:
    """Les journées de festival où il y a au moins un spectacle, triées."""
    days = []
    for performance in festival["performances"]:
        day = festival_day_of(performance)
        if day not in days:
            days.append(day)
    days.sort()
    return days


def programme_of_day(festival: dict, day: date) -> list[dict]:
    """Les spectacles de cette journée de festival, triés par heure de début."""
    programme = []
    for performance in festival["performances"]:
        if festival_day_of(performance) == day:
            programme.append(performance)
    return sorted(programme, key=start_of)


def on_stage_at(festival: dict, moment: datetime) -> list[dict]:
    """Les spectacles en cours à ce moment : commencés, pas encore finis."""
    on_stage = []
    for performance in festival["performances"]:
        if start_of(performance) <= moment < end_of(performance):
            on_stage.append(performance)
    return sorted(on_stage, key=start_of)


def next_after(festival: dict, moment: datetime, count: int) -> list[dict]:
    """Les `count` prochains spectacles qui commencent après ce moment."""
    upcoming = []
    for performance in festival["performances"]:
        if start_of(performance) > moment:
            upcoming.append(performance)
    return sorted(upcoming, key=start_of)[:count]


def roles_in(performance: dict) -> list[tuple[str, str]]:
    """Les artistes d'un spectacle avec leur rôle : [(identifiant, rôle), ...]."""
    if performance["kind"] == "solo":
        return [(performance["artist"], "solo")]
    if performance["kind"] == "lineup":
        roles = [(performance["host"], "host")]
        for act in performance["acts"]:
            roles.append((act, "act"))
        return roles
    if performance["kind"] == "workshop":
        return [(performance["teacher"], "teacher")]
    return []


def performances_of_artist(festival: dict, slug: str) -> list[tuple[dict, str]]:
    """Les spectacles d'un artiste, triés par date, avec son rôle dans chacun."""
    result = []
    for performance in festival["performances"]:
        for artist_slug, role in roles_in(performance):
            if artist_slug == slug:
                result.append((performance, role))
    result.sort(key=lambda pair: start_of(pair[0]))
    return result


def total_seats(festival: dict) -> int:
    """Le nombre total de places, toutes salles confondues."""
    total = 0
    for venue in festival["venues"]:
        total += venue["capacity"]
    return total


def venue_name(festival: dict, slug: str) -> str:
    """Le nom d'une salle à partir de son identifiant."""
    venue = find_venue(festival, slug)
    if venue is None:
        return slug
    return venue["name"]


def performance_id(performance: dict) -> str:
    """L'identifiant d'un spectacle : salle + début, ex. le-kiosque-2027-06-12-0100."""
    return f"{performance['venue']}-{start_of(performance):%Y-%m-%d-%H%M}"


def find_performance(festival: dict, performance_id_text: str) -> dict:
    """Le spectacle qui a cet identifiant, ou ValueError s'il n'existe pas."""
    for performance in festival["performances"]:
        if performance_id(performance) == performance_id_text:
            return performance
    raise ValueError(f"no performance {performance_id_text!r}.")


def too_close(first: dict, second: dict) -> bool:
    """Vrai si les deux spectacles se chevauchent ou sont à moins de 30 min."""
    return (
        start_of(first) < end_of(second) + GAP
        and start_of(second) < end_of(first) + GAP
    )


def check_performance(festival: dict, new: dict) -> None:
    """Vérifie un nouveau spectacle avec les règles du brief.

    Ne renvoie rien si tout va bien ; lève ValueError avec une phrase sinon.
    """
    venue = find_venue(festival, new["venue"])
    if venue is None:
        raise ValueError(f"no venue {new['venue']!r}.")

    for artist_slug, _role in roles_in(new):
        if find_artist(festival, artist_slug) is None:
            raise ValueError(f"no artist {artist_slug!r}.")

    if not MIN_DURATION <= new["duration_minutes"] <= MAX_DURATION:
        raise ValueError(
            f"a performance lasts from {MIN_DURATION} to {MAX_DURATION} minutes, "
            f"not {new['duration_minutes']}."
        )

    day = festival_day_of(new)
    first_day = date.fromisoformat(festival["first_day"])
    last_day = date.fromisoformat(festival["last_day"])
    if not first_day <= day <= last_day:
        raise ValueError(f"{day} is not a day of the festival.")

    new_artists = [artist_slug for artist_slug, _role in roles_in(new)]
    for other in festival["performances"]:
        if not too_close(new, other):
            continue
        if other["venue"] == new["venue"]:
            raise ValueError(
                f"{venue['name']} is busy with {other['title']} "
                f"({start_of(other):%Y-%m-%d %H:%M}-{end_of(other):%H:%M})."
            )
        for artist_slug, _role in roles_in(other):
            if artist_slug in new_artists:
                artist = find_artist(festival, artist_slug)
                raise ValueError(f"{artist['name']} is on stage in {other['title']}.")


def add_performance(festival: dict, new: dict) -> None:
    """Vérifie puis ajoute. Si la vérification lève une erreur, rien n'est ajouté."""
    check_performance(festival, new)
    festival["performances"].append(new)


def cancel_performance(festival: dict, performance_id_text: str) -> dict:
    """Retire un spectacle et le renvoie (ValueError s'il n'existe pas)."""
    performance = find_performance(festival, performance_id_text)
    festival["performances"].remove(performance)
    return performance
