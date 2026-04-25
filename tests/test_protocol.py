import unittest

from tojs.protocol import Message, decode_message, encode_message, render_event_log


class ProtocolTest(unittest.TestCase):
    # JSON Lines で通信メッセージを相互変換できることを確認する。
    def test_encode_and_decode_message(self) -> None:
        message = Message(
            type="request_action",
            request_id="turn-1-main",
            payload={"available_actions": [{"kind": "end_turn"}]},
        )

        encoded = encode_message(message)
        decoded = decode_message(encoded)

        self.assertEqual(decoded, message)

    # 観戦しやすいイベント行フォーマットを整形できることを確認する。
    def test_render_event_log(self) -> None:
        rendered = render_event_log(3, "P1", "REQ", "choose_action actions=end_turn,drive")

        self.assertEqual(rendered, "[R03][P1][REQ] choose_action actions=end_turn,drive")


if __name__ == "__main__":
    unittest.main()
