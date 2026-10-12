"""Deauville Festival du Rire 2027.

uv run main.py                         le résumé du festival
uv run main.py venues                  chaque salle avec son identifiant et ses places
uv run main.py programme 2027-06-11    le programme d'une journée
uv run main.py artist max-pellerin     les spectacles d'un artiste, avec son rôle
uv run main.py now 2027-06-11T21:00    ce qui est sur scène à ce moment, puis la suite
uv run main.py explore                 les six questions de l'étape 01
uv run main.py add                     programmer un nouveau solo (questions posées)
uv run main.py cancel ID               annuler un spectacle
                                       (ex. la-cabane-2027-06-13-0800)
"""

import sys

from festival import (
    DATA_FILE,
    add_performance,
    cancel_performance,
    end_of,
    festival_day_of,
    festival_days,
    find_artist,
    load_festival,
    next_after,
    on_stage_at,
    parse_day,
    parse_minutes,
    parse_moment,
    performance_id,
    performances_of_artist,
    programme_of_day,
    roles_in,
    save_festival,
    slugify,
    start_of,
    total_seats,
    venue_name,
)

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
    day = parse_day(day_text)
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
    moment = parse_moment(moment_text)
    print(f"On stage at {moment:%Y-%m-%d %H:%M}:")
    for performance in on_stage_at(festival, moment):
        venue = venue_name(festival, performance["venue"])
        print(f"- {performance['title']} at {venue}, until {end_of(performance):%H:%M}")
    print("Up next:")
    for performance in next_after(festival, moment, 3):
        print(f"- {performance_line(festival, performance)}")


def ask_and_add(festival: dict) -> None:
    """Commande add : pose les questions, vérifie, ajoute, sauvegarde."""
    title = input("Title: ").strip()
    artist = input("Artist (slug): ").strip()
    venue = input("Venue (slug): ").strip()
    start = parse_moment(input("Start (YYYY-MM-DDTHH:MM): ").strip())
    duration = parse_minutes(input("Duration (minutes): ").strip())
    new = {
        "kind": "solo",
        "title": title,
        "venue": venue,
        "start": f"{start:%Y-%m-%dT%H:%M}",
        "duration_minutes": duration,
        "description": "",
        "artist": artist,
        "min_age": 0,
    }
    add_performance(festival, new)
    save_festival(festival, DATA_FILE)
    print(f"Added: {performance_id(new)}")


def cancel_and_save(festival: dict, performance_id_text: str) -> None:
    """Commande cancel : retire le spectacle puis sauvegarde."""
    cancelled = cancel_performance(festival, performance_id_text)
    save_festival(festival, DATA_FILE)
    print(f"Cancelled: {cancelled['title']}")


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


def run(arguments: list[str]) -> None:
    """Lit la commande tapée et appelle la bonne fonction."""
    festival = load_festival(DATA_FILE)
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
    elif arguments == ["add"]:
        ask_and_add(festival)
    elif arguments[0] == "cancel" and len(arguments) == 2:
        cancel_and_save(festival, arguments[1])
    else:
        print(__doc__)


def main() -> None:
    # Les erreurs sont attrapées ici, à un seul endroit : les autres fonctions
    # se contentent de lever ValueError avec une phrase.
    try:
        # sys.argv : les mots tapés après le nom du fichier,
        # ex. ["artist", "max-pellerin"]
        run(sys.argv[1:])
    except ValueError as error:
        message = str(error)
        print(f"Error: {message[0].upper()}{message[1:]}")
        sys.exit(1)


# Ne lance les commandes que si ce fichier est celui qu'on démarre
# (pas quand un autre fichier fait "import main").
if __name__ == "__main__":
    main()
