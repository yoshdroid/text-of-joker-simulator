from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .cardpool import load_cardpool_from_xlsx
from .deck import validate_deck
from .models import CardDefinition, Regulation
from .regulation import load_regulation


@dataclass(frozen=True)
class BootstrapContext:
    cardpool: list[CardDefinition]
    regulation: Regulation


def bootstrap(cardpool_path: str | Path, regulation_path: str | Path) -> BootstrapContext:
    cardpool = load_cardpool_from_xlsx(cardpool_path)
    regulation = load_regulation(regulation_path)
    return BootstrapContext(cardpool=cardpool, regulation=regulation)


def validate_submitted_deck(
    deck_card_nos: list[str],
    context: BootstrapContext,
) -> tuple[bool, tuple[str, ...]]:
    result = validate_deck(deck_card_nos, context.regulation, context.cardpool)
    return result.is_valid, result.errors

