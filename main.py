"""Deauville Festival du Rire 2027.

uv run main.py                         le résumé du festival
uv run main.py venues                  chaque salle avec son identifiant et ses places
uv run main.py programme 2027-06-11    le programme d'une journée
uv run main.py artist max-pellerin     les spectacles d'un artiste, avec son rôle
uv run main.py explore                 les six questions de l'étape 01
"""

import json
import sys
import unicodedata

DATA_FILE = "data/festival.json"


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


def festival_days(festival: dict) -> list[str]:
    """La liste des jours où il y a au moins un spectacle, sans doublon, triée."""
    days = []
    for performance in festival["performances"]:
        day = performance["start"][:10]
        if day not in days:
            days.append(day)
    days.sort()
    return days


def programme_of_day(festival: dict, day: str) -> list[dict]:
    """Les spectacles qui commencent ce jour-là, triés par heure."""
    programme = []
    for performance in festival["performances"]:
        if performance["start"][:10] == day:
            programme.append(performance)
    programme.sort(key=lambda performance: performance["start"])
    return programme


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
    result.sort(key=lambda pair: pair[0]["start"])
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


def show_programme(festival: dict, day: str) -> None:
    days = festival_days(festival)
    if day not in days:
        print(f"No performance on {day!r}. Days: {', '.join(days)}")
        return
    print(f"Programme for {day}:")
    for performance in programme_of_day(festival, day):
        time = performance["start"][11:]
        venue = venue_name(festival, performance["venue"])
        print(f"{time} | {venue} | {performance['title']} ({performance['kind']})")


def show_artist(festival: dict, slug: str) -> None:
    artist = find_artist(festival, slug)
    if artist is None:
        print(f"No artist {slug!r}.")
        return
    print(artist["name"])
    for performance, role in performances_of_artist(festival, slug):
        start = performance["start"].replace("T", " ")
        venue = venue_name(festival, performance["venue"])
        print(f"{start} | {venue} | {performance['title']} ({role})")


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
            day = performance["start"][:10]
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
    elif arguments == ["explore"]:
        show_explore(festival)
    else:
        print(__doc__)


main()
