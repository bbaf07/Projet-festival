"""Deauville Festival du Rire 2027.

uv run main.py                         le résumé du festival
uv run main.py venues                  chaque salle avec son identifiant et ses places
uv run main.py programme 2027-06-11    le programme d'une journée
uv run main.py artist max-pellerin     les spectacles d'un artiste, avec son rôle
uv run main.py now 2027-06-11T21:00    ce qui est sur scène à ce moment, puis la suite
uv run main.py explore                 les six questions de l'étape 01
"""

import json
import sys
import unicodedata
from datetime import date, datetime, timedelta

DATA_FILE = "data/festival.json"

# Règle du festival : une journée se termine à 06:00. Un spectacle à 1 h du
# matin appartient donc à la journée de la veille.
FESTIVAL_DAY_CHANGE = timedelta(hours=6)


# ----- Fonctions qui calculent : elles renvoient un résultat, n'affichent rien -----


def load_festival(path: str) -> dict:
    """Lit le fichier JSON et le transforme en dict Python."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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


def find_venue(festival: dict, slug: str) -> dict | None:
    """Renvoie la salle qui a cet identifiant, ou None si elle n'existe pas."""
    for venue in festival["venues"]:
        if slugify(venue["name"]) == slug:
            return venue
    return None


def find_artist(festival: dict, slug: str) -> dict | None:
    """Renvoie l'artiste qui a cet identifiant, ou None s'il n'existe pas."""
    for artist in festival["artists"]:
        if slugify(artist["name"]) == slug:
            return artist
    return None


def start_of(performance: dict) -> datetime:
    """Le moment où commence un spectacle (texte -> vraie date et heure)."""
    return datetime.fromisoformat(performance["start"])


def end_of(performance: dict) -> datetime:
    """Le moment où se termine un spectacle : début + durée."""
    return start_of(performance) + timedelta(minutes=performance["duration_minutes"])


def festival_day_of(performance: dict) -> date:
    """La journée de festival d'un spectacle : son début moins 6 heures."""
    return (start_of(performance) - FESTIVAL_DAY_CHANGE).date()


def festival_days(festival: dict) -> list[date]:
    """Les journées de festival où il y a au moins un spectacle, triées."""
    days = []
    for performance in festival["performances"]:
        day = festival_day_of(performance)
        if day not in days:
            days.append(day)
    days.sort()
    return days


def programme_of_day(festival: dict, day: date) -> list[dict]:
    """Les spectacles de cette journée de festival, triés par heure de début."""
    programme = []
    for performance in festival["performances"]:
        if festival_day_of(performance) == day:
            programme.append(performance)
    return sorted(programme, key=start_of)


def on_stage_at(festival: dict, moment: datetime) -> list[dict]:
    """Les spectacles en cours à ce moment : commencés, pas encore finis."""
    on_stage = []
    for performance in festival["performances"]:
        if start_of(performance) <= moment < end_of(performance):
            on_stage.append(performance)
    return sorted(on_stage, key=start_of)


def next_after(festival: dict, moment: datetime, count: int) -> list[dict]:
    """Les `count` prochains spectacles qui commencent après ce moment."""
    upcoming = []
    for performance in festival["performances"]:
        if start_of(performance) > moment:
            upcoming.append(performance)
    return sorted(upcoming, key=start_of)[:count]


def roles_in(performance: dict) -> list[tuple[str, str]]:
    """Les artistes d'un spectacle avec leur rôle : [(identifiant, rôle), ...]."""
    if performance["kind"] == "solo":
        return [(performance["artist"], "solo")]
    if performance["kind"] == "lineup":
        roles = [(performance["host"], "host")]
        for act in performance["acts"]:
            roles.append((act, "act"))
        return roles
    if performance["kind"] == "workshop":
        return [(performance["teacher"], "teacher")]
    return []


def performances_of_artist(festival: dict, slug: str) -> list[tuple[dict, str]]:
    """Les spectacles d'un artiste, triés par date, avec son rôle dans chacun."""
    result = []
    for performance in festival["performances"]:
        for artist_slug, role in roles_in(performance):
            if artist_slug == slug:
                result.append((performance, role))
    result.sort(key=lambda pair: start_of(pair[0]))
    return result


def total_seats(festival: dict) -> int:
    """Le nombre total de places, toutes salles confondues."""
    total = 0
    for venue in festival["venues"]:
        total += venue["capacity"]
    return total


def venue_name(festival: dict, slug: str) -> str:
    """Le nom d'une salle à partir de son identifiant."""
    venue = find_venue(festival, slug)
    if venue is None:
        return slug
    return venue["name"]


# ----- Fonctions qui affichent : une par commande, en bout de chaîne -----


def show_summary(festival: dict) -> None:
    print(festival["name"])
    print(f"From {festival['first_day']} to {festival['last_day']}")
    print(
        f"{len(festival['venues'])} venues, "
        f"{len(festival['artists'])} artists, "
        f"{len(festival['performances'])} performances"
    )


def show_venues(festival: dict) -> None:
    for venue in festival["venues"]:
        print(f"{slugify(venue['name'])}: {venue['name']}, {venue['capacity']} seats")
    print(f"Total: {total_seats(festival)} seats")


def performance_line(festival: dict, performance: dict) -> str:
    """Une ligne de programme : "21:30-22:40 | Salle | Titre (type)"."""
    venue = venue_name(festival, performance["venue"])
    return (
        f"{start_of(performance):%H:%M}-{end_of(performance):%H:%M} | {venue} | "
        f"{performance['title']} ({performance['kind']})"
    )


def show_programme(festival: dict, day_text: str) -> None:
    day = date.fromisoformat(day_text)
    days = festival_days(festival)
    if day not in days:
        days_text = ", ".join(str(festival_day) for festival_day in days)
        print(f"No performance on {day_text!r}. Days: {days_text}")
        return
    print(f"Programme for {day:%A %d %B}:")
    for performance in programme_of_day(festival, day):
        print(performance_line(festival, performance))


def show_artist(festival: dict, slug: str) -> None:
    artist = find_artist(festival, slug)
    if artist is None:
        print(f"No artist {slug!r}.")
        return
    print(artist["name"])
    for performance, role in performances_of_artist(festival, slug):
        day = festival_day_of(performance)
        start = start_of(performance)
        end = end_of(performance)
        venue = venue_name(festival, performance["venue"])
        print(
            f"{day:%a %d} {start:%H:%M}-{end:%H:%M} | {venue} | "
            f"{performance['title']} ({role})"
        )


def show_now(festival: dict, moment_text: str) -> None:
    moment = datetime.fromisoformat(moment_text)
    print(f"On stage at {moment:%Y-%m-%d %H:%M}:")
    for performance in on_stage_at(festival, moment):
        venue = venue_name(festival, performance["venue"])
        print(f"- {performance['title']} at {venue}, until {end_of(performance):%H:%M}")
    print("Up next:")
    for performance in next_after(festival, moment, 3):
        print(f"- {performance_line(festival, performance)}")


def show_explore(festival: dict) -> None:
    """Les six questions de l'étape 01."""
    # 1. Chaque salle avec ses places et son adresse, puis le total
    print("Venues:")
    for venue in festival["venues"]:
        print(f"- {venue['name']}: {venue['capacity']} seats ({venue['address']})")
    print(f"Total: {total_seats(festival)} seats")

    # 2. Nombre de spectacles par type
    print()
    kind_counts = {}
    for performance in festival["performances"]:
        kind = performance["kind"]
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    for kind in sorted(kind_counts):
        print(f"{kind}: {kind_counts[kind]}")

    # 3. Spectacles au Kiosque
    print()
    print("At Le Kiosque:")
    for performance in festival["performances"]:
        if performance["venue"] == "le-kiosque":
            print(f"- {performance['start']} {performance['title']}")

    # 4. Le spectacle le plus long
    print()
    longest = festival["performances"][0]
    for performance in festival["performances"]:
        if performance["duration_minutes"] > longest["duration_minutes"]:
            longest = performance
    print(f"Longest: {longest['title']} ({longest['duration_minutes']} min)")

    # 5. Chaque atelier : son jour et ses inscrits
    print()
    for performance in festival["performances"]:
        if performance["kind"] == "workshop":
            day = festival_day_of(performance)
            registered = len(performance["participants"])
            places = performance["max_participants"]
            print(f"{performance['title']} on {day}: {registered}/{places} registered")

    # 6. [ext.] Les artistes les plus souvent sur scène
    print()
    stage_counts = {}
    for performance in festival["performances"]:
        for artist_slug, _role in roles_in(performance):
            stage_counts[artist_slug] = stage_counts.get(artist_slug, 0) + 1
    most = max(stage_counts.values())
    top_artists = []
    for artist_slug, count in stage_counts.items():
        if count == most:
            top_artists.append(artist_slug)
    print(f"On stage {most} times: {', '.join(top_artists)}")


# ----- Point d'entrée : lit la commande tapée et appelle la bonne fonction -----


def main() -> None:
    festival = load_festival(DATA_FILE)
    # sys.argv : les mots tapés après le nom du fichier, ex. ["artist", "max-pellerin"]
    arguments = sys.argv[1:]
    if len(arguments) == 0:
        show_summary(festival)
    elif arguments == ["venues"]:
        show_venues(festival)
    elif arguments[0] == "programme" and len(arguments) == 2:
        show_programme(festival, arguments[1])
    elif arguments[0] == "artist" and len(arguments) == 2:
        show_artist(festival, arguments[1])
    elif arguments[0] == "now" and len(arguments) == 2:
        show_now(festival, arguments[1])
    elif arguments == ["explore"]:
        show_explore(festival)
    else:
        print(__doc__)


main()
