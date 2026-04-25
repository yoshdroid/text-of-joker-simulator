import unittest
from pathlib import Path

from tojs.engine import bootstrap
from tojs.match import play_single_action_cycle, run_boot_sequence
from tojs.player_runner import PlayerProcess, build_python_bot_command


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

    # bot の既定行動 end_turn により、1 アクションぶん進行できることを確認する。
    def test_play_single_action_cycle(self) -> None:
        result = run_boot_sequence(self.context, self.first_player, self.second_player, seed=7)

        state = play_single_action_cycle(result.match_state, self.first_player, self.second_player, seed=7)

        self.assertEqual(state.turn_player_id, "P2")
        self.assertEqual(state.round_no, 1)
        self.assertEqual(state.turn_serial, 2)


if __name__ == "__main__":
    unittest.main()
