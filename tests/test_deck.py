import unittest
from pathlib import Path

from tojs.cardpool import load_cardpool_from_xlsx
from tojs.deck import validate_deck
from tojs.regulation import load_regulation


class DeckValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cardpool = load_cardpool_from_xlsx(Path("text-of-joker.cardpool.xlsx"))
        self.regulation = load_regulation(Path("configs/regulation.default.json"))

    # 40 枚かつ同名 3 枚以下なら基本ルール上は有効デッキになることを確認する。
    def test_validate_legal_deck(self) -> None:
        deck = []
        for card in self.cardpool[:14]:
            copies = 3 if len(deck) <= 36 else 1
            deck.extend([card.card_no] * copies)
            if len(deck) >= 40:
                deck = deck[:40]
                break

        result = validate_deck(deck, self.regulation, self.cardpool)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, ())

    # カードプール外のカード番号が含まれると違反になることを確認する。
    def test_validate_unknown_card(self) -> None:
        deck = [self.cardpool[0].card_no] * 39 + ["9-9-999"]

        result = validate_deck(deck, self.regulation, self.cardpool)

        self.assertFalse(result.is_valid)
        self.assertIn("カードプールに存在しないカードがあります", result.errors[0])

    # 同名カード 4 枚以上を投入すると違反になることを確認する。
    def test_validate_copy_limit(self) -> None:
        deck = [self.cardpool[0].card_no] * 4
        for card in self.cardpool[1:13]:
            deck.extend([card.card_no] * 3)
        deck = deck[:40]

        result = validate_deck(deck, self.regulation, self.cardpool)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("同名カード上限を超えています" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()

