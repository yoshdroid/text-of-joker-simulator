# Protocol

## Basics

プロセス間通信は `stdio` 上の JSON Lines です。
1 行に 1 メッセージを載せます。

```json
{"type":"hello","request_id":"hello-p1","payload":{"player_name":"example-bot","protocol_version":"1"}}
{"type":"request_action","request_id":"action-2-3-P1","payload":{"available_actions":[{"kind":"end_turn"}]}}
{"type":"action","request_id":"action-2-3-P1","payload":{"kind":"end_turn"}}
```

## Message Types

- `hello`
- `deck_submit`
- `mulligan_decision`
- `state_update`
- `request_action`
- `choice_request`
- `action`
- `choice_response`
- `state_ack`
- `error`

## Request / Response Pairing

- `request_action` と `action` は同じ `request_id` を使います
- `choice_request` と `choice_response` も同じ `request_id` を使います
- 現在の `request_id` には `round_no` と `turn_serial` を含めています

例:

- `action-4-8-P2`
- `choice-4-8-2-P1`

## `state_update`

`state_update` は各アクションサイクルの冒頭と、必要な途中段階で送られます。

主な項目:

- `round_no`
- `turn_serial`
- `turn_player_id`
- `viewer_player_id`
- `available_actions`
- `players`
- `flags.match_ended`

相手プレイヤー視点では、相手手札の中身は公開しません。
`trigger_zone` は相手から見ると色だけ見えます。

## `request_action`

ターンプレイヤーに対して合法手一覧を送ります。

現在の主なアクション:

- `set_trigger`
- `drive`
- `overdrive`
- `override`
- `retreat`
- `attack`
- `end_turn`

例:

```json
{
  "type": "request_action",
  "request_id": "action-2-3-P1",
  "payload": {
    "available_actions": [
      {"kind": "set_trigger", "hand_index": 0, "card_no": "1-0-001"},
      {"kind": "drive", "hand_index": 1, "card_no": "1-0-002", "cost": 0, "trigger_reducer_index": 0},
      {"kind": "retreat", "unit_index": 0, "card_no": "1-0-004", "card_level": 1},
      {"kind": "end_turn"}
    ]
  }
}
```

## `choice_request`

選択を伴う処理は `choice_request` に統一しています。

現在の用途:

- 対象ユニット選択
- 手札コストの選択
- ブロッカー選択
- インターセプト選択

主な項目:

- `round_no`
- `turn_serial`
- `choice_kind`
- `prompt`
- `available_choices`
- `unavailable_choices`

各 choice には UI 向けに次の情報が入ることがあります。

- `choice_label`
- `choice_summary`
- `choice_label_ja`
- `choice_summary_ja`
- `card_name`
- `current_bp`
- `current_damage`
- `disabled_reason`
- `disabled_reason_message`

## Intercept Flow

- ブロックが成立した戦闘でだけ `choice_request` による intercept 選択が始まります
- 攻撃側から先に選びます
- その後は攻撃側と防御側が交互に選びます
- 双方が連続で `no_intercept` を返したら終了です
- 使用した intercept は `trigger_zone` から消え、捨札へ移ります

## Human-Friendly Logs

`demo_match` は生の `messages` に加えて `rendered_messages` も出します。

現在の表示形式:

```text
[R04][E001][P2][REQ] request_action actions=drive,attack,end_turn
[R04][E002][P2][RES] action end_turn
```

- `Rxx`: ROUND 番号
- `Exxx`: その ROUND 内のイベント通し番号
- `P?`: 関係プレイヤー
- `REQ` / `RES` / `EVT`: 要求 / 応答 / 差分イベント
