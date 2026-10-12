"""Le serveur web du festival : les routes de API.md.

    uv run uvicorn api:app --reload

Puis ouvrir http://127.0.0.1:8000 (le site) et http://127.0.0.1:8000/docs
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from festival import DATA_FILE, festival_days, load_festival, slugify

WEBSITE = Path("web/public")

app = FastAPI(title="Deauville Festival du Rire")


# Une route : une méthode (GET), un chemin, une fonction.
# Ce que la fonction renvoie devient du JSON.
@app.get("/api/festival")
def read_festival() -> dict:
    festival = load_festival(DATA_FILE)
    return {
        "name": festival["name"],
        "first_day": festival["first_day"],
        "last_day": festival["last_day"],
        "days": [day.isoformat() for day in festival_days(festival)],
    }


@app.get("/api/venues")
def list_venues() -> list[dict]:
    festival = load_festival(DATA_FILE)
    venues = []
    for venue in festival["venues"]:
        venues.append(
            {
                "slug": slugify(venue["name"]),
                "name": venue["name"],
                "capacity": venue["capacity"],
                "address": venue["address"],
            }
        )
    return venues


@app.get("/api/artists")
def list_artists() -> list[dict]:
    festival = load_festival(DATA_FILE)
    artists = []
    for artist in festival["artists"]:
        artists.append(
            {
                "slug": slugify(artist["name"]),
                "name": artist["name"],
                "bio": artist["bio"],
                "photo_url": artist["photo_url"],
            }
        )
    return sorted(artists, key=lambda artist: artist["slug"])


# Le site, servi à "/". Après les routes, sinon il les cacherait.
if WEBSITE.is_dir():
    app.mount("/", StaticFiles(directory=WEBSITE, html=True), name="website")
