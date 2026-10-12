# Object-Oriented Programming in Python - the project track

ECE Paris - 2026-2027

You learn Python by building one project, from the first line to a web
platform: the programme of the **Deauville Festival du Rire** (10-13 June
2027). The website is given; behind it, everything is yours. Each step adds
one thing that works, and brings the notion that makes it possible.

This repository holds the **sheets** of the steps and small **side examples**
on other subjects (a library, buses, a bank…). They show a technique; your
project is where you use it. Your code lives in **your own repository**,
started from the starter at step 00.

A second repository, the **practice repository**, holds more examples
(notebooks) and exercises with tests for each block. It is optional: use it
when a notion needs more practice. Each sheet ends with the matching part.

## The steps

| Block | Step                                                       | At the end of the step                                       |
| ----- | ---------------------------------------------------------- | ------------------------------------------------------------ |
| B1    | [00 Start](B1/E00_start.md)                                | the project runs and prints a summary of the festival        |
|       | [01 Explore](B1/E01_explore.md)                            | six questions about the data, answered by loops              |
|       | [02 The programme of a day](B1/E02_ask_a_day.md)           | the user asks for a day, gets its programme (with a bug)     |
| B2    | [03 Functions and commands](B2/E03_functions.md)           | `main.py programme 2027-06-11`, on GitHub                    |
|       | [04 Real dates and times](B2/E04_time.md)                  | the night belongs to the right day; what is on stage now     |
|       | [05 Rules, errors and saving](B2/E05_errors_and_saving.md) | adding a show checks the rules and saves the file            |
| B3    | [06 The website lights up](B3/E06_first_routes.md)         | a server; the website shows days, venues, artists            |
|       | [07 The first classes](B3/E07_classes.md)                  | the programme and the artist pages appear                    |
|       | [08 The festival object](B3/E08_festival_object.md)        | "on stage now" appears; tests prove every rule               |
| B4    | [09 Three kinds](B4/E09_three_kinds.md)                    | solo shows, lineups, workshops: one family, no `if kind ==`  |
|       | [10 The admin](B4/E10_admin.md)                            | organisers schedule, move, cancel; nobody bypasses the rules |
|       | [11 A real package](B4/E11_package.md)                     | `uv run deauville serve`, `uv build`                         |
| B5    | [12 The whole contract](B5/E12_full_contract.md)           | all of `API.md`, tested                                      |
|       | [13 Ship it](B5/E13_ship.md)                               | a fresh clone runs; your README explains your structure      |

Each block README lists its steps and side examples: [B1](B1/README.md),
[B2](B2/README.md), [B3](B3/README.md), [B4](B4/README.md),
[B5](B5/README.md).

## How a step works

Each sheet has the same parts:

- **At the end**: what works when the step is done, seen from outside (an
  output in the terminal, a page of the website).
- **Why now**: what the previous version cannot do. The notion of the step
  answers it.
- **Learn**: the notion, short, and the side examples.
- **Do**: what to build. It says _what_ must work, never _which_ functions or
  classes to write: the structure of your project is your work, and you
  defend it at the oral.
- **Check**: the exact output, or what the website must show. No tests are
  given: from step 08, you write your own.

Steps not finished in class are finished at home before the next block: each
block starts where the previous one ended.

## Setup

1. Install uv:
   - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell):
     `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

   Close the terminal, open a new one, check with `uv --version`.

2. Install VS Code with the extensions _Python_ (Microsoft) and _Ruff_
   (Astral). Keep your folders outside OneDrive.
3. Open this folder in VS Code, then a terminal (`Terminal > New Terminal`),
   and run `uv sync`.
4. Side examples run from this folder:

   ```bash
   uv run python B1/side/e00_playlist.py
   ```

Then [step 00](B1/E00_start.md) creates your project, in its own folder.

## Mes classes (étape 07)

Les données du fichier sont chargées une seule fois en objets par
`load_festival` (dans `festival.py`). Après ça, plus personne ne touche aux
dicts du JSON : la ligne de commande (`main.py`) et l'API (`api.py`)
utilisent les mêmes objets, donc les mêmes calculs.

- **`Venue`** (dataclass) — une salle : `name`, `capacity`, `address`.
  Calcule son `slug` (`"le-kiosque"`). `to_view()` donne le dict envoyé par
  l'API.
- **`Artist`** (dataclass) — un artiste : `name`, `bio`, `photo_url`. Calcule
  son `slug`. `to_view()` pour l'API, `to_ref()` pour la forme courte
  `{"slug", "name"}` utilisée dans un spectacle.
- **`Performance`** (dataclass) — un spectacle : `kind`, `title`, `venue`
  (un objet `Venue`, pas un texte), `start` (un vrai `datetime`),
  `duration_minutes`, `description`, et les champs propres à chaque type
  (`artist`/`min_age` pour un solo, `host`/`acts` pour un plateau,
  `teacher`/`max_participants`/`participants` pour un atelier ; `None` sinon).
  `__post_init__` refuse une durée hors de 1 à 360 minutes.
  Propriétés calculées : `end`, `festival_day`, `id`, `roles`, `artists`,
  `summary`, `places_left`. Méthodes : `involves(artist)`,
  `is_too_close_to(other)`, `to_view()` (pour l'API), `to_dict()` (pour
  réécrire le fichier).
  Une seule classe pour les trois types : les `if self.kind == ...` sont
  repérés, ils disparaîtront à l'étape 09 (héritage).
- **`Festival`** (dataclass) — le contenant : `name`, `first_day`,
  `last_day` (de vraies dates) et les listes de salles, d'artistes et de
  spectacles. Les règles et les recherches restent pour l'instant des
  fonctions du module ; l'étape 08 les rangera dans cette classe.

## Known bugs

Aucun bug connu pour l'instant.

### Corrigés

- **Étape 04 — les spectacles après minuit étaient rattachés au mauvais jour.**
  `01:00 | Le Kiosque | After Hours` apparaissait le samedi 12, alors que pour
  le festival c'est la fin de la nuit du **vendredi 11** (une journée se
  termine à 06:00). Le code comparait les 10 premiers caractères de `start`.
  Correction : on utilise de vraies dates (`datetime`), et la journée de
  festival d'un spectacle est la date de son début **moins 6 heures**.
