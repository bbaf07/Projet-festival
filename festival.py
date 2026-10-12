"""Le festival : les classes, la lecture, la sauvegarde et les règles.

Ce module ne fait aucun print : il est partagé par main.py (ligne de commande)
et api.py (serveur web).
"""

import json
import unicodedata
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta

from errors import ConflictError, InvalidError, NotFoundError, StorageError

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


# ----- Le festival : le seul point d'entrée, il garde les règles -----


class Festival:
    """Le festival entier : ses salles, ses artistes, ses spectacles et ses règles.

    Les collections sont privées (_) : les propriétés rendent des copies, et la
    seule façon de changer le programme passe par des méthodes qui vérifient
    toutes les règles.
    """

    def __init__(self, name: str, first_day: date, last_day: date) -> None:
        if last_day < first_day:
            raise InvalidError("The festival cannot end before it starts.")
        self._name = name
        self._first_day = first_day
        self._last_day = last_day
        # Rangés par identifiant : on les retrouve en une étape.
        self._venues: dict[str, Venue] = {}
        self._artists: dict[str, Artist] = {}
        self._performances: list[Performance] = []

    # --- Lire (des copies : modifier ce qui est rendu ne change rien) ---

    @property
    def name(self) -> str:
        return self._name

    @property
    def first_day(self) -> date:
        return self._first_day

    @property
    def last_day(self) -> date:
        return self._last_day

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
        return sum(venue.capacity for venue in self._venues.values())

    # --- Rechercher ---

    def find_venue(self, slug: str) -> Venue | None:
        """La salle qui a cet identifiant, ou None."""
        return self._venues.get(slug)

    def venue(self, slug: str) -> Venue:
        """La salle qui a cet identifiant, ou NotFoundError."""
        if slug not in self._venues:
            raise NotFoundError(f"No venue {slug!r}.")
        return self._venues[slug]

    def find_artist(self, slug: str) -> Artist | None:
        """L'artiste qui a cet identifiant, ou None."""
        return self._artists.get(slug)

    def artist(self, slug: str) -> Artist:
        """L'artiste qui a cet identifiant, ou NotFoundError."""
        if slug not in self._artists:
            raise NotFoundError(f"No artist {slug!r}.")
        return self._artists[slug]

    def performance(self, performance_id: str) -> Performance:
        """Le spectacle qui a cet identifiant, ou NotFoundError."""
        for performance in self._performances:
            if performance.id == performance_id:
                return performance
        raise NotFoundError(f"No performance {performance_id!r}.")

    def days(self) -> list[date]:
        """Les journées de festival où il y a au moins un spectacle, triées."""
        return sorted({p.festival_day for p in self._performances})

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
        return sorted(p for p in self._performances if p.start <= moment < p.end)

    def next_after(self, moment: datetime, count: int = 3) -> list[Performance]:
        """Les `count` prochains spectacles qui commencent après ce moment."""
        return sorted(p for p in self._performances if p.start > moment)[:count]

    # --- Modifier : la seule porte d'entrée, chaque règle est vérifiée ---

    def add_venue(self, venue: Venue) -> None:
        if venue.slug in self._venues:
            raise ConflictError(f"The venue {venue.name} already exists.")
        self._venues[venue.slug] = venue

    def add_artist(self, artist: Artist) -> None:
        """Ajoute un artiste. "zoe tanguy" et "Zoé Tanguy" sont le même (slug)."""
        if artist.slug in self._artists:
            existing = self._artists[artist.slug]
            raise ConflictError(f"The artist {existing.name} already exists.")
        self._artists[artist.slug] = artist

    def check(self, new: Performance, ignore: Performance | None = None) -> None:
        """Vérifie un spectacle avec les règles du festival.

        Les règles propres à chaque type sont déjà vérifiées par son __init__.
        Ici : salle et artistes connus, jour du festival, 30 minutes pour la
        salle et pour chaque artiste. `ignore` est le spectacle qu'on remplace :
        il ne peut pas se gêner lui-même.
        """
        if self._venues.get(new.venue.slug) != new.venue:
            raise NotFoundError(f"No venue {new.venue.slug!r}.")
        for artist in new.artists:
            if self._artists.get(artist.slug) != artist:
                raise NotFoundError(f"No artist {artist.slug!r}.")

        if not self._first_day <= new.festival_day <= self._last_day:
            raise InvalidError(f"{new.festival_day} is not a day of the festival.")

        for other in self._performances:
            if other is ignore or not new.is_too_close_to(other):
                continue
            if other.venue == new.venue:
                raise ConflictError(
                    f"{new.venue.name} is busy with {other.title} "
                    f"({other.start:%Y-%m-%d %H:%M}-{other.end:%H:%M})."
                )
            for artist in new.artists:
                if other.involves(artist):
                    raise ConflictError(f"{artist.name} is on stage in {other.title}.")

    def add_performance(self, new: Performance) -> None:
        """Vérifie puis ajoute. Si une règle est enfreinte, rien n'est ajouté."""
        self.check(new)
        self._performances.append(new)

    def replace(self, performance_id: str, new: Performance) -> Performance:
        """Remplace (déplace, modifie) un spectacle. Refusé : rien ne change."""
        old = self.performance(performance_id)
        self.check(new, ignore=old)
        index = self._performances.index(old)
        self._performances[index] = new
        return new

    def cancel(self, performance_id: str) -> Performance:
        """Retire un spectacle et le renvoie (NotFoundError s'il n'existe pas)."""
        performance = self.performance(performance_id)
        self._performances.remove(performance)
        return performance

    def register(self, performance_id: str, name: str) -> Performance:
        """Inscrit un participant à un atelier (polymorphisme : le spectacle décide)."""
        performance = self.performance(performance_id)
        performance.register(name)
        return performance

    def unregister(self, performance_id: str, name: str) -> Performance:
        performance = self.performance(performance_id)
        performance.unregister(name)
        return performance

    # --- Vers et depuis le fichier ---

    def to_dict(self) -> dict:
        """La forme du fichier JSON, pour le réécrire."""
        return {
            "name": self._name,
            "first_day": self._first_day.isoformat(),
            "last_day": self._last_day.isoformat(),
            "venues": [venue.to_dict() for venue in self._venues.values()],
            "artists": [artist.to_dict() for artist in self._artists.values()],
            "performances": [p.to_dict() for p in self._performances],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Festival":
        """Construit le festival depuis le contenu du fichier.

        Tout passe par les méthodes add_... : les données du fichier sont
        vérifiées avec les mêmes règles qu'un ajout à la main.
        """
        festival = cls(
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


# ----- Lecture et sauvegarde du fichier -----


def load_festival(path: str) -> Festival:
    """Lit le fichier JSON et renvoie l'objet Festival (StorageError sinon)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise StorageError(f"The data file {path} does not exist.") from None
    except json.JSONDecodeError as error:
        raise StorageError(
            f"The data file {path} is damaged (line {error.lineno})."
        ) from None
    return Festival.from_dict(data)


def save_festival(festival: Festival, path: str) -> None:
    """Objets -> JSON : réécrit le fichier avec les données à jour."""
    try:
        # newline="\n" : fins de ligne LF comme le fichier d'origine.
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            # ensure_ascii=False garde "é" lisible, indent=2 garde le fichier lisible.
            json.dump(festival.to_dict(), f, ensure_ascii=False, indent=2)
            f.write("\n")
    except OSError as error:
        raise StorageError(
            f"The data file {path} cannot be written: {error}."
        ) from None


# ----- Lire ce que tape l'utilisateur -----


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
