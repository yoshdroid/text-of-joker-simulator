from pathlib import Path
import unittest

from tojs.bot import load_deck


class SupportedDecksTest(unittest.TestCase):
    # rg_beatdown に含まれるカードは、現在の想定対応集合に収まっていることを確認する。
    def test_rg_beatdown_contains_only_supported_cards(self) -> None:
        deck = load_deck(Path("configs/decks/rg_beatdown.json"))
        supported_cards = {
            "1-0-002",
            "1-0-004",
            "1-0-007",
            "1-0-010",
            "1-0-012",
            "1-0-040",
            "1-0-044",
            "1-0-048",
            "1-0-051",
            "1-0-057",
            "1-0-061",
            "1-0-062",
            "1-0-065",
            "1-0-074",
            "1-0-081",
            "1-0-096",
        }

        missing = sorted({card_no for card_no in deck if card_no not in supported_cards})
        self.assertEqual(missing, [])

    # gb_controlbeat に含まれるカードは、現在の想定対応集合に収まっていることを確認する。
    def test_gb_controlbeat_contains_only_supported_cards(self) -> None:
        deck = load_deck(Path("configs/decks/gb_controlbeat.json"))
        supported_cards = {
            "1-0-027",
            "1-0-029",
            "1-0-031",
            "1-0-033",
            "1-0-039",
            "1-0-040",
            "1-0-043",
            "1-0-045",
            "1-0-061",
            "1-0-062",
            "1-0-069",
            "1-0-089",
            "1-0-091",
            "1-0-092",
        }

        missing = sorted({card_no for card_no in deck if card_no not in supported_cards})
        self.assertEqual(missing, [])
