import unittest
from pathlib import Path

from tojs.regulation import load_regulation


class RegulationTest(unittest.TestCase):
    # レギュレーションひな形が要求された初期値をそのまま読めることを確認する。
    def test_load_default_regulation(self) -> None:
        regulation = load_regulation(Path("configs/regulation.default.json"))

        self.assertEqual(regulation.deck_size, 40)
        self.assertEqual(regulation.max_copies_per_card, 3)
        self.assertEqual(regulation.round_count, 10)
        self.assertEqual(regulation.opening_draws_first[0], 0)
        self.assertEqual(regulation.opening_draws_second[0], 2)
        self.assertEqual(regulation.starting_life_first, 7)
        self.assertEqual(regulation.starting_life_second, 7)


if __name__ == "__main__":
    unittest.main()
