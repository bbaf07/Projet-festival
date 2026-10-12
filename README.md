# Deauville Festival du Rire 2027

La plateforme du festival du rire de Deauville (10-13 juin 2027) : le
programme, les artistes, ce qui est sur scène maintenant, et un espace
d'administration pour programmer, déplacer et annuler des spectacles. Toutes
les règles du festival sont vérifiées à chaque changement.

Projet du cours de programmation orientée objet en Python (ECE Paris,
2026-2027). Le code est le mien ; les dossiers `B1/` à `B5/` contiennent les
fiches et les exemples du cours qui ont guidé chaque étape.

## Ce que fait le projet

- **Une ligne de commande** `deauville` : résumé, salles, programme d'une
  journée, spectacles d'un artiste, ce qui est sur scène à un moment, ajout
  et annulation d'un spectacle.
- **Une API web** (FastAPI) : tout le contrat décrit dans [API.md](API.md),
  en lecture (programme, artistes, « sur scène maintenant ») et en écriture
  (admin : créer, déplacer, annuler, inscrire un participant, ajouter un
  artiste).
- **Le site et l'admin** : servis par la même commande, à `/` et à `/admin/`,
  depuis le dossier `web/` (voir _Ce qui n'est pas fait_).

## Installer

Il faut [uv](https://docs.astral.sh/uv/) :

```bash
uv sync
```

`uv sync` crée l'environnement `.venv`, installe les dépendances (FastAPI,
uvicorn, et pytest/ruff pour le développement) et le projet lui-même.

## Lancer

```bash
uv run deauville                          # le résumé du festival
uv run deauville venues                   # les salles, leur identifiant, leurs places
uv run deauville programme 2027-06-11     # le programme d'une journée
uv run deauville artist max-pellerin      # les spectacles d'un artiste et son rôle
uv run deauville now 2027-06-11T21:00     # sur scène à ce moment, puis les 3 suivants
uv run deauville explore                  # les six questions de l'étape 01
uv run deauville add                      # programmer un solo (questions posées)
uv run deauville cancel la-cabane-2027-06-13-0800
uv run deauville serve                    # le serveur : site, admin et API
uv run deauville --help
```

Le serveur écoute sur <http://127.0.0.1:8000> : le site à `/`, l'admin à
`/admin/`, et toutes les routes testables à `/docs`.

Option `--data FICHIER` : travailler sur un autre fichier de données (une
copie, par exemple) : `uv run deauville --data copie.json serve`.

## Tester

```bash
uv run pytest                 # 135 tests
uv run ruff format .
uv run ruff check .
uv build                      # dist/deauville-0.1.0-py3-none-any.whl
```

Les tests ne touchent jamais `data/festival.json` : chacun travaille sur une
copie dans un dossier temporaire.

> Sur certains PC Windows, une stratégie de sécurité bloque les lanceurs
> `.exe` de `.venv` (« Une stratégie de contrôle d'application a bloqué ce
> fichier »). On passe alors par Python : `uv run python -m pytest`,
> `uv run python -m deauville serve`.

## Ma structure

```
src/deauville/
    errors.py     la famille d'erreurs
    parsing.py    texte tapé -> date, moment, minutes
    models.py     Venue, Artist, Performance et ses trois types
    festival.py   Festival : le seul point d'entrée, il garde les règles
    storage.py    où vit le festival : interface + fichier JSON + mémoire
    api.py        create_app(storage) : les routes FastAPI
    cli.py        la commande deauville
tests/
    test_festival.py   les règles, sur les objets
    test_api.py        le contrat de API.md, par HTTP
    test_cli.py        les sorties de la ligne de commande
data/festival.json     l'édition 2027
```

Les dépendances vont dans un seul sens :
`cli` et `api` → `storage` → `festival` → `models` → `errors` / `parsing`.
Les objets ne savent ni afficher, ni parler HTTP, ni où ils sont rangés.

### Les classes

| Classe                    | Rôle                                                                                                                         |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `Venue`, `Artist`         | une salle, un artiste ; attributs en lecture seule ; `slug` calculé ; égaux s'ils ont le même `slug` (`__eq__`)               |
| `Performance` (abstraite) | ce que tout spectacle partage : début, fin, journée de festival, `id`, durée vérifiée, vue API, tri (`__lt__`), ligne (`__str__`) |
| `SoloShow`                | un artiste et un âge minimum (0 à 18)                                                                                        |
| `Lineup`                  | un présentateur et au moins 2 artistes, chacun une fois, le présentateur n'en fait pas partie, 10 min par artiste + 3 entre deux |
| `Workshop`                | un enseignant et des participants ; places = `min(maximum, places de la salle)` ; inscription sans doublon ni dépassement     |
| `Festival`                | le contenant : salles, artistes, spectacles, et toutes les règles qui les relient                                           |
| `FestivalStorage`         | l'interface `load()` / `save()` ; `JsonStorage` (le fichier) et `MemoryStorage` (les tests)                                  |
| `FestivalError`           | la famille : `NotFoundError`, `ConflictError`, `InvalidError`, `StorageError`                                               |

**Pourquoi l'héritage.** Les trois types de spectacles ont des champs, des
règles et un résumé différents. Avec une seule classe, chaque calcul
commençait par `if kind == ...` (il y en avait six). Avec une classe abstraite
et trois sous-classes, chaque type écrit sa partie (`roles`, `summary()`,
`to_view()`), et l'appelant ne demande jamais de quel type il s'agit
(polymorphisme). Le mot `kind` ne choisit plus qu'à un endroit : le
dictionnaire `KINDS` qui transforme une ligne du fichier en objet.

### Les questions du brief

**Où vivent les règles ?**

- Les règles d'**un seul objet** sont dans son `__init__` : un objet qui
  enfreint une règle ne peut même pas exister. Durée de 1 à 360 minutes
  (`Performance`), âge (`SoloShow`), artistes et durée minimale d'un plateau
  (`Lineup`), places et inscriptions (`Workshop`).
- Les règles qui **relient plusieurs objets** sont dans `Festival.check()` :
  salle et artistes connus, jour du festival, 30 minutes pour une salle et
  pour chaque artiste (quel que soit son rôle). Une journée de festival se
  termine à 06:00 : un spectacle à 01:00 appartient à la veille.
- **Personne ne contourne les règles** : les attributs sont privés et en
  lecture seule (`spectacle.start = ...` lève `AttributeError`), les
  collections rendues sont des copies, les artistes d'un plateau et les
  inscrits d'un atelier sont des tuples. La seule façon de changer le
  programme passe par `add_performance()`, `replace()`, `cancel()`,
  `register()`, qui vérifient tout. Le fichier lui-même est chargé par ces
  méthodes : des données incorrectes sont refusées au chargement.

**Comment les erreurs disent quelle règle ?**

Chaque règle lève une erreur de la famille `FestivalError`, avec une phrase
qui nomme le problème (« Le Kiosque is busy with After Hours (2027-06-12
01:00-02:00). »). Le **type** dit la nature de l'erreur : introuvable,
conflit, valeur invalide, stockage. La ligne de commande attrape toute la
famille à un seul endroit (`Error: ...`, code de sortie 1). L'API a un seul
gestionnaire qui traduit chaque type en code HTTP (404, 409, 422, 500) : les
routes n'ont aucun `try`.

**Que changerait une base de données ?**

Une seule classe de plus : un `SqliteStorage(FestivalStorage)` avec ses
`load()` et `save()`, choisi par une option de la commande. Ni les classes du
festival, ni les routes, ni la ligne de commande ne changeraient : elles ne
connaissent que l'interface `FestivalStorage`. (Pour de gros volumes, on
voudrait ensuite charger moins que tout le festival à chaque requête.)

## Ce qui est fait, ce qui ne l'est pas

Fait : étapes 00 à 13 du cours. Ligne de commande, règles du brief,
trois types de spectacles, encapsulation, famille d'erreurs, API complète
(lecture et écriture), stockage derrière une interface, package installable,
135 tests.

Pas fait / à savoir :

- **Le site et l'admin (`web/`) ne sont pas dans le dépôt.** Le starter du
  cours (qui les fournit avec l'`API.md` officiel) n'était pas disponible.
  Le serveur les sert automatiquement dès qu'un dossier `web/public/` (site)
  et `web/admin/` (admin) existe.
- **`API.md` est reconstitué** d'après les fiches : les champs donnés par les
  fiches sont respectés à l'identique, le reste (routes d'écriture, codes
  d'erreur) est mon choix, documenté et testé.
- Extension non faite : un stockage SQLite.

## Bugs connus

- `/api/now` sans `?at=` prend l'heure locale du serveur, sans fuseau
  horaire : un serveur hébergé ailleurs qu'en France afficherait un décalage.
- Deux écritures exactement simultanées dans l'admin relisent le même
  fichier : la seconde peut effacer la première (pas de verrou).

### Corrigés

- **Étape 04 — les spectacles après minuit étaient rattachés au mauvais
  jour.** `01:00 | Le Kiosque | After Hours` apparaissait le samedi 12, alors
  que pour le festival c'est la fin de la nuit du vendredi 11. Le code
  comparait les 10 premiers caractères de `start`. Correction : de vraies
  dates (`datetime`), et la journée de festival d'un spectacle est la date de
  son début moins 6 heures.
- **Étape 07 — la sauvegarde changeait les fins de ligne** (CRLF sous
  Windows) : le fichier semblait modifié pour Git après un ajout puis une
  annulation. Correction : `newline="\n"` à l'écriture.
