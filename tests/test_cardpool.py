import unittest
from pathlib import Path

from tojs.cardpool import load_cardpool_from_xlsx
from tojs.game import ABILITY_REGISTRY, get_known_event_types


class CardpoolTest(unittest.TestCase):
    # Excel のカードプールから初期カード一覧を読めることを確認する。
    def test_load_cardpool(self) -> None:
        cards = load_cardpool_from_xlsx(Path("text-of-joker.cardpool.xlsx"))

        self.assertGreaterEqual(len(cards), 100)
        self.assertEqual(cards[0].card_no, "1-0-001")
        self.assertEqual(cards[0].name, "ブラッドハウンド")
        self.assertEqual(cards[0].bp_by_level, (3, 4, 5))
        self.assertEqual(cards[0].abilities[0].name, "ダメージブレイク")


    def test_load_cardpool_merges_ability_metadata(self) -> None:
        cards = load_cardpool_from_xlsx(Path("text-of-joker.cardpool.xlsx"))
        card = next(card for card in cards if card.card_no == "1-0-069")

        self.assertEqual(card.abilities[0].raw["event_type"], "opponent_unit_entered")

    def test_registry_backed_abilities_have_declared_event_types(self) -> None:
        cards = load_cardpool_from_xlsx(Path("text-of-joker.cardpool.xlsx"))
        card_map = {card.card_no: card for card in cards}

        missing: list[tuple[str, str]] = []
        for card_no, event_type in ABILITY_REGISTRY:
            card = card_map.get(card_no)
            if card is None:
                continue
            declared_event_types: set[str] = set()
            for ability in card.abilities:
                raw = ability.raw if isinstance(ability.raw, dict) else {}
                raw_event_type = raw.get("event_type")
                if isinstance(raw_event_type, str):
                    declared_event_types.add(raw_event_type)
                raw_event_types = raw.get("event_types")
                if isinstance(raw_event_types, list):
                    declared_event_types.update(
                        value for value in raw_event_types if isinstance(value, str)
                    )
            if declared_event_types and event_type not in declared_event_types:
                missing.append((card_no, event_type))

        self.assertEqual(missing, [])

    def test_declared_ability_event_types_are_known(self) -> None:
        cards = load_cardpool_from_xlsx(Path("text-of-joker.cardpool.xlsx"))
        known_event_types = get_known_event_types()

        unknown: list[tuple[str, str]] = []
        for card in cards:
            for ability in card.abilities:
                raw = ability.raw if isinstance(ability.raw, dict) else {}
                raw_event_type = raw.get("event_type")
                if isinstance(raw_event_type, str) and raw_event_type not in known_event_types:
                    unknown.append((card.card_no, raw_event_type))
                raw_event_types = raw.get("event_types")
                if isinstance(raw_event_types, list):
                    for value in raw_event_types:
                        if isinstance(value, str) and value not in known_event_types:
                            unknown.append((card.card_no, value))

        self.assertEqual(unknown, [])


if __name__ == "__main__":
    unittest.main()
