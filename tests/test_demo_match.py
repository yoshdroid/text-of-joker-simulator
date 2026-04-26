import json
import subprocess
import sys
import unittest

from tojs.demo_match import _render_trace_log


class DemoMatchTest(unittest.TestCase):
    # デモマッチ実行で bot 同士の起動結果とターン進行スナップショットを出力できることを確認する。
    def test_demo_match_command(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "tojs.demo_match", "--cycles", "2", "--seed", "7"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=".",
        )

        payload = json.loads(completed.stdout)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["snapshots"][0]["turn_player_id"], "P1")
        self.assertEqual(payload["snapshots"][0]["players"]["P1"]["hand_count"], 4)
        self.assertEqual(payload["snapshots"][1]["turn_player_id"], "P1")
        self.assertEqual(payload["snapshots"][1]["players"]["P1"]["battlefield_count"], 1)
        self.assertGreater(len(payload["messages"]), 0)
        self.assertGreater(len(payload["rendered_messages"]), 0)
        self.assertEqual(payload["messages"][0]["direction"], "to_player")
        self.assertEqual(payload["messages"][1]["direction"], "from_player")
        self.assertTrue(payload["rendered_messages"][0].startswith("[R"))
        self.assertIn("[E", payload["rendered_messages"][0])
        self.assertIn("hello", payload["rendered_messages"][0])
        self.assertTrue(any("state_update" in line and "life=" in line for line in payload["rendered_messages"]))
        self.assertTrue(any("ユニットドライブ" in line for line in payload["rendered_messages"]))
        self.assertTrue(any("トリガーゾーンに" in line and "セット" in line for line in payload["rendered_messages"]))

    def test_demo_match_command_with_mixed_supported_decks(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "tojs.demo_match",
                "--deck1",
                "configs/decks/rg_beatdown.json",
                "--deck2",
                "configs/decks/gb_controlbeat.json",
                "--cycles",
                "12",
                "--seed",
                "7",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=".",
        )

        payload = json.loads(completed.stdout)

        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(len(payload["snapshots"]), 12)
        self.assertTrue(any("ランサーをユニットドライブ" in line for line in payload["rendered_messages"]))
        self.assertTrue(any("見習い魔導士リーナをユニットドライブ" in line for line in payload["rendered_messages"]))

    def test_render_trace_log_uses_request_round_for_choice_response(self) -> None:
        rendered = _render_trace_log(
            [
                {
                    "direction": "to_player",
                    "player_id": "P1",
                    "message": {
                        "type": "choice_request",
                        "request_id": "choice-9-17-1-P1",
                        "payload": {"round_no": 9, "turn_serial": 17, "choice_kind": "block", "available_choices": []},
                    },
                },
                {
                    "direction": "from_player",
                    "player_id": "P1",
                    "message": {
                        "type": "choice_response",
                        "request_id": "choice-9-17-1-P1",
                        "payload": {"kind": "no_block"},
                    },
                },
            ],
            {},
        )

        self.assertTrue(rendered[0].startswith("[R09][E001][P1][REQ]"))
        self.assertTrue(rendered[1].startswith("[R09][E002][P1][RES]"))

    def test_render_trace_log_uses_request_round_for_request_action(self) -> None:
        rendered = _render_trace_log(
            [
                {
                    "direction": "to_player",
                    "player_id": "P2",
                    "message": {
                        "type": "request_action",
                        "request_id": "action-4-8-P2",
                        "payload": {"available_actions": [{"kind": "end_turn"}]},
                    },
                },
                {
                    "direction": "from_player",
                    "player_id": "P2",
                    "message": {
                        "type": "action",
                        "request_id": "action-4-8-P2",
                        "payload": {"kind": "end_turn"},
                    },
                },
            ],
            {},
        )

        self.assertTrue(rendered[0].startswith("[R04][E001][P2][REQ]"))
        self.assertTrue(rendered[1].startswith("[R04][E002][P2][RES]"))


if __name__ == "__main__":
    unittest.main()
