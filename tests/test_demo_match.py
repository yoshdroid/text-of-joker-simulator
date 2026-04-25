import json
import subprocess
import sys
import unittest


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
        self.assertEqual(payload["messages"][0]["direction"], "to_player")
        self.assertEqual(payload["messages"][1]["direction"], "from_player")


if __name__ == "__main__":
    unittest.main()
