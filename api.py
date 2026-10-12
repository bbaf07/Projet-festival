"""Le serveur web du festival : les routes de API.md.

    uv run python -m uvicorn api:app --reload

Puis ouvrir http://127.0.0.1:8000 (le site), http://127.0.0.1:8000/admin/
(l'admin) et http://127.0.0.1:8000/docs (toutes les routes).
"""

from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from errors import (
    ConflictError,
    FestivalError,
    InvalidError,
    NotFoundError,
    StorageError,
)
from festival import (
    DATA_FILE,
    Artist,
    Festival,
    load_festival,
    performance_from_dict,
    save_festival,
)

WEBSITE = Path("web/public")
ADMIN = Path("web/admin")

app = FastAPI(title="Deauville Festival du Rire")


# ----- Les erreurs : un seul gestionnaire, aucun try dans les routes -----

STATUS = {
    NotFoundError: 404,
    ConflictError: 409,
    InvalidError: 422,
    StorageError: 500,
}


@app.exception_handler(FestivalError)
def festival_error(request: Request, error: FestivalError) -> JSONResponse:
    """Chaque type d'erreur de la famille devient un code HTTP."""
    status = STATUS.get(type(error), 400)
    return JSONResponse(status_code=status, content={"detail": str(error)})


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
    name: str


class ArtistIn(BaseModel):
    name: str
    bio: str = ""
    photo_url: str = ""


def load() -> Festival:
    return load_festival(DATA_FILE)


def save(festival: Festival) -> None:
    save_festival(festival, DATA_FILE)


# ----- Lire -----


# Une route : une méthode (GET), un chemin, une fonction.
# Ce que la fonction renvoie devient du JSON.
@app.get("/api/festival")
def read_festival() -> dict:
    festival = load()
    return {
        "name": festival.name,
        "first_day": festival.first_day.isoformat(),
        "last_day": festival.last_day.isoformat(),
        "days": [day.isoformat() for day in festival.days()],
    }


@app.get("/api/venues")
def list_venues() -> list[dict]:
    return [venue.to_view() for venue in load().venues]


@app.get("/api/artists")
def list_artists() -> list[dict]:
    artists = sorted(load().artists, key=lambda artist: artist.slug)
    return [artist.to_view() for artist in artists]


# {slug} dans le chemin devient un paramètre de la fonction.
@app.get("/api/artists/{slug}")
def read_artist(slug: str) -> dict:
    festival = load()
    artist = festival.artist(slug)  # NotFoundError -> 404 par le gestionnaire
    view = artist.to_view()
    view["performances"] = [
        performance.to_view() for performance, _role in festival.performances_of(artist)
    ]
    return view


# Les paramètres absents du chemin viennent de la requête : ?day=...&venue=...
# Grâce à l'annotation `date`, FastAPI refuse ?day=June 11 avec un 422 tout seul.
@app.get("/api/programme")
def list_programme(day: date | None = None, venue: str | None = None) -> list[dict]:
    festival = load()
    venue_object = festival.venue(venue) if venue is not None else None
    performances = festival.programme(day=day, venue=venue_object)
    return [performance.to_view() for performance in performances]


@app.get("/api/performances/{performance_id}")
def read_performance(performance_id: str) -> dict:
    return load().performance(performance_id).to_view()


# ?at=2027-06-11T21:00 remplace l'heure actuelle (pratique pour tester).
@app.get("/api/now")
def read_now(at: datetime | None = None) -> dict:
    festival = load()
    if at is None:
        at = datetime.now()
    at = at.replace(tzinfo=None)
    return {
        "at": f"{at:%Y-%m-%dT%H:%M}",
        "now_playing": [p.to_view() for p in festival.on_stage_at(at)],
        "up_next": [p.to_view() for p in festival.next_after(at, 3)],
    }


# ----- Écrire (admin) : chaque changement vérifie les règles puis sauvegarde -----


@app.post("/api/performances", status_code=201)
def create_performance(body: PerformanceIn) -> dict:
    festival = load()
    new = performance_from_dict(festival, body.model_dump())
    festival.add_performance(new)
    save(festival)
    return new.to_view()


@app.put("/api/performances/{performance_id}")
def replace_performance(performance_id: str, body: PerformanceIn) -> dict:
    """Remplace un spectacle (le déplacer change son id). Refusé : rien ne change."""
    festival = load()
    new = performance_from_dict(festival, body.model_dump())
    festival.replace(performance_id, new)
    save(festival)
    return new.to_view()


@app.delete("/api/performances/{performance_id}", status_code=204)
def delete_performance(performance_id: str) -> Response:
    festival = load()
    festival.cancel(performance_id)
    save(festival)
    return Response(status_code=204)


@app.post("/api/performances/{performance_id}/participants", status_code=201)
def register_participant(performance_id: str, body: ParticipantIn) -> dict:
    festival = load()
    performance = festival.register(performance_id, body.name)
    save(festival)
    return performance.to_view()


@app.delete("/api/performances/{performance_id}/participants/{name}", status_code=204)
def unregister_participant(performance_id: str, name: str) -> Response:
    festival = load()
    festival.unregister(performance_id, name)
    save(festival)
    return Response(status_code=204)


@app.post("/api/artists", status_code=201)
def create_artist(body: ArtistIn) -> dict:
    festival = load()
    artist = Artist(body.name, body.bio, body.photo_url)
    festival.add_artist(artist)
    save(festival)
    return artist.to_view()


# ----- Les fichiers du site : après les routes, sinon ils les cacheraient -----

if ADMIN.is_dir():
    app.mount("/admin", StaticFiles(directory=ADMIN, html=True), name="admin")
if WEBSITE.is_dir():
    app.mount("/", StaticFiles(directory=WEBSITE, html=True), name="website")
