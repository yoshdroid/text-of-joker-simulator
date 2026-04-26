import unittest

from tojs.demo_match import _format_choice
from tojs.protocol import Message, decode_message, encode_message, render_event_log


class ProtocolTest(unittest.TestCase):
    # JSON Lines で送受信メッセージを往復変換できることを確認する
    def test_encode_and_decode_message(self) -> None:
        message = Message(
            type="request_action",
            request_id="turn-1-main",
            payload={"available_actions": [{"kind": "end_turn"}]},
        )

        encoded = encode_message(message)
        decoded = decode_message(encoded)

        self.assertEqual(decoded, message)

    # 観戦用のイベントログを整形できることを確認する
    def test_render_event_log(self) -> None:
        rendered = render_event_log(3, "P1", "REQ", "choose_action actions=end_turn,drive")

        self.assertEqual(rendered, "[R03][P1][REQ] choose_action actions=end_turn,drive")

    def test_render_event_log_with_event_number(self) -> None:
        rendered = render_event_log(3, "P1", "REQ", "choose_action actions=end_turn,drive", event_no=7)

        self.assertEqual(rendered, "[R03][E007][P1][REQ] choose_action actions=end_turn,drive")

    # 選択肢表示は日本語ラベルと理由文を優先することを確認する
    def test_format_choice_prefers_japanese_display(self) -> None:
        rendered = _format_choice(
            {
                "kind": "use_intercept",
                "choice_label": "Use Hero Sword",
                "choice_label_ja": "Hero Swordを使う",
                "choice_summary_ja": "CP 0 / 対象 自分ユニット",
                "disabled_reason_message": "CPが足りないため使えません。",
            }
        )

        self.assertIn("Hero Swordを使う", rendered)
        self.assertIn("CP 0 / 対象 自分ユニット", rendered)
        self.assertIn("理由: CPが足りないため使えません。", rendered)


if __name__ == "__main__":
    unittest.main()
