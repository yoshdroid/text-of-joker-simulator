from __future__ import annotations

import json
from pathlib import Path

from .models import Regulation


def load_regulation(path: str | Path) -> Regulation:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Regulation(
        deck_size=data["deck_size"],
        max_copies_per_card=data["max_copies_per_card"],
        max_cp_per_round=data["max_cp_per_round"],
        round_count=data["round_count"],
        initial_hand_size=data["initial_hand_size"],
        hand_size_limit=data["hand_size_limit"],
        battlefield_unit_limit=data["battlefield_unit_limit"],
        trigger_zone_limit=data["trigger_zone_limit"],
        opening_draws_first=tuple(data["opening_draws"]["first"]),
        opening_draws_second=tuple(data["opening_draws"]["second"]),
        round_start_cp_first=tuple(data["round_start_cp"]["first"]),
        round_start_cp_second=tuple(data["round_start_cp"]["second"]),
        starting_life_first=data["starting_life"]["first"],
        starting_life_second=data["starting_life"]["second"],
    )

