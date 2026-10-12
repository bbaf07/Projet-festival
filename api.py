"""Le serveur web du festival : les routes de API.md.

    uv run python -m uvicorn api:app --reload

Puis ouvrir http://127.0.0.1:8000 (le site) et http://127.0.0.1:8000/docs
"""

from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from festival import DATA_FILE, load_festival

WEBSITE = Path("web/public")

app = FastAPI(title="Deauville Festival du Rire")


# Une route : une méthode (GET), un chemin, une fonction.
# Ce que la fonction renvoie devient du JSON.
@app.get("/api/festival")
def read_festival() -> dict:
    festival = load_festival(DATA_FILE)
    return {
        "name": festival.name,
        "first_day": festival.first_day.isoformat(),
        "last_day": festival.last_day.isoformat(),
        "days": [day.isoformat() for day in festival.days()],
    }


@app.get("/api/venues")
def list_venues() -> list[dict]:
    festival = load_festival(DATA_FILE)
    return [venue.to_view() for venue in festival.venues]


@app.get("/api/artists")
def list_artists() -> list[dict]:
    festival = load_festival(DATA_FILE)
    artists = sorted(festival.artists, key=lambda artist: artist.slug)
    return [artist.to_view() for artist in artists]


# {slug} dans le chemin devient un paramètre de la fonction.
@app.get("/api/artists/{slug}")
def read_artist(slug: str) -> dict:
    festival = load_festival(DATA_FILE)
    artist = festival.find_artist(slug)
    if artist is None:
        raise HTTPException(status_code=404, detail=f"No artist {slug!r}.")
    view = artist.to_view()
    view["performances"] = [
        performance.to_view() for performance, _role in festival.performances_of(artist)
    ]
    return view


# Les paramètres absents du chemin viennent de la requête : ?day=...&venue=...
# Grâce à l'annotation `date`, FastAPI refuse ?day=June 11 avec un 422 tout seul.
@app.get("/api/programme")
def list_programme(day: date | None = None, venue: str | None = None) -> list[dict]:
    festival = load_festival(DATA_FILE)
    venue_object = None
    if venue is not None:
        venue_object = festival.find_venue(venue)
        if venue_object is None:
            raise HTTPException(status_code=404, detail=f"No venue {venue!r}.")
    performances = festival.programme(day=day, venue=venue_object)
    return [performance.to_view() for performance in performances]


@app.get("/api/performances/{performance_id}")
def read_performance(performance_id: str) -> dict:
    festival = load_festival(DATA_FILE)
    try:
        return festival.performance(performance_id).to_view()
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None


# ?at=2027-06-11T21:00 remplace l'heure actuelle (pratique pour tester).
@app.get("/api/now")
def read_now(at: datetime | None = None) -> dict:
    festival = load_festival(DATA_FILE)
    if at is None:
        at = datetime.now()
    return {
        "at": f"{at:%Y-%m-%dT%H:%M}",
        "now_playing": [p.to_view() for p in festival.on_stage_at(at)],
        "up_next": [p.to_view() for p in festival.next_after(at, 3)],
    }


# Le site, servi à "/". Après les routes, sinon il les cacherait.
if WEBSITE.is_dir():
    app.mount("/", StaticFiles(directory=WEBSITE, html=True), name="website")
