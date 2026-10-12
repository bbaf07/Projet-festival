"""Deauville Festival du Rire 2027 : le programme, ses règles, son API.

Modules :
    errors    la famille d'erreurs (introuvable, conflit, invalide, stockage)
    parsing   texte tapé -> dates, moments, minutes
    models    Venue, Artist, Performance et ses trois types
    festival  Festival : le seul point d'entrée, il garde les règles
    storage   où vit le festival (fichier JSON, mémoire)
    api       le serveur web (FastAPI), construit par create_app()
    cli       la ligne de commande `deauville`
"""

__version__ = "0.1.0"
