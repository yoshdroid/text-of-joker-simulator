# Protocol

## 基本案

通信は 1 行 1 JSON の `JSON Lines` を採用します。

例:

```json
{"type":"hello","request_id":"boot-1","payload":{"player_name":"example-bot","protocol_version":"1"}}
{"type":"request_action","request_id":"turn-3-main","payload":{"available_actions":[{"kind":"end_turn"}]}}
{"type":"action","request_id":"turn-3-main","payload":{"kind":"end_turn"}}
```

## この方式の利点

- パースが簡単
- ログ保存しやすい
- 1 行単位で中継しやすい
- 将来 WebSocket 等へ移植しやすい

## 見栄えの良いログ案

プロトコル自体は JSON にしつつ、人間向け表示は別フォーマットにするのがおすすめです。

例:

```text
[R03][P1][REQ] choose_action actions=end_turn,drive,attack
[R03][P1][RES] attack attacker=u1 target=player
[R03][SYS][EVT] life_change player=P2 delta=-1 life=5
```

この方式なら通信の堅牢性は JSON に任せつつ、実況ログだけ格好よく整えられます。

## メッセージ種別の最小セット

- `hello`
- `deck_submit`
- `mulligan_decision`
- `state_update`
- `request_action`
- `block_request`
- `action`
- `result`
- `error`

## Python bot ひな形の基本フロー

1. `hello` を受けたら bot 名と対応プロトコルを返す
2. `deck_submit` を受けたらデッキ一覧を返す
3. `mulligan_decision` を受けたら既定では `false` を返す
4. `request_action` を受けたら、候補の先頭を選ぶ

この挙動にしておくと、今後の強化時に「合法手探索」へ差し替えやすくなります。

## `state_update` の最小スキーマ

```json
{
  "round_no": 1,
  "turn_player_id": "P1",
  "turn_serial": 1,
  "viewer_player_id": "P1",
  "available_actions": [{"kind": "end_turn"}],
  "players": {
    "P1": {
      "player_id": "P1",
      "life": 7,
      "current_cp": 2,
      "hand_count": 4,
      "hand_card_nos": ["1-0-001"],
      "deck_count": 36,
      "discard_top_to_bottom": [],
      "battlefield": [],
      "trigger_zone": []
    },
    "P2": {
      "player_id": "P2",
      "life": 7,
      "current_cp": 0,
      "hand_count": 4,
      "deck_count": 36,
      "discard_top_to_bottom": [],
      "battlefield": [],
      "trigger_zone": []
    }
  },
  "flags": {
    "round_one_first_player_cannot_attack": true,
    "match_ended": false
  }
}
```

この例では、先攻 1 ターン目ドローは特例ではなくレギュレーションの `opening_draws.first[0]` に従います。

## `request_action` の最小スキーマ

```json
{
  "type": "request_action",
  "request_id": "action-1-P1",
  "payload": {
    "available_actions": [
      {"kind": "set_trigger", "hand_index": 0, "card_no": "1-0-001"},
      {"kind": "drive", "hand_index": 1, "card_no": "1-0-002", "cost": 0, "trigger_reducer_index": 0},
      {"kind": "end_turn"}
    ]
  }
}
```

## 追加した基本アクション

- `set_trigger`: 手札からカードを trigger_zone の右端へ置く
- `drive`: 現在は unit 限定で場へ出す
- `attack`: 現在はプレイヤーアタックのみ
- `block_request`: 防御側が 1 体だけ blocker を選ぶ

unit / evolution カードが trigger_zone にあり、同属性 unit を `drive` する場合は、左から最初に見つかった 1 枚が強制的に使われ、コストを 1 軽減してから捨札へ送られます。
