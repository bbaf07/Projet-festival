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
from festival import (
    Artist,
    Festival,
    Lineup,
    Performance,
    SoloShow,
    Venue,
    Workshop,
    load_festival,
)

DATA_FILE = Path(__file__).parent.parent / "data" / "festival.json"


# Une fixture : un festival tout neuf, relu depuis le fichier, pour chaque test
# qui le demande par son nom. Les tests ne réécrivent jamais le fichier.
@pytest.fixture
def festival() -> Festival:
    return load_festival(str(DATA_FILE))


def solo(festival: Festival, artist: str, venue: str, start: str, minutes=30):
    """Fabrique un solo à partir des identifiants, pour écrire des tests courts."""
    return SoloShow(
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


# ----- Étape 09 : trois types, chacun ses règles -----


def lineup(festival: Festival, acts: list[str], minutes: int, host="tom-vasseur"):
    """Fabrique un plateau le 13 à 08:00 à La Cabane."""
    return Lineup(
        title="Test Lineup",
        venue=festival.venue("la-cabane"),
        start=datetime(2027, 6, 13, 8, 0),
        duration_minutes=minutes,
        host=festival.artist(host),
        acts=[festival.artist(slug) for slug in acts],
    )


def workshop(festival: Festival, venue: str, max_participants: int, participants=()):
    """Fabrique un atelier le 13 à 08:00."""
    return Workshop(
        title="Test Workshop",
        venue=festival.venue(venue),
        start=datetime(2027, 6, 13, 8, 0),
        duration_minutes=60,
        teacher=festival.artist("ines-moreau"),
        max_participants=max_participants,
        participants=list(participants),
    )


def test_a_bare_performance_cannot_be_created(festival):
    with pytest.raises(TypeError):
        Performance("X", festival.venue("la-cabane"), datetime(2027, 6, 13, 8), 30)


def test_the_loader_chooses_the_class(festival):
    assert isinstance(festival.performance("le-kiosque-2027-06-12-0100"), Lineup)
    assert isinstance(festival.performance("la-cabane-2027-06-11-1030"), Workshop)
    assert isinstance(festival.performance("grand-casino-2027-06-11-2030"), SoloShow)


@pytest.mark.parametrize(
    ("performance_id", "summary"),
    [
        (
            "le-kiosque-2027-06-12-0100",
            "hosted by Tom Vasseur, with Hugo Lemaire, Maya Choukri",
        ),
        ("la-cabane-2027-06-11-1030", "with Inès Moreau, 3/12 places taken"),
        ("grand-casino-2027-06-11-2030", "Léa Fontaine"),
    ],
)
def test_each_kind_writes_its_own_summary(festival, performance_id, summary):
    assert festival.performance(performance_id).summary() == summary


@pytest.mark.parametrize("min_age", [-1, 19])
def test_a_minimum_age_out_of_range_is_refused(festival, min_age):
    with pytest.raises(ValueError, match="minimum age goes from 0 to 18"):
        SoloShow(
            "X",
            festival.venue("la-cabane"),
            datetime(2027, 6, 13, 8),
            30,
            artist=festival.artist("karim-benali"),
            min_age=min_age,
        )


def test_a_lineup_needs_two_acts(festival):
    with pytest.raises(ValueError, match="at least 2 acts"):
        lineup(festival, ["hugo-lemaire"], 60)


def test_each_act_only_once(festival):
    with pytest.raises(ValueError, match="only once"):
        lineup(festival, ["hugo-lemaire", "hugo-lemaire"], 60)


def test_the_host_is_not_an_act(festival):
    with pytest.raises(ValueError, match="both the host and an act"):
        lineup(festival, ["hugo-lemaire", "tom-vasseur"], 60)


def test_a_lineup_of_three_acts_needs_36_minutes(festival):
    acts = ["hugo-lemaire", "maya-choukri", "karim-benali"]
    with pytest.raises(ValueError, match="at least 36 minutes, not 35"):
        lineup(festival, acts, 35)
    assert lineup(festival, acts, 36).duration_minutes == 36


def test_a_workshop_needs_one_place(festival):
    with pytest.raises(ValueError, match="at least 1 place"):
        workshop(festival, "la-cabane", 0)


def test_workshop_places_never_exceed_the_venue(festival):
    big = workshop(festival, "grand-casino", 999)
    assert big.places == 650
    assert big.capacity == 650


def test_a_workshop_cannot_hold_more_participants_than_places(festival):
    with pytest.raises(ValueError, match="has 1 places, not 2"):
        workshop(festival, "la-cabane", 1, ["Lou", "Zoé"])


def test_the_view_of_each_kind_adds_its_own_fields(festival):
    common = {"id", "kind", "title", "venue", "venue_name", "start", "end"}
    solo_view = festival.performance("grand-casino-2027-06-11-2030").to_view()
    assert common <= set(solo_view)
    assert {"artist", "min_age"} <= set(solo_view)
    workshop_view = festival.performance("la-cabane-2027-06-11-1030").to_view()
    assert workshop_view["places_left"] == 9
    assert "acts" not in workshop_view
