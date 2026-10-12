"""La ligne de commande `deauville`.

    deauville                          le résumé du festival
    deauville venues                   chaque salle, son identifiant, ses places
    deauville programme 2027-06-11     le programme d'une journée
    deauville artist max-pellerin      les spectacles d'un artiste, avec son rôle
    deauville now 2027-06-11T21:00     ce qui est sur scène, puis la suite
    deauville explore                  les six questions de l'étape 01
    deauville add                      programmer un nouveau solo (questions)
    deauville cancel ID                annuler un spectacle
    deauville serve                    lancer le site, l'admin et l'API

Option : --data FICHIER pour utiliser un autre fichier de données.
Sur ce PC (Windows bloque les .exe de .venv) : uv run python -m deauville ...
"""

import argparse
import sys
from collections.abc import Callable

from deauville.errors import FestivalError
from deauville.festival import Festival
from deauville.models import SoloShow, Workshop
from deauville.parsing import parse_day, parse_minutes, parse_moment
from deauville.storage import FestivalStorage, JsonStorage

DEFAULT_DATA = "data/festival.json"

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


def ask_and_add(festival: Festival, storage: FestivalStorage) -> None:
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
    storage.save(festival)
    print(f"Added: {new.id}")


def cancel_and_save(
    festival: Festival, storage: FestivalStorage, performance_id: str
) -> None:
    """Commande cancel : retire le spectacle puis sauvegarde."""
    cancelled = festival.cancel(performance_id)
    storage.save(festival)
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
    kind_counts: dict[str, int] = {}
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
    stage_counts: dict[str, int] = {}
    for performance in festival.performances:
        for artist in performance.artists:
            stage_counts[artist.slug] = stage_counts.get(artist.slug, 0) + 1
    most = max(stage_counts.values())
    top_artists = [slug for slug, count in stage_counts.items() if count == most]
    print(f"On stage {most} times: {', '.join(top_artists)}")


def serve(storage: FestivalStorage, host: str, port: int) -> None:
    """Commande serve : lance le site, l'admin et l'API avec uvicorn."""
    import uvicorn  # importé ici : les autres commandes n'en ont pas besoin

    from deauville.api import create_app

    print(f"Website: http://{host}:{port}/   Admin: http://{host}:{port}/admin/")
    uvicorn.run(create_app(storage), host=host, port=port)


# ----- Point d'entrée : lit la commande tapée et appelle la bonne fonction -----


def build_parser() -> argparse.ArgumentParser:
    """Décrit les commandes et leurs arguments (argparse écrit l'aide tout seul)."""
    parser = argparse.ArgumentParser(
        prog="deauville", description="Deauville Festival du Rire 2027."
    )
    parser.add_argument(
        "--data", default=DEFAULT_DATA, help=f"data file (default: {DEFAULT_DATA})"
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("venues", help="each venue, its slug and its seats")
    commands.add_parser("programme", help="the programme of a day").add_argument(
        "day", help="YYYY-MM-DD"
    )
    commands.add_parser("artist", help="the performances of an artist").add_argument(
        "slug"
    )
    commands.add_parser("now", help="on stage at a moment").add_argument(
        "moment", help="YYYY-MM-DDTHH:MM"
    )
    commands.add_parser("explore", help="the six questions of step 01")
    commands.add_parser("add", help="schedule a solo show (asks questions)")
    commands.add_parser("cancel", help="cancel a performance").add_argument("id")
    serve_parser = commands.add_parser("serve", help="website, admin and API")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    return parser


def run(arguments: list[str]) -> None:
    """Lit la commande tapée et appelle la bonne fonction."""
    options = build_parser().parse_args(arguments)
    storage = JsonStorage(options.data)
    if options.command == "serve":
        serve(storage, options.host, options.port)
        return
    festival = storage.load()
    # Chaque commande -> la fonction qui l'affiche (un dict, pas une suite de if).
    commands: dict[str | None, Callable[[], None]] = {
        None: lambda: show_summary(festival),
        "venues": lambda: show_venues(festival),
        "programme": lambda: show_programme(festival, options.day),
        "artist": lambda: show_artist(festival, options.slug),
        "now": lambda: show_now(festival, options.moment),
        "explore": lambda: show_explore(festival),
        "add": lambda: ask_and_add(festival, storage),
        "cancel": lambda: cancel_and_save(festival, storage, options.id),
    }
    commands[options.command]()


def main(arguments: list[str] | None = None) -> None:
    """Point d'entrée de la commande `deauville`.

    Les erreurs sont attrapées ici, à un seul endroit : les autres fonctions se
    contentent de lever une erreur de la famille FestivalError.
    """
    try:
        run(sys.argv[1:] if arguments is None else arguments)
    except FestivalError as error:  # un seul except pour toute la famille
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
