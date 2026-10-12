"""La famille d'erreurs du festival.

Chaque type dit ce qui ne va pas. La ligne de commande attrape toute la
famille (`except FestivalError`) ; l'API transforme chaque type en un code
HTTP (404, 409, 422, 500), sans aucun `try` dans les routes.
"""


class FestivalError(Exception):
    """Toutes les erreurs du festival."""


class NotFoundError(FestivalError):
    """Une salle, un artiste, un spectacle ou un participant introuvable (404)."""


class ConflictError(FestivalError):
    """La demande est correcte mais heurte l'existant (409).

    Salle ou artiste déjà occupé, atelier complet, doublon.
    """


class InvalidError(FestivalError):
    """Une valeur qui enfreint une règle du brief (422).

    Durée, âge, nombre d'artistes, jour hors festival, format de date…
    """


class StorageError(FestivalError):
    """Le fichier de données ne peut être lu ou écrit (500)."""
