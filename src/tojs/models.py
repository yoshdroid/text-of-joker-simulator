from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AbilityDefinition:
    name: str
    text: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CardDefinition:
    card_no: str
    category: str
    rarity: str
    color: str
    name: str
    cp: int | None
    bp_by_level: tuple[int, ...]
    abilities: tuple[AbilityDefinition, ...]
    race: str


@dataclass(frozen=True)
class Regulation:
    deck_size: int
    max_copies_per_card: int
    max_cp_per_round: int
    round_count: int
    initial_hand_size: int
    hand_size_limit: int
    battlefield_unit_limit: int
    trigger_zone_limit: int
    opening_draws_first: tuple[int, ...]
    opening_draws_second: tuple[int, ...]
    round_start_cp_first: tuple[int, ...]
    round_start_cp_second: tuple[int, ...]
    starting_life_first: int
    starting_life_second: int


@dataclass(frozen=True)
class DeckValidationResult:
    is_valid: bool
    errors: tuple[str, ...] = ()

