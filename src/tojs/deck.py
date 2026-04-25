from __future__ import annotations

from collections import Counter

from .models import CardDefinition, DeckValidationResult, Regulation


def validate_deck(
    deck_card_nos: list[str],
    regulation: Regulation,
    cardpool: list[CardDefinition],
) -> DeckValidationResult:
    errors: list[str] = []
    known_cards = {card.card_no: card for card in cardpool}

    if len(deck_card_nos) != regulation.deck_size:
        errors.append(
            f"デッキ枚数が不正です: expected={regulation.deck_size}, actual={len(deck_card_nos)}"
        )

    missing_cards = sorted({card_no for card_no in deck_card_nos if card_no not in known_cards})
    if missing_cards:
        errors.append(f"カードプールに存在しないカードがあります: {', '.join(missing_cards)}")

    counts = Counter(deck_card_nos)
    exceeded = sorted(
        card_no
        for card_no, count in counts.items()
        if count > regulation.max_copies_per_card
    )
    if exceeded:
        errors.append(
            "同名カード上限を超えています: "
            + ", ".join(
                f"{card_no} x{counts[card_no]} > {regulation.max_copies_per_card}" for card_no in exceeded
            )
        )

    return DeckValidationResult(is_valid=not errors, errors=tuple(errors))

