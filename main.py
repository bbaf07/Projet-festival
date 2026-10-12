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

from errors import FestivalError
from festival import (
    DATA_FILE,
    Festival,
    SoloShow,
    Workshop,
    load_festival,
    parse_day,
    parse_minutes,
    parse_moment,
    save_festival,
)

# ----- Fonctions qui affichent : une par commande, en bout de chaîne -----


def show_summary(festival: Festival) -> None:
    print(festival.name)
    print(f"From {festival.first_day} to {festival.last_day}")
    print(
        f"{len(festival.venues)} venues, "
        f"{len(festival.artists)} artists, "
        f"{len(festival.performances)} performances"
    )


def show_venues(festival: Festival) -> None:
    for venue in festival.venues:
        print(f"{venue.slug}: {venue.name}, {venue.capacity} seats")
    print(f"Total: {festival.total_seats} seats")


def show_programme(festival: Festival, day_text: str) -> None:
    day = parse_day(day_text)
    days = festival.days()
    if day not in days:
        days_text = ", ".join(str(festival_day) for festival_day in days)
        print(f"No performance on {day_text!r}. Days: {days_text}")
        return
    print(f"Programme for {day:%A %d %B}:")
    for performance in festival.programme(day=day):
        print(performance)  # print() utilise Performance.__str__


def show_artist(festival: Festival, slug: str) -> None:
    artist = festival.find_artist(slug)
    if artist is None:
        print(f"No artist {slug!r}.")
        return
    print(artist.name)
    for performance, role in festival.performances_of(artist):
        print(
            f"{performance.festival_day:%a %d} "
            f"{performance.start:%H:%M}-{performance.end:%H:%M} | "
            f"{performance.venue.name} | {performance.title} ({role})"
        )


def show_now(festival: Festival, moment_text: str) -> None:
    moment = parse_moment(moment_text)
    print(f"On stage at {moment:%Y-%m-%d %H:%M}:")
    for performance in festival.on_stage_at(moment):
        print(
            f"- {performance.title} at {performance.venue.name}, "
            f"until {performance.end:%H:%M}"
        )
    print("Up next:")
    for performance in festival.next_after(moment, 3):
        print(f"- {performance}")


def ask_and_add(festival: Festival) -> None:
    """Commande add : pose les questions, crée l'objet, vérifie, ajoute, sauve."""
    title = input("Title: ").strip()
    artist_slug = input("Artist (slug): ").strip()
    venue_slug = input("Venue (slug): ").strip()
    start = parse_moment(input("Start (YYYY-MM-DDTHH:MM): ").strip())
    duration = parse_minutes(input("Duration (minutes): ").strip())
    # venue() / artist() lèvent une erreur si l'identifiant est inconnu,
    # et SoloShow(...) refuse une durée hors des règles (dans __init__).
    new = SoloShow(
        title=title,
        venue=festival.venue(venue_slug),
        start=start,
        duration_minutes=duration,
        artist=festival.artist(artist_slug),
        min_age=0,
    )
    festival.add_performance(new)  # vérifie toutes les règles avant d'ajouter
    save_festival(festival, DATA_FILE)
    print(f"Added: {new.id}")


def cancel_and_save(festival: Festival, performance_id: str) -> None:
    """Commande cancel : retire le spectacle puis sauvegarde."""
    cancelled = festival.cancel(performance_id)
    save_festival(festival, DATA_FILE)
    print(f"Cancelled: {cancelled.title}")


def show_explore(festival: Festival) -> None:
    """Les six questions de l'étape 01."""
    # 1. Chaque salle avec ses places et son adresse, puis le total
    print("Venues:")
    for venue in festival.venues:
        print(f"- {venue.name}: {venue.capacity} seats ({venue.address})")
    print(f"Total: {festival.total_seats} seats")

    # 2. Nombre de spectacles par type
    print()
    kind_counts = {}
    for performance in festival.performances:
        kind_counts[performance.kind] = kind_counts.get(performance.kind, 0) + 1
    for kind in sorted(kind_counts):
        print(f"{kind}: {kind_counts[kind]}")

    # 3. Spectacles au Kiosque
    print()
    print("At Le Kiosque:")
    for performance in festival.performances:
        if performance.venue.slug == "le-kiosque":
            print(f"- {performance.start:%Y-%m-%dT%H:%M} {performance.title}")

    # 4. Le spectacle le plus long
    print()
    longest = festival.performances[0]
    for performance in festival.performances:
        if performance.duration_minutes > longest.duration_minutes:
            longest = performance
    print(f"Longest: {longest.title} ({longest.duration_minutes} min)")

    # 5. Chaque atelier : son jour et ses inscrits
    print()
    for performance in festival.performances:
        if isinstance(performance, Workshop):
            print(
                f"{performance.title} on {performance.festival_day}: "
                f"{len(performance.participants)}/{performance.max_participants} "
                "registered"
            )

    # 6. [ext.] Les artistes les plus souvent sur scène
    print()
    stage_counts = {}
    for performance in festival.performances:
        for artist in performance.artists:
            stage_counts[artist.slug] = stage_counts.get(artist.slug, 0) + 1
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
    # se contentent de lever une erreur de la famille FestivalError.
    try:
        # sys.argv : les mots tapés après le nom du fichier,
        # ex. ["artist", "max-pellerin"]
        run(sys.argv[1:])
    except FestivalError as error:  # un seul except pour toute la famille
        print(f"Error: {error}")
        sys.exit(1)


# Ne lance les commandes que si ce fichier est celui qu'on démarre
# (pas quand un autre fichier fait "import main").
if __name__ == "__main__":
    main()
