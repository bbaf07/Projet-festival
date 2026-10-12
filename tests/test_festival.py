"""Les tests du festival : chaque règle du brief est prouvée.

    uv run pytest tests/test_festival.py -v

Un test est une fonction dont le nom commence par test_. Il prépare une
situation, agit, puis vérifie avec assert. pytest les trouve et les lance tous.
"""

from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import app
from festival import Artist, Festival, Performance, Venue, load_festival

DATA_FILE = Path(__file__).parent.parent / "data" / "festival.json"


# Une fixture : un festival tout neuf, relu depuis le fichier, pour chaque test
# qui le demande par son nom. Les tests ne réécrivent jamais le fichier.
@pytest.fixture
def festival() -> Festival:
    return load_festival(str(DATA_FILE))


def solo(festival: Festival, artist: str, venue: str, start: str, minutes=30):
    """Fabrique un solo à partir des identifiants, pour écrire des tests courts."""
    return Performance(
        kind="solo",
        title="Test Show",
        venue=festival.venue(venue),
        start=datetime.fromisoformat(start),
        duration_minutes=minutes,
        artist=festival.artist(artist),
        min_age=0,
    )


# ----- Le fichier et les calculs -----


def test_the_data_file_is_loaded(festival):
    assert festival.name == "Deauville Festival du Rire 2027"
    assert len(festival.venues) == 4
    assert len(festival.artists) == 12
    assert len(festival.performances) == 23
    assert festival.total_seats == 1130


def test_end_of_a_performance(festival):
    tall_tales = festival.performance("grand-casino-2027-06-11-2030")
    assert tall_tales.end == datetime(2027, 6, 11, 21, 50)


def test_a_show_at_one_am_belongs_to_the_previous_day(festival):
    after_hours = festival.performance("le-kiosque-2027-06-12-0100")
    assert after_hours.festival_day == date(2027, 6, 11)
    friday = festival.programme(day=date(2027, 6, 11))
    assert friday[-1].title == "After Hours"
    saturday = festival.programme(day=date(2027, 6, 12))
    assert "After Hours" not in [p.title for p in saturday]


def test_places_left_of_a_workshop(festival):
    workshop = festival.performance("la-cabane-2027-06-11-1030")
    assert workshop.places_left == 9


def test_performances_of_an_artist_with_their_role(festival):
    max_pellerin = festival.artist("max-pellerin")
    found = [(p.title, role) for p, role in festival.performances_of(max_pellerin)]
    assert found == [
        ("Opening Gala", "act"),
        ("Late Laughs", "solo"),
        ("Deauville Comedy Club", "host"),
        ("Closing Gala", "act"),
    ]


def test_on_stage_and_up_next(festival):
    moment = datetime(2027, 6, 11, 21, 0)
    assert [p.title for p in festival.on_stage_at(moment)] == ["Tall Tales"]
    assert [p.title for p in festival.next_after(moment)] == [
        "Straight Face",
        "Late Laughs",
        "After Hours",
    ]


# ----- Les méthodes spéciales -----


def test_performances_sort_by_start_then_venue_name(festival):
    performances = sorted(festival.performances)
    for first, second in zip(performances, performances[1:], strict=False):
        assert (first.start, first.venue.name) <= (second.start, second.venue.name)


def test_two_artists_with_the_same_slug_are_equal():
    assert Artist("Max Pellerin", "", "") == Artist("Max Pellerin", "other bio", "")
    assert Artist("Max Pellerin", "", "") != Artist("Hugo Lemaire", "", "")


def test_str_of_a_performance_is_the_programme_line(festival):
    straight_face = festival.performance("theatre-des-planches-2027-06-11-2130")
    assert str(straight_face) == (
        "21:30-22:40 | Théâtre des Planches | Straight Face (solo)"
    )


# ----- Les règles : un ajout valide passe, chaque règle enfreinte est refusée -----


def test_a_valid_performance_is_added(festival):
    new = solo(festival, "karim-benali", "la-cabane", "2027-06-13T08:00")
    festival.add_performance(new)
    assert festival.performance("la-cabane-2027-06-13-0800") == new
    assert festival.programme(day=date(2027, 6, 13))[0] == new


def test_venue_busy(festival):
    # After Hours occupe le Kiosque de 01:00 à 02:00, donc pas avant 02:30.
    new = solo(festival, "karim-benali", "le-kiosque", "2027-06-12T02:15")
    with pytest.raises(ValueError, match="Le Kiosque is busy with After Hours"):
        festival.add_performance(new)
    assert len(festival.performances) == 23  # rien n'a été ajouté


def test_venue_free_exactly_30_minutes_after(festival):
    # La limite : 30 minutes pile après la fin, c'est autorisé.
    new = solo(festival, "karim-benali", "le-kiosque", "2027-06-12T02:30")
    festival.add_performance(new)
    assert len(festival.performances) == 24


def test_artist_busy_in_another_venue(festival):
    # Max Pellerin joue Late Laughs au Kiosque à 23:30 le 11.
    new = solo(festival, "max-pellerin", "la-cabane", "2027-06-11T23:00")
    with pytest.raises(ValueError, match="Max Pellerin is on stage in Late Laughs"):
        festival.add_performance(new)


def test_artist_busy_as_an_act_of_a_lineup(festival):
    # Hugo Lemaire est un "act" d'After Hours (01:00-02:00) : pas de solo à 02:00.
    new = solo(festival, "hugo-lemaire", "la-cabane", "2027-06-12T02:00")
    with pytest.raises(ValueError, match="Hugo Lemaire is on stage in After Hours"):
        festival.add_performance(new)


def test_a_day_outside_the_festival(festival):
    new = solo(festival, "karim-benali", "la-cabane", "2027-06-14T08:00")
    with pytest.raises(ValueError, match="2027-06-14 is not a day of the festival"):
        festival.add_performance(new)


def test_one_am_before_the_first_day_is_outside_the_festival(festival):
    # Le 10 à 03:00 appartient à la journée du 9 : avant le festival.
    new = solo(festival, "karim-benali", "la-cabane", "2027-06-10T03:00")
    with pytest.raises(ValueError, match="2027-06-09 is not a day of the festival"):
        festival.add_performance(new)


@pytest.mark.parametrize("minutes", [0, 361])
def test_a_duration_out_of_range_is_refused(festival, minutes):
    with pytest.raises(ValueError, match="from 1 to 360 minutes"):
        solo(festival, "karim-benali", "la-cabane", "2027-06-13T08:00", minutes)


@pytest.mark.parametrize("minutes", [1, 360])
def test_the_limits_of_the_duration_are_allowed(festival, minutes):
    new = solo(festival, "karim-benali", "la-cabane", "2027-06-13T07:00", minutes)
    assert new.duration_minutes == minutes


def test_an_unknown_venue(festival):
    with pytest.raises(ValueError, match="No venue 'piscine'"):
        festival.venue("piscine")


def test_an_unknown_artist(festival):
    with pytest.raises(ValueError, match="No artist 'nobody'"):
        festival.artist("nobody")


def test_a_venue_not_in_the_festival_is_refused(festival):
    # Même un objet Venue fabriqué à la main ne passe pas s'il n'est pas au festival.
    new = solo(festival, "karim-benali", "la-cabane", "2027-06-13T08:00")
    new.venue = Venue("Piscine", 50, "Nowhere")
    with pytest.raises(ValueError, match="No venue 'piscine'"):
        festival.add_performance(new)


def test_an_artist_not_in_the_festival_is_refused(festival):
    new = solo(festival, "karim-benali", "la-cabane", "2027-06-13T08:00")
    new.artist = Artist("Nobody Known", "", "")
    with pytest.raises(ValueError, match="No artist 'nobody-known'"):
        festival.add_performance(new)


def test_cancel(festival):
    cancelled = festival.cancel("le-kiosque-2027-06-12-0100")
    assert cancelled.title == "After Hours"
    assert len(festival.performances) == 22
    with pytest.raises(ValueError, match="No performance"):
        festival.cancel("le-kiosque-2027-06-12-0100")


# ----- L'API -----


def test_api_now():
    client = TestClient(app)
    response = client.get("/api/now", params={"at": "2027-06-11T21:00"})
    assert response.status_code == 200
    body = response.json()
    assert [p["title"] for p in body["now_playing"]] == ["Tall Tales"]
    assert [p["title"] for p in body["up_next"]] == [
        "Straight Face",
        "Late Laughs",
        "After Hours",
    ]


def test_api_unknown_venue_is_a_404():
    client = TestClient(app)
    response = client.get("/api/programme", params={"venue": "nowhere"})
    assert response.status_code == 404
    assert response.json() == {"detail": "No venue 'nowhere'."}
