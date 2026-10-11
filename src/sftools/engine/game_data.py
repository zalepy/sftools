from dataclasses import dataclass
from functools import lru_cache
from typing import Dict

from sftools.domain.models.building import Building
from sftools.domain.models.item import Item
from sftools.domain.models.recipe import Recipe
from sftools.engine.loader import load_models


@dataclass(frozen=True)
class GameData:
    items: Dict[str, Item]
    recipes: Dict[str, Recipe]
    buildings: Dict[str, Building]


@lru_cache(maxsize=1)
def get_game_data() -> GameData:
    """Loads the game data once per process; it is read-only after that."""
    return GameData(*load_models())
