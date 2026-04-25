import random
import unittest

from tojs.game import (
    apply_action,
    build_state_update_payload,
    create_match_state,
    start_turn,
)
from tojs.models import Regulation


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
        self.first_deck = [f"1-0-{index:03d}" for index in range(1, 41)]
        self.second_deck = [f"2-0-{index:03d}" for index in range(1, 41)]

    # 初期生成時に両プレイヤーへ初期手札 4 枚が配られることを確認する。
    def test_create_match_state_draws_initial_hand(self) -> None:
        state = create_match_state(self.regulation, self.first_deck, self.second_deck, random.Random(7))

        self.assertEqual(len(state.players["P1"].hand), 4)
        self.assertEqual(len(state.players["P2"].hand), 4)
        self.assertEqual(len(state.players["P1"].draw_pile), 36)
        self.assertEqual(len(state.players["P2"].draw_pile), 36)

    # 先攻 1 ターン目はレギュレーション配列どおり 0 枚ドローし、CP だけ設定されることを確認する。
    def test_start_turn_for_first_player_round_one(self) -> None:
        state = create_match_state(self.regulation, self.first_deck, self.second_deck, random.Random(7))

        start_turn(state, "P1", random.Random(7))

        self.assertEqual(state.turn_player_id, "P1")
        self.assertEqual(state.turn_serial, 1)
        self.assertEqual(len(state.players["P1"].hand), 4)
        self.assertEqual(state.players["P1"].current_cp, 2)

    # state_update では自分の手札は見えるが、相手の手札内容は見えないことを確認する。
    def test_build_state_update_payload_hides_opponent_hand(self) -> None:
        state = create_match_state(self.regulation, self.first_deck, self.second_deck, random.Random(7))
        start_turn(state, "P1", random.Random(7))

        payload = build_state_update_payload(state, "P1")

        self.assertEqual(payload["viewer_player_id"], "P1")
        self.assertEqual(len(payload["players"]["P1"]["hand_card_nos"]), 4)
        self.assertNotIn("hand_card_nos", payload["players"]["P2"])

    # end_turn を適用するとターンが後攻へ移り、同ラウンドのまま次ターン準備が走ることを確認する。
    def test_apply_end_turn_moves_to_second_player(self) -> None:
        state = create_match_state(self.regulation, self.first_deck, self.second_deck, random.Random(7))
        start_turn(state, "P1", random.Random(7))

        apply_action(state, "P1", {"kind": "end_turn"}, random.Random(7))

        self.assertEqual(state.turn_player_id, "P2")
        self.assertEqual(state.round_no, 1)
        self.assertEqual(state.players["P2"].current_cp, 3)
        self.assertEqual(len(state.players["P2"].hand), 6)


if __name__ == "__main__":
    unittest.main()
