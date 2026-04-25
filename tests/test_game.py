import random
import unittest

from tojs.game import (
    UnitState,
    apply_action,
    apply_attack_action,
    apply_intercept_action,
    build_state_update_payload,
    create_match_state,
    list_available_intercept_actions,
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
                color="red",
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
                    color="blue",
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
            color="red",
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
            color="blue",
            name="Blue Evolution",
            cp=2,
            bp_by_level=(5, 6, 7),
            abilities=(),
            race="test",
        )
        self.card_catalog.update(
            {
                "1-0-040": CardDefinition(
                    card_no="1-0-040",
                    category="unit",
                    rarity="C",
                    color="red",
                    name="Happaloid",
                    cp=1,
                    bp_by_level=(3, 4, 5),
                    abilities=(),
                    race="test",
                ),
                "1-0-051": CardDefinition(
                    card_no="1-0-051",
                    category="evolution",
                    rarity="R",
                    color="red",
                    name="Barbatos",
                    cp=2,
                    bp_by_level=(5, 6, 7),
                    abilities=(),
                    race="test",
                ),
                "1-0-057": CardDefinition(
                    card_no="1-0-057",
                    category="trigger",
                    rarity="R",
                    color="red",
                    name="Support Trigger",
                    cp=None,
                    bp_by_level=(),
                    abilities=(),
                    race="test",
                ),
                "1-0-061": CardDefinition(
                    card_no="1-0-061",
                    category="intercept",
                    rarity="R",
                    color="red",
                    name="Support Intercept",
                    cp=1,
                    bp_by_level=(),
                    abilities=(),
                    race="test",
                ),
                "1-0-062": CardDefinition(
                    card_no="1-0-062",
                    category="trigger",
                    rarity="R",
                    color="yellow",
                    name="Draw Trigger",
                    cp=None,
                    bp_by_level=(),
                    abilities=(),
                    race="test",
                ),
                "1-0-065": CardDefinition(
                    card_no="1-0-065",
                    category="intercept",
                    rarity="R",
                    color="無",
                    name="Power Shortage",
                    cp=1,
                    bp_by_level=(),
                    abilities=(),
                    race="test",
                ),
                "1-0-074": CardDefinition(
                    card_no="1-0-074",
                    category="intercept",
                    rarity="R",
                    color="無",
                    name="Hero Sword",
                    cp=0,
                    bp_by_level=(),
                    abilities=(),
                    race="test",
                ),
                "1-0-081": CardDefinition(
                    card_no="1-0-081",
                    category="intercept",
                    rarity="R",
                    color="red",
                    name="Awakening of Evil",
                    cp=0,
                    bp_by_level=(),
                    abilities=(),
                    race="test",
                ),
                "1-0-096": CardDefinition(
                    card_no="1-0-096",
                    category="intercept",
                    rarity="R",
                    color="green",
                    name="Fortress Wall",
                    cp=0,
                    bp_by_level=(),
                    abilities=(),
                    race="test",
                ),
            }
        )
        self.first_deck = [f"1-0-{index:03d}" for index in range(1, 41)]
        self.second_deck = [f"2-0-{index:03d}" for index in range(1, 41)]

    def create_state(self):
        return create_match_state(
            self.regulation,
            self.card_catalog,
            self.first_deck,
            self.second_deck,
            random.Random(7),
        )

    # 初期生成時に両プレイヤーへ初期手札 4 枚が配られることを確認する。
    def test_create_match_state_draws_initial_hand(self) -> None:
        state = self.create_state()

        self.assertEqual(len(state.players["P1"].hand), 4)
        self.assertEqual(len(state.players["P2"].hand), 4)
        self.assertEqual(len(state.players["P1"].draw_pile), 36)
        self.assertEqual(len(state.players["P2"].draw_pile), 36)

    # 先攻 1 ターン目はレギュレーション配列どおり 0 枚ドローし、CP だけ設定されることを確認する。
    def test_start_turn_for_first_player_round_one(self) -> None:
        state = self.create_state()

        start_turn(state, "P1", random.Random(7))

        self.assertEqual(state.turn_player_id, "P1")
        self.assertEqual(state.turn_serial, 1)
        self.assertEqual(len(state.players["P1"].hand), 4)
        self.assertEqual(state.players["P1"].current_cp, 2)

    # state_update では自分の手札は見えるが、相手の手札内容は見えないことを確認する。
    def test_build_state_update_payload_hides_opponent_hand(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))

        payload = build_state_update_payload(state, "P1")

        self.assertEqual(payload["viewer_player_id"], "P1")
        self.assertEqual(len(payload["players"]["P1"]["hand_card_nos"]), 4)
        self.assertNotIn("hand_card_nos", payload["players"]["P2"])

    # 相手から見える trigger_zone にはカード内容ではなく色だけが見えることを確認する。
    def test_build_state_update_payload_shows_trigger_colors_to_opponent(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].trigger_zone.append("1-0-001")

        payload = build_state_update_payload(state, "P2")

        self.assertEqual(payload["players"]["P1"]["trigger_zone"][0]["color"], "red")
        self.assertNotIn("card_no", payload["players"]["P1"]["trigger_zone"][0])

    # end_turn を適用するとターンが後攻へ移り、同ラウンドのまま次ターン準備が走ることを確認する。
    def test_apply_end_turn_moves_to_second_player(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))

        apply_action(state, "P1", {"kind": "end_turn"}, random.Random(7))

        self.assertEqual(state.turn_player_id, "P2")
        self.assertEqual(state.round_no, 1)
        self.assertEqual(state.players["P2"].current_cp, 3)
        self.assertEqual(len(state.players["P2"].hand), 6)

    # ドライブ可能なユニットがある時は drive アクションが候補に含まれることを確認する。
    def test_list_available_actions_includes_drive(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))

        actions = list_available_actions(state, "P1")

        self.assertTrue(any(action["kind"] == "drive" for action in actions))

    # トリガーゾーンに空きがある時は set_trigger アクションが候補に含まれることを確認する。
    def test_list_available_actions_includes_set_trigger(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))

        actions = list_available_actions(state, "P1")

        self.assertTrue(any(action["kind"] == "set_trigger" for action in actions))

    # 同名カードが手札に2枚ある時は override アクションが候補に含まれることを確認する。
    def test_list_available_actions_includes_override(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-001", "1-0-001", "1-0-002"]

        actions = list_available_actions(state, "P1")

        self.assertTrue(any(action["kind"] == "override" for action in actions))

    # 同属性ユニットが場にいる時は evolution カードの overdrive が候補に含まれることを確認する。
    def test_list_available_actions_includes_overdrive(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].current_cp = 2
        state.players["P1"].hand = ["1-0-101"]
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-001", level=1, exhausted=False, attack_restricted=True)
        ]

        actions = list_available_actions(state, "P1")

        self.assertTrue(any(action["kind"] == "overdrive" for action in actions))

    # set_trigger を実行すると手札からトリガーゾーン右端へ移ることを確認する。
    def test_apply_set_trigger_action(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "set_trigger")

        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(len(state.players["P1"].hand), 3)
        self.assertEqual(len(state.players["P1"].trigger_zone), 1)

    # override では手札内同名カードを重ねて Lv.2 になり、素材が捨札へ送られて1枚ドローすることを確認する。
    def test_apply_override_action(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-001", "1-0-001", "1-0-002"]
        state.players["P1"].draw_pile = ["1-0-003"] + state.players["P1"].draw_pile
        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "override")

        apply_action(state, "P1", action, random.Random(7))

        self.assertIn("1-0-001@L2", state.players["P1"].hand)
        self.assertIn("1-0-003", state.players["P1"].hand)
        self.assertEqual(state.players["P1"].discard_pile[0], "1-0-001")

    # Lv.2 の同名カード同士を override すると Lv.3 になることを確認する。
    def test_apply_override_action_reaches_level_three(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-001@L2", "1-0-001@L2"]
        state.players["P1"].draw_pile = []
        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "override")

        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(state.players["P1"].hand, ["1-0-001@L3"])

    # Lv.3 のカードは override 候補に出ないことを確認する。
    def test_list_available_actions_excludes_override_for_level_three(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-001@L3", "1-0-001@L3"]

        actions = list_available_actions(state, "P1")

        self.assertFalse(any(action["kind"] == "override" for action in actions))

    # ユニットをドライブすると手札から場へ移動し、CP が消費されることを確認する。
    def test_apply_drive_action(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        drive_action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "drive")

        apply_action(state, "P1", drive_action, random.Random(7))

        self.assertEqual(len(state.players["P1"].battlefield), 1)
        self.assertEqual(len(state.players["P1"].hand), 3)
        self.assertEqual(state.players["P1"].current_cp, 1)
        self.assertTrue(state.players["P1"].battlefield[0].attack_restricted)

    # override した Lv.2 ユニットを drive すると場にも Lv.2 で出ることを確認する。
    def test_apply_drive_action_preserves_hand_level(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-001@L2"]
        state.players["P1"].current_cp = 1

        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "drive")
        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(state.players["P1"].battlefield[0].level, 2)

    # 同属性ユニットが trigger_zone にある時は drive コストが 1 軽減され、該当カードが捨札へ送られることを確認する。
    def test_apply_drive_action_uses_trigger_reduction(self) -> None:
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

    # ハッパロイドが場に出た時は能力で 1 枚ドローすることを確認する。
    def test_field_enter_ability_draws_card(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-040"]
        state.players["P1"].draw_pile = ["1-0-003"] + state.players["P1"].draw_pile
        state.players["P1"].current_cp = 1

        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "drive")
        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(state.players["P1"].battlefield[0].card_no, "1-0-040")
        self.assertEqual(state.players["P1"].hand, ["1-0-003"])

    # 何でも屋の陳列台を trigger_zone に置いた時、自分のユニット登場で 1 枚ドローすることを確認する。
    def test_trigger_zone_field_enter_ability_draws_card(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-001"]
        state.players["P1"].trigger_zone = ["1-0-062"]
        state.players["P1"].draw_pile = ["1-0-003"] + state.players["P1"].draw_pile
        state.players["P1"].current_cp = 1

        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "drive")
        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(state.players["P1"].hand, ["1-0-003"])
        self.assertEqual(state.players["P1"].trigger_zone, [])
        self.assertEqual(state.players["P1"].discard_pile[0], "1-0-062")

    # 効果が全く及ばない trigger は発動せず、trigger_zone に残ることを確認する
    def test_trigger_zone_ability_stays_when_no_effect(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-001"]
        state.players["P1"].trigger_zone = ["1-0-062"]
        state.players["P1"].draw_pile = []
        state.players["P1"].current_cp = 1

        action = {
            "kind": "drive",
            "hand_index": 0,
            "card_no": "1-0-001",
            "card_level": 1,
            "cost": 1,
            "trigger_reducer_index": None,
        }
        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(state.players["P1"].trigger_zone, ["1-0-062"])
        self.assertEqual(state.players["P1"].discard_pile, [])

    # 左から順に trigger が解決され、使用済みカードが順に捨札へ送られることを確認する
    def test_multiple_trigger_zone_abilities_resolve_from_left_to_right(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-001"]
        state.players["P1"].trigger_zone = ["1-0-062", "1-0-061"]
        state.players["P1"].draw_pile = ["1-0-003", "1-0-074"] + state.players["P1"].draw_pile
        state.players["P1"].current_cp = 1

        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "drive")
        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(state.players["P1"].trigger_zone, [])
        self.assertEqual(state.players["P1"].discard_pile[:2], ["1-0-061", "1-0-062"])
        self.assertIn("1-0-003", state.players["P1"].hand)
        self.assertIn("1-0-074", state.players["P1"].hand)

    # ソードファイターのアタック時能力で BP が +2000 され、ターン終了時に元へ戻ることを確認する。
    def test_attack_trigger_temporary_bp_bonus(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-002", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        )

        apply_attack_action(state, "P1", {"kind": "attack", "attacker_index": 0, "target": "player"}, rng=random.Random(7))

        self.assertEqual(build_state_update_payload(state, "P1")["players"]["P1"]["battlefield"][0]["current_bp"], 5000)
        apply_action(state, "P1", {"kind": "end_turn"}, random.Random(7))
        self.assertEqual(state.players["P1"].battlefield[0].temporary_bp_modifier, 0)

    # ランサーのアタック時能力はブロック前に相手ユニットへ 1000 ダメージを与えることを確認する。
    def test_attack_trigger_damage_resolves_before_combat(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.card_catalog["2-0-001"] = CardDefinition(
            card_no="2-0-001",
            category="unit",
            rarity="C",
            color="blue",
            name="Weak Blue Unit",
            cp=1,
            bp_by_level=(1, 1, 1),
            abilities=(),
            race="test",
        )
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-004", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        )
        state.players["P2"].battlefield.append(
            UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        )

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            {"kind": "block", "blocker_index": 0},
            rng=random.Random(7),
        )

        self.assertEqual(len(state.players["P1"].battlefield), 1)
        self.assertEqual(len(state.players["P2"].battlefield), 0)

    # ゴライアスが戦闘勝利で Lv.3 になった時、オーバークロック能力で相手ライフが 1 減ることを確認する。
    def test_overclock_trigger_deals_life_damage(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.card_catalog["2-0-001"] = CardDefinition(
            card_no="2-0-001",
            category="unit",
            rarity="C",
            color="blue",
            name="Weak Blue Unit",
            cp=1,
            bp_by_level=(1, 1, 1),
            abilities=(),
            race="test",
        )
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-007", unit_id=1, level=2, exhausted=False, attack_restricted=False)
        )
        state.players["P2"].battlefield.append(
            UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        )

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            {"kind": "block", "blocker_index": 0},
            rng=random.Random(7),
        )

        self.assertEqual(state.players["P2"].life, 6)

    # 無色 intercept は戦闘時に使用可能で、使用すると trigger_zone から捨札へ移り BP 補正が反映されることを確認する
    def test_apply_intercept_action_for_battle_buff(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        attacker = UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        blocker = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [attacker]
        state.players["P2"].battlefield = [blocker]
        state.players["P1"].trigger_zone = ["1-0-074"]

        actions = list_available_intercept_actions(state, "P1", attacker, blocker, True)
        action = next(action for action in actions if action["kind"] == "use_intercept")

        apply_intercept_action(state, "P1", action, attacker, blocker, True)

        self.assertEqual(state.players["P1"].trigger_zone, [])
        self.assertEqual(state.players["P1"].discard_pile[0], "1-0-074")
        self.assertEqual(build_state_update_payload(state, "P1")["players"]["P1"]["battlefield"][0]["current_bp"], 5000)

    # 色指定 intercept は同色ユニットがいないと使用できず、赤ユニットがいれば使用可能になることを確認する
    def test_list_available_intercept_actions_respects_color_requirement(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        attacker = UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        blocker = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = []
        state.players["P1"].trigger_zone = ["1-0-081"]

        no_actions = list_available_intercept_actions(state, "P1", attacker, blocker, True)
        self.assertFalse(any(action["kind"] == "use_intercept" for action in no_actions))

        state.players["P1"].battlefield = [attacker]
        yes_actions = list_available_intercept_actions(state, "P1", attacker, blocker, True)
        self.assertTrue(any(action["kind"] == "use_intercept" for action in yes_actions))

    # overdrive では対象ユニットを evolution に置き換え、元ユニットを捨札へ送ることを確認する。
    def test_apply_overdrive_action(self) -> None:
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

    # Lv.3 evolution を overdrive した時は OC 効果で行動権が回復することを確認する。
    def test_apply_overdrive_action_recovers_exhaustion_for_level_three(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].current_cp = 2
        state.players["P1"].hand = ["1-0-101@L3"]
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-001", level=1, exhausted=True, attack_restricted=True)
        ]

        apply_action(
            state,
            "P1",
            {
                "kind": "overdrive",
                "hand_index": 0,
                "card_no": "1-0-101@L3",
                "target_index": 0,
                "cost": 2,
                "trigger_reducer_index": None,
                "card_level": 3,
            },
            random.Random(7),
        )

        self.assertFalse(state.players["P1"].battlefield[0].exhausted)
        self.assertEqual(state.players["P1"].battlefield[0].level, 3)

    # evolution でも同属性 trigger_zone カードでコスト 1 軽減できることを確認する。
    def test_apply_overdrive_action_uses_trigger_reduction(self) -> None:
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

    # ブロックされないアタックでは相手ライフが 1 減ることを確認する。
    def test_apply_attack_action_without_block(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-001", level=1, exhausted=False, attack_restricted=False)
        )

        apply_attack_action(state, "P1", {"kind": "attack", "attacker_index": 0, "target": "player"})

        self.assertEqual(state.players["P2"].life, 6)
        self.assertTrue(state.players["P1"].battlefield[0].exhausted)

    # 1 体ブロックされたアタックでは両者の BP 比較で破壊判定が行われることを確認する。
    def test_apply_attack_action_with_single_block(self) -> None:
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

    # 攻撃側が戦闘勝利した時はクロックアップし、ダメージが全快することを確認する。
    def test_clock_up_on_attacker_battle_win(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.card_catalog["2-0-001"] = CardDefinition(
            card_no="2-0-001",
            category="unit",
            rarity="C",
            color="blue",
            name="Weak Blue Unit",
            cp=1,
            bp_by_level=(1, 1, 1),
            abilities=(),
            race="test",
        )
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-001", level=1, exhausted=False, attack_restricted=False, current_damage=1000)
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

        self.assertEqual(len(state.players["P1"].battlefield), 1)
        self.assertEqual(state.players["P1"].battlefield[0].level, 2)
        self.assertEqual(state.players["P1"].battlefield[0].current_damage, 0)
        self.assertEqual(len(state.players["P2"].battlefield), 0)

    # 防御側が戦闘勝利した時もクロックアップすることを確認する。
    def test_clock_up_on_blocker_battle_win(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.card_catalog["1-0-001"] = CardDefinition(
            card_no="1-0-001",
            category="unit",
            rarity="C",
            color="red",
            name="Weak Red Unit",
            cp=1,
            bp_by_level=(1, 1, 1),
            abilities=(),
            race="test",
        )
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-001", level=1, exhausted=False, attack_restricted=False)
        )
        state.players["P2"].battlefield.append(
            UnitState(card_no="2-0-001", level=1, exhausted=False, attack_restricted=False, current_damage=1000)
        )

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            {"kind": "block", "blocker_index": 0},
        )

        self.assertEqual(len(state.players["P1"].battlefield), 0)
        self.assertEqual(len(state.players["P2"].battlefield), 1)
        self.assertEqual(state.players["P2"].battlefield[0].level, 2)
        self.assertEqual(state.players["P2"].battlefield[0].current_damage, 0)

    # Lv.2 のユニットが戦闘勝利して Lv.3 になる時は OC 効果で行動権回復とアタック制限解除が起きることを確認する。
    def test_clock_up_to_overclock_recovers_action_and_attack_restriction(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.card_catalog["2-0-001"] = CardDefinition(
            card_no="2-0-001",
            category="unit",
            rarity="C",
            color="blue",
            name="Weak Blue Unit",
            cp=1,
            bp_by_level=(1, 1, 1),
            abilities=(),
            race="test",
        )
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-001", level=2, exhausted=False, attack_restricted=False)
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

        self.assertEqual(state.players["P1"].battlefield[0].level, 3)
        self.assertFalse(state.players["P1"].battlefield[0].exhausted)
        self.assertFalse(state.players["P1"].battlefield[0].attack_restricted)

    # すでに Lv.3 のユニットは戦闘勝利してもこれ以上クロックアップせず、その戦闘ダメージは残ることを確認する。
    def test_level_three_unit_does_not_clock_up_or_heal_on_battle_win(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.card_catalog["2-0-001"] = CardDefinition(
            card_no="2-0-001",
            category="unit",
            rarity="C",
            color="blue",
            name="Weak Blue Unit",
            cp=1,
            bp_by_level=(2, 2, 2),
            abilities=(),
            race="test",
        )
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-001", level=3, exhausted=False, attack_restricted=False, current_damage=1000)
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

        self.assertEqual(state.players["P1"].battlefield[0].level, 3)
        self.assertEqual(state.players["P1"].battlefield[0].current_damage, 3000)


if __name__ == "__main__":
    unittest.main()
