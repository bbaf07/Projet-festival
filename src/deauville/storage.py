"""Où vit le festival : une interface, et deux façons de la remplir.

Le reste du programme ne connaît que `FestivalStorage` : load() et save().
Changer de stockage (une base SQLite par exemple) ne toucherait ni les classes
du festival, ni l'API, ni la ligne de commande.
"""

import json
from abc import ABC, abstractmethod
from copy import deepcopy
from pathlib import Path

from deauville.errors import StorageError
from deauville.festival import Festival


class FestivalStorage(ABC):
    """L'interface : charger le festival, le sauvegarder."""

    @abstractmethod
    def load(self) -> Festival:
        """Renvoie le festival, vérifié avec toutes ses règles."""

    @abstractmethod
    def save(self, festival: Festival) -> None:
        """Enregistre l'état actuel du festival."""


class JsonStorage(FestivalStorage):
    """Le festival dans un fichier JSON (data/festival.json par défaut)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> Festival:
        try:
            with open(self.path, encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            raise StorageError(f"The data file {self.path} does not exist.") from None
        except json.JSONDecodeError as error:
            raise StorageError(
                f"The data file {self.path} is damaged (line {error.lineno})."
            ) from None
        return Festival.from_dict(data)

    def save(self, festival: Festival) -> None:
        try:
            # newline="\n" : fins de ligne LF comme le fichier d'origine.
            with open(self.path, "w", encoding="utf-8", newline="\n") as file:
                # ensure_ascii=False garde "é" lisible, indent=2 le fichier lisible.
                json.dump(festival.to_dict(), file, ensure_ascii=False, indent=2)
                file.write("\n")
        except OSError as error:
            raise StorageError(
                f"The data file {self.path} cannot be written ({error.strerror})."
            ) from None


class MemoryStorage(FestivalStorage):
    """Rien sur le disque : pratique pour les tests."""

    def __init__(self, data: dict) -> None:
        self._data = deepcopy(data)

    def load(self) -> Festival:
        return Festival.from_dict(deepcopy(self._data))

    def save(self, festival: Festival) -> None:
        self._data = festival.to_dict()
