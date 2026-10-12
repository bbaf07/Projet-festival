"""Le contrat de API.md, testé par HTTP, sans serveur et sans toucher au vrai
fichier de données.

    uv run pytest tests/test_api.py -v

Chaque test reçoit une copie de data/festival.json dans `tmp_path` (un dossier
neuf, effacé ensuite) : aucun test ne dépend d'un autre.
"""

import json
import os
import shutil
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from deauville.api import create_app
from deauville.storage import JsonStorage, MemoryStorage

DATA_FILE = Path(__file__).parent.parent / "data" / "festival.json"

AFTER_HOURS = "le-kiosque-2027-06-12-0100"
IMPROV = "la-cabane-2027-06-11-1030"
STAND_UP_LAB = "la-cabane-2027-06-12-1030"


@pytest.fixture
def data_file(tmp_path: Path) -> Path:
    """Une copie du fichier de données, propre à ce test."""
    copy = tmp_path / "festival.json"
    shutil.copy(DATA_FILE, copy)
    return copy


@pytest.fixture
def client(data_file: Path) -> TestClient:
    return TestClient(create_app(JsonStorage(data_file)))


def saved(data_file: Path) -> dict:
    """Ce qui est écrit dans le fichier, relu depuis le disque."""
    return json.loads(data_file.read_text(encoding="utf-8"))


def solo_body(**changes: object) -> dict:
    """Un solo valide (Nora Lebrun au Kiosque le 13 à 11:00), modifiable."""
    body = {
        "kind": "solo",
        "title": "Brunch Solo",
        "venue": "le-kiosque",
        "start": "2027-06-13T11:00",
        "duration_minutes": 45,
        "artist": "nora-lebrun",
        "min_age": 16,
    }
    body.update(changes)
    return body


# ----- Lire -----


def test_festival(client):
    assert client.get("/api/festival").json() == {
        "name": "Deauville Festival du Rire 2027",
        "first_day": "2027-06-10",
        "last_day": "2027-06-13",
        "days": ["2027-06-10", "2027-06-11", "2027-06-12", "2027-06-13"],
    }


def test_venues_in_the_order_of_the_file(client):
    venues = client.get("/api/venues").json()
    assert [v["slug"] for v in venues] == [
        "grand-casino",
        "theatre-des-planches",
        "le-kiosque",
        "la-cabane",
    ]
    assert set(venues[0]) == {"slug", "name", "capacity", "address"}


def test_artists_sorted_by_slug(client):
    artists = client.get("/api/artists").json()
    assert len(artists) == 12
    assert artists[0]["name"] == "Élodie Marchal"
    slugs = [a["slug"] for a in artists]
    assert slugs == sorted(slugs)


def test_one_artist_with_their_performances(client):
    max_pellerin = client.get("/api/artists/max-pellerin").json()
    titles = [p["title"] for p in max_pellerin["performances"]]
    assert titles == [
        "Opening Gala",
        "Late Laughs",
        "Deauville Comedy Club",
        "Closing Gala",
    ]


def test_programme_without_filter_is_sorted(client):
    programme = client.get("/api/programme").json()
    assert len(programme) == 23
    starts = [p["start"] for p in programme]
    assert starts == sorted(starts)


def test_programme_of_a_day_ends_with_after_hours(client):
    friday = client.get("/api/programme", params={"day": "2027-06-11"}).json()
    assert friday[-1]["id"] == AFTER_HOURS


def test_programme_of_a_venue(client):
    kiosque = client.get("/api/programme", params={"venue": "le-kiosque"}).json()
    assert len(kiosque) == 7


def test_programme_of_a_day_and_a_venue(client):
    params = {"day": "2027-06-11", "venue": "le-kiosque"}
    titles = [p["title"] for p in client.get("/api/programme", params=params).json()]
    assert titles == ["Writing a Punchline", "Late Laughs", "After Hours"]


def test_one_performance_is_the_view_of_the_sheet(client):
    assert client.get(f"/api/performances/{AFTER_HOURS}").json() == {
        "id": AFTER_HOURS,
        "kind": "lineup",
        "title": "After Hours",
        "venue": "le-kiosque",
        "venue_name": "Le Kiosque",
        "start": "2027-06-12T01:00",
        "end": "2027-06-12T02:00",
        "duration_minutes": 60,
        "festival_day": "2027-06-11",
        "description": "The last show of Friday night, after midnight.",
        "summary": "hosted by Tom Vasseur, with Hugo Lemaire, Maya Choukri",
        "capacity": 120,
        "host": "tom-vasseur",
        "acts": ["hugo-lemaire", "maya-choukri"],
        "artists": [
            {"slug": "tom-vasseur", "name": "Tom Vasseur"},
            {"slug": "hugo-lemaire", "name": "Hugo Lemaire"},
            {"slug": "maya-choukri", "name": "Maya Choukri"},
        ],
    }


def test_a_workshop_view(client):
    improv = client.get(f"/api/performances/{IMPROV}").json()
    assert improv["places_left"] == 9
    assert improv["teacher"] == "ines-moreau"
    assert improv["participants"] == ["Camille R.", "Yanis B.", "Lou M."]


@pytest.mark.parametrize(
    ("at", "now_playing", "up_next"),
    [
        (
            "2027-06-11T21:00",
            ["Tall Tales"],
            ["Straight Face", "Late Laughs", "After Hours"],
        ),
        (
            "2027-06-12T01:30",
            ["After Hours"],
            ["Stand-up Lab", "Brunch & Punchlines", "New Faces"],
        ),
    ],
)
def test_now(client, at, now_playing, up_next):
    body = client.get("/api/now", params={"at": at}).json()
    assert [p["title"] for p in body["now_playing"]] == now_playing
    assert [p["title"] for p in body["up_next"]] == up_next


def test_now_without_at_uses_the_current_time(client):
    response = client.get("/api/now")
    assert response.status_code == 200
    assert len(response.json()["up_next"]) <= 3


# ----- Les erreurs de lecture -----


@pytest.mark.parametrize(
    ("url", "detail"),
    [
        ("/api/artists/nobody", "No artist 'nobody'."),
        ("/api/performances/nowhere-2027", "No performance 'nowhere-2027'."),
        ("/api/programme?venue=nowhere", "No venue 'nowhere'."),
    ],
)
def test_unknown_is_a_404_with_a_sentence(client, url, detail):
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize("url", ["/api/programme?day=June 11", "/api/now?at=tonight"])
def test_a_badly_shaped_parameter_is_a_422(client, url):
    assert client.get(url).status_code == 422


# ----- Écrire -----


def test_create_a_performance_is_saved(client, data_file):
    response = client.post("/api/performances", json=solo_body())
    assert response.status_code == 201
    assert response.json()["id"] == "le-kiosque-2027-06-13-1100"
    assert response.json()["min_age"] == 16
    titles = [p["title"] for p in saved(data_file)["performances"]]
    assert "Brunch Solo" in titles


def test_create_each_kind(client):
    lineup = {
        "kind": "lineup",
        "title": "Morning Lineup",
        "venue": "la-cabane",
        "start": "2027-06-13T08:00",
        "duration_minutes": 30,
        "host": "tom-vasseur",
        "acts": ["karim-benali", "elodie-marchal"],
    }
    response = client.post("/api/performances", json=lineup)
    assert response.status_code == 201, response.json()
    workshop = {
        "kind": "workshop",
        "title": "Clowning",
        "venue": "grand-casino",
        "start": "2027-06-10T10:00",
        "duration_minutes": 90,
        "teacher": "ines-moreau",
        "max_participants": 999,
    }
    response = client.post("/api/performances", json=workshop)
    assert response.status_code == 201, response.json()
    assert response.json()["capacity"] == 650
    assert response.json()["places_left"] == 650


@pytest.mark.parametrize(
    ("changes", "status", "detail"),
    [
        ({"venue": "nowhere"}, 404, "No venue 'nowhere'."),
        ({"artist": "nobody"}, 404, "No artist 'nobody'."),
        ({"start": "2027-06-12T02:15", "venue": "le-kiosque"}, 409, "busy"),
        (
            {
                "start": "2027-06-11T23:00",
                "artist": "max-pellerin",
                "venue": "la-cabane",
            },
            409,
            "Max Pellerin is on stage in Late Laughs",
        ),
        ({"duration_minutes": 0}, 422, "from 1 to 360 minutes"),
        ({"duration_minutes": 361}, 422, "from 1 to 360 minutes"),
        ({"min_age": 19}, 422, "minimum age"),
        ({"start": "2027-06-14T11:00"}, 422, "not a day of the festival"),
        ({"artist": None}, 422, "needs the field 'artist'"),
        ({"title": "  "}, 422, "needs a title"),
    ],
)
def test_create_refused(client, data_file, changes, status, detail):
    before = saved(data_file)
    response = client.post("/api/performances", json=solo_body(**changes))
    assert response.status_code == status
    assert detail in response.json()["detail"]
    assert saved(data_file) == before  # rien n'a changé


def test_lineup_rules_through_the_api(client):
    body = {
        "kind": "lineup",
        "title": "Too Short",
        "venue": "la-cabane",
        "start": "2027-06-13T08:00",
        "duration_minutes": 35,
        "host": "tom-vasseur",
        "acts": ["karim-benali", "elodie-marchal", "sacha-diallo"],
    }
    response = client.post("/api/performances", json=body)
    assert response.status_code == 422
    assert "at least 36 minutes" in response.json()["detail"]
    one_act = {**body, "acts": ["karim-benali"], "duration_minutes": 60}
    response = client.post("/api/performances", json=one_act)
    assert response.status_code == 422
    assert "at least 2 acts" in response.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "solo"},
        {**solo_body(), "kind": "opera"},
        {**solo_body(), "duration_minutes": "an hour"},
        {**solo_body(), "start": "tomorrow"},
    ],
)
def test_a_badly_shaped_body_is_a_422(client, body):
    assert client.post("/api/performances", json=body).status_code == 422


def test_put_moves_and_changes_the_id(client, data_file):
    client.post("/api/performances", json=solo_body())
    response = client.put(
        "/api/performances/le-kiosque-2027-06-13-1100",
        json=solo_body(start="2027-06-13T12:00"),
    )
    assert response.status_code == 200
    assert response.json()["id"] == "le-kiosque-2027-06-13-1200"
    old = client.get("/api/performances/le-kiosque-2027-06-13-1100")
    assert old.status_code == 404
    rows = saved(data_file)["performances"]
    brunch = [p["start"] for p in rows if p["title"] == "Brunch Solo"]
    assert brunch == ["2027-06-13T12:00"]  # déplacé, pas copié


def test_put_refused_changes_nothing(client, data_file):
    client.post("/api/performances", json=solo_body(start="2027-06-13T12:00"))
    before = saved(data_file)
    # À 15:00, Maya Choukri joue "First Time Here" au Kiosque.
    response = client.put(
        "/api/performances/le-kiosque-2027-06-13-1200",
        json=solo_body(start="2027-06-13T15:00"),
    )
    assert response.status_code == 409
    assert saved(data_file) == before
    still = client.get("/api/performances/le-kiosque-2027-06-13-1200")
    assert still.status_code == 200


def test_put_on_an_unknown_performance_is_a_404(client):
    response = client.put("/api/performances/nowhere", json=solo_body())
    assert response.status_code == 404


def test_delete_twice(client, data_file):
    first = client.delete(f"/api/performances/{AFTER_HOURS}")
    assert first.status_code == 204
    assert first.content == b""
    assert len(saved(data_file)["performances"]) == 22
    second = client.delete(f"/api/performances/{AFTER_HOURS}")
    assert second.status_code == 404


def test_register_a_participant(client, data_file):
    url = f"/api/performances/{STAND_UP_LAB}/participants"
    response = client.post(url, json={"name": "Zoé"})
    assert response.status_code == 201
    assert response.json()["places_left"] == 5
    rows = saved(data_file)["performances"]
    lab = next(p for p in rows if p["title"] == "Stand-up Lab")
    assert lab["participants"][-1] == "Zoé"


def test_the_same_participant_twice_is_a_409(client):
    url = f"/api/performances/{STAND_UP_LAB}/participants"
    assert client.post(url, json={"name": "Zoé"}).status_code == 201
    response = client.post(url, json={"name": "zoé"})
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


def test_a_full_workshop_is_a_409(client):
    url = f"/api/performances/{STAND_UP_LAB}/participants"
    for number in range(6):  # 4 inscrits sur 10 : 6 places restantes
        assert client.post(url, json={"name": f"P{number}"}).status_code == 201
    response = client.post(url, json={"name": "One Too Many"})
    assert response.status_code == 409
    assert "full" in response.json()["detail"]


def test_register_in_a_show_that_is_not_a_workshop_is_a_422(client):
    url = f"/api/performances/{AFTER_HOURS}/participants"
    assert client.post(url, json={"name": "Lou"}).status_code == 422


def test_unregister(client):
    url = f"/api/performances/{IMPROV}/participants"
    assert client.delete(f"{url}/Lou M.").status_code == 204
    assert client.delete(f"{url}/Lou M.").status_code == 404
    improv = client.get(f"/api/performances/{IMPROV}").json()
    assert improv["places_left"] == 10


def test_add_an_artist_then_the_same_again(client, data_file):
    response = client.post("/api/artists", json={"name": "Zoé Tanguy"})
    assert response.status_code == 201
    assert response.json()["slug"] == "zoe-tanguy"
    assert saved(data_file)["artists"][-1]["name"] == "Zoé Tanguy"
    again = client.post("/api/artists", json={"name": "zoe tanguy"})
    assert again.status_code == 409
    assert again.json() == {"detail": "The artist Zoé Tanguy already exists."}


def test_an_artist_without_a_name_is_a_422(client):
    assert client.post("/api/artists", json={"name": " ! "}).status_code == 422
    assert client.post("/api/artists", json={}).status_code == 422


# ----- Le stockage -----


def test_a_damaged_file_is_a_500(client, data_file):
    data_file.write_text("[{", encoding="utf-8")
    response = client.get("/api/festival")
    assert response.status_code == 500
    assert "damaged" in response.json()["detail"]


def test_a_file_that_cannot_be_written_is_a_500(client, data_file):
    os.chmod(data_file, stat.S_IREAD)  # lecture seule
    try:
        response = client.post("/api/performances", json=solo_body())
        assert response.status_code == 500
        assert "cannot be written" in response.json()["detail"]
    finally:
        os.chmod(data_file, stat.S_IREAD | stat.S_IWRITE)


def test_the_api_works_with_a_storage_in_memory():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    client = TestClient(create_app(MemoryStorage(data)))
    assert client.post("/api/performances", json=solo_body()).status_code == 201
    assert len(client.get("/api/programme").json()) == 24
    assert len(data["performances"]) == 23  # le dict d'origine n'a pas bougé
