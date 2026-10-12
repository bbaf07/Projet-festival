"""Les objets du festival : salles, artistes et les trois types de spectacles.

Chaque classe garde ses données (en lecture seule) et ce qu'on en calcule.
Les règles propres à un objet sont vérifiées dans son __init__.
"""

import unicodedata
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from deauville.errors import ConflictError, InvalidError, NotFoundError
from deauville.parsing import parse_moment

if TYPE_CHECKING:  # seulement pour les annotations : évite un import circulaire
    from deauville.festival import Festival

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


# ----- Salles et artistes -----


class Venue:
    """Une salle du festival. Ses attributs se lisent mais ne se modifient pas."""

    def __init__(self, name: str, capacity: int, address: str = "") -> None:
        if slugify(name) == "":
            raise InvalidError("A venue needs a name.")
        if capacity < 1:
            raise InvalidError(f"{name} needs at least one seat.")
        self._name = name.strip()
        self._capacity = capacity
        self._address = address

    @property
    def name(self) -> str:
        return self._name

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def address(self) -> str:
        return self._address

    @property
    def slug(self) -> str:
        """Se lit comme un attribut (venue.slug), mais est calculé à chaque fois."""
        return slugify(self._name)

    def __eq__(self, other: object) -> bool:
        """Deux salles sont la même si elles ont le même identifiant."""
        return isinstance(other, Venue) and self.slug == other.slug

    def __hash__(self) -> int:
        return hash(self.slug)

    def __repr__(self) -> str:
        return f"Venue({self._name!r})"

    def to_view(self) -> dict:
        """Ce que l'API envoie pour une salle."""
        return {
            "slug": self.slug,
            "name": self._name,
            "capacity": self._capacity,
            "address": self._address,
        }

    def to_dict(self) -> dict:
        """La forme du fichier JSON."""
        return {
            "name": self._name,
            "capacity": self._capacity,
            "address": self._address,
        }


class Artist:
    """Un artiste du festival. Ses attributs se lisent mais ne se modifient pas."""

    def __init__(self, name: str, bio: str = "", photo_url: str = "") -> None:
        if slugify(name) == "":
            raise InvalidError("An artist needs a name.")
        self._name = name.strip()
        self._bio = bio
        self._photo_url = photo_url

    @property
    def name(self) -> str:
        return self._name

    @property
    def bio(self) -> str:
        return self._bio

    @property
    def photo_url(self) -> str:
        return self._photo_url

    @property
    def slug(self) -> str:
        return slugify(self._name)

    def __eq__(self, other: object) -> bool:
        """Deux artistes sont le même s'ils ont le même identifiant (slug)."""
        return isinstance(other, Artist) and self.slug == other.slug

    def __hash__(self) -> int:
        return hash(self.slug)

    def __repr__(self) -> str:
        return f"Artist({self._name!r})"

    def to_ref(self) -> dict:
        """La forme courte, utilisée dans un spectacle : {"slug", "name"}."""
        return {"slug": self.slug, "name": self._name}

    def to_view(self) -> dict:
        """Ce que l'API envoie pour un artiste."""
        return {
            "slug": self.slug,
            "name": self._name,
            "bio": self._bio,
            "photo_url": self._photo_url,
        }

    def to_dict(self) -> dict:
        """La forme du fichier JSON."""
        return {"name": self._name, "bio": self._bio, "photo_url": self._photo_url}


# ----- Les spectacles : une famille de trois classes -----


def required(row: dict, key: str) -> object:
    """La valeur d'un champ obligatoire d'un dict, ou InvalidError."""
    if row.get(key) is None:
        kind = row.get("kind", "performance")
        raise InvalidError(f"A {kind} needs the field {key!r}.")
    return row[key]


class Performance(ABC):
    """Ce que tous les spectacles ont en commun.

    Classe abstraite : on ne peut pas créer un `Performance` tout court
    (TypeError), seulement un SoloShow, un Lineup ou un Workshop. Chaque
    sous-classe doit écrire `roles`, `summary()` et `from_dict()`.

    Les attributs sont privés (_) et en lecture seule : pour déplacer un
    spectacle, on en crée un nouveau et on passe par Festival.replace(), qui
    vérifie les règles.
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
            raise InvalidError("A performance needs a title.")
        if not MIN_DURATION <= duration_minutes <= MAX_DURATION:
            raise InvalidError(
                f"A performance lasts from {MIN_DURATION} to {MAX_DURATION} "
                f"minutes, not {duration_minutes}."
            )
        self._title = title.strip()
        self._venue = venue
        self._start = start.replace(second=0, microsecond=0, tzinfo=None)
        self._duration_minutes = duration_minutes
        self._description = description

    # --- Commun à tous les types : écrit une seule fois ---

    @property
    def title(self) -> str:
        return self._title

    @property
    def venue(self) -> Venue:
        return self._venue

    @property
    def start(self) -> datetime:
        return self._start

    @property
    def duration_minutes(self) -> int:
        return self._duration_minutes

    @property
    def description(self) -> str:
        return self._description

    @property
    def end(self) -> datetime:
        """Début + durée."""
        return self._start + timedelta(minutes=self._duration_minutes)

    @property
    def festival_day(self) -> date:
        """La journée de festival : le début moins 6 heures."""
        return (self._start - FESTIVAL_DAY_CHANGE).date()

    @property
    def id(self) -> str:
        """Salle + début, ex. le-kiosque-2027-06-12-0100."""
        return f"{self._venue.slug}-{self._start:%Y-%m-%d-%H%M}"

    @property
    def capacity(self) -> int:
        """Le nombre de places : celles de la salle (un atelier le remplace)."""
        return self._venue.capacity

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

    def register(self, name: str) -> None:
        """Inscrire un participant : seul un atelier l'accepte (il remplace ceci)."""
        raise InvalidError(f"{self._title} is not a workshop: nobody registers.")

    def unregister(self, name: str) -> None:
        """Désinscrire un participant : seul un atelier l'accepte."""
        raise InvalidError(f"{self._title} is not a workshop: nobody registers.")

    def __lt__(self, other: "Performance") -> bool:
        """sorted() utilise < : par début, puis par nom de salle."""
        return (self._start, self._venue.name) < (other.start, other.venue.name)

    def __str__(self) -> str:
        """Ce qu'affiche print() : "21:30-22:40 | Salle | Titre (type)"."""
        return (
            f"{self._start:%H:%M}-{self.end:%H:%M} | {self._venue.name} | "
            f"{self._title} ({self.kind})"
        )

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id!r})"

    def to_view(self) -> dict:
        """Les champs communs de la vue API ; chaque sous-classe ajoute les siens."""
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self._title,
            "venue": self._venue.slug,
            "venue_name": self._venue.name,
            "start": f"{self._start:%Y-%m-%dT%H:%M}",
            "end": f"{self.end:%Y-%m-%dT%H:%M}",
            "duration_minutes": self._duration_minutes,
            "festival_day": self.festival_day.isoformat(),
            "description": self._description,
            "summary": self.summary(),
            "capacity": self.capacity,
            "artists": [artist.to_ref() for artist in self.artists],
        }

    def to_dict(self) -> dict:
        """Les champs communs du fichier JSON ; chaque sous-classe ajoute les siens."""
        return {
            "kind": self.kind,
            "title": self._title,
            "venue": self._venue.slug,
            "start": f"{self._start:%Y-%m-%dT%H:%M}",
            "duration_minutes": self._duration_minutes,
            "description": self._description,
        }

    @staticmethod
    def common_fields(festival: "Festival", row: dict) -> dict:
        """Lit dans un dict les champs communs à tous les types."""
        start = required(row, "start")
        if isinstance(start, str):
            start = parse_moment(start)
        return {
            "title": required(row, "title"),
            "venue": festival.venue(required(row, "venue")),
            "start": start,
            "duration_minutes": required(row, "duration_minutes"),
            "description": row.get("description") or "",
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
        """Un dict (fichier ou API) -> un objet de cette classe."""


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
            raise InvalidError(
                f"The minimum age goes from {MIN_AGE} to {MAX_AGE}, not {min_age}."
            )
        self._artist = artist
        self._min_age = min_age

    @property
    def artist(self) -> Artist:
        return self._artist

    @property
    def min_age(self) -> int:
        return self._min_age

    @property
    def roles(self) -> list[tuple[Artist, str]]:
        return [(self._artist, "solo")]

    def summary(self) -> str:
        return self._artist.name

    def to_view(self) -> dict:
        view = super().to_view()  # la partie commune, puis la sienne
        view["artist"] = self._artist.slug
        view["min_age"] = self._min_age
        return view

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["artist"] = self._artist.slug
        data["min_age"] = self._min_age
        return data

    @classmethod
    def from_dict(cls, festival: "Festival", row: dict) -> "SoloShow":
        return cls(
            **cls.common_fields(festival, row),
            artist=festival.artist(required(row, "artist")),
            min_age=row.get("min_age") or 0,
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
            raise InvalidError(f"A lineup needs at least {MIN_ACTS} acts.")
        if len(set(acts)) != len(acts):
            raise InvalidError("Each act appears only once in a lineup.")
        if host in acts:
            raise InvalidError(f"{host.name} cannot be both the host and an act.")
        # 10 minutes par artiste, et 3 minutes pour le présentateur entre deux.
        needed = MINUTES_PER_ACT * len(acts) + MINUTES_BETWEEN_ACTS * (len(acts) - 1)
        if duration_minutes < needed:
            raise InvalidError(
                f"A lineup of {len(acts)} acts needs at least {needed} minutes, "
                f"not {duration_minutes}."
            )
        self._host = host
        self._acts = tuple(acts)  # un tuple ne se modifie pas

    @property
    def host(self) -> Artist:
        return self._host

    @property
    def acts(self) -> tuple[Artist, ...]:
        """Les artistes du plateau, dans l'ordre : un tuple, non modifiable."""
        return self._acts

    @property
    def roles(self) -> list[tuple[Artist, str]]:
        return [(self._host, "host")] + [(act, "act") for act in self._acts]

    def summary(self) -> str:
        acts = ", ".join(act.name for act in self._acts)
        return f"hosted by {self._host.name}, with {acts}"

    def to_view(self) -> dict:
        view = super().to_view()
        view["host"] = self._host.slug
        view["acts"] = [act.slug for act in self._acts]
        return view

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["host"] = self._host.slug
        data["acts"] = [act.slug for act in self._acts]
        return data

    @classmethod
    def from_dict(cls, festival: "Festival", row: dict) -> "Lineup":
        return cls(
            **cls.common_fields(festival, row),
            host=festival.artist(required(row, "host")),
            acts=[festival.artist(slug) for slug in row.get("acts") or []],
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
            raise InvalidError("A workshop needs at least 1 place.")
        self._teacher = teacher
        self._max_participants = max_participants
        self._participants: list[str] = []
        for name in participants or []:
            self.register(name)  # mêmes règles qu'une inscription à la main

    @property
    def teacher(self) -> Artist:
        return self._teacher

    @property
    def max_participants(self) -> int:
        return self._max_participants

    @property
    def participants(self) -> tuple[str, ...]:
        """Les inscrits : un tuple, on n'ajoute qu'avec register()."""
        return tuple(self._participants)

    @property
    def places(self) -> int:
        """Les places : le maximum demandé, mais jamais plus que la salle."""
        return min(self._max_participants, self.venue.capacity)

    @property
    def places_left(self) -> int:
        return self.places - len(self._participants)

    @property
    def capacity(self) -> int:
        """Un atelier remplace la capacité de la salle par ses places."""
        return self.places

    @property
    def roles(self) -> list[tuple[Artist, str]]:
        return [(self._teacher, "teacher")]

    def register(self, name: str) -> None:
        """Inscrit un participant : un nom, pas de doublon, pas au-delà des places."""
        name = name.strip()
        if name == "":
            raise InvalidError("A participant needs a name.")
        if name.lower() in (other.lower() for other in self._participants):
            raise ConflictError(f"{name} is already registered in {self.title}.")
        if self.places_left <= 0:
            raise ConflictError(f"{self.title} is full ({self.places} places).")
        self._participants.append(name)

    def unregister(self, name: str) -> None:
        """Désinscrit un participant."""
        for other in self._participants:
            if other.lower() == name.strip().lower():
                self._participants.remove(other)
                return
        raise NotFoundError(f"{name} is not registered in {self.title}.")

    def summary(self) -> str:
        taken = len(self._participants)
        return f"with {self._teacher.name}, {taken}/{self.places} places taken"

    def to_view(self) -> dict:
        view = super().to_view()
        view["teacher"] = self._teacher.slug
        view["max_participants"] = self._max_participants
        view["participants"] = list(self._participants)
        view["places_left"] = self.places_left
        return view

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["teacher"] = self._teacher.slug
        data["max_participants"] = self._max_participants
        data["participants"] = list(self._participants)
        return data

    @classmethod
    def from_dict(cls, festival: "Festival", row: dict) -> "Workshop":
        return cls(
            **cls.common_fields(festival, row),
            teacher=festival.artist(required(row, "teacher")),
            max_participants=required(row, "max_participants"),
            participants=row.get("participants") or [],
        )


# Le seul endroit où le mot "kind" choisit quelque chose : à la lecture.
# Un dict fait le choix de la classe, sans aucun if.
KINDS: dict[str, type[Performance]] = {
    "solo": SoloShow,
    "lineup": Lineup,
    "workshop": Workshop,
}


def performance_from_dict(festival: "Festival", row: dict) -> Performance:
    """Un dict (fichier ou API) -> un objet de la bonne classe, choisie par "kind"."""
    kind = row.get("kind")
    if kind not in KINDS:
        raise InvalidError(f"Unknown kind of performance {kind!r}.")
    return KINDS[kind].from_dict(festival, row)
