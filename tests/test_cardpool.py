import unittest
from pathlib import Path

from tojs.cardpool import load_cardpool_from_xlsx


class CardpoolTest(unittest.TestCase):
    # Excel のカードプールから初期カード一覧を読めることを確認する。
    def test_load_cardpool(self) -> None:
        cards = load_cardpool_from_xlsx(Path("text-of-joker.cardpool.xlsx"))

        self.assertGreaterEqual(len(cards), 100)
        self.assertEqual(cards[0].card_no, "1-0-001")
        self.assertEqual(cards[0].name, "ブラッドハウンド")
        self.assertEqual(cards[0].bp_by_level, (3, 4, 5))
        self.assertEqual(cards[0].abilities[0].name, "ダメージブレイク")


if __name__ == "__main__":
    unittest.main()

