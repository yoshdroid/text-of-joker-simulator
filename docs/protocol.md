# Protocol

## Basics

Processes communicate over `stdio` using one JSON object per line in `JSON Lines` format.

```json
{"type":"hello","request_id":"boot-1","payload":{"player_name":"example-bot","protocol_version":"1"}}
{"type":"request_action","request_id":"turn-3-main","payload":{"available_actions":[{"kind":"end_turn"}]}}
{"type":"action","request_id":"turn-3-main","payload":{"kind":"end_turn"}}
```

The machine-facing protocol stays JSON. For human-facing logs, the engine can render a compact event line such as:

```text
[R03][P1][REQ] choose_action actions=end_turn,drive,attack
[R03][P1][RES] attack attacker=u1 target=player
[R03][SYS][EVT] life_change player=P2 delta=-1 life=5
```

## Message Types

- `hello`
- `deck_submit`
- `mulligan_decision`
- `state_update`
- `request_action`
- `choice_request`
- `action`
- `result`
- `error`

`choice_request` is the unified selection message. It is used when a player must choose:

- an ability target
- a hand card for a discard cost
- a blocker
- an intercept to use, or to pass

Each entry in `available_choices` may also include UI-oriented metadata such as:

- `choice_label`
- `choice_summary`
- `choice_label_ja`
- `choice_summary_ja`
- `card_name`
- `current_bp`
- `current_damage`

When a candidate exists but is currently unusable, `choice_request` may also include `unavailable_choices`.
Each unavailable choice can carry a `disabled_reason` such as:

- `unit_exhausted`
- `not_enough_cp`
- `color_requirement_not_met`
- `attacker_only`
- `effect_not_implemented`

For immediate display use, unavailable choices may also include `disabled_reason_message` in Japanese.

Intercept choices can be requested multiple times in one battle. The attacker and defender alternate until both pass consecutively. A used intercept leaves `trigger_zone` and moves to the discard pile after effect resolution.

## Starter Python Bot Flow

1. Reply to `hello` with bot name and protocol version.
2. Reply to `deck_submit` with the deck list.
3. Reply to `mulligan_decision` with `false` by default.
4. Reply to `request_action` by choosing one legal action.
5. Reply to `choice_request` by choosing one legal option.

## Example `state_update`

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

For the first player on round 1, the opening draw count follows `opening_draws.first[0]`.

## Example `request_action`

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

## Implemented Actions

- `set_trigger`: place a card from hand into the leftmost open trigger slot
- `drive`: play a unit onto the battlefield
- `overdrive`: evolve onto a same-color unit already on the battlefield
- `override`: combine same-name cards in hand to raise level and draw 1
- `attack`: declare an attack
- `choice_request` with `choice_kind: "block"`: defender chooses one blocker or `no_block`
- `choice_request` with `choice_kind: "intercept"`: current player chooses one intercept or `no_intercept`

When a unit or evolution card in `trigger_zone` matches the color of a newly played unit, the leftmost matching card is consumed automatically, reduces cost by 1, and moves to the discard pile.
