"""Le festival : les classes, la lecture, la sauvegarde et les règles.

Ce module ne fait aucun print : il est partagé par main.py (ligne de commande)
et api.py (serveur web).
"""

import json
import unicodedata
from abc import ABC, abstractmethod
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
MIN_AGE = 0  # âge minimum d'un solo : de 0 à 18 ans
MAX_AGE = 18
MIN_ACTS = 2  # un plateau a au moins 2 artistes
MINUTES_PER_ACT = 10  # chaque artiste d'un plateau joue au moins 10 minutes
MINUTES_BETWEEN_ACTS = 3  # le présentateur parle 3 minutes entre deux artistes


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


class Performance(ABC):
    """Ce que tous les spectacles ont en commun.

    Classe abstraite : on ne peut pas créer un `Performance` tout court
    (TypeError), seulement un SoloShow, un Lineup ou un Workshop. Chaque
    sous-classe doit écrire `roles`, `summary()` et `from_dict()`.
    """

    kind = "performance"  # attribut de classe : chaque sous-classe le remplace

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime,
        duration_minutes: int,
        description: str = "",
    ) -> None:
        if title.strip() == "":
            raise ValueError("A performance needs a title.")
        if not MIN_DURATION <= duration_minutes <= MAX_DURATION:
            raise ValueError(
                f"A performance lasts from {MIN_DURATION} to {MAX_DURATION} "
                f"minutes, not {duration_minutes}."
            )
        self.title = title.strip()
        self.venue = venue
        self.start = start
        self.duration_minutes = duration_minutes
        self.description = description

    # --- Commun à tous les types : écrit une seule fois ---

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
    def capacity(self) -> int:
        """Le nombre de places : celles de la salle (un atelier le remplace)."""
        return self.venue.capacity

    @property
    def artists(self) -> list[Artist]:
        """Les artistes du spectacle, sans leur rôle."""
        return [artist for artist, _role in self.roles]

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
        """Les champs communs de la vue API ; chaque sous-classe ajoute les siens."""
        return {
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
            "summary": self.summary(),
            "capacity": self.capacity,
            "artists": [artist.to_ref() for artist in self.artists],
        }

    def to_dict(self) -> dict:
        """Les champs communs du fichier JSON ; chaque sous-classe ajoute les siens."""
        return {
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue.slug,
            "start": f"{self.start:%Y-%m-%dT%H:%M}",
            "duration_minutes": self.duration_minutes,
            "description": self.description,
        }

    @staticmethod
    def common_fields(festival: "Festival", row: dict) -> dict:
        """Lit dans un dict du fichier les champs communs à tous les types."""
        return {
            "title": row["title"],
            "venue": festival.venue(row["venue"]),
            "start": datetime.fromisoformat(row["start"]),
            "duration_minutes": row["duration_minutes"],
            "description": row.get("description", ""),
        }

    # --- Propre à chaque type : chaque sous-classe DOIT l'écrire ---

    @property
    @abstractmethod
    def roles(self) -> list[tuple[Artist, str]]:
        """Les artistes du spectacle avec leur rôle : [(artiste, rôle), ...]."""

    @abstractmethod
    def summary(self) -> str:
        """Une phrase qui dit qui est sur scène."""

    @classmethod
    @abstractmethod
    def from_dict(cls, festival: "Festival", row: dict) -> "Performance":
        """Un dict du fichier -> un objet de cette classe."""


class SoloShow(Performance):
    """Un seul artiste sur scène, avec un âge minimum."""

    kind = "solo"

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime,
        duration_minutes: int,
        artist: Artist,
        min_age: int = 0,
        description: str = "",
    ) -> None:
        super().__init__(title, venue, start, duration_minutes, description)
        if not MIN_AGE <= min_age <= MAX_AGE:
            raise ValueError(
                f"The minimum age goes from {MIN_AGE} to {MAX_AGE}, not {min_age}."
            )
        self.artist = artist
        self.min_age = min_age

    @property
    def roles(self) -> list[tuple[Artist, str]]:
        return [(self.artist, "solo")]

    def summary(self) -> str:
        return self.artist.name

    def to_view(self) -> dict:
        view = super().to_view()  # la partie commune, puis la sienne
        view["artist"] = self.artist.slug
        view["min_age"] = self.min_age
        return view

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["artist"] = self.artist.slug
        data["min_age"] = self.min_age
        return data

    @classmethod
    def from_dict(cls, festival: "Festival", row: dict) -> "SoloShow":
        return cls(
            **cls.common_fields(festival, row),
            artist=festival.artist(row["artist"]),
            min_age=row.get("min_age", 0),
        )


class Lineup(Performance):
    """Un plateau : un présentateur (host) et plusieurs artistes (acts)."""

    kind = "lineup"

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime,
        duration_minutes: int,
        host: Artist,
        acts: list[Artist],
        description: str = "",
    ) -> None:
        super().__init__(title, venue, start, duration_minutes, description)
        if len(acts) < MIN_ACTS:
            raise ValueError(f"A lineup needs at least {MIN_ACTS} acts.")
        if len(set(acts)) != len(acts):
            raise ValueError("Each act appears only once in a lineup.")
        if host in acts:
            raise ValueError(f"{host.name} cannot be both the host and an act.")
        # 10 minutes par artiste, et 3 minutes pour le présentateur entre deux.
        needed = MINUTES_PER_ACT * len(acts) + MINUTES_BETWEEN_ACTS * (len(acts) - 1)
        if duration_minutes < needed:
            raise ValueError(
                f"A lineup of {len(acts)} acts needs at least {needed} minutes, "
                f"not {duration_minutes}."
            )
        self.host = host
        self.acts = list(acts)

    @property
    def roles(self) -> list[tuple[Artist, str]]:
        return [(self.host, "host")] + [(act, "act") for act in self.acts]

    def summary(self) -> str:
        acts = ", ".join(act.name for act in self.acts)
        return f"hosted by {self.host.name}, with {acts}"

    def to_view(self) -> dict:
        view = super().to_view()
        view["host"] = self.host.slug
        view["acts"] = [act.slug for act in self.acts]
        return view

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["host"] = self.host.slug
        data["acts"] = [act.slug for act in self.acts]
        return data

    @classmethod
    def from_dict(cls, festival: "Festival", row: dict) -> "Lineup":
        return cls(
            **cls.common_fields(festival, row),
            host=festival.artist(row["host"]),
            acts=[festival.artist(slug) for slug in row["acts"]],
        )


class Workshop(Performance):
    """Un atelier : un enseignant et des participants inscrits."""

    kind = "workshop"

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime,
        duration_minutes: int,
        teacher: Artist,
        max_participants: int,
        participants: list[str] | None = None,
        description: str = "",
    ) -> None:
        super().__init__(title, venue, start, duration_minutes, description)
        if max_participants < 1:
            raise ValueError("A workshop needs at least 1 place.")
        self.teacher = teacher
        self.max_participants = max_participants
        self.participants = list(participants or [])
        if len(self.participants) > self.places:
            raise ValueError(
                f"{self.title} has {self.places} places, not {len(self.participants)}."
            )

    @property
    def places(self) -> int:
        """Les places : le maximum demandé, mais jamais plus que la salle."""
        return min(self.max_participants, self.venue.capacity)

    @property
    def places_left(self) -> int:
        return self.places - len(self.participants)

    @property
    def capacity(self) -> int:
        """Un atelier remplace la capacité de la salle par ses places."""
        return self.places

    @property
    def roles(self) -> list[tuple[Artist, str]]:
        return [(self.teacher, "teacher")]

    def summary(self) -> str:
        taken = len(self.participants)
        return f"with {self.teacher.name}, {taken}/{self.places} places taken"

    def to_view(self) -> dict:
        view = super().to_view()
        view["teacher"] = self.teacher.slug
        view["max_participants"] = self.max_participants
        view["participants"] = list(self.participants)
        view["places_left"] = self.places_left
        return view

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["teacher"] = self.teacher.slug
        data["max_participants"] = self.max_participants
        data["participants"] = list(self.participants)
        return data

    @classmethod
    def from_dict(cls, festival: "Festival", row: dict) -> "Workshop":
        return cls(
            **cls.common_fields(festival, row),
            teacher=festival.artist(row["teacher"]),
            max_participants=row["max_participants"],
            participants=row.get("participants", []),
        )


# Le seul endroit où le mot "kind" choisit quelque chose : à la lecture.
# Un dict fait le choix de la classe, sans aucun if.
KINDS: dict[str, type[Performance]] = {
    "solo": SoloShow,
    "lineup": Lineup,
    "workshop": Workshop,
}


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
    """Un dict du fichier -> un objet de la bonne classe, choisie par "kind"."""
    kind = row.get("kind")
    if kind not in KINDS:
        raise ValueError(f"Unknown kind of performance {kind!r}.")
    return KINDS[kind].from_dict(festival, row)


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
