import random
import unittest
from pathlib import Path

from tojs.engine import bootstrap
from tojs.game import UnitState, create_match_state
from tojs.match import play_single_action_cycle, run_boot_sequence
from tojs.protocol import Message
from tojs.player_runner import PlayerProcess, build_python_bot_command


class FakePlayerProcess:
    def __init__(self, responses: dict[str, list[dict[str, object]]]) -> None:
        self.responses = {key: list(value) for key, value in responses.items()}
        self.received_messages: list[Message] = []

    def request(self, message: Message) -> Message:
        self.received_messages.append(message)
        if message.type == "state_update":
            return Message(type="state_ack", request_id=message.request_id, payload={"received": True})
        queue = self.responses.get(message.type, [])
        if not queue:
            raise AssertionError(f"unexpected message type: {message.type}")
        payload = queue.pop(0)
        response_type = {
            "hello": "hello",
            "deck_submit": "deck_submit",
            "mulligan_decision": "mulligan_decision",
            "request_action": "action",
            "block_request": "block_action",
        }[message.type]
        return Message(type=response_type, request_id=message.request_id, payload=payload)

    def close(self) -> None:
        return


class MatchRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context = bootstrap(
            Path("text-of-joker.cardpool.xlsx"),
            Path("configs/regulation.default.json"),
        )
        self.first_player = PlayerProcess(build_python_bot_command(Path("configs/decks/example_deck.json")), cwd=".")
        self.second_player = PlayerProcess(build_python_bot_command(Path("configs/decks/example_deck.json")), cwd=".")
        self.addCleanup(self.first_player.close)
        self.addCleanup(self.second_player.close)

    # 起動シーケンスで deck 提出とマリガン確認を終え、先攻 1 ターン目へ進めることを確認する。
    def test_run_boot_sequence(self) -> None:
        result = run_boot_sequence(self.context, self.first_player, self.second_player, seed=7)

        self.assertEqual(result.match_state.turn_player_id, "P1")
        self.assertEqual(result.match_state.turn_serial, 1)
        self.assertEqual(len(result.match_state.players["P1"].hand), 4)
        self.assertEqual(result.match_state.players["P1"].current_cp, 2)

    # bot の既定行動ではまず drive が選ばれ、先攻ターン中に盤面が進むことを確認する。
    def test_play_single_action_cycle(self) -> None:
        result = run_boot_sequence(self.context, self.first_player, self.second_player, seed=7)

        state = play_single_action_cycle(result.match_state, self.first_player, self.second_player, seed=7)

        self.assertEqual(state.turn_player_id, "P1")
        self.assertEqual(state.round_no, 1)
        self.assertEqual(state.turn_serial, 1)
        self.assertEqual(len(state.players["P1"].battlefield), 1)
        self.assertEqual(state.players["P1"].current_cp, 1)

    # アタック時能力でブロッカー候補が消えた場合は block_request を出さずにノーブロックとして解決することを確認する
    def test_attack_trigger_resolves_before_block_request(self) -> None:
        card_catalog = {card.card_no: card for card in self.context.cardpool}
        weak_blocker = card_catalog["1-0-002"]
        card_catalog["2-9-001"] = weak_blocker.__class__(
            card_no="2-9-001",
            category="unit",
            rarity="C",
            color="blue",
            name="Weak Blocker",
            cp=1,
            bp_by_level=(1, 1, 1),
            abilities=(),
            race="test",
        )
        state = create_match_state(
            self.context.regulation,
            card_catalog,
            ["1-0-004"] * 40,
            ["2-9-001"] * 40,
            random.Random(7),
        )
        state.round_no = 2
        state.turn_player_id = "P1"
        state.turn_serial = 2
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-004", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P2"].battlefield = [
            UnitState(card_no="2-9-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        ]

        first_player = FakePlayerProcess(
            {
                "request_action": [{"kind": "attack", "attacker_index": 0, "target": "player"}],
            }
        )
        second_player = FakePlayerProcess({})

        play_single_action_cycle(state, first_player, second_player, seed=7)

        self.assertFalse(any(message.type == "block_request" for message in second_player.received_messages))
        self.assertEqual(len(state.players["P2"].battlefield), 0)
        self.assertEqual(state.players["P2"].life, 6)


if __name__ == "__main__":
    unittest.main()
