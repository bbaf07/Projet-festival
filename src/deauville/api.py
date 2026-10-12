"""Le serveur web du festival : les routes de API.md.

L'application est construite par `create_app(storage)` : le serveur lui donne
le vrai fichier, chaque test une copie. Aucun festival global : chaque requête
relit le stockage, et chaque écriture le sauvegarde.

    uv run deauville serve        (ou : uv run python -m deauville serve)
"""

from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from deauville.errors import (
    ConflictError,
    FestivalError,
    InvalidError,
    NotFoundError,
    StorageError,
)
from deauville.models import Artist, performance_from_dict
from deauville.storage import FestivalStorage

# Chaque type d'erreur de la famille devient un code HTTP.
STATUS: dict[type[FestivalError], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    InvalidError: 422,
    StorageError: 500,
}


# ----- Les corps de requête : la forme du JSON attendu -----
# FastAPI refuse une autre forme (champ manquant, mauvais type) avec un 422.


class PerformanceIn(BaseModel):
    """Un spectacle envoyé par l'admin. Les champs d'un type ne servent qu'à lui."""

    kind: Literal["solo", "lineup", "workshop"]
    title: str
    venue: str
    start: datetime
    duration_minutes: int
    description: str = ""
    # solo
    artist: str | None = None
    min_age: int = 0
    # lineup
    host: str | None = None
    acts: list[str] = []
    # workshop
    teacher: str | None = None
    max_participants: int | None = None
    participants: list[str] = []


class ParticipantIn(BaseModel):
    """Un participant à inscrire dans un atelier."""

    name: str


class ArtistIn(BaseModel):
    """Un nouvel artiste."""

    name: str
    bio: str = ""
    photo_url: str = ""


def create_app(storage: FestivalStorage, web_dir: Path | str = "web") -> FastAPI:
    """Une nouvelle application autour du festival rangé dans `storage`.

    `web_dir` contient `public/` (le site) et `admin/` (l'admin), s'ils existent.
    """
    app = FastAPI(title="Deauville Festival du Rire")
    web = Path(web_dir)

    # Un seul gestionnaire d'erreurs : aucun try dans les routes.
    @app.exception_handler(FestivalError)
    def festival_error(request: Request, error: FestivalError) -> JSONResponse:
        status = STATUS.get(type(error), 400)
        return JSONResponse(status_code=status, content={"detail": str(error)})

    # ----- Lire -----

    @app.get("/api/festival")
    def read_festival() -> dict:
        festival = storage.load()
        return {
            "name": festival.name,
            "first_day": festival.first_day.isoformat(),
            "last_day": festival.last_day.isoformat(),
            "days": [day.isoformat() for day in festival.days()],
        }

    @app.get("/api/venues")
    def list_venues() -> list[dict]:
        return [venue.to_view() for venue in storage.load().venues]

    @app.get("/api/artists")
    def list_artists() -> list[dict]:
        artists = sorted(storage.load().artists, key=lambda artist: artist.slug)
        return [artist.to_view() for artist in artists]

    # {slug} dans le chemin devient un paramètre de la fonction.
    @app.get("/api/artists/{slug}")
    def read_artist(slug: str) -> dict:
        festival = storage.load()
        artist = festival.artist(slug)  # NotFoundError -> 404 par le gestionnaire
        view = artist.to_view()
        view["performances"] = [
            performance.to_view()
            for performance, _role in festival.performances_of(artist)
        ]
        return view

    # Les paramètres absents du chemin viennent de la requête : ?day=&venue=
    # Grâce à l'annotation `date`, FastAPI refuse ?day=June 11 avec un 422.
    @app.get("/api/programme")
    def list_programme(day: date | None = None, venue: str | None = None) -> list[dict]:
        festival = storage.load()
        venue_object = festival.venue(venue) if venue is not None else None
        performances = festival.programme(day=day, venue=venue_object)
        return [performance.to_view() for performance in performances]

    @app.get("/api/performances/{performance_id}")
    def read_performance(performance_id: str) -> dict:
        return storage.load().performance(performance_id).to_view()

    # ?at=2027-06-11T21:00 remplace l'heure actuelle (pratique pour tester).
    @app.get("/api/now")
    def read_now(at: datetime | None = None) -> dict:
        festival = storage.load()
        moment = (at or datetime.now()).replace(tzinfo=None)
        return {
            "at": f"{moment:%Y-%m-%dT%H:%M}",
            "now_playing": [p.to_view() for p in festival.on_stage_at(moment)],
            "up_next": [p.to_view() for p in festival.next_after(moment, 3)],
        }

    # ----- Écrire (admin) : chaque changement vérifie les règles puis sauvegarde

    @app.post("/api/performances", status_code=201)
    def create_performance(body: PerformanceIn) -> dict:
        festival = storage.load()
        new = performance_from_dict(festival, body.model_dump())
        festival.add_performance(new)
        storage.save(festival)
        return new.to_view()

    @app.put("/api/performances/{performance_id}")
    def replace_performance(performance_id: str, body: PerformanceIn) -> dict:
        """Remplace un spectacle (son id peut changer). Refusé : rien ne change."""
        festival = storage.load()
        new = performance_from_dict(festival, body.model_dump())
        festival.replace(performance_id, new)
        storage.save(festival)
        return new.to_view()

    @app.delete("/api/performances/{performance_id}", status_code=204)
    def delete_performance(performance_id: str) -> Response:
        festival = storage.load()
        festival.cancel(performance_id)
        storage.save(festival)
        return Response(status_code=204)

    @app.post("/api/performances/{performance_id}/participants", status_code=201)
    def register_participant(performance_id: str, body: ParticipantIn) -> dict:
        festival = storage.load()
        performance = festival.register(performance_id, body.name)
        storage.save(festival)
        return performance.to_view()

    @app.delete(
        "/api/performances/{performance_id}/participants/{name}", status_code=204
    )
    def unregister_participant(performance_id: str, name: str) -> Response:
        festival = storage.load()
        festival.unregister(performance_id, name)
        storage.save(festival)
        return Response(status_code=204)

    @app.post("/api/artists", status_code=201)
    def create_artist(body: ArtistIn) -> dict:
        festival = storage.load()
        artist = Artist(body.name, body.bio, body.photo_url)
        festival.add_artist(artist)
        storage.save(festival)
        return artist.to_view()

    # ----- Les fichiers du site : après les routes, sinon ils les cacheraient.
    # /admin avant /, sinon / l'avalerait.
    if (web / "admin").is_dir():
        app.mount(
            "/admin", StaticFiles(directory=web / "admin", html=True), name="admin"
        )
    if (web / "public").is_dir():
        app.mount("/", StaticFiles(directory=web / "public", html=True), name="site")

    return app
