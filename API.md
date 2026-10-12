---
noteId: "b25d6980c64711f196be113a468f1c2a"
tags: []

---

# API du festival

> Contrat reconstitué à partir des fiches du cours (étapes 06 à 12) : le
> fichier `API.md` du starter n'était pas disponible. Les noms de champs
> donnés par les fiches sont respectés à l'identique ; le reste (routes
> d'écriture, codes d'erreur) suit les règles des fiches 10 et 12. À
> confronter avec l'`API.md` officiel dès qu'il est disponible.

Toutes les réponses sont en JSON. Les dates sont au format `YYYY-MM-DD`, les
moments au format `YYYY-MM-DDTHH:MM`.

## Objets

### Festival

```json
{
  "name": "Deauville Festival du Rire 2027",
  "first_day": "2027-06-10",
  "last_day": "2027-06-13",
  "days": ["2027-06-10", "2027-06-11", "2027-06-12", "2027-06-13"]
}
```

`days` : les journées de festival qui ont au moins un spectacle.

### Venue

```json
{ "slug": "le-kiosque", "name": "Le Kiosque", "capacity": 120, "address": "Beach promenade" }
```

### Artist

```json
{ "slug": "max-pellerin", "name": "Max Pellerin", "bio": "...", "photo_url": "" }
```

Dans un spectacle, un artiste apparaît sous sa forme courte :
`{ "slug": "max-pellerin", "name": "Max Pellerin" }`.

### Performance

Champs communs à tous les types :

| Champ              | Exemple                                    | Remarque                                         |
| ------------------ | ------------------------------------------ | ------------------------------------------------ |
| `id`               | `"le-kiosque-2027-06-12-0100"`             | salle + début ; change si le spectacle bouge     |
| `kind`             | `"solo"`, `"lineup"` ou `"workshop"`       |                                                  |
| `title`            | `"After Hours"`                            |                                                  |
| `venue`            | `"le-kiosque"`                             | identifiant de la salle                          |
| `venue_name`       | `"Le Kiosque"`                             |                                                  |
| `start`, `end`     | `"2027-06-12T01:00"`, `"2027-06-12T02:00"` |                                                  |
| `duration_minutes` | `60`                                       |                                                  |
| `festival_day`     | `"2027-06-11"`                             | le début moins 6 heures                          |
| `description`      | `"..."`                                    |                                                  |
| `summary`          | `"hosted by Tom Vasseur, with ..."`        | écrit par chaque type                            |
| `capacity`         | `120`                                      | places de la salle ; pour un atelier, ses places |
| `artists`          | `[{"slug": "...", "name": "..."}]`         | tous les artistes sur scène                      |

Champs propres à chaque type :

| Type       | Champs ajoutés                                                                                    | `summary`                              |
| ---------- | ------------------------------------------------------------------------------------------------- | -------------------------------------- |
| `solo`     | `artist` (slug), `min_age` (0 à 18)                                                               | `"Léa Fontaine"`                       |
| `lineup`   | `host` (slug), `acts` (liste de slugs)                                                            | `"hosted by Tom Vasseur, with A, B"`   |
| `workshop` | `teacher` (slug), `max_participants`, `participants` (noms), `places_left` | `"with Inès Moreau, 3/12 places taken"` |

## Lire

| Route                             | Réponse                                                                   |
| --------------------------------- | ------------------------------------------------------------------------- |
| `GET /api/festival`               | le Festival                                                               |
| `GET /api/venues`                 | les Venue, dans l'ordre du fichier                                        |
| `GET /api/artists`                | les Artist, triés par slug                                                |
| `GET /api/artists/{slug}`         | l'Artist, plus `performances` : ses spectacles triés                      |
| `GET /api/programme`              | les Performance triées par début ; filtres `?day=YYYY-MM-DD`, `?venue=slug` |
| `GET /api/performances/{id}`      | la Performance                                                            |
| `GET /api/now`                    | `{"at", "now_playing": [...], "up_next": [... 3 au plus]}` ; `?at=` remplace l'heure actuelle |

## Écrire (admin)

Chaque écriture vérifie toutes les règles du brief, puis sauvegarde le
fichier. Une écriture refusée ne change rien.

| Route                                                     | Corps                                   | Réponse                           |
| --------------------------------------------------------- | --------------------------------------- | --------------------------------- |
| `POST /api/performances`                                  | PerformanceIn                           | `201` + la Performance créée      |
| `PUT /api/performances/{id}`                              | PerformanceIn                           | `200` + la Performance (nouvel id) |
| `DELETE /api/performances/{id}`                           | —                                       | `204`, sans corps                 |
| `POST /api/performances/{id}/participants`                | `{"name": "Lou"}`                       | `201` + l'atelier                 |
| `DELETE /api/performances/{id}/participants/{name}`       | —                                       | `204`, sans corps                 |
| `POST /api/artists`                                       | `{"name", "bio"?, "photo_url"?}`        | `201` + l'Artist                  |

PerformanceIn : `kind`, `title`, `venue` (slug), `start`, `duration_minutes`,
`description` (facultatif), puis les champs du type :

- `solo` : `artist` (slug), `min_age` (facultatif, 0 par défaut) ;
- `lineup` : `host` (slug), `acts` (liste de slugs) ;
- `workshop` : `teacher` (slug), `max_participants`, `participants` (facultatif).

## Erreurs

Toute erreur renvoie `{"detail": "une phrase qui dit ce qui ne va pas"}`
(sauf les `422` de forme, produits par FastAPI, où `detail` est une liste).

| Code  | Quand                                                                                                         |
| ----- | ------------------------------------------------------------------------------------------------------------- |
| `404` | salle, artiste, spectacle ou participant introuvable (y compris dans un corps : `"venue": "nowhere"`)         |
| `409` | conflit avec l'existant : salle occupée, artiste sur scène, atelier complet, participant ou artiste en double |
| `422` | valeur contraire à une règle (durée, âge, nombre d'artistes, jour hors festival, champ du type manquant) ou corps / paramètre de mauvaise forme |
| `500` | le fichier de données ne peut pas être lu ou écrit                                                            |
