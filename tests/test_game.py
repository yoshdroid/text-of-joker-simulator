import random
import unittest

from tojs.game import (
    UnitState,
    apply_action,
    apply_attack_action,
    build_state_update_payload,
    create_match_state,
    list_available_actions,
    start_turn,
)
from tojs.models import CardDefinition, Regulation


class GameStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.regulation = Regulation(
            deck_size=40,
            max_copies_per_card=3,
            max_cp_per_round=12,
            round_count=10,
            initial_hand_size=4,
            hand_size_limit=7,
            battlefield_unit_limit=5,
            trigger_zone_limit=4,
            opening_draws_first=(0, 2, 2, 2, 2, 2, 2, 2, 2, 2),
            opening_draws_second=(2, 2, 2, 2, 2, 2, 2, 2, 2, 2),
            round_start_cp_first=(2, 3, 4, 5, 6, 7, 7, 7, 7, 7),
            round_start_cp_second=(3, 3, 4, 5, 6, 7, 7, 7, 7, 7),
            starting_life_first=7,
            starting_life_second=7,
        )
        self.card_catalog = {
            f"1-0-{index:03d}": CardDefinition(
                card_no=f"1-0-{index:03d}",
                category="unit",
                rarity="C",
                color="赤",
                name=f"Red Unit {index}",
                cp=1,
                bp_by_level=(3, 4, 5),
                abilities=(),
                race="test",
            )
            for index in range(1, 41)
        }
        self.card_catalog.update(
            {
                f"2-0-{index:03d}": CardDefinition(
                    card_no=f"2-0-{index:03d}",
                    category="unit",
                    rarity="C",
                    color="青",
                    name=f"Blue Unit {index}",
                    cp=1,
                    bp_by_level=(3, 4, 5),
                    abilities=(),
                    race="test",
                )
                for index in range(1, 41)
            }
        )
        self.card_catalog["1-0-101"] = CardDefinition(
            card_no="1-0-101",
            category="evolution",
            rarity="R",
            color="赤",
            name="Red Evolution",
            cp=2,
            bp_by_level=(5, 6, 7),
            abilities=(),
            race="test",
        )
        self.card_catalog["2-0-101"] = CardDefinition(
            card_no="2-0-101",
            category="evolution",
            rarity="R",
            color="青",
            name="Blue Evolution",
            cp=2,
            bp_by_level=(5, 6, 7),
            abilities=(),
            race="test",
        )
        self.first_deck = [f"1-0-{index:03d}" for index in range(1, 41)]
        self.second_deck = [f"2-0-{index:03d}" for index in range(1, 41)]

    def create_state(self) -> object:
        return create_match_state(
            self.regulation,
            self.card_catalog,
            self.first_deck,
            self.second_deck,
            random.Random(7),
        )

    def test_create_match_state_draws_initial_hand(self) -> None:
        # 初期生成時に両プレイヤーへ初期手札 4 枚が配られることを確認する。
        state = self.create_state()

        self.assertEqual(len(state.players["P1"].hand), 4)
        self.assertEqual(len(state.players["P2"].hand), 4)
        self.assertEqual(len(state.players["P1"].draw_pile), 36)
        self.assertEqual(len(state.players["P2"].draw_pile), 36)

    def test_start_turn_for_first_player_round_one(self) -> None:
        # 先攻 1 ターン目はレギュレーション配列どおり 0 枚ドローし、CP だけ設定されることを確認する。
        state = self.create_state()

        start_turn(state, "P1", random.Random(7))

        self.assertEqual(state.turn_player_id, "P1")
        self.assertEqual(state.turn_serial, 1)
        self.assertEqual(len(state.players["P1"].hand), 4)
        self.assertEqual(state.players["P1"].current_cp, 2)

    def test_build_state_update_payload_hides_opponent_hand(self) -> None:
        # state_update では自分の手札は見えるが、相手の手札内容は見えないことを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))

        payload = build_state_update_payload(state, "P1")

        self.assertEqual(payload["viewer_player_id"], "P1")
        self.assertEqual(len(payload["players"]["P1"]["hand_card_nos"]), 4)
        self.assertNotIn("hand_card_nos", payload["players"]["P2"])

    def test_build_state_update_payload_shows_trigger_colors_to_opponent(self) -> None:
        # 相手から見える trigger_zone にはカード内容ではなく色だけが見えることを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].trigger_zone.append("1-0-001")

        payload = build_state_update_payload(state, "P2")

        self.assertEqual(payload["players"]["P1"]["trigger_zone"][0]["color"], "赤")
        self.assertNotIn("card_no", payload["players"]["P1"]["trigger_zone"][0])

    def test_apply_end_turn_moves_to_second_player(self) -> None:
        # end_turn を適用するとターンが後攻へ移り、同ラウンドのまま次ターン準備が走ることを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))

        apply_action(state, "P1", {"kind": "end_turn"}, random.Random(7))

        self.assertEqual(state.turn_player_id, "P2")
        self.assertEqual(state.round_no, 1)
        self.assertEqual(state.players["P2"].current_cp, 3)
        self.assertEqual(len(state.players["P2"].hand), 6)

    def test_list_available_actions_includes_drive(self) -> None:
        # ドライブ可能なユニットがある時は drive アクションが候補に含まれることを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))

        actions = list_available_actions(state, "P1")

        self.assertTrue(any(action["kind"] == "drive" for action in actions))

    def test_list_available_actions_includes_set_trigger(self) -> None:
        # トリガーゾーンに空きがある時は set_trigger アクションが候補に含まれることを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))

        actions = list_available_actions(state, "P1")

        self.assertTrue(any(action["kind"] == "set_trigger" for action in actions))

    def test_apply_set_trigger_action(self) -> None:
        # set_trigger を実行すると手札からトリガーゾーン右端へ移ることを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "set_trigger")

        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(len(state.players["P1"].hand), 3)
        self.assertEqual(len(state.players["P1"].trigger_zone), 1)

    def test_apply_drive_action(self) -> None:
        # ユニットをドライブすると手札から場へ移動し、CP が消費されることを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        drive_action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "drive")

        apply_action(state, "P1", drive_action, random.Random(7))

        self.assertEqual(len(state.players["P1"].battlefield), 1)
        self.assertEqual(len(state.players["P1"].hand), 3)
        self.assertEqual(state.players["P1"].current_cp, 1)
        self.assertTrue(state.players["P1"].battlefield[0].attack_restricted)

    def test_apply_drive_action_uses_trigger_reduction(self) -> None:
        # 同属性ユニットが trigger_zone にある時は drive コストが 1 軽減され、該当カードが捨札へ送られることを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].current_cp = 0
        state.players["P1"].hand = ["1-0-001"]
        state.players["P1"].trigger_zone = ["1-0-002"]

        drive_action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "drive")
        apply_action(state, "P1", drive_action, random.Random(7))

        self.assertEqual(len(state.players["P1"].battlefield), 1)
        self.assertEqual(state.players["P1"].battlefield[0].card_no, "1-0-001")
        self.assertEqual(state.players["P1"].current_cp, 0)
        self.assertEqual(state.players["P1"].trigger_zone, [])
        self.assertEqual(state.players["P1"].discard_pile[0], "1-0-002")

    def test_list_available_actions_includes_overdrive(self) -> None:
        # 同属性ユニットが場にいる時は evolution カードの overdrive が候補に含まれることを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].current_cp = 2
        state.players["P1"].hand = ["1-0-101"]
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-001", level=1, exhausted=False, attack_restricted=True)
        ]

        actions = list_available_actions(state, "P1")

        self.assertTrue(any(action["kind"] == "overdrive" for action in actions))

    def test_apply_overdrive_action(self) -> None:
        # overdrive では対象ユニットを evolution に置き換え、元ユニットを捨札へ送ることを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].current_cp = 2
        state.players["P1"].hand = ["1-0-101"]
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-001", level=1, exhausted=True, attack_restricted=True, current_damage=2)
        ]

        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "overdrive")
        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(len(state.players["P1"].battlefield), 1)
        self.assertEqual(state.players["P1"].battlefield[0].card_no, "1-0-101")
        self.assertTrue(state.players["P1"].battlefield[0].exhausted)
        self.assertFalse(state.players["P1"].battlefield[0].attack_restricted)
        self.assertEqual(state.players["P1"].battlefield[0].current_damage, 0)
        self.assertEqual(state.players["P1"].discard_pile[0], "1-0-001")

    def test_apply_overdrive_action_recovers_exhaustion_for_level_three(self) -> None:
        # Lv.3 evolution を overdrive した時は OC 効果で行動権が回復することを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].current_cp = 2
        state.players["P1"].hand = ["1-0-101"]
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-001", level=1, exhausted=True, attack_restricted=True)
        ]

        apply_action(
            state,
            "P1",
            {
                "kind": "overdrive",
                "hand_index": 0,
                "card_no": "1-0-101",
                "target_index": 0,
                "cost": 2,
                "trigger_reducer_index": None,
                "card_level": 3,
            },
            random.Random(7),
        )

        self.assertFalse(state.players["P1"].battlefield[0].exhausted)
        self.assertEqual(state.players["P1"].battlefield[0].level, 3)

    def test_apply_overdrive_action_uses_trigger_reduction(self) -> None:
        # evolution でも同属性 trigger_zone カードでコスト 1 軽減できることを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].current_cp = 1
        state.players["P1"].hand = ["1-0-101"]
        state.players["P1"].trigger_zone = ["1-0-002"]
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-001", level=1, exhausted=False, attack_restricted=True)
        ]

        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "overdrive")
        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(state.players["P1"].current_cp, 0)
        self.assertEqual(state.players["P1"].trigger_zone, [])
        self.assertEqual(state.players["P1"].discard_pile[0], "1-0-001")
        self.assertEqual(state.players["P1"].discard_pile[1], "1-0-002")

    def test_apply_attack_action_without_block(self) -> None:
        # ブロックされないアタックでは相手ライフが 1 減ることを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-001", level=1, exhausted=False, attack_restricted=False)
        )

        apply_attack_action(state, "P1", {"kind": "attack", "attacker_index": 0, "target": "player"})

        self.assertEqual(state.players["P2"].life, 6)
        self.assertTrue(state.players["P1"].battlefield[0].exhausted)

    def test_apply_attack_action_with_single_block(self) -> None:
        # 1 体ブロックされたアタックでは両者の BP 比較で破壊判定が行われることを確認する。
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-001", level=1, exhausted=False, attack_restricted=False)
        )
        state.players["P2"].battlefield.append(
            UnitState(card_no="2-0-001", level=1, exhausted=False, attack_restricted=False)
        )

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            {"kind": "block", "blocker_index": 0},
        )

        self.assertEqual(len(state.players["P1"].battlefield), 0)
        self.assertEqual(len(state.players["P2"].battlefield), 0)
        self.assertEqual(state.players["P1"].discard_pile[0], "1-0-001")
        self.assertEqual(state.players["P2"].discard_pile[0], "2-0-001")


if __name__ == "__main__":
    unittest.main()
