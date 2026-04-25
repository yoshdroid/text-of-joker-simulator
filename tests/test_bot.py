import unittest
from pathlib import Path

from tojs.bot import SimpleBot, choose_action, load_deck
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

    # block_request ではブロック可能なら最初の blocker を返すことを確認する。
    def test_handle_block_request(self) -> None:
        bot = SimpleBot(deck_card_nos=["1-0-001"] * 40)

        response = bot.handle(
            Message(
                type="block_request",
                request_id="block-1",
                payload={"available_actions": [{"kind": "no_block"}, {"kind": "block", "blocker_index": 0}]},
            )
        )

        self.assertEqual(response.type, "block_action")
        self.assertEqual(response.payload["kind"], "block")

    # bot は overdrive を最優先し、次に drive を選ぶことを確認する。
    def test_choose_action_prefers_overdrive(self) -> None:
        chosen = choose_action(
            [
                {"kind": "set_trigger", "hand_index": 0},
                {"kind": "attack", "attacker_index": 0},
                {"kind": "drive", "hand_index": 1},
                {"kind": "overdrive", "hand_index": 2, "target_index": 0},
                {"kind": "end_turn"},
            ]
        )

        self.assertEqual(chosen["kind"], "overdrive")


if __name__ == "__main__":
    unittest.main()
