import unittest
from pathlib import Path

from tojs.player_runner import PlayerProcess, build_python_bot_command
from tojs.protocol import Message


class PlayerRunnerTest(unittest.TestCase):
    # メイン側が stdio 経由で bot を起動し、hello と deck_submit を往復できることを確認する。
    def test_request_round_trip(self) -> None:
        player = PlayerProcess(
            build_python_bot_command(Path("configs/decks/example_deck.json")),
            cwd=".",
        )
        self.addCleanup(player.close)

        hello = player.request(Message(type="hello", request_id="boot-1", payload={}))
        deck = player.request(Message(type="deck_submit", request_id="deck-1", payload={}))

        self.assertEqual(hello.type, "hello")
        self.assertEqual(hello.payload["protocol_version"], "1")
        self.assertEqual(deck.type, "deck_submit")
        self.assertEqual(len(deck.payload["deck_card_nos"]), 40)


if __name__ == "__main__":
    unittest.main()
