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
        self.assertTrue(any("[E" in line for line in payload["rendered_messages"]))
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
        self.assertTrue(any("[E" in line for line in payload["rendered_messages"]))

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

        self.assertTrue(rendered[0].startswith("[R09][P1][REQ]"))
        self.assertTrue(rendered[1].startswith("[R09][P1][RES]"))

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

        self.assertTrue(rendered[0].startswith("[R04][P2][REQ]"))
        self.assertTrue(rendered[1].startswith("[R04][P2][RES]"))

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
                {
                    "round_no": 2,
                    "player_id": "P1",
                    "type": "turn_start_cp_set",
                    "amount": 1,
                    "metadata": {"before_cp": 2, "after_cp": 3, "set_cp": 3},
                },
            ],
        )

        self.assertIn("ターン開始時に2枚ドロー", rendered[0])
        self.assertIn("ターン開始 CPセット 3", rendered[1])
        self.assertIn("[REQ] state_update", rendered[2])
        self.assertTrue(rendered[0].startswith("[R02][E001] "))
        self.assertTrue(rendered[1].startswith("[R02][E002] "))

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

    # 同一盤面のstate_updateが複数プレイヤーへ送られてもEVTは一度だけ表示されることを確認する
    def test_render_trace_log_deduplicates_shared_state_events(self) -> None:
        rendered = _render_trace_log(
            [
                {
                    "direction": "to_player",
                    "player_id": "P1",
                    "message": {
                        "type": "state_update",
                        "request_id": "state-3-P1",
                        "payload": {
                            "round_no": 3,
                            "turn_serial": 5,
                            "event_log_count": 0,
                            "viewer_player_id": "P1",
                            "turn_player_id": "P1",
                            "players": {
                                "P1": {"life": 7, "current_cp": 3, "hand_count": 4, "deck_count": 36, "battlefield": [], "trigger_zone": []},
                                "P2": {"life": 7, "current_cp": 3, "hand_count": 4, "deck_count": 36, "battlefield": [], "trigger_zone": []},
                            },
                        },
                    },
                },
                {
                    "direction": "to_player",
                    "player_id": "P1",
                    "message": {
                        "type": "state_update",
                        "request_id": "state-3b-P1",
                        "payload": {
                            "round_no": 3,
                            "turn_serial": 5,
                            "event_log_count": 0,
                            "viewer_player_id": "P1",
                            "turn_player_id": "P1",
                            "players": {
                                "P1": {"life": 7, "current_cp": 3, "hand_count": 4, "deck_count": 36, "battlefield": [], "trigger_zone": []},
                                "P2": {"life": 6, "current_cp": 3, "hand_count": 4, "deck_count": 36, "battlefield": [], "trigger_zone": []},
                            },
                        },
                    },
                },
                {
                    "direction": "to_player",
                    "player_id": "P2",
                    "message": {
                        "type": "state_update",
                        "request_id": "state-3-P2",
                        "payload": {
                            "round_no": 3,
                            "turn_serial": 5,
                            "event_log_count": 0,
                            "viewer_player_id": "P2",
                            "turn_player_id": "P1",
                            "players": {
                                "P1": {"life": 7, "current_cp": 3, "hand_count": 4, "deck_count": 36, "battlefield": [], "trigger_zone": []},
                                "P2": {"life": 6, "current_cp": 3, "hand_count": 4, "deck_count": 36, "battlefield": [], "trigger_zone": []},
                            },
                        },
                    },
                },
            ],
            {},
            [],
            show_reqres=False,
        )

        life_lines = [line for line in rendered if "P2のライフが6になった" in line]
        self.assertEqual(life_lines, [])

    # アタック宣言とブロック宣言は選択ユニットのカード名つきで表示されることを確認する
    def test_render_trace_log_renders_attack_and_block_with_card_names(self) -> None:
        rendered = _render_trace_log(
            [
                {
                    "direction": "to_player",
                    "player_id": "P1",
                    "message": {
                        "type": "state_update",
                        "request_id": "state-3-P1",
                        "payload": {
                            "round_no": 3,
                            "turn_serial": 5,
                            "event_log_count": 0,
                            "viewer_player_id": "P1",
                            "turn_player_id": "P1",
                            "players": {
                                "P1": {
                                    "life": 7,
                                    "current_cp": 3,
                                    "hand_count": 4,
                                    "deck_count": 36,
                                    "battlefield": [{"card_no": "1-0-004", "level": 1, "current_bp": 4000}],
                                    "trigger_zone": [],
                                },
                                "P2": {
                                    "life": 7,
                                    "current_cp": 3,
                                    "hand_count": 4,
                                    "deck_count": 36,
                                    "battlefield": [{"card_no": "1-0-031", "level": 1, "current_bp": 3000}],
                                    "trigger_zone": [],
                                },
                            },
                        },
                    },
                },
                {
                    "direction": "to_player",
                    "player_id": "P2",
                    "message": {
                        "type": "state_update",
                        "request_id": "state-3-P2",
                        "payload": {
                            "round_no": 3,
                            "turn_serial": 5,
                            "event_log_count": 2,
                            "viewer_player_id": "P2",
                            "turn_player_id": "P1",
                            "players": {
                                "P1": {
                                    "life": 7,
                                    "current_cp": 3,
                                    "hand_count": 4,
                                    "deck_count": 36,
                                    "battlefield": [{"card_no": "1-0-004", "level": 1, "current_bp": 4000}],
                                    "trigger_zone": [],
                                },
                                "P2": {
                                    "life": 7,
                                    "current_cp": 3,
                                    "hand_count": 4,
                                    "deck_count": 36,
                                    "battlefield": [{"card_no": "1-0-031", "level": 1, "current_bp": 3000}],
                                    "trigger_zone": [],
                                },
                            },
                        },
                    },
                },
            ],
            {
                "1-0-004": type("Card", (), {"name": "ランサー"})(),
                "1-0-031": type("Card", (), {"name": "冥札再臨"})(),
            },
            [
                {"round_no": 3, "player_id": "P1", "type": "attack_declared", "source_card_no": "1-0-004"},
                {"round_no": 3, "player_id": "P2", "type": "block_declared", "source_card_no": "1-0-031"},
            ],
            show_reqres=False,
        )

        self.assertTrue(any("P1がランサーでアタックを宣言" in line for line in rendered))
        self.assertTrue(any("P2が冥札再臨でブロックを宣言" in line for line in rendered))

    # トリガー発動とインターセプト使用もカード名つきで表示されることを確認する
    # game_events 由来で drive や set_trigger などの行動系EVTが描画されることを確認する。
    def test_render_trace_log_renders_action_events_from_game_events(self) -> None:
        rendered = _render_trace_log(
            [],
            {
                "1-0-004": type("Card", (), {"name": "ランサー"})(),
                "1-0-061": type("Card", (), {"name": "不可侵防壁"})(),
                "1-0-101": type("Card", (), {"name": "赤進化ユニット"})(),
            },
            [
                {"round_no": 4, "player_id": "P1", "type": "unit_driven", "source_card_no": "1-0-004"},
                {"round_no": 4, "player_id": "P1", "type": "card_set_to_trigger_zone", "source_card_no": "1-0-061"},
                {"round_no": 4, "player_id": "P1", "type": "unit_overdriven", "source_card_no": "1-0-101"},
                {
                    "round_no": 4,
                    "player_id": "P1",
                    "type": "card_overridden",
                    "source_card_no": "1-0-004",
                    "metadata": {"from_level": 1, "to_level": 2},
                },
                {"round_no": 4, "player_id": "P1", "type": "unit_retreated", "source_card_no": "1-0-004"},
            ],
            show_reqres=False,
        )

        self.assertTrue(any("ランサーをユニットドライブ" in line for line in rendered))
        self.assertTrue(any("トリガーゾーンに不可侵防壁をセット" in line for line in rendered))
        self.assertTrue(any("赤進化ユニットでオーバードライブ" in line for line in rendered))
        self.assertTrue(any("ランサーをオーバーライド Lv.1 -> Lv.2" in line for line in rendered))
        self.assertTrue(any("ランサーを撤退させる" in line for line in rendered))

    # 対象ユニットに与える能力ダメージもカード名つきで描画されることを確認する。
    def test_render_trace_log_renders_targeted_ability_damage(self) -> None:
        rendered = _render_trace_log(
            [],
            {
                "1-0-004": type("Card", (), {"name": "ランサー"})(),
                "2-0-010": type("Card", (), {"name": "見習い魔導士リーナ"})(),
            },
            [
                {
                    "round_no": 3,
                    "player_id": "P2",
                    "type": "ability_damage_dealt_to_unit",
                    "source_card_no": "1-0-004",
                    "amount": 1000,
                    "metadata": {
                        "target_card_no": "2-0-010",
                        "current_damage": 1000,
                        "current_bp": 3000,
                        "effect_name": "ダメージブレイク",
                    },
                }
            ],
            show_reqres=False,
        )

        self.assertTrue(any("ランサーのダメージブレイクが見習い魔導士リーナに発動" in line for line in rendered))
        self.assertTrue(any("現BP 3000" in line for line in rendered))

    # インターセプトによるBP変動もカード名つきで描画されることを確認する。
    def test_render_trace_log_renders_intercept_bp_change(self) -> None:
        rendered = _render_trace_log(
            [],
            {
                "1-0-096": type("Card", (), {"name": "不可侵防壁"})(),
                "1-0-004": type("Card", (), {"name": "ランサー"})(),
            },
            [
                {
                    "round_no": 3,
                    "player_id": "P1",
                    "type": "unit_bp_modified",
                    "source_card_no": "1-0-096",
                    "amount": 3000,
                    "metadata": {"target_card_no": "1-0-004", "current_bp": 7000},
                }
            ],
            show_reqres=False,
        )

        self.assertTrue(any("不可侵防壁の効果でランサーのBPが+3000" in line for line in rendered))
        self.assertTrue(any("現BP 7000" in line for line in rendered))

    def test_render_trace_log_renders_drive_cp_cost_without_effect_wording(self) -> None:
        rendered = _render_trace_log(
            [],
            {
                "1-0-004": type("Card", (), {"name": "ランサー"})(),
            },
            [
                {
                    "round_no": 2,
                    "player_id": "P1",
                    "type": "cp_changed",
                    "source_card_no": "1-0-004",
                    "amount": -2,
                    "metadata": {"reason": "unit_drive", "before_cp": 2, "after_cp": 0},
                }
            ],
            show_reqres=False,
        )

        self.assertEqual(rendered, ["[R02][E001] ユニットドライブでP1のCPが-2 (2 -> 0)"])

    def test_render_trace_log_renders_trigger_and_intercept_with_card_names(self) -> None:
        rendered = _render_trace_log(
            [
                {
                    "direction": "from_player",
                    "player_id": "P2",
                    "message": {
                        "type": "choice_response",
                        "request_id": "choice-3-5-1-P2",
                        "payload": {"kind": "use_intercept", "card_no": "1-0-091", "trigger_index": 0},
                    },
                },
            ],
            {
                "1-0-091": type("Card", (), {"name": "ダーク・アーマー"})(),
                "1-0-061": type("Card", (), {"name": "不可侵防壁"})(),
            },
            [
                {"round_no": 3, "player_id": "P1", "type": "trigger_used", "source_card_no": "1-0-061"},
                {"round_no": 3, "player_id": "P2", "type": "intercept_used", "source_card_no": "1-0-091"},
            ],
            show_reqres=False,
        )

        self.assertTrue(any("P1のトリガー 不可侵防壁 が発動" in line for line in rendered))
        self.assertTrue(any("P2がダーク・アーマーをインターセプト使用" in line for line in rendered))


    def test_render_trace_log_renders_drawn_card_names(self) -> None:
        rendered = _render_trace_log(
            [],
            {
                "1-0-040": type("Card", (), {"name": "ハッパロイド"})(),
                "1-0-003": type("Card", (), {"name": "Red Unit 3"})(),
            },
            [
                {
                    "round_no": 3,
                    "player_id": "P1",
                    "type": "card_moved",
                    "source_card_no": "1-0-003",
                    "metadata": {"from_zone": "deck", "to_zone": "hand", "reason": "draw_effect"},
                },
                {
                    "round_no": 3,
                    "player_id": "P1",
                    "type": "cards_drawn",
                    "source_card_no": "1-0-040",
                    "amount": 1,
                    "metadata": {"drawn_card_nos": ["1-0-003"]},
                }
            ],
            show_reqres=False,
        )

        self.assertTrue(any("ハッパロイドの効果でP1が1枚ドロー" in line for line in rendered))
        self.assertTrue(any("Red Unit 3" in line for line in rendered))
        self.assertTrue(any("山札から手札に加える" in line and "Red Unit 3" in line for line in rendered))

    def test_render_trace_log_renders_revive_move(self) -> None:
        rendered = _render_trace_log(
            [],
            {
                "1-0-003": type("Card", (), {"name": "Red Unit 3"})(),
            },
            [
                {
                    "round_no": 3,
                    "player_id": "P1",
                    "type": "card_moved",
                    "source_card_no": "1-0-003",
                    "metadata": {"from_zone": "discard", "to_zone": "hand", "reason": "revive"},
                }
            ],
            show_reqres=False,
        )

        self.assertTrue(any("Red Unit 3" in line and "捨札から手札に戻る" in line for line in rendered))


    def test_render_trace_log_renders_life_changed_for_player_attack(self) -> None:
        rendered = _render_trace_log(
            [],
            {
                "1-0-004": type("Card", (), {"name": "繝ｩ繝ｳ繧ｵ繝ｼ"})(),
            },
            [
                {
                    "round_no": 3,
                    "player_id": "P1",
                    "target_player_id": "P2",
                    "type": "life_changed",
                    "source_card_no": "1-0-004",
                    "amount": -1,
                    "metadata": {"reason": "player_attack", "current_life": 6},
                }
            ],
            show_reqres=False,
        )

        self.assertEqual(rendered, ["[R03][E001] 繝ｩ繝ｳ繧ｵ繝ｼのアタックでP2のライフが-1 (現LIFE 6)"])

        self.assertEqual(rendered, ["[R03][E001] 繝ｩ繝ｳ繧ｵ繝ｼのアタックでP2のライフが-1 (現LIFE 6)"])

    def test_render_trace_log_renders_match_ended(self) -> None:
        rendered = _render_trace_log(
            [],
            {},
            [
                {
                    "round_no": 4,
                    "player_id": "P1",
                    "type": "match_ended",
                    "metadata": {"winner": "P1", "reason": "life_zero", "final_life": {"P1": 7, "P2": 0}},
                }
            ],
            show_reqres=False,
        )

        self.assertEqual(rendered, ["[R04][E001] P1の勝利 (P1 LIFE 7 / P2 LIFE 0)"])

    def test_render_trace_log_does_not_render_noop_overdrive_level_change(self) -> None:
        rendered = _render_trace_log(
            [],
            {
                "1-0-039": type("Card", (), {"name": "冥王ハデス"})(),
            },
            [
                {
                    "round_no": 7,
                    "player_id": "P2",
                    "type": "unit_overdriven",
                    "source_card_no": "1-0-039",
                }
            ],
            show_reqres=False,
        )

        self.assertEqual(rendered, ["[R07][E001] P2が冥王ハデスでオーバードライブ"])


if __name__ == "__main__":
    unittest.main()
