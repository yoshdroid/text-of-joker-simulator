import json
import subprocess
import sys
import unittest

from tojs.demo_match import _render_trace_log


class DemoMatchTest(unittest.TestCase):
    # demo_match実行で bot 応答の通信ログとターン進行スナップショットを取得できることを確認する
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
        self.assertGreater(len(payload["game_events"]), 0)
        self.assertGreater(len(payload["rendered_messages"]), 0)
        self.assertEqual(payload["messages"][0]["direction"], "to_player")
        self.assertEqual(payload["messages"][1]["direction"], "from_player")
        self.assertTrue(payload["rendered_messages"][0].startswith("[R"))
        self.assertIn("[E", payload["rendered_messages"][0])
        self.assertIn("ターン開始時", "\n".join(payload["rendered_messages"]))
        self.assertTrue(any("state_update" in line and "life=" in line for line in payload["rendered_messages"]))
        self.assertTrue(any("ユニットドライブ" in line for line in payload["rendered_messages"]))
        self.assertTrue(any("トリガーゾーンに" in line and "セット" in line for line in payload["rendered_messages"]))

    # REQ/RES非表示オプションで観戦用EVTだけを出せることを確認する
    def test_demo_match_command_can_hide_reqres(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "tojs.demo_match", "--cycles", "2", "--seed", "7", "--hide-reqres"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=".",
        )

        payload = json.loads(completed.stdout)

        self.assertTrue(payload["rendered_messages"])
        self.assertFalse(any("[REQ]" in line or "[RES]" in line for line in payload["rendered_messages"]))
        self.assertTrue(any("[EVT]" in line for line in payload["rendered_messages"]))

    # 混成デッキ同士の対戦でも観戦ログが崩れず生成できることを確認する
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

    # choice_responseは対応するchoice_requestのROUND番号で描画されることを確認する
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

    # request_actionへの応答も対応する要求のROUND番号で描画されることを確認する
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

    # game_eventsはstate_updateのevent_log_countに合わせて時系列に差し込まれることを確認する
    def test_render_trace_log_inserts_game_events_before_state_update(self) -> None:
        rendered = _render_trace_log(
            [
                {
                    "direction": "to_player",
                    "player_id": "P1",
                    "message": {
                        "type": "state_update",
                        "request_id": "state-2-P1",
                        "payload": {
                            "round_no": 2,
                            "turn_serial": 3,
                            "event_log_count": 2,
                            "viewer_player_id": "P1",
                            "turn_player_id": "P1",
                            "players": {
                                "P1": {"life": 7, "current_cp": 3, "hand_count": 4, "deck_count": 36, "battlefield": [], "trigger_zone": []},
                                "P2": {"life": 7, "current_cp": 3, "hand_count": 4, "deck_count": 36, "battlefield": [], "trigger_zone": []},
                            },
                        },
                    },
                },
            ],
            {},
            [
                {"round_no": 2, "player_id": "P1", "type": "turn_start_draw", "amount": 2},
                {"round_no": 2, "player_id": "P1", "type": "turn_start_cp_set", "amount": 1},
            ],
        )

        self.assertIn("ターン開始時に2枚ドロー", rendered[0])
        self.assertIn("ターン開始時にCPを変動 +1", rendered[1])
        self.assertIn("[REQ] state_update", rendered[2])

    # show_reqres=FalseのときはREQ/RES行が省かれることを確認する
    def test_render_trace_log_can_hide_reqres(self) -> None:
        rendered = _render_trace_log(
            [
                {
                    "direction": "to_player",
                    "player_id": "P1",
                    "message": {
                        "type": "request_action",
                        "request_id": "action-4-8-P1",
                        "payload": {"available_actions": [{"kind": "end_turn"}]},
                    },
                },
                {
                    "direction": "from_player",
                    "player_id": "P1",
                    "message": {
                        "type": "action",
                        "request_id": "action-4-8-P1",
                        "payload": {"kind": "end_turn"},
                    },
                },
            ],
            {},
            [],
            show_reqres=False,
        )

        self.assertEqual(rendered, [])


if __name__ == "__main__":
    unittest.main()
