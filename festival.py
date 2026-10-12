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

    def __eq__(self, other: object) -> bool:
        """Deux salles sont la même si elles ont le même identifiant."""
        return isinstance(other, Venue) and self.slug == other.slug

    def __hash__(self) -> int:
        return hash(self.slug)

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

    def __eq__(self, other: object) -> bool:
        """Deux artistes sont le même s'ils ont le même identifiant (slug)."""
        return isinstance(other, Artist) and self.slug == other.slug

    def __hash__(self) -> int:
        return hash(self.slug)

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

    def __lt__(self, other: "Performance") -> bool:
        """sorted() utilise < : par début, puis par nom de salle."""
        return (self.start, self.venue.name) < (other.start, other.venue.name)

    def __str__(self) -> str:
        """Ce qu'affiche print() : "21:30-22:40 | Salle | Titre (type)"."""
        return (
            f"{self.start:%H:%M}-{self.end:%H:%M} | {self.venue.name} | "
            f"{self.title} ({self.kind})"
        )

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


class Festival:
    """Le festival entier : ses salles, ses artistes, ses spectacles et ses règles.

    Les listes sont "privées" (le _ devant le nom) : on passe toujours par les
    méthodes, donc les règles s'appliquent toujours.
    """

    def __init__(self, name: str, first_day: date, last_day: date) -> None:
        self.name = name
        self.first_day = first_day
        self.last_day = last_day
        # Rangés par identifiant : on les retrouve en une étape.
        self._venues: dict[str, Venue] = {}
        self._artists: dict[str, Artist] = {}
        self._performances: list[Performance] = []

    # --- Lire le contenu (des copies : modifier la liste rendue ne change rien) ---

    @property
    def venues(self) -> list[Venue]:
        """Les salles, dans l'ordre du fichier."""
        return list(self._venues.values())

    @property
    def artists(self) -> list[Artist]:
        """Les artistes, dans l'ordre du fichier."""
        return list(self._artists.values())

    @property
    def performances(self) -> list[Performance]:
        """Tous les spectacles, dans l'ordre du fichier."""
        return list(self._performances)

    @property
    def total_seats(self) -> int:
        """Le nombre total de places, toutes salles confondues."""
        total = 0
        for venue in self._venues.values():
            total += venue.capacity
        return total

    # --- Rechercher ---

    def find_venue(self, slug: str) -> Venue | None:
        """La salle qui a cet identifiant, ou None."""
        return self._venues.get(slug)

    def venue(self, slug: str) -> Venue:
        """La salle qui a cet identifiant, ou ValueError."""
        if slug not in self._venues:
            raise ValueError(f"No venue {slug!r}.")
        return self._venues[slug]

    def find_artist(self, slug: str) -> Artist | None:
        """L'artiste qui a cet identifiant, ou None."""
        return self._artists.get(slug)

    def artist(self, slug: str) -> Artist:
        """L'artiste qui a cet identifiant, ou ValueError."""
        if slug not in self._artists:
            raise ValueError(f"No artist {slug!r}.")
        return self._artists[slug]

    def performance(self, performance_id: str) -> Performance:
        """Le spectacle qui a cet identifiant, ou ValueError."""
        for performance in self._performances:
            if performance.id == performance_id:
                return performance
        raise ValueError(f"No performance {performance_id!r}.")

    def days(self) -> list[date]:
        """Les journées de festival où il y a au moins un spectacle, triées."""
        days = []
        for performance in self._performances:
            if performance.festival_day not in days:
                days.append(performance.festival_day)
        return sorted(days)

    def programme(
        self, day: date | None = None, venue: Venue | None = None
    ) -> list[Performance]:
        """Les spectacles, filtrés par journée et/ou par salle, triés.

        sorted() utilise Performance.__lt__ : par début, puis par nom de salle.
        """
        result = []
        for performance in self._performances:
            if day is not None and performance.festival_day != day:
                continue
            if venue is not None and performance.venue != venue:
                continue
            result.append(performance)
        return sorted(result)

    def performances_of(self, artist: Artist) -> list[tuple[Performance, str]]:
        """Les spectacles d'un artiste, triés, avec son rôle dans chacun."""
        result = []
        for performance in self.programme():
            for other, role in performance.roles:
                if other == artist:
                    result.append((performance, role))
        return result

    def on_stage_at(self, moment: datetime) -> list[Performance]:
        """Les spectacles en cours à ce moment : commencés, pas encore finis."""
        on_stage = []
        for performance in self._performances:
            if performance.start <= moment < performance.end:
                on_stage.append(performance)
        return sorted(on_stage)

    def next_after(self, moment: datetime, count: int = 3) -> list[Performance]:
        """Les `count` prochains spectacles qui commencent après ce moment."""
        upcoming = []
        for performance in self._performances:
            if performance.start > moment:
                upcoming.append(performance)
        return sorted(upcoming)[:count]

    # --- Modifier : la seule porte d'entrée, chaque règle est vérifiée ---

    def add_venue(self, venue: Venue) -> None:
        if venue.slug in self._venues:
            raise ValueError(f"{venue.name} is already a venue.")
        self._venues[venue.slug] = venue

    def add_artist(self, artist: Artist) -> None:
        if artist.slug in self._artists:
            raise ValueError(f"{artist.name} is already an artist.")
        self._artists[artist.slug] = artist

    def check(self, new: Performance) -> None:
        """Vérifie un nouveau spectacle avec les règles du brief.

        La durée est déjà vérifiée à la création de l'objet (__post_init__).
        Ne renvoie rien si tout va bien ; lève ValueError avec une phrase sinon.
        """
        if self._venues.get(new.venue.slug) != new.venue:
            raise ValueError(f"No venue {new.venue.slug!r}.")
        for artist in new.artists:
            if self._artists.get(artist.slug) != artist:
                raise ValueError(f"No artist {artist.slug!r}.")

        if not self.first_day <= new.festival_day <= self.last_day:
            raise ValueError(f"{new.festival_day} is not a day of the festival.")

        for other in self._performances:
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

    def add_performance(self, new: Performance) -> None:
        """Vérifie puis ajoute. Si une règle est enfreinte, rien n'est ajouté."""
        self.check(new)
        self._performances.append(new)

    def cancel(self, performance_id: str) -> Performance:
        """Retire un spectacle et le renvoie (ValueError s'il n'existe pas)."""
        performance = self.performance(performance_id)
        self._performances.remove(performance)
        return performance

    # --- Vers le fichier ---

    def to_dict(self) -> dict:
        """La forme du fichier JSON, pour le réécrire."""
        return {
            "name": self.name,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "venues": [
                {"name": v.name, "capacity": v.capacity, "address": v.address}
                for v in self._venues.values()
            ],
            "artists": [
                {"name": a.name, "bio": a.bio, "photo_url": a.photo_url}
                for a in self._artists.values()
            ],
            "performances": [p.to_dict() for p in self._performances],
        }


# ----- Lecture et sauvegarde : JSON <-> objets -----


def load_festival(path: str) -> Festival:
    """Lit le fichier JSON et renvoie l'objet Festival.

    Tout passe par les méthodes add_... : les données du fichier sont
    vérifiées avec les mêmes règles qu'un ajout à la main.
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

    festival = Festival(
        data["name"],
        date.fromisoformat(data["first_day"]),
        date.fromisoformat(data["last_day"]),
    )
    for row in data["venues"]:
        festival.add_venue(Venue(row["name"], row["capacity"], row["address"]))
    for row in data["artists"]:
        festival.add_artist(Artist(row["name"], row["bio"], row["photo_url"]))
    for row in data["performances"]:
        festival.add_performance(performance_from_dict(festival, row))
    return festival


def performance_from_dict(festival: Festival, row: dict) -> Performance:
    """Un dict du fichier -> un objet Performance (les identifiants -> objets)."""
    kind = row["kind"]
    performance = Performance(
        kind=kind,
        title=row["title"],
        venue=festival.venue(row["venue"]),
        start=datetime.fromisoformat(row["start"]),
        duration_minutes=row["duration_minutes"],
        description=row["description"],
    )
    if kind == "solo":
        performance.artist = festival.artist(row["artist"])
        performance.min_age = row["min_age"]
    elif kind == "lineup":
        performance.host = festival.artist(row["host"])
        performance.acts = [festival.artist(slug) for slug in row["acts"]]
    elif kind == "workshop":
        performance.teacher = festival.artist(row["teacher"])
        performance.max_participants = row["max_participants"]
        performance.participants = row["participants"]
    return performance


def save_festival(festival: Festival, path: str) -> None:
    """Objets -> JSON : réécrit le fichier avec les données à jour."""
    # newline="\n" : fins de ligne LF comme le fichier d'origine (pas CRLF Windows).
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        # ensure_ascii=False garde "é" lisible, indent=2 garde le fichier lisible.
        json.dump(festival.to_dict(), f, ensure_ascii=False, indent=2)
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
