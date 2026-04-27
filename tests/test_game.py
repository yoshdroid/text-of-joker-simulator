import random
import unittest

import tojs.game as game_module

from tojs.game import (
    AbilityEvent,
    UnitState,
    apply_action,
    apply_attack_action,
    apply_intercept_action,
    apply_reactive_intercept_action,
    build_reactive_intercept_choice_payload,
    build_block_choice_payload,
    build_intercept_choice_payload,
    build_state_update_payload,
    create_match_state,
    get_event_definition,
    list_available_block_actions,
    list_available_intercept_actions,
    list_available_actions,
    resolve_ability_events,
    start_turn,
)
from tojs.models import AbilityDefinition, CardDefinition, Regulation


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

    # イベント定義表から、登場時と破壊時の能力収集モードを読み取れることを確認する。
    def test_event_definitions_describe_collection_modes(self) -> None:
        unit_entered = get_event_definition("unit_entered")
        unit_destroyed = get_event_definition("unit_destroyed")

        self.assertEqual(unit_entered.collection_mode, "priority")
        self.assertTrue(unit_entered.collect_unit_abilities)
        self.assertTrue(unit_entered.collect_trigger_abilities)
        self.assertTrue(unit_entered.unit_ability_source_only)
        self.assertEqual(unit_entered.opponent_event_type, "opponent_unit_entered")

        self.assertEqual(unit_destroyed.collection_mode, "destroyed_source")
        self.assertEqual(unit_destroyed.source_zone, "graveyard")

    # 相手ユニットの登場は opponent_unit_entered として相手側ユニット能力に渡されることを確認する。
    def test_opponent_prefixed_unit_enter_event_is_collected_for_opponent_side(self) -> None:
        state = self.create_state()
        state.card_catalog["9-0-001"] = CardDefinition(
            card_no="9-0-001",
            category="unit",
            rarity="R",
            color="yellow",
            name="Opponent Enter Watcher",
            cp=2,
            bp_by_level=(4, 5, 6),
            abilities=(AbilityDefinition(name="見張り", text=""),),
            race="test",
        )
        state.players["P1"].battlefield = [
            UnitState(card_no="9-0-001", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P2"].battlefield = [
            UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        ]

        registry_key = ("9-0-001", "opponent_unit_entered")
        original_resolver = game_module.ABILITY_REGISTRY.get(registry_key)
        game_module.ABILITY_REGISTRY[registry_key] = (
            lambda state, event, triggered_ability, rng, choice_resolver=None: []
        )
        try:
            resolve_ability_events(
                state,
                [AbilityEvent(type="unit_entered", player_id="P2", source_unit_id=2)],
                random.Random(7),
            )
        finally:
            if original_resolver is None:
                del game_module.ABILITY_REGISTRY[registry_key]
            else:
                game_module.ABILITY_REGISTRY[registry_key] = original_resolver

        ability_triggered = next(event for event in state.event_log if event["type"] == "ability_triggered")
        self.assertEqual(ability_triggered["player_id"], "P1")
        self.assertEqual(ability_triggered["source_card_no"], "9-0-001")
        self.assertEqual(ability_triggered["metadata"]["event_type"], "opponent_unit_entered")

    # 必要ドロー枚数がデッキ残枚数を上回る場合は、残りデッキを先に引かず、捨札を混ぜた新デッキから引くことを確認する
    def test_draw_rebuilds_deck_before_drawing(self) -> None:
        state = self.create_state()
        player = state.players["P1"]
        player.hand = []
        player.draw_pile = ["1-0-001"]
        player.discard_pile = ["1-0-002", "1-0-003"]

        from tojs.game import draw_cards

        draw_cards(player, 2, random.Random(7), self.regulation.hand_size_limit)

        self.assertEqual(len(player.hand), 2)
        self.assertNotEqual(player.hand[0], "1-0-001")
        self.assertEqual(player.discard_pile, [])
        self.assertEqual(len(player.draw_pile), 1)

    # 山札再構築後は捨札が空になり、必要枚数だけ引いた残りが新しい山札に残ることを確認する
    def test_draw_rebuild_clears_discard_pile(self) -> None:
        state = self.create_state()
        player = state.players["P1"]
        player.hand = []
        player.draw_pile = []
        player.discard_pile = ["1-0-010", "1-0-011", "1-0-012"]

        from tojs.game import draw_cards

        draw_cards(player, 2, random.Random(3), self.regulation.hand_size_limit)

        self.assertEqual(len(player.hand), 2)
        self.assertEqual(player.discard_pile, [])
        self.assertEqual(len(player.draw_pile), 1)

    # 先攻 1 ターン目はレギュレーション配列どおり 0 枚ドローし、CP だけ設定されることを確認する。
    def test_start_turn_for_first_player_round_one(self) -> None:
        state = self.create_state()

        start_turn(state, "P1", random.Random(7))

        self.assertEqual(state.turn_player_id, "P1")
        self.assertEqual(state.turn_serial, 1)
        self.assertEqual(len(state.players["P1"].hand), 4)
        self.assertEqual(state.players["P1"].current_cp, 2)
        self.assertEqual(state.event_log[0]["type"], "turn_started")
        self.assertEqual(state.event_log[1]["type"], "turn_start_draw")
        self.assertEqual(state.event_log[1]["amount"], 0)
        self.assertEqual(state.event_log[1]["metadata"]["drawn_card_nos"], [])
        self.assertEqual(state.event_log[2]["type"], "turn_start_cp_set")
        self.assertEqual(state.event_log[2]["amount"], 2)
        self.assertEqual(state.event_log[2]["metadata"]["set_cp"], 2)

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

    # 場にいるユニットは自ターン中に撤退を選べることを確認する。
    def test_list_available_actions_includes_retreat(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=False, attack_restricted=True)
        )

        actions = list_available_actions(state, "P1")

        self.assertTrue(any(action["kind"] == "retreat" for action in actions))

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

    # set_trigger ではトリガーゾーン配置イベントが記録されることを確認する。
    def test_apply_set_trigger_action_records_event(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "set_trigger")

        apply_action(state, "P1", action, random.Random(7))

        move_event = state.event_log[-2]
        event = state.event_log[-1]
        self.assertEqual(move_event["type"], "card_moved")
        self.assertEqual(move_event["metadata"]["from_zone"], "hand")
        self.assertEqual(move_event["metadata"]["to_zone"], "trigger_zone")
        self.assertEqual(event["type"], "card_set_to_trigger_zone")
        self.assertEqual(event["player_id"], "P1")
        self.assertEqual(event["source_card_no"], state.players["P1"].trigger_zone[0])

    # 撤退すると場のユニットが捨札へ移り、バトルフィールドから取り除かれることを確認する。
    def test_apply_retreat_action(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=True, attack_restricted=False)
        )
        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "retreat")

        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(state.players["P1"].battlefield, [])
        self.assertEqual(state.players["P1"].discard_pile[0], "1-0-001")

    # retreat では撤退イベントと捨札移動イベントが記録されることを確認する。
    def test_apply_retreat_action_records_events(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=True, attack_restricted=False)
        )
        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "retreat")

        apply_action(state, "P1", action, random.Random(7))

        event_types = [event["type"] for event in state.event_log]
        self.assertIn("unit_retreated", event_types)
        self.assertIn("unit_sent_to_discard", event_types)

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

    # override では素材移動、レベル変化、1枚ドローのイベントが記録されることを確認する。
    def test_apply_override_action_records_events(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-001", "1-0-001", "1-0-002"]
        state.players["P1"].draw_pile = ["1-0-003"] + state.players["P1"].draw_pile
        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "override")

        apply_action(state, "P1", action, random.Random(7))

        event_types = [event["type"] for event in state.event_log]
        self.assertIn("card_moved", event_types)
        self.assertIn("card_overridden", event_types)
        self.assertIn("cards_drawn", event_types)
        draw_event = next(event for event in state.event_log if event["type"] == "cards_drawn")
        self.assertEqual(draw_event["metadata"]["drawn_card_nos"], ["1-0-003"])
        moved_event = next(
            event
            for event in state.event_log
            if event["type"] == "card_moved"
            and event["source_card_no"] == "1-0-003"
            and event["metadata"]["from_zone"] == "deck"
        )
        self.assertEqual(moved_event["metadata"]["to_zone"], "hand")
        self.assertEqual(moved_event["metadata"]["reason"], "override_draw")

    # Lv.2 の同名カード同士を override すると Lv.3 になり、山札不足時は捨札を含む新山札から 1 枚引くことを確認する。
    def test_apply_override_action_reaches_level_three(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-001@L2", "1-0-001@L2"]
        state.players["P1"].draw_pile = []
        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "override")

        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(state.players["P1"].hand, ["1-0-001@L3", "1-0-001"])

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

    # drive では CP消費とユニットドライブのイベントが記録されることを確認する。
    def test_apply_drive_action_records_events(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        drive_action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "drive")

        apply_action(state, "P1", drive_action, random.Random(7))

        event_types = [event["type"] for event in state.event_log]
        self.assertIn("cp_changed", event_types)
        self.assertIn("unit_driven", event_types)
        self.assertIn("unit_entered", event_types)

    # スピードムーブを持つユニットは出たターンでもアタック制限を受けないことを確認する。
    def test_apply_drive_action_with_speed_move_removes_attack_restriction(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-006"] = CardDefinition(
            card_no="1-0-006",
            category="unit",
            rarity="C",
            color="red",
            name="Speed Unit",
            cp=1,
            bp_by_level=(3, 4, 5),
            abilities=(AbilityDefinition(name="スピードムーブ", text=""),),
            race="test",
        )
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].hand = ["1-0-006"]
        state.players["P1"].current_cp = 1

        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "drive")
        apply_action(state, "P1", action, random.Random(7))

        self.assertFalse(state.players["P1"].battlefield[0].attack_restricted)
        self.assertTrue(any(a["kind"] == "attack" for a in list_available_actions(state, "P1")))

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
        draw_event = next(
            event
            for event in state.event_log
            if event["type"] == "cards_drawn" and event["source_card_no"] == "1-0-040"
        )
        self.assertEqual(draw_event["metadata"]["drawn_card_nos"], ["1-0-003"])

    # ユニット能力が発動した時、能力名つきの ability_triggered イベントが記録されることを確認する。
    def test_unit_ability_trigger_records_ability_name(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-040"]
        state.players["P1"].draw_pile = ["1-0-003"] + state.players["P1"].draw_pile
        state.players["P1"].current_cp = 1

        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "drive")
        apply_action(state, "P1", action, random.Random(7))

        trigger_event = next(event for event in state.event_log if event["type"] == "ability_triggered")
        self.assertEqual(trigger_event["player_id"], "P1")
        self.assertEqual(trigger_event["source_card_no"], "1-0-040")
        self.assertEqual(trigger_event["metadata"]["ability_name"], "ハッパロイド")

    # abilities.raw の event_type 指定がある場合、その能力名を優先して表示することを確認する。
    def test_unit_ability_trigger_prefers_raw_event_type_match(self) -> None:
        state = self.create_state()
        state.card_catalog["9-0-002"] = CardDefinition(
            card_no="9-0-002",
            category="unit",
            rarity="R",
            color="red",
            name="Dual Trigger Unit",
            cp=2,
            bp_by_level=(4, 5, 6),
            abilities=(
                AbilityDefinition(name="登場反応", text="", raw={"event_type": "unit_entered"}),
                AbilityDefinition(name="相手登場反応", text="", raw={"event_type": "opponent_unit_entered"}),
            ),
            race="test",
        )
        state.players["P1"].battlefield = [
            UnitState(card_no="9-0-002", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]

        registry_key = ("9-0-002", "opponent_unit_entered")
        original_resolver = game_module.ABILITY_REGISTRY.get(registry_key)
        game_module.ABILITY_REGISTRY[registry_key] = (
            lambda state, event, triggered_ability, rng, choice_resolver=None: []
        )
        try:
            resolve_ability_events(
                state,
                [AbilityEvent(type="unit_entered", player_id="P2", source_unit_id=3)],
                random.Random(7),
            )
        finally:
            if original_resolver is None:
                del game_module.ABILITY_REGISTRY[registry_key]
            else:
                game_module.ABILITY_REGISTRY[registry_key] = original_resolver

        trigger_event = next(event for event in state.event_log if event["type"] == "ability_triggered")
        self.assertEqual(trigger_event["metadata"]["ability_name"], "相手登場反応")
        self.assertEqual(trigger_event["metadata"]["event_type"], "opponent_unit_entered")

    # raw の event_type が宣言されている場合、その契機以外では resolver が存在しても候補収集しないことを確認する。
    def test_declared_event_type_blocks_non_matching_trigger_collection(self) -> None:
        state = self.create_state()
        state.card_catalog["9-0-003"] = CardDefinition(
            card_no="9-0-003",
            category="unit",
            rarity="R",
            color="red",
            name="Declared Event Unit",
            cp=2,
            bp_by_level=(4, 5, 6),
            abilities=(
                AbilityDefinition(name="相手登場反応", text="", raw={"event_type": "opponent_unit_entered"}),
            ),
            race="test",
        )
        state.players["P1"].battlefield = [
            UnitState(card_no="9-0-003", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]

        unit_enter_key = ("9-0-003", "unit_entered")
        opponent_enter_key = ("9-0-003", "opponent_unit_entered")
        original_unit_enter = game_module.ABILITY_REGISTRY.get(unit_enter_key)
        original_opponent_enter = game_module.ABILITY_REGISTRY.get(opponent_enter_key)
        resolver = lambda state, event, triggered_ability, rng, choice_resolver=None: []
        game_module.ABILITY_REGISTRY[unit_enter_key] = resolver
        game_module.ABILITY_REGISTRY[opponent_enter_key] = resolver
        try:
            resolve_ability_events(
                state,
                [AbilityEvent(type="unit_entered", player_id="P1", source_unit_id=1)],
                random.Random(7),
            )
        finally:
            if original_unit_enter is None:
                del game_module.ABILITY_REGISTRY[unit_enter_key]
            else:
                game_module.ABILITY_REGISTRY[unit_enter_key] = original_unit_enter
            if original_opponent_enter is None:
                del game_module.ABILITY_REGISTRY[opponent_enter_key]
            else:
                game_module.ABILITY_REGISTRY[opponent_enter_key] = original_opponent_enter

        self.assertEqual([event for event in state.event_log if event["type"] == "ability_triggered"], [])

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

    # 相手ユニットの登場では、自分の「あなたのユニットがフィールドに出たとき」trigger は発動しないことを確認する。
    def test_trigger_zone_field_enter_ability_does_not_fire_for_opponent_unit(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-001"]
        state.players["P1"].current_cp = 1
        state.players["P2"].trigger_zone = ["1-0-062", "1-0-061"]
        state.players["P2"].draw_pile = ["1-0-003", "1-0-074"] + state.players["P2"].draw_pile

        action = {
            "kind": "drive",
            "hand_index": 0,
            "card_no": "1-0-001",
            "card_level": 1,
            "cost": 1,
            "trigger_reducer_index": None,
        }
        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(state.players["P2"].trigger_zone, ["1-0-062", "1-0-061"])
        trigger_draw_events = [
            event
            for event in state.event_log
            if event["type"] == "cards_drawn" and event["source_card_no"] in {"1-0-061", "1-0-062"}
        ]
        self.assertEqual(trigger_draw_events, [])

    # 同じプレイヤーの別ユニットが持つ登場時能力は、そのユニット自身が出た時だけ発動することを確認する。
    def test_unit_enter_trigger_does_not_fire_for_other_friendly_unit(self) -> None:
        state = self.create_state()
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-040", unit_id=1, exhausted=False, attack_restricted=True),
            UnitState(card_no="1-0-001", unit_id=2, exhausted=False, attack_restricted=True),
        ]
        before_hand = list(state.players["P1"].hand)

        resolve_ability_events(
            state,
            [AbilityEvent(type="unit_entered", player_id="P1", source_unit_id=2)],
            random.Random(0),
        )

        self.assertEqual(state.players["P1"].hand, before_hand)

    # トリガーゾーンのユニットカードは軽減用としてのみ扱われ、ユニット能力は発動しないことを確認する。
    def test_unit_card_in_trigger_zone_does_not_resolve_unit_abilities(self) -> None:
        state = self.create_state()
        state.players["P1"].trigger_zone = ["1-0-012"]
        state.players["P2"].battlefield = [
            UnitState(card_no="1-0-033", unit_id=3, exhausted=False, attack_restricted=True)
        ]

        resolve_ability_events(
            state,
            [AbilityEvent(type="unit_entered", player_id="P1", source_unit_id=1)],
            random.Random(0),
        )
        resolve_ability_events(
            state,
            [AbilityEvent(type="unit_attacked", player_id="P1", source_unit_id=1, target_player_id="P2")],
            random.Random(0),
        )

        self.assertEqual(state.players["P2"].battlefield[0].current_damage, 0)
        self.assertEqual(state.players["P2"].trigger_zone, [])

    # 対象選択を伴う登場能力では choice_resolver に渡した対象が選ばれることを確認する
    def test_enter_ability_uses_selected_target(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].hand = ["1-0-051"]
        state.players["P1"].current_cp = 2
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-001", unit_id=10, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P2"].battlefield = [
            UnitState(card_no="2-0-001", unit_id=1, level=1, exhausted=False, attack_restricted=False),
            UnitState(card_no="2-0-002", unit_id=2, level=1, exhausted=False, attack_restricted=False),
        ]

        apply_action(
            state,
            "P1",
            next(action for action in list_available_actions(state, "P1") if action["kind"] == "overdrive"),
            random.Random(7),
            choice_resolver=lambda _player_id, _payload: {"kind": "choose_unit", "target_index": 1},
        )

        self.assertEqual(len(state.players["P2"].battlefield), 1)
        self.assertEqual(state.players["P2"].battlefield[0].card_no, "2-0-001")

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

    # 相手側のアタック時能力は、自分のユニットが攻撃した時には発動しないことを確認する。
    def test_attack_trigger_does_not_fire_for_opponent_attacker(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-002", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P2"].battlefield = [
            UnitState(card_no="1-0-002", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        ]

        apply_attack_action(state, "P1", {"kind": "attack", "attacker_index": 0, "target": "player"}, rng=random.Random(7))

        self.assertEqual(state.players["P1"].battlefield[0].temporary_bp_modifier, 2000)
        self.assertEqual(state.players["P2"].battlefield[0].temporary_bp_modifier, 0)

    # 同じプレイヤーの別ユニットが持つアタック時能力は、攻撃していない限り発動しないことを確認する。
    def test_attack_trigger_does_not_fire_for_other_friendly_unit(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-002", unit_id=1, level=1, exhausted=False, attack_restricted=False),
            UnitState(card_no="1-0-012", unit_id=2, level=1, exhausted=False, attack_restricted=False),
        ]
        state.players["P2"].battlefield = [
            UnitState(card_no="1-0-033", unit_id=3, level=1, exhausted=False, attack_restricted=False)
        ]

        apply_attack_action(state, "P1", {"kind": "attack", "attacker_index": 0, "target": "player"}, rng=random.Random(7))

        self.assertEqual(state.players["P2"].battlefield[0].current_damage, 0)
        self.assertEqual(state.players["P1"].battlefield[0].temporary_bp_modifier, 2000)

    # 手札選択を伴うアタック時能力では choice_resolver が選んだ手札が捨札になることを確認する
    def test_attack_ability_uses_selected_hand_card(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].hand = ["1-0-002", "1-0-003"]
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-010", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        )

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            rng=random.Random(7),
            choice_resolver=lambda _player_id, _payload: {"kind": "discard_hand", "hand_index": 1},
        )

        self.assertEqual(state.players["P1"].hand, ["1-0-002"])
        self.assertEqual(state.players["P1"].discard_pile[0], "1-0-003")

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

    # ブロック時能力はブロックした側のユニットだけが発動し、攻撃側の同能力ユニットは発動しないことを確認する。
    def test_block_trigger_does_not_fire_for_attacker_side_unit(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-045"] = CardDefinition(
            card_no="1-0-045",
            category="unit",
            rarity="R",
            color="red",
            name="Leafia",
            cp=3,
            bp_by_level=(6, 7, 8),
            abilities=(AbilityDefinition(name="ブロッカー", text=""),),
            race="test",
        )
        state.card_catalog["1-0-300"] = CardDefinition(
            card_no="1-0-300",
            category="unit",
            rarity="C",
            color="red",
            name="Six Power Attacker",
            cp=1,
            bp_by_level=(6, 6, 6),
            abilities=(),
            race="test",
        )
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-045", unit_id=1, level=1, exhausted=False, attack_restricted=False),
            UnitState(card_no="1-0-300", unit_id=2, level=1, exhausted=False, attack_restricted=False),
        ]
        state.players["P2"].battlefield = [
            UnitState(card_no="1-0-045", unit_id=3, level=1, exhausted=False, attack_restricted=False)
        ]

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 1, "target": "player"},
            {"kind": "block", "blocker_index": 0},
            random.Random(7),
        )

        self.assertEqual(state.players["P1"].battlefield[0].temporary_bp_modifier, 0)

    # 戦闘で与えるダメージは基本BPではなく、戦闘開始時点の現BPを参照することを確認する。
    def test_combat_damage_uses_current_bp_after_precombat_damage(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.card_catalog["1-0-004"] = CardDefinition(
            card_no="1-0-004",
            category="unit",
            rarity="C",
            color="red",
            name="Lancer",
            cp=1,
            bp_by_level=(4, 5, 6),
            abilities=(AbilityDefinition(name="ダメージブレイク", text=""),),
            race="test",
        )
        state.card_catalog["2-0-010"] = CardDefinition(
            card_no="2-0-010",
            category="unit",
            rarity="C",
            color="blue",
            name="Rina",
            cp=1,
            bp_by_level=(4, 4, 4),
            abilities=(),
            race="test",
        )
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-004", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P2"].battlefield = [
            UnitState(card_no="2-0-010", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        ]

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            {"kind": "block", "blocker_index": 0},
            random.Random(7),
            lambda _player_id, _payload: {"kind": "choose_unit", "target_index": 0},
        )

        attacker_damage_event = next(
            event
            for event in state.event_log
            if event["type"] == "battle_bp_changed" and event["player_id"] == "P1"
        )
        self.assertEqual(attacker_damage_event["amount"], 3000)

    # ランサーのダメージブレイクは対象ユニット名つきのイベントとして記録されることを確認する。
    def test_lancer_attack_records_damage_break_event(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.card_catalog["2-0-010"] = CardDefinition(
            card_no="2-0-010",
            category="unit",
            rarity="C",
            color="blue",
            name="Rina",
            cp=1,
            bp_by_level=(4, 4, 4),
            abilities=(),
            race="test",
        )
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-004", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P2"].battlefield = [
            UnitState(card_no="2-0-010", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        ]

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            {"kind": "no_block"},
            random.Random(7),
            lambda _player_id, _payload: {"kind": "choose_unit", "target_index": 0},
        )

        damage_event = next(event for event in state.event_log if event["type"] == "ability_damage_dealt_to_unit")
        self.assertEqual(damage_event["source_card_no"], "1-0-004")
        self.assertEqual(damage_event["amount"], 1000)
        self.assertEqual(damage_event["metadata"]["target_card_no"], "2-0-010")
        self.assertEqual(damage_event["metadata"]["effect_name"], "ダメージブレイク")

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

    # インターセプトでBPが変わった時は、その変化がイベントとして記録されることを確認する。
    def test_apply_intercept_action_records_bp_modified_event(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        attacker = UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        blocker = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [attacker]
        state.players["P2"].battlefield = [blocker]
        state.players["P1"].trigger_zone = ["1-0-074"]

        apply_intercept_action(
            state,
            "P1",
            {"kind": "use_intercept", "trigger_index": 0, "card_no": "1-0-074"},
            attacker,
            blocker,
            True,
        )

        bp_event = next(event for event in state.event_log if event["type"] == "unit_bp_modified")
        self.assertEqual(bp_event["source_card_no"], "1-0-074")
        self.assertEqual(bp_event["amount"], 2000)
        self.assertEqual(bp_event["metadata"]["target_card_no"], "1-0-001")
        self.assertEqual(bp_event["metadata"]["current_bp"], 5000)

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

    # 無色 intercept は同色ユニットが場にいなくても使用可能であることを確認する。
    def test_list_available_intercept_actions_allows_colorless_without_field_unit(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        attacker = UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        blocker = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = []
        state.players["P1"].current_cp = 1
        state.players["P1"].trigger_zone = ["1-0-065"]

        actions = list_available_intercept_actions(state, "P1", attacker, blocker, True)

        self.assertTrue(any(action["kind"] == "use_intercept" for action in actions))

    # blocker 選択肢には UI 表示に使える名前と BP 情報が含まれることを確認する。
    def test_list_available_block_actions_includes_choice_metadata(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-001", unit_id=1, level=2, exhausted=False, attack_restricted=False, current_damage=1000)
        ]

        actions = list_available_block_actions(state, "P1")
        block_action = next(action for action in actions if action["kind"] == "block")

        self.assertEqual(block_action["card_name"], "Red Unit 1")
        self.assertEqual(block_action["current_bp"], 3000)
        self.assertIn("choice_label", block_action)
        self.assertIn("choice_summary", block_action)
        self.assertEqual(block_action["choice_label_ja"], "Red Unit 1でブロック")
        self.assertIn("BP 3000", block_action["choice_summary_ja"])

    # exhausted ユニットしかいない場合、block choice payload に選べない理由が含まれることを確認する。
    def test_build_block_choice_payload_includes_unavailable_reason(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=True, attack_restricted=False)
        ]

        payload = build_block_choice_payload(state, "P1")

        self.assertEqual(payload["choice_kind"], "block")
        self.assertEqual(payload["available_choices"][0]["kind"], "no_block")
        self.assertEqual(payload["unavailable_choices"][0]["disabled_reason"], "unit_exhausted")
        self.assertEqual(
            payload["unavailable_choices"][0]["disabled_reason_message"],
            "行動済みユニットのため選べません。",
        )

    # intercept 選択肢には UI 表示に使えるカード名と説明が含まれることを確認する。
    def test_list_available_intercept_actions_includes_choice_metadata(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        attacker = UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        blocker = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [attacker]
        state.players["P1"].trigger_zone = ["1-0-074"]

        actions = list_available_intercept_actions(state, "P1", attacker, blocker, True)
        intercept_action = next(action for action in actions if action["kind"] == "use_intercept")

        self.assertEqual(intercept_action["card_name"], "Hero Sword")
        self.assertEqual(intercept_action["cost"], 0)
        self.assertIn("choice_label", intercept_action)
        self.assertIn("choice_summary", intercept_action)
        self.assertEqual(intercept_action["choice_label_ja"], "Hero Swordを使う")
        self.assertEqual(intercept_action["choice_summary_ja"], "CP 0 / 対象 自分ユニット")

    # intercept が使えない場合でも payload に選べない理由が含まれることを確認する。
    def test_build_intercept_choice_payload_includes_unavailable_reason(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        attacker = UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        blocker = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = []
        state.players["P1"].current_cp = 0
        state.players["P1"].trigger_zone = ["1-0-065", "1-0-081"]

        payload = build_intercept_choice_payload(state, "P1", attacker, blocker, True)

        self.assertEqual(payload["choice_kind"], "intercept")
        self.assertEqual(payload["available_choices"][0]["kind"], "no_intercept")
        self.assertEqual(len(payload["unavailable_choices"]), 2)
        self.assertEqual(payload["unavailable_choices"][0]["disabled_reason"], "not_enough_cp")
        self.assertEqual(payload["unavailable_choices"][1]["disabled_reason"], "color_requirement_not_met")
        self.assertEqual(
            payload["unavailable_choices"][0]["disabled_reason_message"],
            "CPが足りないため使えません。",
        )
        self.assertEqual(
            payload["unavailable_choices"][1]["disabled_reason_message"],
            "同属性ユニットが場にいないため使えません。",
        )

    # 対象選択を伴う能力では choice_request に choice_kind と表示用情報が含まれることを確認する。
    def test_targeted_ability_choice_request_includes_choice_metadata(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-004", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        )
        state.players["P2"].battlefield = [
            UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        ]
        captured_payloads: list[dict[str, object]] = []

        def choice_resolver(_player_id, payload):
            captured_payloads.append(payload)
            return {"kind": "choose_unit", "target_index": 0}

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            rng=random.Random(7),
            choice_resolver=choice_resolver,
        )

        self.assertEqual(captured_payloads[0]["choice_kind"], "target_unit")
        self.assertEqual(captured_payloads[0]["round_no"], 2)
        self.assertEqual(captured_payloads[0]["turn_serial"], 1)
        first_choice = captured_payloads[0]["available_choices"][0]
        self.assertEqual(first_choice["card_name"], "Blue Unit 1")
        self.assertIn("choice_label", first_choice)
        self.assertEqual(first_choice["choice_label_ja"], "Blue Unit 1を対象にする")

    # 手札コスト選択を伴う能力では choice_request に choice_kind と表示用情報が含まれることを確認する。
    def test_hand_discard_choice_request_includes_choice_metadata(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].hand = ["1-0-002", "1-0-003"]
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-010", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        )
        captured_payloads: list[dict[str, object]] = []

        def choice_resolver(_player_id, payload):
            captured_payloads.append(payload)
            return {"kind": "discard_hand", "hand_index": 1}

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            rng=random.Random(7),
            choice_resolver=choice_resolver,
        )

        self.assertEqual(captured_payloads[0]["choice_kind"], "discard_hand")
        self.assertEqual(captured_payloads[0]["round_no"], 2)
        self.assertEqual(captured_payloads[0]["turn_serial"], 1)
        first_choice = captured_payloads[0]["available_choices"][0]
        self.assertEqual(first_choice["card_name"], "Red Unit 2")
        self.assertIn("choice_label", first_choice)
        self.assertEqual(first_choice["choice_label_ja"], "Red Unit 2を捨てる")

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

    # overdrive では素材の捨札移動とオーバードライブイベントが記録されることを確認する。
    def test_apply_overdrive_action_records_events(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].current_cp = 2
        state.players["P1"].hand = ["1-0-101"]
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-001", unit_id=5, level=1, exhausted=True, attack_restricted=True, current_damage=2)
        ]

        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "overdrive")
        apply_action(state, "P1", action, random.Random(7))

        event_types = [event["type"] for event in state.event_log]
        self.assertIn("cp_changed", event_types)
        self.assertIn("unit_sent_to_discard", event_types)
        self.assertIn("unit_overdriven", event_types)
        self.assertNotIn("unit_level_changed", event_types)
        self.assertEqual(state.players["P1"].battlefield[0].current_damage, 0)
        self.assertEqual(state.players["P1"].discard_pile[0], "1-0-001")

    # overdrive でレベルが変わる時だけ unit_level_changed が記録されることを確認する。
    def test_apply_overdrive_action_records_level_change_only_when_changed(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.players["P1"].current_cp = 2
        state.players["P1"].hand = ["1-0-101@L3"]
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-001", unit_id=5, level=1, exhausted=True, attack_restricted=True, current_damage=2)
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

        level_event = next(event for event in state.event_log if event["type"] == "unit_level_changed")
        self.assertEqual(level_event["metadata"]["from_level"], 1)
        self.assertEqual(level_event["metadata"]["to_level"], 3)
        self.assertEqual(level_event["metadata"]["reason"], "overdrive")

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
        self.assertTrue(
            any(
                event["type"] == "life_changed"
                and event["target_player_id"] == "P2"
                and event["amount"] == -1
                for event in state.event_log
            )
        )
        self.assertTrue(
            any(
                event["type"] == "life_changed"
                and event["target_player_id"] == "P2"
                and event.get("metadata", {}).get("reason") == "player_attack"
                and event.get("metadata", {}).get("current_life") == 6
                for event in state.event_log
            )
        )

    # ライフが 0 以下になった時は、その場で勝敗が確定することを確認する。
    def test_apply_attack_action_ends_match_when_life_reaches_zero(self) -> None:
        state = self.create_state()
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P2"].life = 1
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-001", level=1, exhausted=False, attack_restricted=False)
        )

        apply_attack_action(state, "P1", {"kind": "attack", "attacker_index": 0, "target": "player"})

        self.assertEqual(state.players["P2"].life, 0)
        self.assertEqual(state.winner, "P1")
        self.assertEqual(state.ended_reason, "life_zero")
        self.assertTrue(
            any(
                event["type"] == "match_ended"
                and event.get("metadata", {}).get("winner") == "P1"
                and event.get("metadata", {}).get("reason") == "life_zero"
                and event.get("metadata", {}).get("final_life") == {"P1": 7, "P2": 0}
                for event in state.event_log
            )
        )

    def test_end_turn_decides_winner_by_life_at_round_limit(self) -> None:
        state = self.create_state()
        state.round_no = state.regulation.round_count
        state.turn_player_id = "P2"
        state.turn_serial = 20
        state.players["P1"].life = 5
        state.players["P2"].life = 3

        apply_action(state, "P2", {"kind": "end_turn"}, random.Random(7))

        self.assertEqual(state.round_no, state.regulation.round_count)
        self.assertEqual(state.winner, "P1")
        self.assertEqual(state.ended_reason, "round_limit")
        self.assertTrue(
            any(
                event["type"] == "match_ended"
                and event.get("metadata", {}).get("winner") == "P1"
                and event.get("metadata", {}).get("reason") == "round_limit"
                and event.get("metadata", {}).get("final_life") == {"P1": 5, "P2": 3}
                for event in state.event_log
            )
        )

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

    # 貫通を持つユニットは、ブロックされた戦闘に勝利した時だけ対戦相手のライフにダメージを与えることを確認する。
    def test_attack_action_with_pierce_deals_life_damage_only_on_battle_win(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-046"] = CardDefinition(
            card_no="1-0-046",
            category="unit",
            rarity="R",
            color="green",
            name="Pierce Unit",
            cp=2,
            bp_by_level=(4, 5, 6),
            abilities=(AbilityDefinition(name="貫通", text=""),),
            race="test",
        )
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-046", level=1, exhausted=False, attack_restricted=False)
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

        self.assertEqual(state.players["P2"].life, 6)

    # 貫通を持っていても、戦闘に勝利しなければライフダメージは与えないことを確認する。
    def test_attack_action_with_pierce_does_not_deal_life_damage_on_draw(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-046"] = CardDefinition(
            card_no="1-0-046",
            category="unit",
            rarity="R",
            color="green",
            name="Pierce Unit",
            cp=2,
            bp_by_level=(3, 4, 5),
            abilities=(AbilityDefinition(name="貫通", text=""),),
            race="test",
        )
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].battlefield.append(
            UnitState(card_no="1-0-046", level=1, exhausted=False, attack_restricted=False)
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

        self.assertEqual(state.players["P2"].life, 7)

    # 不屈を持つユニットはターン終了時に行動権が回復することを確認する。
    def test_turn_end_recovers_exhausted_unit_with_untiring(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-021"] = CardDefinition(
            card_no="1-0-021",
            category="unit",
            rarity="R",
            color="yellow",
            name="Untiring Unit",
            cp=2,
            bp_by_level=(4, 5, 6),
            abilities=(AbilityDefinition(name="不屈", text=""),),
            race="test",
        )
        state.turn_player_id = "P1"
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-021", unit_id=1, level=1, exhausted=True, attack_restricted=False)
        ]

        apply_action(state, "P1", {"kind": "end_turn"}, random.Random(7))

        self.assertFalse(state.players["P1"].battlefield[0].exhausted)
        ability_triggered_events = [event for event in state.event_log if event["type"] == "ability_triggered"]
        self.assertEqual(len(ability_triggered_events), 1)
        action_recovered_event = next(event for event in state.event_log if event["type"] == "unit_action_recovered")
        self.assertEqual(action_recovered_event["player_id"], "P1")
        self.assertEqual(action_recovered_event["source_card_no"], "1-0-021")
        self.assertEqual(action_recovered_event["metadata"]["reason"], "untiring")

    # 不屈は相手ターン終了時には発動せず、能力発動イベントも記録されないことを確認する。
    def test_untiring_does_not_trigger_on_opponent_turn_end(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-021"] = CardDefinition(
            card_no="1-0-021",
            category="unit",
            rarity="R",
            color="red",
            name="Untiring Unit",
            cp=2,
            bp_by_level=(4, 5, 6),
            abilities=(AbilityDefinition(name="不屈", text=""),),
            race="test",
        )
        state.turn_player_id = "P2"
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-021", unit_id=1, level=1, exhausted=True, attack_restricted=False)
        ]

        resolve_ability_events(
            state,
            [AbilityEvent(type="turn_end", player_id="P2")],
            random.Random(7),
        )

        self.assertTrue(state.players["P1"].battlefield[0].exhausted)
        self.assertEqual([event for event in state.event_log if event["type"] == "ability_triggered"], [])
        self.assertEqual([event for event in state.event_log if event["type"] == "unit_action_recovered"], [])

    # 不屈が別契機を宣言している場合、turn_end では候補収集されないことを確認する。
    def test_untiring_respects_declared_event_type(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-021"] = CardDefinition(
            card_no="1-0-021",
            category="unit",
            rarity="R",
            color="yellow",
            name="Untiring Unit",
            cp=2,
            bp_by_level=(4, 5, 6),
            abilities=(AbilityDefinition(name="不屈", text="", raw={"event_type": "opponent_turn_end"}),),
            race="test",
        )
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-021", unit_id=1, level=1, exhausted=True, attack_restricted=False)
        ]

        resolve_ability_events(
            state,
            [AbilityEvent(type="turn_end", player_id="P1")],
            random.Random(7),
        )

        self.assertTrue(state.players["P1"].battlefield[0].exhausted)
        self.assertEqual([event for event in state.event_log if event["type"] == "ability_triggered"], [])
        self.assertEqual([event for event in state.event_log if event["type"] == "unit_action_recovered"], [])

    def test_start_turn_recovers_exhausted_unit_and_records_event(self) -> None:
        state = self.create_state()
        state.round_no = 2
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-021", unit_id=1, level=1, exhausted=True, attack_restricted=True)
        ]

        start_turn(state, "P1", random.Random(7))

        unit = state.players["P1"].battlefield[0]
        self.assertFalse(unit.exhausted)
        self.assertFalse(unit.attack_restricted)
        action_recovered_event = next(event for event in state.event_log if event["type"] == "unit_action_recovered")
        self.assertEqual(action_recovered_event["player_id"], "P1")
        self.assertEqual(action_recovered_event["source_card_no"], "1-0-021")
        self.assertEqual(action_recovered_event["metadata"]["reason"], "turn_start_recover")

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

    # 戦闘では宣言、ダメージ、勝敗、捨札送り、クロックアップがイベント列に記録されることを確認する。
    def test_battle_records_combat_events(self) -> None:
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
            UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        )
        state.players["P2"].battlefield.append(
            UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        )

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            {"kind": "block", "blocker_index": 0},
            random.Random(7),
        )

        event_types = [event["type"] for event in state.event_log]
        self.assertIn("attack_declared", event_types)
        self.assertIn("block_declared", event_types)
        self.assertIn("battle_bp_changed", event_types)
        self.assertIn("battle_resolved", event_types)
        self.assertIn("unit_sent_to_discard", event_types)
        self.assertIn("unit_clock_up", event_types)

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

    # OC時のリバイブは捨札から選んだカードを手札に戻せることを確認する。
    def test_overclock_revive_returns_selected_discard_card(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-031"] = CardDefinition(
            card_no="1-0-031",
            category="unit",
            rarity="C",
            color="blue",
            name="Revive OC Unit",
            cp=1,
            bp_by_level=(3, 4, 5),
            abilities=(AbilityDefinition(name="リバイブ", text=""),),
            race="test",
        )
        state.card_catalog["2-0-900"] = CardDefinition(
            card_no="2-0-900",
            category="unit",
            rarity="C",
            color="red",
            name="Weak Enemy",
            cp=1,
            bp_by_level=(1, 1, 1),
            abilities=(),
            race="test",
        )
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-031", unit_id=1, level=2, exhausted=False, attack_restricted=False)
        ]
        state.players["P1"].discard_pile = ["1-0-002", "1-0-003"]
        state.players["P2"].battlefield = [
            UnitState(card_no="2-0-900", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        ]

        def choice_resolver(_player_id, payload):
            return {"kind": "choose_discard", "discard_index": 1}

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            {"kind": "block", "blocker_index": 0},
            random.Random(7),
            choice_resolver,
        )

        self.assertIn("1-0-003", state.players["P1"].hand)
        moved_event = next(
            event
            for event in state.event_log
            if event["type"] == "card_moved" and event["source_card_no"] == "1-0-003"
        )
        self.assertEqual(moved_event["metadata"]["from_zone"], "discard")
        self.assertEqual(moved_event["metadata"]["to_zone"], "hand")
        self.assertEqual(moved_event["metadata"]["reason"], "revive")

    # 登場時リバイブは自分の捨札のユニットをランダムで手札へ戻すことを確認する。
    def test_revive_unit_enter_returns_random_unit_from_discard(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-033"] = CardDefinition(
            card_no="1-0-033",
            category="unit",
            rarity="C",
            color="blue",
            name="Revive Enter Unit",
            cp=3,
            bp_by_level=(5, 6, 7),
            abilities=(AbilityDefinition(name="リバイブ", text=""),),
            race="test",
        )
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].hand = ["1-0-033"]
        state.players["P1"].discard_pile = ["1-0-002", "1-0-061"]
        state.players["P1"].current_cp = 3

        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "drive")
        apply_action(state, "P1", action, random.Random(7))

        self.assertIn("1-0-002", state.players["P1"].hand)

    # ハデス登場時は相手のLv.2以上ユニットをすべて破壊することを確認する。
    def test_hades_enter_destroys_all_enemy_level_two_or_higher(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-031"] = CardDefinition(
            card_no="1-0-031",
            category="unit",
            rarity="C",
            color="blue",
            name="Blue Support Unit",
            cp=1,
            bp_by_level=(3, 4, 5),
            abilities=(),
            race="test",
        )
        state.card_catalog["1-0-039"] = CardDefinition(
            card_no="1-0-039",
            category="evolution",
            rarity="R",
            color="blue",
            name="Hades",
            cp=4,
            bp_by_level=(6, 7, 8),
            abilities=(AbilityDefinition(name="血塗られし報復", text=""),),
            race="test",
        )
        state.card_catalog["1-0-027"] = CardDefinition(
            card_no="1-0-027",
            category="unit",
            rarity="C",
            color="blue",
            name="Lost Unit",
            cp=1,
            bp_by_level=(1, 2, 3),
            abilities=(AbilityDefinition(name="ロスト", text=""),),
            race="test",
        )
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].hand = ["1-0-039"]
        state.players["P1"].current_cp = 4
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-031", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P2"].battlefield = [
            UnitState(card_no="2-0-002", unit_id=2, level=1, exhausted=False, attack_restricted=False),
            UnitState(card_no="1-0-027", unit_id=3, level=2, exhausted=False, attack_restricted=False),
            UnitState(card_no="2-0-004", unit_id=4, level=3, exhausted=False, attack_restricted=False),
        ]
        state.players["P1"].hand = ["1-0-039"]
        action = {
            "kind": "overdrive",
            "hand_index": 0,
            "card_no": "1-0-039",
            "target_index": 0,
            "cost": 4,
            "trigger_reducer_index": None,
            "card_level": 1,
        }

        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(len(state.players["P2"].battlefield), 1)
        self.assertEqual(state.players["P2"].battlefield[0].card_no, "2-0-002")
        self.assertEqual(len(state.players["P1"].hand), 0)

    # グラインドビートルはチャージでCP+2し、先に緑2CP以上を使っていれば1ドローすることを確認する。
    def test_grind_beetle_enter_adds_cp_and_draws_if_prior_green_cost_two_plus_was_used(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-043"] = CardDefinition(
            card_no="1-0-043",
            category="unit",
            rarity="R",
            color="red",
            name="Grind Beetle",
            cp=3,
            bp_by_level=(5, 6, 7),
            abilities=(
                AbilityDefinition(name="チャージ", text=""),
                AbilityDefinition(name="連撃・グラインドドロー", text=""),
            ),
            race="test",
        )
        state.card_catalog["1-0-200"] = CardDefinition(
            card_no="1-0-200",
            category="unit",
            rarity="C",
            color="green",
            name="Big Green",
            cp=2,
            bp_by_level=(4, 5, 6),
            abilities=(),
            race="test",
        )
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.used_card_nos_this_turn = ["1-0-200"]
        state.players["P1"].hand = ["1-0-043"]
        state.players["P1"].draw_pile = ["1-0-002"] + state.players["P1"].draw_pile
        state.players["P1"].current_cp = 3

        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "drive")
        apply_action(state, "P1", action, random.Random(7))

        self.assertEqual(state.players["P1"].current_cp, 2)
        self.assertIn("1-0-002", state.players["P1"].hand)

    # ユニット登場時はターンプレイヤーのユニット効果が先に解決され、その後トリガー効果が解決されることを確認する。
    def test_unit_enter_priority_resolves_grind_beetle_before_trigger(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-043"] = CardDefinition(
            card_no="1-0-043",
            category="unit",
            rarity="R",
            color="green",
            name="Grind Beetle",
            cp=3,
            bp_by_level=(5, 6, 7),
            abilities=(
                AbilityDefinition(name="チャージ", text=""),
                AbilityDefinition(name="連撃・グラインドドロー", text=""),
            ),
            race="test",
        )
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.used_card_nos_this_turn = []
        state.players["P1"].current_cp = 3
        state.players["P1"].hand = ["1-0-043"]
        state.players["P1"].trigger_zone = ["1-0-061"]
        state.players["P1"].draw_pile = ["1-0-074", "1-0-074", "1-0-002"] + state.players["P1"].draw_pile

        action = next(action for action in list_available_actions(state, "P1") if action["kind"] == "drive")
        apply_action(state, "P1", action, random.Random(7))

        cp_index = next(
            index
            for index, event in enumerate(state.event_log)
            if event["type"] == "cp_changed" and event["source_card_no"] == "1-0-043" and event["amount"] == 2
        )
        trigger_index = next(
            index
            for index, event in enumerate(state.event_log)
            if event["type"] == "cards_drawn" and event["source_card_no"] == "1-0-061"
        )
        self.assertLess(cp_index, trigger_index)

    # ブロッカーを持つユニットはブロック時にBP+2000され、相討ちを耐えることを確認する。
    def test_blocker_bonus_applies_before_combat_damage(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-045"] = CardDefinition(
            card_no="1-0-045",
            category="unit",
            rarity="R",
            color="green",
            name="Leafia",
            cp=3,
            bp_by_level=(6, 7, 8),
            abilities=(AbilityDefinition(name="ブロッカー", text=""),),
            race="test",
        )
        state.card_catalog["1-0-300"] = CardDefinition(
            card_no="1-0-300",
            category="unit",
            rarity="C",
            color="red",
            name="Six Power Attacker",
            cp=1,
            bp_by_level=(6, 6, 6),
            abilities=(),
            race="test",
        )
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-300", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P2"].battlefield = [
            UnitState(card_no="1-0-045", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        ]

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            {"kind": "block", "blocker_index": 0},
            random.Random(7),
        )

        self.assertEqual(len(state.players["P2"].battlefield), 1)

    # 戦闘勝利時のトリガーが battle_won 契機で発動し、CP が増えることを確認する。
    def test_battle_won_trigger_gains_cp(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-060"] = CardDefinition(
            card_no="1-0-060",
            category="trigger",
            rarity="R",
            color="green",
            name="Advance Energy",
            cp=None,
            bp_by_level=(),
            abilities=(AbilityDefinition(name="アドバンスエネルギー", text=""),),
            race="test",
        )
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        attacker = UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        blocker = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False, current_damage=1000)
        state.players["P1"].battlefield = [attacker]
        state.players["P2"].battlefield = [blocker]
        state.players["P1"].trigger_zone = ["1-0-060"]
        state.players["P1"].current_cp = 2

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            {"kind": "block", "blocker_index": 0},
            random.Random(7),
        )

        self.assertEqual(state.players["P1"].current_cp, 4)
        self.assertEqual(state.players["P1"].trigger_zone, [])
        self.assertTrue(any(event["type"] == "battle_won" for event in state.event_log))
        self.assertTrue(any(event["type"] == "cp_changed" and event["source_card_no"] == "1-0-060" for event in state.event_log))

    # ベヒーモスドラゴンのアタック時効果が自分の捨札枚数×500ぶんのBP上昇を与えることを確認する。
    def test_attack_trigger_uses_discard_count_for_temp_bp(self) -> None:
        state = self.create_state()
        source = UnitState(card_no="1-0-011", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [source]
        state.players["P1"].discard_pile = ["1-0-001", "1-0-002", "1-0-003"]

        resolve_ability_events(
            state,
            [AbilityEvent(type="unit_attacked", player_id="P1", source_unit_id=source.unit_id, source_card_no=source.card_no)],
            random.Random(7),
        )

        self.assertEqual(source.temporary_bp_modifier, 1500)

    # 疑惑のロシアンルーレットがアタック後にランダムなBP上昇を与えることを確認する。
    def test_attack_trigger_grants_random_temp_bp(self) -> None:
        state = self.create_state()
        source = UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [source]
        state.players["P1"].trigger_zone = ["1-0-059"]
        state.card_catalog["1-0-059"] = CardDefinition(
            card_no="1-0-059",
            category="trigger",
            rarity="R",
            color="none",
            name="Russian Roulette",
            cp=None,
            bp_by_level=(),
            abilities=(),
            race="test",
        )

        resolve_ability_events(
            state,
            [AbilityEvent(type="unit_attacked", player_id="P1", source_unit_id=source.unit_id, source_card_no=source.card_no)],
            random.Random(7),
        )

        self.assertIn(source.temporary_bp_modifier, {1000, 3000, 4000})
        self.assertEqual(state.players["P1"].trigger_zone, [])

    # サイボーグ僧兵のブロック時効果が戦闘開始時に発動してBPを上げることを確認する。
    def test_cyborg_soldier_block_bonus_applies_on_battle_started(self) -> None:
        state = self.create_state()
        blocker = UnitState(card_no="1-0-015", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        attacker = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [blocker]
        state.players["P2"].battlefield = [attacker]

        resolve_ability_events(
            state,
            [
                AbilityEvent(
                    type="battle_started",
                    player_id="P2",
                    source_unit_id=attacker.unit_id,
                    target_player_id="P1",
                    metadata={"blocker_player_id": "P1", "blocker_unit_id": blocker.unit_id},
                )
            ],
            random.Random(7),
        )

        self.assertEqual(blocker.temporary_bp_modifier, 2000)

    # 湖畔のアリエの登場時効果が相手ユニットを行動済みにすることを確認する。
    def test_enter_ability_can_exhaust_enemy_unit(self) -> None:
        state = self.create_state()
        source = UnitState(card_no="1-0-017", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        enemy = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [source]
        state.players["P2"].battlefield = [enemy]

        resolve_ability_events(
            state,
            [AbilityEvent(type="unit_entered", player_id="P1", source_unit_id=source.unit_id, source_card_no=source.card_no)],
            random.Random(7),
        )

        self.assertTrue(enemy.exhausted)

    # ジャンプーの登場時効果が相手ユニットを手札に戻すことを確認する。
    def test_enter_ability_can_return_enemy_unit_to_hand(self) -> None:
        state = self.create_state()
        source = UnitState(card_no="1-0-019", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        enemy = UnitState(card_no="2-0-001", unit_id=2, level=2, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [source]
        state.players["P2"].battlefield = [enemy]

        resolve_ability_events(
            state,
            [AbilityEvent(type="unit_entered", player_id="P1", source_unit_id=source.unit_id, source_card_no=source.card_no)],
            random.Random(7),
        )

        self.assertEqual(state.players["P2"].battlefield, [])
        self.assertIn("2-0-001", state.players["P2"].hand)

    # ラグエルの登場時効果が相手の行動済みユニット全てにダメージを与えることを確認する。
    def test_enter_ability_damages_all_exhausted_enemy_units(self) -> None:
        state = self.create_state()
        source = UnitState(card_no="1-0-023", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        exhausted_enemy = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=True, attack_restricted=False)
        ready_enemy = UnitState(card_no="2-0-002", unit_id=3, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [source]
        state.players["P2"].battlefield = [exhausted_enemy, ready_enemy]

        resolve_ability_events(
            state,
            [AbilityEvent(type="unit_entered", player_id="P1", source_unit_id=source.unit_id, source_card_no=source.card_no)],
            random.Random(7),
        )

        self.assertEqual(exhausted_enemy.current_damage, 3000)
        self.assertEqual(ready_enemy.current_damage, 0)

    # 戦神・毘沙門の登場時効果が自分以外の全ユニットを破壊することを確認する。
    def test_enter_ability_destroys_all_other_units(self) -> None:
        state = self.create_state()
        source = UnitState(card_no="1-0-026", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ally = UnitState(card_no="1-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        enemy = UnitState(card_no="2-0-001", unit_id=3, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [source, ally]
        state.players["P2"].battlefield = [enemy]

        resolve_ability_events(
            state,
            [AbilityEvent(type="unit_entered", player_id="P1", source_unit_id=source.unit_id, source_card_no=source.card_no)],
            random.Random(7),
        )

        self.assertEqual([unit.unit_id for unit in state.players["P1"].battlefield], [source.unit_id])
        self.assertEqual(state.players["P2"].battlefield, [])

    # 中忍月影のプレイヤーアタック成功時効果が相手手札を1枚ランダムで捨てることを確認する。
    def test_player_attack_success_can_random_discard_opponent_hand(self) -> None:
        state = self.create_state()
        source = UnitState(card_no="1-0-032", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [source]
        state.players["P2"].hand = ["2-0-001", "2-0-002"]

        resolve_ability_events(
            state,
            [AbilityEvent(type="player_attack_success", player_id="P1", source_unit_id=source.unit_id, source_card_no=source.card_no)],
            random.Random(7),
        )

        self.assertEqual(len(state.players["P2"].hand), 1)
        self.assertEqual(len(state.players["P2"].discard_pile), 1)

    # メガジョーの登場時効果が4色条件を満たす時だけ基本BPを上げることを確認する。
    def test_enter_ability_checks_all_four_colors(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-038"] = CardDefinition(
            card_no="1-0-038",
            category="unit",
            rarity="C",
            color="green",
            name="Mega Jaw",
            cp=3,
            bp_by_level=(6, 7, 8),
            abilities=(),
            race="test",
        )
        state.card_catalog["1-0-015"] = CardDefinition(
            card_no="1-0-015",
            category="unit",
            rarity="C",
            color="yellow",
            name="Yellow Helper",
            cp=1,
            bp_by_level=(3, 4, 5),
            abilities=(),
            race="test",
        )
        state.card_catalog["1-0-032"] = CardDefinition(
            card_no="1-0-032",
            category="unit",
            rarity="C",
            color="blue",
            name="Blue Helper",
            cp=2,
            bp_by_level=(3, 4, 5),
            abilities=(),
            race="test",
        )
        state.card_catalog["1-0-041"] = CardDefinition(
            card_no="1-0-041",
            category="unit",
            rarity="C",
            color="green",
            name="Green Helper",
            cp=1,
            bp_by_level=(3, 4, 5),
            abilities=(),
            race="test",
        )
        source = UnitState(card_no="1-0-038", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        red = UnitState(card_no="1-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        yellow = UnitState(card_no="1-0-015", unit_id=3, level=1, exhausted=False, attack_restricted=False)
        blue = UnitState(card_no="1-0-032", unit_id=4, level=1, exhausted=False, attack_restricted=False)
        green = UnitState(card_no="1-0-041", unit_id=5, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [source, red, yellow, blue, green]

        resolve_ability_events(
            state,
            [AbilityEvent(type="unit_entered", player_id="P1", source_unit_id=source.unit_id, source_card_no=source.card_no)],
            random.Random(7),
        )

        self.assertEqual(source.permanent_bp_modifier, 4000)

    # ケロール・キッドのOC効果が相手ユニットの基本BPを下げることを確認する。
    def test_overclock_ability_reduces_enemy_basic_bp(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-042"] = CardDefinition(
            card_no="1-0-042",
            category="unit",
            rarity="C",
            color="green",
            name="Kerole Kid",
            cp=1,
            bp_by_level=(3, 4, 5),
            abilities=(),
            race="test",
        )
        source = UnitState(card_no="1-0-042", unit_id=1, level=3, exhausted=False, attack_restricted=False)
        enemy = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [source]
        state.players["P2"].battlefield = [enemy]

        resolve_ability_events(
            state,
            [AbilityEvent(type="unit_overclocked", player_id="P1", source_unit_id=source.unit_id, source_card_no=source.card_no)],
            random.Random(7),
        )

        self.assertEqual(enemy.permanent_bp_modifier, -3000)

    # ブロックされないユニットはブロック宣言を受けてもプレイヤーアタックになることを確認する。
    def test_unblockable_unit_ignores_block_action(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-008"] = CardDefinition(
            card_no="1-0-008",
            category="unit",
            rarity="R",
            color="red",
            name="Valkyrie Clara",
            cp=3,
            bp_by_level=(3, 4, 5),
            abilities=(AbilityDefinition(name="聖女の加護", text="このユニットはブロックされない。"),),
            race="test",
        )
        attacker = UnitState(card_no="1-0-008", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        blocker = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [attacker]
        state.players["P2"].battlefield = [blocker]
        state.round_no = 2

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0},
            {"kind": "block", "blocker_index": 0},
            random.Random(7),
        )

        self.assertEqual(state.players["P2"].life, 6)
        self.assertEqual(blocker.current_damage, 0)

    # 対戦相手のアタック時インターセプトが opponent_unit_attacked 契機で行動権を回復することを確認する。
    def test_opponent_unit_attacked_intercept_recovers_friendly_actions(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-100"] = CardDefinition(
            card_no="1-0-100",
            category="intercept",
            rarity="R",
            color="red",
            name="Great Tornado of Reversal",
            cp=0,
            bp_by_level=(),
            abilities=(AbilityDefinition(name="逆転の大竜巻", text="", raw={"event_type": "opponent_unit_attacked"}),),
            race="test",
        )
        exhausted_unit = UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=True, attack_restricted=False)
        enemy_attacker = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [exhausted_unit]
        state.players["P1"].trigger_zone = ["1-0-100"]
        state.players["P2"].battlefield = [enemy_attacker]

        event = AbilityEvent(type="unit_attacked", player_id="P2", source_unit_id=enemy_attacker.unit_id, target_player_id="P1")
        payload = build_reactive_intercept_choice_payload(state, "P1", event)
        chosen = next(choice for choice in payload["available_choices"] if choice["kind"] == "use_intercept")
        apply_reactive_intercept_action(
            state,
            "P1",
            chosen,
            event,
            random.Random(7),
        )

        self.assertFalse(exhausted_unit.exhausted)
        self.assertEqual(state.players["P1"].trigger_zone, [])
        self.assertTrue(any(event["type"] == "unit_action_recovered" and event["source_card_no"] == "1-0-100" for event in state.event_log))

    # 登場時インターセプトが unit_entered 契機で発動し、ダメージと捨札移動を行うことを確認する。
    def test_field_enter_intercept_deals_damage(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-077"] = CardDefinition(
            card_no="1-0-077",
            category="intercept",
            rarity="R",
            color="red",
            name="Armor Break",
            cp=0,
            bp_by_level=(),
            abilities=(AbilityDefinition(name="アーマーブレイク", text="", raw={"event_type": "unit_entered"}),),
            race="test",
        )
        source = UnitState(card_no="1-0-001", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        target = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        state.players["P1"].battlefield = [source]
        state.players["P1"].trigger_zone = ["1-0-077"]
        state.players["P2"].battlefield = [target]

        event = AbilityEvent(type="unit_entered", player_id="P1", source_unit_id=source.unit_id, target_player_id="P2")
        payload = build_reactive_intercept_choice_payload(state, "P1", event)
        chosen = next(choice for choice in payload["available_choices"] if choice["kind"] == "use_intercept")
        apply_reactive_intercept_action(
            state,
            "P1",
            chosen,
            event,
            random.Random(7),
        )

        self.assertEqual(target.current_damage, 3000)
        self.assertEqual(state.players["P1"].trigger_zone, [])
        self.assertTrue(any(event["type"] == "ability_damage_dealt_to_unit" and event["source_card_no"] == "1-0-077" for event in state.event_log))

    # 破壊時誘発によりロストで相手手札を捨てさせ、インターセプトドローで1枚引くことを確認する。
    def test_unit_destroyed_abilities_can_discard_opponent_and_draw_intercept(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-027"] = CardDefinition(
            card_no="1-0-027",
            category="unit",
            rarity="C",
            color="blue",
            name="Lost Unit",
            cp=1,
            bp_by_level=(1, 2, 3),
            abilities=(AbilityDefinition(name="ロスト", text=""),),
            race="test",
        )
        state.card_catalog["1-0-029"] = CardDefinition(
            card_no="1-0-029",
            category="unit",
            rarity="C",
            color="blue",
            name="Intercept Draw Unit",
            cp=1,
            bp_by_level=(1, 2, 3),
            abilities=(AbilityDefinition(name="インターセプトドロー", text=""),),
            race="test",
        )
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-027", unit_id=1, level=1, exhausted=False, attack_restricted=False),
            UnitState(card_no="1-0-029", unit_id=2, level=1, exhausted=False, attack_restricted=False),
        ]
        state.players["P1"].draw_pile = ["1-0-061"] + state.players["P1"].draw_pile
        state.players["P2"].hand = ["2-0-001", "2-0-002"]
        state.players["P1"].battlefield[0].current_damage = 1000
        state.players["P1"].battlefield[1].current_damage = 1000

        from tojs.game import _destroy_broken_units

        _destroy_broken_units(state, "P1", random.Random(7), None)

        self.assertEqual(len(state.players["P2"].hand), 1)
        self.assertIn("1-0-061", state.players["P1"].hand)

    # 相打ちで双方の破壊時効果が同時に誘発した場合、ターンプレイヤー側の破壊時効果から先に解決されることを確認する。
    def test_simultaneous_destroyed_effects_resolve_turn_player_first(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-027"] = CardDefinition(
            card_no="1-0-027",
            category="unit",
            rarity="C",
            color="blue",
            name="Lost Unit",
            cp=1,
            bp_by_level=(1, 1, 1),
            abilities=(AbilityDefinition(name="ロスト", text=""),),
            race="test",
        )
        state.card_catalog["1-0-029"] = CardDefinition(
            card_no="1-0-029",
            category="unit",
            rarity="C",
            color="blue",
            name="Intercept Draw Unit",
            cp=1,
            bp_by_level=(1, 1, 1),
            abilities=(AbilityDefinition(name="インターセプトドロー", text=""),),
            race="test",
        )
        start_turn(state, "P1", random.Random(7))
        state.round_no = 2
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-027", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P2"].battlefield = [
            UnitState(card_no="1-0-029", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P2"].hand = ["2-0-001"]
        state.players["P2"].draw_pile = ["1-0-061", "2-0-002", "2-0-003"]

        apply_attack_action(
            state,
            "P1",
            {"kind": "attack", "attacker_index": 0, "target": "player"},
            {"kind": "block", "blocker_index": 0},
            random.Random(7),
        )

        relevant_events = [
            (event["type"], event.get("source_card_no"), event.get("player_id"))
            for event in state.event_log
            if event["type"] in {"unit_destroyed", "cards_drawn"}
        ]
        p1_destroy_index = relevant_events.index(("unit_destroyed", "1-0-027", "P1"))
        p2_destroy_index = relevant_events.index(("unit_destroyed", "1-0-029", "P2"))
        p2_draw_index = relevant_events.index(("cards_drawn", "1-0-029", "P2"))
        self.assertLess(p1_destroy_index, p2_destroy_index)
        self.assertLess(p2_destroy_index, p2_draw_index)

    # 絶妙な挑発は相手ユニットのレベルを3にするが、OCによる回復は発生しないことを確認する。
    def test_reactive_intercept_on_unit_entered_can_set_enemy_level_to_three(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-069"] = CardDefinition(
            card_no="1-0-069",
            category="intercept",
            rarity="R",
            color="none",
            name="Taunt",
            cp=0,
            bp_by_level=(),
            abilities=(AbilityDefinition(name="絶妙な挑発", text=""),),
            race="test",
        )
        state.players["P1"].trigger_zone = ["1-0-069"]
        state.players["P2"].battlefield = [
            UnitState(card_no="2-0-001", unit_id=1, level=1, exhausted=True, attack_restricted=True)
        ]

        enter_event = AbilityEvent(type="unit_entered", player_id="P2", source_unit_id=1)
        payload = build_reactive_intercept_choice_payload(state, "P1", enter_event)
        action = next(choice for choice in payload["available_choices"] if choice.get("kind") == "use_intercept")
        apply_reactive_intercept_action(state, "P1", action, enter_event)

        self.assertEqual(state.players["P2"].battlefield[0].level, 3)
        self.assertTrue(state.players["P2"].battlefield[0].exhausted)
        self.assertTrue(state.players["P2"].battlefield[0].attack_restricted)
        level_event = next(event for event in state.event_log if event["type"] == "unit_level_changed")
        self.assertEqual(level_event["player_id"], "P2")
        self.assertEqual(level_event["metadata"]["from_level"], 1)
        self.assertEqual(level_event["metadata"]["to_level"], 3)
        self.assertEqual(level_event["metadata"]["reason"], "effect")

    # ムーンセイヴァーは攻撃時にLv.2以上の相手ユニットを破壊できることを確認する。
    def test_reactive_intercept_on_unit_attacked_can_destroy_level_two_or_higher_unit(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-031"] = CardDefinition(
            card_no="1-0-031",
            category="unit",
            rarity="C",
            color="blue",
            name="Blue Support Unit",
            cp=1,
            bp_by_level=(3, 4, 5),
            abilities=(),
            race="test",
        )
        state.card_catalog["1-0-089"] = CardDefinition(
            card_no="1-0-089",
            category="intercept",
            rarity="R",
            color="blue",
            name="Moon Saver",
            cp=1,
            bp_by_level=(),
            abilities=(AbilityDefinition(name="ムーンセイヴァー", text=""),),
            race="test",
        )
        state.players["P1"].trigger_zone = ["1-0-089"]
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-031", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P1"].current_cp = 1
        state.players["P2"].battlefield = [
            UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False),
            UnitState(card_no="2-0-002", unit_id=3, level=2, exhausted=False, attack_restricted=False),
        ]

        payload = build_reactive_intercept_choice_payload(state, "P1", "unit_attacked")
        action = next(choice for choice in payload["available_choices"] if choice.get("kind") == "use_intercept")
        apply_reactive_intercept_action(state, "P1", action, "unit_attacked")

        self.assertEqual(len(state.players["P2"].battlefield), 1)
        self.assertEqual(state.players["P2"].battlefield[0].level, 1)
        cp_event = next(event for event in state.event_log if event["type"] == "cp_changed")
        self.assertEqual(cp_event["metadata"]["reason"], "reactive_intercept_use")
        self.assertEqual(cp_event["metadata"]["before_cp"], 1)
        self.assertEqual(cp_event["metadata"]["after_cp"], 0)

    # ムーンセイヴァーは自分が攻撃した時だけ使え、相手の攻撃では使えないことを確認する。
    def test_reactive_intercept_moon_saver_is_attacker_only(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-089"] = CardDefinition(
            card_no="1-0-089",
            category="intercept",
            rarity="R",
            color="blue",
            name="Moon Saver",
            cp=1,
            bp_by_level=(),
            abilities=(AbilityDefinition(name="ムーンセイヴァー", text=""),),
            race="test",
        )
        state.players["P1"].trigger_zone = ["1-0-089"]
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-031", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P1"].current_cp = 1
        state.players["P2"].battlefield = [
            UnitState(card_no="2-0-002", unit_id=3, level=2, exhausted=False, attack_restricted=False)
        ]

        payload = build_reactive_intercept_choice_payload(
            state,
            "P1",
            AbilityEvent(type="unit_attacked", player_id="P2", source_unit_id=3, target_player_id="P1"),
        )

        self.assertEqual(payload["available_choices"][0]["kind"], "no_intercept")
        self.assertEqual(payload["unavailable_choices"], [])

    # ダーク・アーマーは自ユニットにBP+7000し、自分のライフを1減らすことを確認する。
    def test_battle_intercept_dark_armor_adds_bp_and_costs_life(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-031"] = CardDefinition(
            card_no="1-0-031",
            category="unit",
            rarity="C",
            color="blue",
            name="Blue Support Unit",
            cp=1,
            bp_by_level=(3, 4, 5),
            abilities=(),
            race="test",
        )
        state.card_catalog["1-0-091"] = CardDefinition(
            card_no="1-0-091",
            category="intercept",
            rarity="R",
            color="blue",
            name="Dark Armor",
            cp=1,
            bp_by_level=(),
            abilities=(AbilityDefinition(name="ダーク・アーマー", text=""),),
            race="test",
        )
        state.players["P1"].trigger_zone = ["1-0-091"]
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-031", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P1"].current_cp = 1
        own_unit = state.players["P1"].battlefield[0]
        enemy_unit = UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)

        apply_intercept_action(
            state,
            "P1",
            {"kind": "use_intercept", "trigger_index": 0, "card_no": "1-0-091"},
            own_unit,
            enemy_unit,
            True,
        )

        self.assertEqual(own_unit.temporary_bp_modifier, 7000)
        self.assertEqual(state.players["P1"].life, 6)
        cp_event = next(event for event in state.event_log if event["type"] == "cp_changed")
        self.assertEqual(cp_event["metadata"]["reason"], "intercept_use")
        self.assertEqual(cp_event["metadata"]["before_cp"], 1)
        self.assertEqual(cp_event["metadata"]["after_cp"], 0)
        bp_index = next(index for index, event in enumerate(state.event_log) if event["type"] == "unit_bp_modified")
        life_index = next(
            index
            for index, event in enumerate(state.event_log)
            if event["type"] == "life_changed" and event["source_card_no"] == "1-0-091"
        )
        self.assertLess(bp_index, life_index)

    # エクトプラズムは自分のユニット破壊時に相手ユニットを破壊できることを確認する。
    def test_reactive_intercept_on_unit_destroyed_can_destroy_enemy_unit(self) -> None:
        state = self.create_state()
        state.card_catalog["1-0-031"] = CardDefinition(
            card_no="1-0-031",
            category="unit",
            rarity="C",
            color="blue",
            name="Blue Support Unit",
            cp=1,
            bp_by_level=(3, 4, 5),
            abilities=(),
            race="test",
        )
        state.card_catalog["1-0-092"] = CardDefinition(
            card_no="1-0-092",
            category="intercept",
            rarity="R",
            color="blue",
            name="Ectoplasm",
            cp=3,
            bp_by_level=(),
            abilities=(AbilityDefinition(name="エクトプラズム", text=""),),
            race="test",
        )
        state.players["P1"].trigger_zone = ["1-0-092"]
        state.players["P1"].battlefield = [
            UnitState(card_no="1-0-031", unit_id=1, level=1, exhausted=False, attack_restricted=False)
        ]
        state.players["P1"].current_cp = 3
        state.players["P2"].battlefield = [
            UnitState(card_no="2-0-001", unit_id=2, level=1, exhausted=False, attack_restricted=False)
        ]

        payload = build_reactive_intercept_choice_payload(state, "P1", "unit_destroyed")
        action = next(choice for choice in payload["available_choices"] if choice.get("kind") == "use_intercept")
        apply_reactive_intercept_action(state, "P1", action, "unit_destroyed")

        self.assertEqual(state.players["P2"].battlefield, [])


if __name__ == "__main__":
    unittest.main()
