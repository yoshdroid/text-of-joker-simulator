import unittest
from pathlib import Path

from tojs.bot import SimpleBot, load_deck
from tojs.protocol import Message


class BotTest(unittest.TestCase):
    # bot がデッキファイルを読み込み、そのまま提出用データとして保持できることを確認する。
    def test_load_example_deck(self) -> None:
        deck = load_deck(Path("configs/decks/example_deck.json"))

        self.assertEqual(len(deck), 40)
        self.assertEqual(deck[0], "1-0-001")

    # hello 要求に対して bot 名とプロトコル番号を返すことを確認する。
    def test_handle_hello(self) -> None:
        bot = SimpleBot(deck_card_nos=["1-0-001"] * 40, bot_name="test-bot")

        response = bot.handle(Message(type="hello", request_id="boot-1", payload={}))

        self.assertEqual(response.type, "hello")
        self.assertEqual(response.payload["player_name"], "test-bot")
        self.assertEqual(response.payload["protocol_version"], "1")

    # アクション要求に対して候補の先頭を選ぶ既定動作を確認する。
    def test_handle_request_action(self) -> None:
        bot = SimpleBot(deck_card_nos=["1-0-001"] * 40)

        response = bot.handle(
            Message(
                type="request_action",
                request_id="turn-1",
                payload={"available_actions": [{"kind": "attack"}, {"kind": "end_turn"}]},
            )
        )

        self.assertEqual(response.type, "action")
        self.assertEqual(response.payload["kind"], "attack")


if __name__ == "__main__":
    unittest.main()

