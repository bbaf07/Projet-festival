"""Le festival : le seul point d'entrée vers les données, il garde les règles."""

from datetime import date, datetime

from deauville.errors import ConflictError, InvalidError, NotFoundError
from deauville.models import Artist, Performance, Venue, performance_from_dict


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
