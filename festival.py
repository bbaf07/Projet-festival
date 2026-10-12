"""Le festival : les classes, la lecture, la sauvegarde et les règles.

Ce module ne fait aucun print : il est partagé par main.py (ligne de commande)
et api.py (serveur web).
"""

import json
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta

DATA_FILE = "data/festival.json"

# Règle du festival : une journée se termine à 06:00. Un spectacle à 1 h du
# matin appartient donc à la journée de la veille.
FESTIVAL_DAY_CHANGE = timedelta(hours=6)

# Règles du brief pour programmer un spectacle.
MIN_DURATION = 1  # minutes
MAX_DURATION = 360  # minutes
GAP = timedelta(minutes=30)  # battement entre deux spectacles (salle ou artiste)


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


# ----- Les classes : chaque objet garde ses données et ce qu'on en calcule -----


@dataclass
class Venue:
    """Une salle du festival."""

    name: str
    capacity: int
    address: str

    @property
    def slug(self) -> str:
        """Se lit comme un attribut (venue.slug), mais est calculé à chaque fois."""
        return slugify(self.name)

    def to_view(self) -> dict:
        """Ce que l'API envoie pour une salle."""
        return {
            "slug": self.slug,
            "name": self.name,
            "capacity": self.capacity,
            "address": self.address,
        }


@dataclass
class Artist:
    """Un artiste du festival."""

    name: str
    bio: str
    photo_url: str

    @property
    def slug(self) -> str:
        return slugify(self.name)

    def to_ref(self) -> dict:
        """La forme courte, utilisée dans un spectacle : {"slug", "name"}."""
        return {"slug": self.slug, "name": self.name}

    def to_view(self) -> dict:
        """Ce que l'API envoie pour un artiste."""
        return {
            "slug": self.slug,
            "name": self.name,
            "bio": self.bio,
            "photo_url": self.photo_url,
        }


@dataclass
class Performance:
    """Un spectacle : solo, plateau (lineup) ou atelier (workshop).

    Une seule classe pour les trois types : les champs qui ne concernent pas
    ce type valent None. Chaque `if self.kind == ...` ci-dessous est un signe
    que l'étape 09 (héritage) sera utile.
    """

    kind: str
    title: str
    venue: Venue
    start: datetime
    duration_minutes: int
    description: str = ""
    # solo
    artist: Artist | None = None
    min_age: int | None = None
    # lineup
    host: Artist | None = None
    acts: list[Artist] | None = None
    # workshop
    teacher: Artist | None = None
    max_participants: int | None = None
    participants: list[str] | None = None

    def __post_init__(self) -> None:
        """Lancé juste après le __init__ écrit par @dataclass : on vérifie."""
        if not MIN_DURATION <= self.duration_minutes <= MAX_DURATION:
            raise ValueError(
                f"A performance lasts from {MIN_DURATION} to {MAX_DURATION} "
                f"minutes, not {self.duration_minutes}."
            )

    @property
    def end(self) -> datetime:
        """Début + durée."""
        return self.start + timedelta(minutes=self.duration_minutes)

    @property
    def festival_day(self) -> date:
        """La journée de festival : le début moins 6 heures."""
        return (self.start - FESTIVAL_DAY_CHANGE).date()

    @property
    def id(self) -> str:
        """Salle + début, ex. le-kiosque-2027-06-12-0100."""
        return f"{self.venue.slug}-{self.start:%Y-%m-%d-%H%M}"

    @property
    def roles(self) -> list[tuple[Artist, str]]:
        """Les artistes du spectacle avec leur rôle : [(artiste, rôle), ...]."""
        if self.kind == "solo":
            return [(self.artist, "solo")]
        if self.kind == "lineup":
            return [(self.host, "host")] + [(act, "act") for act in self.acts]
        if self.kind == "workshop":
            return [(self.teacher, "teacher")]
        return []

    @property
    def artists(self) -> list[Artist]:
        """Les artistes du spectacle, sans leur rôle."""
        return [artist for artist, _role in self.roles]

    @property
    def summary(self) -> str:
        """Une phrase qui dit qui est sur scène."""
        if self.kind == "lineup":
            acts = ", ".join(act.name for act in self.acts)
            return f"hosted by {self.host.name}, with {acts}"
        if self.kind == "workshop":
            return f"with {self.teacher.name}"
        return f"by {self.artist.name}"

    @property
    def places_left(self) -> int | None:
        """Pour un atelier : les places encore libres. None sinon."""
        if self.kind != "workshop":
            return None
        return self.max_participants - len(self.participants)

    def involves(self, artist: Artist) -> bool:
        """Vrai si cet artiste est sur scène ici, quel que soit son rôle."""
        return artist in self.artists

    def is_too_close_to(self, other: "Performance") -> bool:
        """Vrai si les deux spectacles se chevauchent ou sont à moins de 30 min."""
        return self.start < other.end + GAP and other.start < self.end + GAP

    def to_view(self) -> dict:
        """Ce que l'API envoie : des valeurs simples, les valeurs calculées incluses."""
        view = {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue.slug,
            "venue_name": self.venue.name,
            "start": f"{self.start:%Y-%m-%dT%H:%M}",
            "end": f"{self.end:%Y-%m-%dT%H:%M}",
            "duration_minutes": self.duration_minutes,
            "festival_day": self.festival_day.isoformat(),
            "description": self.description,
            "summary": self.summary,
            "capacity": self.venue.capacity,
            "artists": [artist.to_ref() for artist in self.artists],
        }
        if self.kind == "solo":
            view["artist"] = self.artist.slug
            view["min_age"] = self.min_age
        elif self.kind == "lineup":
            view["host"] = self.host.slug
            view["acts"] = [act.slug for act in self.acts]
        elif self.kind == "workshop":
            view["teacher"] = self.teacher.slug
            view["max_participants"] = self.max_participants
            view["participants"] = self.participants
            view["places_left"] = self.places_left
        return view

    def to_dict(self) -> dict:
        """La forme du fichier JSON, dans le même ordre, pour le réécrire."""
        data = {
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue.slug,
            "start": f"{self.start:%Y-%m-%dT%H:%M}",
            "duration_minutes": self.duration_minutes,
            "description": self.description,
        }
        if self.kind == "solo":
            data["artist"] = self.artist.slug
            data["min_age"] = self.min_age
        elif self.kind == "lineup":
            data["host"] = self.host.slug
            data["acts"] = [act.slug for act in self.acts]
        elif self.kind == "workshop":
            data["teacher"] = self.teacher.slug
            data["max_participants"] = self.max_participants
            data["participants"] = self.participants
        return data


@dataclass
class Festival:
    """Le contenant : le festival, ses salles, ses artistes, ses spectacles."""

    name: str
    first_day: date
    last_day: date
    venues: list[Venue]
    artists: list[Artist]
    performances: list[Performance]


# ----- Lecture et sauvegarde : JSON <-> objets -----


def load_festival(path: str) -> Festival:
    """Lit le fichier JSON et renvoie des objets.

    Lève ValueError avec une phrase claire si le fichier manque ou est abîmé.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"The data file {path} does not exist.") from None
    except json.JSONDecodeError as error:
        raise ValueError(
            f"The data file {path} is damaged (line {error.lineno})."
        ) from None

    venues = [Venue(v["name"], v["capacity"], v["address"]) for v in data["venues"]]
    artists = [Artist(a["name"], a["bio"], a["photo_url"]) for a in data["artists"]]
    festival = Festival(
        name=data["name"],
        first_day=date.fromisoformat(data["first_day"]),
        last_day=date.fromisoformat(data["last_day"]),
        venues=venues,
        artists=artists,
        performances=[],
    )
    for row in data["performances"]:
        festival.performances.append(performance_from_dict(festival, row))
    return festival


def performance_from_dict(festival: Festival, row: dict) -> Performance:
    """Un dict du fichier -> un objet Performance (les identifiants -> objets)."""
    kind = row["kind"]
    performance = Performance(
        kind=kind,
        title=row["title"],
        venue=get_venue(festival, row["venue"]),
        start=datetime.fromisoformat(row["start"]),
        duration_minutes=row["duration_minutes"],
        description=row["description"],
    )
    if kind == "solo":
        performance.artist = get_artist(festival, row["artist"])
        performance.min_age = row["min_age"]
    elif kind == "lineup":
        performance.host = get_artist(festival, row["host"])
        performance.acts = [get_artist(festival, slug) for slug in row["acts"]]
    elif kind == "workshop":
        performance.teacher = get_artist(festival, row["teacher"])
        performance.max_participants = row["max_participants"]
        performance.participants = row["participants"]
    return performance


def save_festival(festival: Festival, path: str) -> None:
    """Objets -> JSON : réécrit le fichier avec les données à jour."""
    data = {
        "name": festival.name,
        "first_day": festival.first_day.isoformat(),
        "last_day": festival.last_day.isoformat(),
        "venues": [
            {"name": v.name, "capacity": v.capacity, "address": v.address}
            for v in festival.venues
        ],
        "artists": [
            {"name": a.name, "bio": a.bio, "photo_url": a.photo_url}
            for a in festival.artists
        ],
        "performances": [p.to_dict() for p in festival.performances],
    }
    # newline="\n" : fins de ligne LF comme le fichier d'origine (pas CRLF Windows).
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        # ensure_ascii=False garde "é" lisible, indent=2 garde le fichier lisible.
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ----- Lire ce que tape l'utilisateur -----


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


# ----- Rechercher dans le festival -----


def find_venue(festival: Festival, slug: str) -> Venue | None:
    """La salle qui a cet identifiant, ou None."""
    for venue in festival.venues:
        if venue.slug == slug:
            return venue
    return None


def get_venue(festival: Festival, slug: str) -> Venue:
    """La salle qui a cet identifiant, ou ValueError."""
    venue = find_venue(festival, slug)
    if venue is None:
        raise ValueError(f"No venue {slug!r}.")
    return venue


def find_artist(festival: Festival, slug: str) -> Artist | None:
    """L'artiste qui a cet identifiant, ou None."""
    for artist in festival.artists:
        if artist.slug == slug:
            return artist
    return None


def get_artist(festival: Festival, slug: str) -> Artist:
    """L'artiste qui a cet identifiant, ou ValueError."""
    artist = find_artist(festival, slug)
    if artist is None:
        raise ValueError(f"No artist {slug!r}.")
    return artist


def get_performance(festival: Festival, performance_id: str) -> Performance:
    """Le spectacle qui a cet identifiant, ou ValueError."""
    for performance in festival.performances:
        if performance.id == performance_id:
            return performance
    raise ValueError(f"No performance {performance_id!r}.")


def festival_days(festival: Festival) -> list[date]:
    """Les journées de festival où il y a au moins un spectacle, triées."""
    days = []
    for performance in festival.performances:
        if performance.festival_day not in days:
            days.append(performance.festival_day)
    return sorted(days)


def by_start(performance: Performance) -> datetime:
    """Clé de tri : l'heure de début."""
    return performance.start


def programme(
    festival: Festival, day: date | None = None, venue: Venue | None = None
) -> list[Performance]:
    """Les spectacles, filtrés par journée et/ou par salle, triés par début."""
    result = []
    for performance in festival.performances:
        if day is not None and performance.festival_day != day:
            continue
        if venue is not None and performance.venue != venue:
            continue
        result.append(performance)
    return sorted(result, key=by_start)


def on_stage_at(festival: Festival, moment: datetime) -> list[Performance]:
    """Les spectacles en cours à ce moment : commencés, pas encore finis."""
    on_stage = []
    for performance in festival.performances:
        if performance.start <= moment < performance.end:
            on_stage.append(performance)
    return sorted(on_stage, key=by_start)


def next_after(festival: Festival, moment: datetime, count: int) -> list[Performance]:
    """Les `count` prochains spectacles qui commencent après ce moment."""
    upcoming = []
    for performance in festival.performances:
        if performance.start > moment:
            upcoming.append(performance)
    return sorted(upcoming, key=by_start)[:count]


def performances_of_artist(
    festival: Festival, artist: Artist
) -> list[tuple[Performance, str]]:
    """Les spectacles d'un artiste, triés par date, avec son rôle dans chacun."""
    result = []
    for performance in programme(festival):
        for other, role in performance.roles:
            if other == artist:
                result.append((performance, role))
    return result


def total_seats(festival: Festival) -> int:
    """Le nombre total de places, toutes salles confondues."""
    total = 0
    for venue in festival.venues:
        total += venue.capacity
    return total


# ----- Les règles : vérifier, ajouter, annuler -----


def check_performance(festival: Festival, new: Performance) -> None:
    """Vérifie un nouveau spectacle avec les règles du brief.

    La salle, les artistes et la durée sont déjà vérifiés à la création de
    l'objet. Ici : le jour, puis les 30 minutes pour la salle et les artistes.
    Ne renvoie rien si tout va bien ; lève ValueError avec une phrase sinon.
    """
    if not festival.first_day <= new.festival_day <= festival.last_day:
        raise ValueError(f"{new.festival_day} is not a day of the festival.")

    for other in festival.performances:
        if not new.is_too_close_to(other):
            continue
        if other.venue == new.venue:
            raise ValueError(
                f"{new.venue.name} is busy with {other.title} "
                f"({other.start:%Y-%m-%d %H:%M}-{other.end:%H:%M})."
            )
        for artist in new.artists:
            if other.involves(artist):
                raise ValueError(f"{artist.name} is on stage in {other.title}.")


def add_performance(festival: Festival, new: Performance) -> None:
    """Vérifie puis ajoute. Si la vérification lève une erreur, rien n'est ajouté."""
    check_performance(festival, new)
    festival.performances.append(new)


def cancel_performance(festival: Festival, performance_id: str) -> Performance:
    """Retire un spectacle et le renvoie (ValueError s'il n'existe pas)."""
    performance = get_performance(festival, performance_id)
    festival.performances.remove(performance)
    return performance
