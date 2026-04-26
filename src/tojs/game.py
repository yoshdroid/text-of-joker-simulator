from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable

from .models import CardDefinition, Regulation


PlayerId = str
ChoiceResolver = Callable[[PlayerId, dict[str, Any]], dict[str, Any]]


@dataclass
class UnitState:
    card_no: str
    unit_id: int = 0
    level: int = 1
    exhausted: bool = False
    attack_restricted: bool = True
    current_damage: int = 0
    temporary_bp_modifier: int = 0
    permanent_bp_modifier: int = 0


@dataclass
class PlayerState:
    player_id: PlayerId
    role: str
    life: int
    draw_pile: list[str]
    hand: list[str] = field(default_factory=list)
    discard_pile: list[str] = field(default_factory=list)
    battlefield: list[UnitState] = field(default_factory=list)
    trigger_zone: list[str] = field(default_factory=list)
    current_cp: int = 0


@dataclass
class MatchState:
    regulation: Regulation
    card_catalog: dict[str, CardDefinition]
    players: dict[PlayerId, PlayerState]
    next_unit_id: int = 1
    round_no: int = 1
    turn_player_id: PlayerId = "P1"
    turn_serial: int = 0
    winner: str | None = None
    ended_reason: str | None = None
    used_card_nos_this_turn: list[str] = field(default_factory=list)
    event_log: list[dict[str, Any]] = field(default_factory=list)
    next_event_no: int = 1


@dataclass(frozen=True)
class AbilityEvent:
    type: str
    player_id: PlayerId
    source_unit_id: int | None = None
    target_player_id: PlayerId | None = None
    source_card_no: str | None = None
    amount: int | None = None
    metadata: dict[str, Any] | None = None


def create_match_state(
    regulation: Regulation,
    card_catalog: dict[str, CardDefinition],
    first_deck: list[str],
    second_deck: list[str],
    rng: random.Random,
) -> MatchState:
    first_draw_pile = list(first_deck)
    second_draw_pile = list(second_deck)
    rng.shuffle(first_draw_pile)
    rng.shuffle(second_draw_pile)

    state = MatchState(
        regulation=regulation,
        card_catalog=card_catalog,
        players={
            "P1": PlayerState(
                player_id="P1",
                role="first",
                life=regulation.starting_life_first,
                draw_pile=first_draw_pile,
            ),
            "P2": PlayerState(
                player_id="P2",
                role="second",
                life=regulation.starting_life_second,
                draw_pile=second_draw_pile,
            ),
        },
    )
    for player_id in ("P1", "P2"):
        draw_cards(state.players[player_id], regulation.initial_hand_size, rng, regulation.hand_size_limit)
    return state


def apply_mulligan(state: MatchState, player_id: PlayerId, do_mulligan: bool, rng: random.Random) -> None:
    if not do_mulligan:
        return
    player = state.players[player_id]
    player.draw_pile.extend(player.hand)
    player.hand.clear()
    rng.shuffle(player.draw_pile)
    draw_cards(player, state.regulation.initial_hand_size, rng, state.regulation.hand_size_limit)


def start_turn(state: MatchState, player_id: PlayerId, rng: random.Random) -> None:
    state.turn_player_id = player_id
    state.turn_serial += 1
    state.used_card_nos_this_turn = []
    player = state.players[player_id]
    draw_count = get_scheduled_draw_count(state, player)
    cp_value = get_scheduled_cp(state, player)
    drawn_cards = _draw_card_nos(player, draw_count, rng, state.regulation.hand_size_limit)
    _record_draw_card_moves(state, player_id, drawn_cards, reason="turn_start_draw")
    resolve_ability_events(
        state,
        [
            AbilityEvent(
                type="turn_start_draw",
                player_id=player_id,
                amount=len(drawn_cards),
                metadata={"drawn_card_nos": list(drawn_cards)},
            ),
        ],
        rng,
    )
    previous_cp = player.current_cp
    player.current_cp = min(cp_value, state.regulation.max_cp_per_round)
    resolve_ability_events(
        state,
        [
            AbilityEvent(
                type="turn_start_cp_set",
                player_id=player_id,
                amount=player.current_cp - previous_cp,
            ),
        ],
        rng,
    )
    for unit in player.battlefield:
        if unit.level >= 1:
            unit.exhausted = False
        unit.attack_restricted = False


def end_turn(state: MatchState, rng: random.Random) -> None:
    resolve_ability_events(
        state,
        [AbilityEvent(type="turn_end", player_id=state.turn_player_id)],
        rng,
    )
    for player in state.players.values():
        for unit in player.battlefield:
            unit.current_damage = 0
            unit.temporary_bp_modifier = 0

    next_player_id = "P2" if state.turn_player_id == "P1" else "P1"
    if state.turn_player_id == "P2" and state.round_no >= state.regulation.round_count:
        first_life = state.players["P1"].life
        second_life = state.players["P2"].life
        if first_life > second_life:
            _set_match_outcome(state, "P1", "round_limit")
        elif second_life > first_life:
            _set_match_outcome(state, "P2", "round_limit")
        else:
            _set_match_outcome(state, "draw", "round_limit")
        return

    if state.turn_player_id == "P2":
        state.round_no += 1

    start_turn(state, next_player_id, rng)

def apply_action(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> None:
    if player_id != state.turn_player_id:
        raise ValueError(f"not turn player: {player_id}")
    kind = action.get("kind")
    if kind == "retreat":
        apply_retreat_action(state, player_id, action)
        return
    if kind == "set_trigger":
        apply_set_trigger_action(state, player_id, action)
        return
    if kind == "override":
        apply_override_action(state, player_id, action, rng)
        return
    if kind == "overdrive":
        apply_overdrive_action(state, player_id, action, rng, choice_resolver)
        return
    if kind == "drive":
        apply_drive_action(state, player_id, action, rng, choice_resolver)
        return
    if kind == "attack":
        apply_attack_action(state, player_id, action, rng=rng, choice_resolver=choice_resolver)
        return
    if kind == "end_turn":
        end_turn(state, rng)
        return
    raise ValueError(f"unsupported action kind: {kind}")


def build_state_update_payload(state: MatchState, viewer_id: PlayerId) -> dict[str, Any]:
    viewer = state.players[viewer_id]
    opponent = state.players[get_opponent_id(viewer_id)]
    available_actions = list_available_actions(state, viewer_id)
    return {
        "round_no": state.round_no,
        "turn_player_id": state.turn_player_id,
        "turn_serial": state.turn_serial,
        "event_log_count": len(state.event_log),
        "viewer_player_id": viewer_id,
        "available_actions": available_actions,
        "players": {
            viewer_id: _build_private_player_view(viewer, state),
            opponent.player_id: _build_public_player_view(opponent, state),
        },
        "flags": {
            "round_one_first_player_cannot_attack": state.round_no == 1 and state.turn_player_id == "P1",
            "match_ended": state.winner is not None,
        },
    }


def draw_cards(player: PlayerState, count: int, rng: random.Random, hand_limit: int) -> int:
    return len(_draw_card_nos(player, count, rng, hand_limit))


def _draw_card_nos(player: PlayerState, count: int, rng: random.Random, hand_limit: int) -> list[str]:
    if count <= 0 or len(player.hand) >= hand_limit:
        return []
    actual_count = min(count, hand_limit - len(player.hand))
    if len(player.draw_pile) < actual_count:
        _rebuild_draw_pile(player, rng)
    drawn = player.draw_pile[:actual_count]
    del player.draw_pile[:actual_count]
    player.hand.extend(drawn)
    return drawn


def _record_draw_card_moves(state: MatchState, player_id: PlayerId, drawn_cards: list[str], reason: str) -> None:
    for card_no in drawn_cards:
        _record_ability_event(
            state,
            AbilityEvent(
                type="card_moved",
                player_id=player_id,
                source_card_no=card_no,
                metadata={"from_zone": "deck", "to_zone": "hand", "reason": reason},
            ),
        )


def _rebuild_draw_pile(player: PlayerState, rng: random.Random) -> None:
    player.draw_pile.extend(player.discard_pile)
    player.discard_pile.clear()
    rng.shuffle(player.draw_pile)


def get_scheduled_draw_count(state: MatchState, player: PlayerState) -> int:
    schedule = (
        state.regulation.opening_draws_first
        if player.role == "first"
        else state.regulation.opening_draws_second
    )
    index = min(state.round_no, len(schedule)) - 1
    return schedule[index]


def get_scheduled_cp(state: MatchState, player: PlayerState) -> int:
    schedule = (
        state.regulation.round_start_cp_first
        if player.role == "first"
        else state.regulation.round_start_cp_second
    )
    index = min(state.round_no, len(schedule)) - 1
    return schedule[index]


def get_opponent_id(player_id: PlayerId) -> PlayerId:
    return "P2" if player_id == "P1" else "P1"


def _build_private_player_view(player: PlayerState, state: MatchState) -> dict[str, Any]:
    return {
        "player_id": player.player_id,
        "life": player.life,
        "current_cp": player.current_cp,
        "hand_count": len(player.hand),
        "hand_card_nos": list(player.hand),
        "deck_count": len(player.draw_pile),
        "discard_top_to_bottom": list(player.discard_pile),
        "battlefield": [_serialize_unit(unit, state) for unit in player.battlefield],
        "trigger_zone": [
            {
                "position": index,
                "card_no": card_no,
                "color": state.card_catalog[card_no].color,
            }
            for index, card_no in enumerate(player.trigger_zone)
        ],
    }


def _build_public_player_view(player: PlayerState, state: MatchState) -> dict[str, Any]:
    return {
        "player_id": player.player_id,
        "life": player.life,
        "current_cp": player.current_cp,
        "hand_count": len(player.hand),
        "deck_count": len(player.draw_pile),
        "discard_top_to_bottom": list(player.discard_pile),
        "battlefield": [_serialize_unit(unit, state) for unit in player.battlefield],
        "trigger_zone": [
            {"position": index, "color": state.card_catalog[card_no].color}
            for index, card_no in enumerate(player.trigger_zone)
        ],
    }


def list_available_actions(state: MatchState, player_id: PlayerId) -> list[dict[str, Any]]:
    if state.winner is not None or state.turn_player_id != player_id:
        return []

    player = state.players[player_id]
    actions: list[dict[str, Any]] = []

    if len(player.trigger_zone) < state.regulation.trigger_zone_limit:
        for hand_index, hand_card_id in enumerate(player.hand):
            card_no, _card_level = parse_hand_card_id(hand_card_id)
            if card_no not in state.card_catalog:
                continue
            actions.append(
                {
                    "kind": "set_trigger",
                    "hand_index": hand_index,
                    "card_no": hand_card_id,
                }
            )

    for base_index, base_hand_card_id in enumerate(player.hand):
        base_card_no, base_level = parse_hand_card_id(base_hand_card_id)
        base_card = state.card_catalog.get(base_card_no)
        if base_card is None or base_card.category not in {"unit", "evolution"}:
            continue
        if base_level >= 3:
            continue
        for material_index, material_card_no in enumerate(player.hand):
            material_base_card_no, material_level = parse_hand_card_id(material_card_no)
            if material_index == base_index or material_base_card_no != base_card_no or material_level != base_level:
                continue
            material_card = state.card_catalog.get(material_base_card_no)
            if material_card is None or material_card.category != base_card.category:
                continue
            actions.append(
                {
                    "kind": "override",
                    "base_index": base_index,
                    "material_index": material_index,
                    "card_no": base_hand_card_id,
                    "base_level": base_level,
                }
            )

    if len(player.battlefield) < state.regulation.battlefield_unit_limit:
        for hand_index, hand_card_id in enumerate(player.hand):
            card_no, card_level = parse_hand_card_id(hand_card_id)
            card = state.card_catalog.get(card_no)
            if card is None or card.category != "unit" or card.cp is None:
                continue
            cost, reducer_index = get_drive_cost(state, player_id, card_no)
            if cost <= player.current_cp:
                actions.append(
                    {
                        "kind": "drive",
                        "hand_index": hand_index,
                        "card_no": hand_card_id,
                        "card_level": card_level,
                        "cost": cost,
                        "trigger_reducer_index": reducer_index,
                    }
                )

    for hand_index, hand_card_id in enumerate(player.hand):
        card_no, card_level = parse_hand_card_id(hand_card_id)
        card = state.card_catalog.get(card_no)
        if card is None or card.category != "evolution" or card.cp is None:
            continue
        cost, reducer_index = get_drive_cost(state, player_id, card_no)
        if cost > player.current_cp:
            continue
        for target_index, unit in enumerate(player.battlefield):
            target_card = state.card_catalog[unit.card_no]
            if target_card.color != card.color:
                continue
            actions.append(
                {
                    "kind": "overdrive",
                    "hand_index": hand_index,
                    "card_no": hand_card_id,
                    "target_index": target_index,
                    "cost": cost,
                    "trigger_reducer_index": reducer_index,
                    "card_level": card_level,
                }
            )

    for unit_index, unit in enumerate(player.battlefield):
        actions.append(
            {
                "kind": "retreat",
                "unit_index": unit_index,
                "card_no": unit.card_no,
                "card_level": unit.level,
            }
        )

    round_one_first_player_cannot_attack = state.round_no == 1 and state.turn_player_id == "P1"
    if not round_one_first_player_cannot_attack:
        for attacker_index, unit in enumerate(player.battlefield):
            if unit.exhausted or unit.attack_restricted:
                continue
            actions.append(
                {
                    "kind": "attack",
                    "attacker_index": attacker_index,
                    "target": "player",
                }
            )

    actions.append({"kind": "end_turn"})
    return actions


def list_available_block_actions(state: MatchState, player_id: PlayerId) -> list[dict[str, Any]]:
    return build_block_choice_payload(state, player_id)["available_choices"]


def build_block_choice_payload(state: MatchState, player_id: PlayerId) -> dict[str, Any]:
    player = state.players[player_id]
    actions: list[dict[str, Any]] = [
        {
            "kind": "no_block",
            "choice_label": "No block",
            "choice_summary": "Take the attack without assigning a blocker.",
            "choice_label_ja": "ブロックしない",
            "choice_summary_ja": "ブロッカーを指定せずに攻撃を受けます。",
        }
    ]
    unavailable_choices: list[dict[str, Any]] = []
    for blocker_index, unit in enumerate(player.battlefield):
        card = state.card_catalog[unit.card_no]
        if unit.exhausted:
            unavailable_choices.append(
                {
                    "kind": "block",
                    "blocker_index": blocker_index,
                    "card_no": unit.card_no,
                    "card_name": card.name,
                    "level": unit.level,
                    "current_bp": get_unit_current_bp(state, unit),
                    "current_damage": unit.current_damage,
                    "disabled_reason": "unit_exhausted",
                    "disabled_reason_message": _get_disabled_reason_message("unit_exhausted"),
                    "choice_label": f"Block with {card.name}",
                    "choice_summary": "Cannot block because the unit is exhausted.",
                    "choice_label_ja": f"{card.name}でブロック",
                    "choice_summary_ja": _get_disabled_reason_message("unit_exhausted"),
                }
            )
            continue
        actions.append(
            {
                "kind": "block",
                "blocker_index": blocker_index,
                "card_no": unit.card_no,
                "card_name": card.name,
                "level": unit.level,
                "current_bp": get_unit_current_bp(state, unit),
                "current_damage": unit.current_damage,
                "choice_label": f"Block with {card.name}",
                "choice_summary": f"Lv.{unit.level} / {get_unit_current_bp(state, unit)} BP / damage {unit.current_damage}",
                "choice_label_ja": f"{card.name}でブロック",
                "choice_summary_ja": f"Lv.{unit.level} / BP {get_unit_current_bp(state, unit)} / ダメージ {unit.current_damage}",
            }
        )
    return {
        "round_no": state.round_no,
        "turn_serial": state.turn_serial,
        "choice_kind": "block",
        "prompt": "Choose a blocker or no block.",
        "available_choices": actions,
        "unavailable_choices": unavailable_choices,
        "no_valid_target": "有効な対象がいないため使えません。",
    }


def list_available_intercept_actions(
    state: MatchState,
    player_id: PlayerId,
    own_unit: UnitState,
    enemy_unit: UnitState,
    own_unit_is_attacker: bool,
) -> list[dict[str, Any]]:
    return build_intercept_choice_payload(
        state,
        player_id,
        own_unit,
        enemy_unit,
        own_unit_is_attacker,
    )["available_choices"]


def build_intercept_choice_payload(
    state: MatchState,
    player_id: PlayerId,
    own_unit: UnitState,
    enemy_unit: UnitState,
    own_unit_is_attacker: bool,
) -> dict[str, Any]:
    player = state.players[player_id]
    actions: list[dict[str, Any]] = [
        {
            "kind": "no_intercept",
            "choice_label": "Pass intercept",
            "choice_summary": "Do not use an intercept in this step.",
            "choice_label_ja": "インターセプトしない",
            "choice_summary_ja": "このタイミングではインターセプトを使いません。",
        }
    ]
    unavailable_choices: list[dict[str, Any]] = []
    for trigger_index, card_no in enumerate(player.trigger_zone):
        card = state.card_catalog[card_no]
        if card.category != "intercept":
            continue
        disabled_reason = _get_intercept_disabled_reason(state, player_id, card_no, own_unit_is_attacker)
        target = _get_intercept_target(card_no, own_unit_is_attacker)
        if disabled_reason is not None:
            unavailable_choices.append(
                {
                    "kind": "use_intercept",
                    "trigger_index": trigger_index,
                    "card_no": card_no,
                    "card_name": card.name,
                    "cost": card.cp or 0,
                    "target": target,
                    "disabled_reason": disabled_reason,
                    "disabled_reason_message": _get_disabled_reason_message(disabled_reason),
                    "choice_label": f"Use {card.name}",
                    "choice_summary": f"Unavailable: {disabled_reason}",
                    "choice_label_ja": f"{card.name}を使う",
                    "choice_summary_ja": _get_disabled_reason_message(disabled_reason),
                }
            )
            continue
        actions.append(
            {
                "kind": "use_intercept",
                "trigger_index": trigger_index,
                "card_no": card_no,
                "card_name": card.name,
                "cost": card.cp or 0,
                "target": target,
                "choice_label": f"Use {card.name}",
                "choice_summary": f"CP {card.cp or 0} / target {target}",
                "choice_label_ja": f"{card.name}を使う",
                "choice_summary_ja": f"CP {card.cp or 0} / 対象 {_get_target_label_ja(target)}",
            }
        )
    return {
        "round_no": state.round_no,
        "turn_serial": state.turn_serial,
        "choice_kind": "intercept",
        "prompt": "Choose an intercept or pass.",
        "available_choices": actions,
        "unavailable_choices": unavailable_choices,
        "battle": _build_battle_choice_payload(state, own_unit, enemy_unit, own_unit_is_attacker),
    }


def apply_drive_action(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> None:
    player = state.players[player_id]
    hand_index = action["hand_index"]
    if hand_index < 0 or hand_index >= len(player.hand):
        raise ValueError(f"invalid hand index: {hand_index}")

    hand_card_id = player.hand[hand_index]
    card_no, card_level = parse_hand_card_id(hand_card_id)
    card = state.card_catalog.get(card_no)
    if card is None or card.category != "unit" or card.cp is None:
        raise ValueError(f"card is not a drivable unit: {card_no}")
    if len(player.battlefield) >= state.regulation.battlefield_unit_limit:
        raise ValueError("battlefield is full")
    drive_cost, reducer_index = get_drive_cost(state, player_id, card_no)
    if drive_cost > player.current_cp:
        raise ValueError("not enough cp")

    player.current_cp -= drive_cost
    player.hand.pop(hand_index)
    if drive_cost > 0:
        _record_ability_event(
            state,
            AbilityEvent(
                type="cp_changed",
                player_id=player_id,
                target_player_id=player_id,
                source_card_no=card_no,
                amount=-drive_cost,
            ),
        )
    if reducer_index is not None:
        reducer_card_no = player.trigger_zone.pop(reducer_index)
        player.discard_pile.insert(0, reducer_card_no)
        _record_ability_event(
            state,
            AbilityEvent(
                type="card_moved",
                player_id=player_id,
                source_card_no=reducer_card_no,
                metadata={"from_zone": "trigger_zone", "to_zone": "discard", "reason": "cost_reduction"},
            ),
        )
    attack_restricted = not _has_ability_name(state.card_catalog[card_no], "スピードムーブ")
    player.battlefield.append(
        UnitState(
            card_no=card_no,
            unit_id=_allocate_unit_id(state),
            level=card_level,
            exhausted=False,
            attack_restricted=attack_restricted,
            current_damage=0,
        )
    )
    _record_ability_event(
        state,
        AbilityEvent(
            type="unit_driven",
            player_id=player_id,
            source_unit_id=player.battlefield[-1].unit_id,
            source_card_no=card_no,
            metadata={"level": card_level, "current_bp": get_unit_bp(state, player.battlefield[-1])},
        ),
    )
    resolve_ability_events(
        state,
        [
            AbilityEvent(
                type="unit_entered",
                player_id=player_id,
                source_unit_id=player.battlefield[-1].unit_id,
            )
        ],
        rng,
        choice_resolver,
    )
    _record_card_use(state, card_no)


def apply_overdrive_action(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> None:
    player = state.players[player_id]
    hand_index = action["hand_index"]
    target_index = action["target_index"]
    if hand_index < 0 or hand_index >= len(player.hand):
        raise ValueError(f"invalid hand index: {hand_index}")
    if target_index < 0 or target_index >= len(player.battlefield):
        raise ValueError(f"invalid target index: {target_index}")

    hand_card_id = player.hand[hand_index]
    card_no, evolved_level = parse_hand_card_id(hand_card_id)
    card = state.card_catalog.get(card_no)
    if card is None or card.category != "evolution" or card.cp is None:
        raise ValueError(f"card is not an overdrivable evolution: {card_no}")

    target_unit = player.battlefield[target_index]
    if target_unit.unit_id == 0:
        target_unit.unit_id = _allocate_unit_id(state)
    target_card = state.card_catalog[target_unit.card_no]
    if target_card.color != card.color:
        raise ValueError("overdrive target color mismatch")

    overdrive_cost, reducer_index = get_drive_cost(state, player_id, card_no)
    if overdrive_cost > player.current_cp:
        raise ValueError("not enough cp")

    inherited_exhausted = target_unit.exhausted
    previous_level = target_unit.level

    player.current_cp -= overdrive_cost
    player.hand.pop(hand_index)
    if overdrive_cost > 0:
        _record_ability_event(
            state,
            AbilityEvent(
                type="cp_changed",
                player_id=player_id,
                target_player_id=player_id,
                source_card_no=card_no,
                amount=-overdrive_cost,
            ),
        )
    if reducer_index is not None:
        reducer_card_no = player.trigger_zone.pop(reducer_index)
        player.discard_pile.insert(0, reducer_card_no)
        _record_ability_event(
            state,
            AbilityEvent(
                type="card_moved",
                player_id=player_id,
                source_card_no=reducer_card_no,
                metadata={"from_zone": "trigger_zone", "to_zone": "discard", "reason": "cost_reduction"},
            ),
        )
    player.discard_pile.insert(0, target_unit.card_no)
    _record_ability_event(
        state,
        AbilityEvent(
            type="unit_sent_to_discard",
            player_id=player_id,
            source_unit_id=target_unit.unit_id,
            source_card_no=target_unit.card_no,
            metadata={"reason": "overdrive_material"},
        ),
    )
    player.battlefield[target_index] = UnitState(
        card_no=card_no,
        unit_id=target_unit.unit_id,
        level=evolved_level,
        exhausted=False if evolved_level >= 3 else inherited_exhausted,
        attack_restricted=False,
        current_damage=0,
    )
    _record_ability_event(
        state,
        AbilityEvent(
            type="unit_overdriven",
            player_id=player_id,
            source_unit_id=player.battlefield[target_index].unit_id,
            source_card_no=card_no,
            metadata={"base_card_no": target_card.card_no, "from_level": previous_level, "to_level": evolved_level},
        ),
    )
    _record_ability_event(
        state,
        AbilityEvent(
            type="unit_level_changed",
            player_id=player_id,
            source_unit_id=player.battlefield[target_index].unit_id,
            source_card_no=card_no,
            metadata={"from_level": previous_level, "to_level": evolved_level, "reason": "overdrive"},
        ),
    )
    emitted_events = [
        AbilityEvent(
            type="unit_entered",
            player_id=player_id,
            source_unit_id=player.battlefield[target_index].unit_id,
        )
    ]
    if evolved_level >= 3:
        emitted_events.append(
            AbilityEvent(
                type="unit_overclocked",
                player_id=player_id,
                source_unit_id=player.battlefield[target_index].unit_id,
            )
        )
    resolve_ability_events(state, emitted_events, rng, choice_resolver)
    _record_card_use(state, card_no)


def apply_retreat_action(state: MatchState, player_id: PlayerId, action: dict[str, Any]) -> None:
    player = state.players[player_id]
    unit_index = int(action["unit_index"])
    if unit_index < 0 or unit_index >= len(player.battlefield):
        raise ValueError(f"invalid retreat unit index: {unit_index}")

    unit = player.battlefield.pop(unit_index)
    player.discard_pile.insert(0, unit.card_no)
    _record_ability_event(
        state,
        AbilityEvent(
            type="unit_retreated",
            player_id=player_id,
            source_unit_id=unit.unit_id,
            source_card_no=unit.card_no,
        ),
    )
    _record_ability_event(
        state,
        AbilityEvent(
            type="unit_sent_to_discard",
            player_id=player_id,
            source_unit_id=unit.unit_id,
            source_card_no=unit.card_no,
            metadata={"reason": "retreat"},
        ),
    )


def apply_set_trigger_action(state: MatchState, player_id: PlayerId, action: dict[str, Any]) -> None:
    player = state.players[player_id]
    if len(player.trigger_zone) >= state.regulation.trigger_zone_limit:
        raise ValueError("trigger zone is full")

    hand_index = action["hand_index"]
    if hand_index < 0 or hand_index >= len(player.hand):
        raise ValueError(f"invalid hand index: {hand_index}")

    hand_card_id = player.hand.pop(hand_index)
    card_no, _card_level = parse_hand_card_id(hand_card_id)
    player.trigger_zone.append(card_no)
    _record_ability_event(
        state,
        AbilityEvent(
            type="card_set_to_trigger_zone",
            player_id=player_id,
            source_card_no=card_no,
            metadata={"position": len(player.trigger_zone) - 1},
        ),
    )
    _record_card_use(state, card_no)


def apply_override_action(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    rng: random.Random,
) -> None:
    player = state.players[player_id]
    base_index = action["base_index"]
    material_index = action["material_index"]
    if base_index < 0 or base_index >= len(player.hand):
        raise ValueError(f"invalid base index: {base_index}")
    if material_index < 0 or material_index >= len(player.hand):
        raise ValueError(f"invalid material index: {material_index}")
    if base_index == material_index:
        raise ValueError("override requires two different hand indexes")

    base_hand_card_id = player.hand[base_index]
    material_hand_card_id = player.hand[material_index]
    base_card_no, base_level = parse_hand_card_id(base_hand_card_id)
    material_card_no, material_level = parse_hand_card_id(material_hand_card_id)
    if base_card_no != material_card_no:
        raise ValueError("override requires the same card name")
    if base_level != material_level:
        raise ValueError("override requires the same current level")

    base_card = state.card_catalog.get(base_card_no)
    if base_card is None or base_card.category not in {"unit", "evolution"}:
        raise ValueError(f"card cannot be overridden: {base_card_no}")

    remaining_hand = list(player.hand)
    higher_index = max(base_index, material_index)
    lower_index = min(base_index, material_index)
    remaining_hand.pop(higher_index)
    remaining_hand.pop(lower_index)

    new_level = min(3, int(action.get("base_level", base_level)) + 1)
    if int(action.get("base_level", base_level)) >= 3:
        raise ValueError("level 3 card cannot be overridden")

    player.hand = [format_hand_card_id(base_card_no, new_level)] + remaining_hand
    player.discard_pile.insert(0, material_card_no)
    _record_ability_event(
        state,
        AbilityEvent(
            type="card_moved",
            player_id=player_id,
            source_card_no=material_card_no,
            metadata={"from_zone": "hand", "to_zone": "discard", "reason": "override_material"},
        ),
    )
    _record_ability_event(
        state,
        AbilityEvent(
            type="card_overridden",
            player_id=player_id,
            source_card_no=base_card_no,
            metadata={"from_level": base_level, "to_level": new_level},
        ),
    )
    drawn_cards = _draw_card_nos(player, 1, rng, state.regulation.hand_size_limit)
    if drawn_cards:
        _record_draw_card_moves(state, player_id, drawn_cards, reason="override_draw")
        _record_ability_event(
            state,
            AbilityEvent(
                type="cards_drawn",
                player_id=player_id,
                target_player_id=player_id,
                source_card_no=base_card_no,
                amount=len(drawn_cards),
                metadata={"drawn_card_nos": list(drawn_cards)},
            ),
        )
    _record_card_use(state, base_card_no)


def apply_attack_action(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    block_action: dict[str, Any] | None = None,
    rng: random.Random | None = None,
    choice_resolver: ChoiceResolver | None = None,
) -> None:
    if rng is None:
        rng = random.Random(0)
    declare_attack_action(state, player_id, action, rng, choice_resolver)
    resolve_declared_attack_action(state, player_id, action, block_action, rng, choice_resolver)


def declare_attack_action(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> None:
    attacker_owner = state.players[player_id]
    attacker_index = action["attacker_index"]
    if attacker_index < 0 or attacker_index >= len(attacker_owner.battlefield):
        raise ValueError(f"invalid attacker index: {attacker_index}")

    attacker = attacker_owner.battlefield[attacker_index]
    if attacker.exhausted:
        raise ValueError("attacker is exhausted")
    if attacker.attack_restricted:
        raise ValueError("attacker has attack restriction")
    if state.round_no == 1 and player_id == "P1":
        raise ValueError("first player cannot attack on round one")

    attacker.exhausted = True
    if attacker.unit_id == 0:
        attacker.unit_id = _allocate_unit_id(state)
    _record_ability_event(
        state,
        AbilityEvent(
            type="attack_declared",
            player_id=player_id,
            source_unit_id=attacker.unit_id,
            target_player_id=get_opponent_id(player_id),
            source_card_no=attacker.card_no,
        ),
    )
    resolve_ability_events(
        state,
        [
            AbilityEvent(
                type="unit_attacked",
                player_id=player_id,
                source_unit_id=attacker.unit_id,
                target_player_id=get_opponent_id(player_id),
            )
        ],
        rng,
        choice_resolver,
    )


def resolve_declared_attack_action(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    block_action: dict[str, Any] | None,
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> None:
    attacker_owner = state.players[player_id]
    attacker_index = action["attacker_index"]
    if attacker_index < 0 or attacker_index >= len(attacker_owner.battlefield):
        raise ValueError(f"invalid attacker index: {attacker_index}")
    attacker = attacker_owner.battlefield[attacker_index]
    defender_id = get_opponent_id(player_id)
    defender = state.players[defender_id]

    if block_action is not None and block_action.get("kind") == "block":
        blocker_index = block_action["blocker_index"]
        if blocker_index < 0 or blocker_index >= len(defender.battlefield):
            block_action = None
        else:
            blocker = defender.battlefield[blocker_index]
            if blocker.exhausted:
                block_action = None
            elif blocker.unit_id == 0:
                blocker.unit_id = _allocate_unit_id(state)

    if block_action is not None and block_action.get("kind") == "block":
        blocker_index = block_action["blocker_index"]
        blocker = defender.battlefield[blocker_index]
        _record_ability_event(
            state,
            AbilityEvent(
                type="block_declared",
                player_id=defender_id,
                source_unit_id=blocker.unit_id,
                target_player_id=player_id,
                source_card_no=blocker.card_no,
            ),
        )
        resolve_ability_events(
            state,
            [
                AbilityEvent(
                    type="unit_blocked",
                    player_id=defender_id,
                    source_unit_id=blocker.unit_id,
                    target_player_id=player_id,
                )
            ],
            rng,
            choice_resolver,
        )
        blocker.exhausted = True
        attacker_bp = get_unit_current_bp(state, attacker)
        blocker_bp = get_unit_current_bp(state, blocker)
        attacker.current_damage += blocker_bp
        blocker.current_damage += attacker_bp
        _record_ability_event(
            state,
            AbilityEvent(
                type="battle_bp_changed",
                player_id=player_id,
                source_unit_id=attacker.unit_id,
                source_card_no=attacker.card_no,
                amount=blocker_bp,
                metadata={
                    "current_damage": attacker.current_damage,
                    "current_bp": get_unit_current_bp(state, attacker),
                    "role": "attacker",
                },
            ),
        )
        _record_ability_event(
            state,
            AbilityEvent(
                type="battle_bp_changed",
                player_id=defender_id,
                source_unit_id=blocker.unit_id,
                source_card_no=blocker.card_no,
                amount=attacker_bp,
                metadata={
                    "current_damage": blocker.current_damage,
                    "current_bp": get_unit_current_bp(state, blocker),
                    "role": "blocker",
                },
            ),
        )
        attacker_survives = attacker.current_damage < get_unit_bp(state, attacker)
        blocker_survives = blocker.current_damage < get_unit_bp(state, blocker)
        if _unit_has_ability(state, attacker, "貫通") and attacker_survives and not blocker_survives:
            defender.life -= 1
        _record_ability_event(
            state,
            AbilityEvent(
                type="battle_resolved",
                player_id=player_id,
                source_unit_id=attacker.unit_id,
                target_player_id=defender_id,
                source_card_no=attacker.card_no,
                metadata={
                    "result": (
                        "attacker_win"
                        if attacker_survives and not blocker_survives
                        else "blocker_win"
                        if blocker_survives and not attacker_survives
                        else "draw"
                    ),
                    "attacker_card_no": attacker.card_no,
                    "blocker_card_no": blocker.card_no,
                },
            ),
        )
        emitted_events: list[AbilityEvent] = []
        if attacker_survives and not blocker_survives:
            emitted_events.extend(_clock_up_unit(state, player_id, attacker))
        elif blocker_survives and not attacker_survives:
            emitted_events.extend(_clock_up_unit(state, defender_id, blocker))
        if emitted_events:
            resolve_ability_events(state, emitted_events, rng, choice_resolver)
        _destroy_broken_units(state, player_id, rng, choice_resolver)
        _destroy_broken_units(state, defender_id, rng, choice_resolver)
        _update_winner_by_life(state)
        return

    defender.life -= 1
    resolve_ability_events(
        state,
        [
            AbilityEvent(
                type="life_changed",
                player_id=player_id,
                source_unit_id=attacker.unit_id,
                source_card_no=attacker.card_no,
                target_player_id=defender_id,
                amount=-1,
                metadata={"reason": "player_attack", "current_life": defender.life},
            ),
            AbilityEvent(
                type="player_attack_success",
                player_id=player_id,
                source_unit_id=attacker.unit_id,
                target_player_id=defender_id,
            ),
        ],
        rng,
        choice_resolver,
    )
    _update_winner_by_life(state)


def apply_intercept_action(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    own_unit: UnitState,
    enemy_unit: UnitState,
    own_unit_is_attacker: bool,
) -> None:
    if action.get("kind") != "use_intercept":
        return
    player = state.players[player_id]
    trigger_index = int(action["trigger_index"])
    if trigger_index < 0 or trigger_index >= len(player.trigger_zone):
        raise ValueError(f"invalid trigger index: {trigger_index}")

    card_no = player.trigger_zone[trigger_index]
    if not _can_use_intercept_card(state, player_id, card_no, own_unit_is_attacker):
        raise ValueError(f"intercept cannot be used: {card_no}")

    card = state.card_catalog[card_no]
    player.current_cp -= card.cp or 0
    used_card_no = player.trigger_zone.pop(trigger_index)
    player.discard_pile.insert(0, used_card_no)
    _record_ability_event(
        state,
        AbilityEvent(
            type="card_moved",
            player_id=player_id,
            source_card_no=used_card_no,
            metadata={"from_zone": "trigger_zone", "to_zone": "discard", "reason": "intercept_resolution"},
        ),
    )
    _record_ability_event(
        state,
        AbilityEvent(
            type="intercept_used",
            player_id=player_id,
            target_player_id=player_id,
            source_card_no=used_card_no,
        ),
    )
    _resolve_intercept_effect(state, player_id, card_no, own_unit, enemy_unit, own_unit_is_attacker)
    _record_card_use(state, card_no)


def get_drive_cost(state: MatchState, player_id: PlayerId, card_no: str) -> tuple[int, int | None]:
    player = state.players[player_id]
    card = state.card_catalog[card_no]
    if card.cp is None:
        return 0, None

    reducer_index = find_trigger_reducer_index(state, player_id, card_no)
    if reducer_index is None:
        return card.cp, None
    return max(0, card.cp - 1), reducer_index


def find_trigger_reducer_index(state: MatchState, player_id: PlayerId, card_no: str) -> int | None:
    player = state.players[player_id]
    target_card = state.card_catalog[card_no]
    for index, trigger_card_no in enumerate(player.trigger_zone):
        trigger_card = state.card_catalog[trigger_card_no]
        if _colors_match(trigger_card.color, target_card.color) and trigger_card.category in {"unit", "evolution"}:
            return index
    return None


def resolve_ability_events(
    state: MatchState,
    initial_events: list[AbilityEvent],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> None:
    pending_events = list(initial_events)
    while pending_events:
        event = pending_events.pop(0)
        _record_ability_event(state, event)
        triggered = collect_triggered_abilities(state, event)
        for triggered_ability in triggered:
            emitted = resolve_triggered_ability(state, event, triggered_ability, rng, choice_resolver)
            pending_events.extend(emitted)


def _record_ability_event(state: MatchState, event: AbilityEvent) -> None:
    state.event_log.append(
        {
            "event_no": state.next_event_no,
            "round_no": state.round_no,
            "turn_serial": state.turn_serial,
            "type": event.type,
            "player_id": event.player_id,
            "target_player_id": event.target_player_id,
            "source_unit_id": event.source_unit_id,
            "source_card_no": event.source_card_no,
            "amount": event.amount,
            "metadata": dict(event.metadata) if isinstance(event.metadata, dict) else None,
        }
    )
    state.next_event_no += 1


def collect_triggered_abilities(state: MatchState, event: AbilityEvent) -> list[dict[str, Any]]:
    triggered: list[dict[str, Any]] = []
    owner = state.players[event.player_id]

    for unit in owner.battlefield:
        if unit.unit_id == 0:
            unit.unit_id = _allocate_unit_id(state)
        if unit.unit_id != event.source_unit_id:
            continue
        triggered.extend(
            _build_triggered_abilities_for_card(
                state,
                unit.card_no,
                event.type,
                event.player_id,
                "battlefield",
                source_unit_id=unit.unit_id,
            )
        )

    if event.type == "unit_entered":
        for index, card_no in enumerate(owner.trigger_zone):
            triggered.extend(
                _build_triggered_abilities_for_card(
                    state,
                    card_no,
                    event.type,
                    event.player_id,
                    "trigger_zone",
                    source_index=index,
                )
            )

    if event.type in {"turn_end", "turn_start_draw", "turn_start_cp_set", "cards_drawn", "cp_changed", "life_changed"}:
        for unit in owner.battlefield:
            if unit.unit_id == 0:
                unit.unit_id = _allocate_unit_id(state)
            triggered.extend(
                _build_triggered_abilities_for_card(
                    state,
                    unit.card_no,
                    event.type,
                    event.player_id,
                    "battlefield",
                    source_unit_id=unit.unit_id,
                )
            )
    if event.type == "unit_destroyed" and event.source_card_no is not None:
        triggered.extend(
            _build_triggered_abilities_for_card(
                state,
                event.source_card_no,
                event.type,
                event.player_id,
                "graveyard",
                source_unit_id=event.source_unit_id,
            )
        )
    return triggered


def supports_ability_event(card_no: str, event_type: str) -> bool:
    key = (card_no, event_type)
    return key in ABILITY_REGISTRY


def resolve_triggered_ability(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    key = (
        triggered_ability["card_no"],
        event.type,
    )
    keyword_name = triggered_ability.get("keyword_name")
    if keyword_name == "不屈":
        return _resolve_untiring(state, event, triggered_ability, rng, choice_resolver)
    resolver = ABILITY_REGISTRY.get(key)
    if resolver is None:
        return []
    return resolver(state, event, triggered_ability, rng, choice_resolver)


def _build_triggered_abilities_for_card(
    state: MatchState,
    card_no: str,
    event_type: str,
    owner_id: PlayerId,
    source_zone: str,
    source_unit_id: int | None = None,
    source_index: int | None = None,
) -> list[dict[str, Any]]:
    triggered: list[dict[str, Any]] = []
    if (card_no, event_type) in ABILITY_REGISTRY:
        triggered.append(
            {
                "owner_id": owner_id,
                "source_zone": source_zone,
                "source_unit_id": source_unit_id,
                "source_index": source_index,
                "card_no": card_no,
            }
        )
    card = state.card_catalog[card_no]
    if event_type == "turn_end" and _has_ability_name(card, "不屈"):
        triggered.append(
            {
                "owner_id": owner_id,
                "source_zone": source_zone,
                "source_unit_id": source_unit_id,
                "source_index": source_index,
                "card_no": card_no,
                "keyword_name": "不屈",
            }
        )
    return triggered


def get_unit_bp(state: MatchState, unit: UnitState) -> int:
    card = state.card_catalog[unit.card_no]
    if not card.bp_by_level:
        return 0
    index = min(unit.level, len(card.bp_by_level)) - 1
    return (
        card.bp_by_level[index] * 1000
        + unit.permanent_bp_modifier
        + unit.temporary_bp_modifier
    )


def get_unit_current_bp(state: MatchState, unit: UnitState) -> int:
    return max(0, get_unit_bp(state, unit) - unit.current_damage)


def _clock_up_unit(state: MatchState, player_id: PlayerId, unit: UnitState) -> list[AbilityEvent]:
    if unit.level >= 3:
        return []
    previous_level = unit.level
    unit.level += 1
    unit.current_damage = 0
    _record_ability_event(
        state,
        AbilityEvent(
            type="unit_clock_up",
            player_id=player_id,
            source_unit_id=unit.unit_id,
            source_card_no=unit.card_no,
            metadata={"from_level": previous_level, "to_level": unit.level},
        ),
    )
    emitted: list[AbilityEvent] = []
    if unit.level >= 3:
        unit.exhausted = False
        unit.attack_restricted = False
        emitted.append(
            AbilityEvent(
                type="unit_overclocked",
                player_id=player_id,
                source_unit_id=unit.unit_id,
                target_player_id=get_opponent_id(player_id),
            )
        )
    return emitted


def _allocate_unit_id(state: MatchState) -> int:
    unit_id = state.next_unit_id
    state.next_unit_id += 1
    return unit_id


def _find_unit_by_id(state: MatchState, player_id: PlayerId, unit_id: int | None) -> UnitState | None:
    if unit_id is None:
        return None
    for unit in state.players[player_id].battlefield:
        if unit.unit_id == unit_id:
            return unit
    return None


def _has_ability_name(card: CardDefinition, ability_name: str) -> bool:
    return any(ability.name == ability_name for ability in card.abilities)


def _unit_has_ability(state: MatchState, unit: UnitState, ability_name: str) -> bool:
    return _has_ability_name(state.card_catalog[unit.card_no], ability_name)


def _find_first_enemy_unit(state: MatchState, player_id: PlayerId) -> UnitState | None:
    enemy_id = get_opponent_id(player_id)
    enemy_units = state.players[enemy_id].battlefield
    return enemy_units[0] if enemy_units else None


def _request_choice(
    player_id: PlayerId,
    payload: dict[str, Any],
    choice_resolver: ChoiceResolver | None,
) -> dict[str, Any]:
    available_choices = payload.get("available_choices", [])
    if not available_choices:
        return {"kind": "no_choice"}
    if choice_resolver is None:
        return available_choices[0]
    choice = choice_resolver(player_id, payload)
    return choice if choice else available_choices[0]


def _build_enemy_unit_choices(state: MatchState, player_id: PlayerId) -> list[dict[str, Any]]:
    enemy_id = get_opponent_id(player_id)
    choices: list[dict[str, Any]] = []
    for target_index, unit in enumerate(state.players[enemy_id].battlefield):
        card = state.card_catalog[unit.card_no]
        choices.append(
            {
                "kind": "choose_unit",
                "target_index": target_index,
                "card_no": unit.card_no,
                "card_name": card.name,
                "level": unit.level,
                "current_bp": get_unit_current_bp(state, unit),
                "current_damage": unit.current_damage,
                "choice_label": f"Target {card.name}",
                "choice_summary": f"Lv.{unit.level} / {get_unit_current_bp(state, unit)} BP / damage {unit.current_damage}",
                "choice_label_ja": f"{card.name}を対象にする",
                "choice_summary_ja": f"Lv.{unit.level} / BP {get_unit_current_bp(state, unit)} / ダメージ {unit.current_damage}",
            }
        )
    return choices


def _choose_enemy_unit(
    state: MatchState,
    player_id: PlayerId,
    source_card_no: str,
    prompt: str,
    choice_resolver: ChoiceResolver | None,
) -> UnitState | None:
    enemy_id = get_opponent_id(player_id)
    choices = _build_enemy_unit_choices(state, player_id)
    if not choices:
        return None
    selected = _request_choice(
        player_id,
        {
            "round_no": state.round_no,
            "turn_serial": state.turn_serial,
            "choice_kind": "target_unit",
            "prompt": prompt,
            "source_card_no": source_card_no,
            "available_choices": choices,
        },
        choice_resolver,
    )
    target_index = int(selected.get("target_index", 0))
    if target_index < 0 or target_index >= len(state.players[enemy_id].battlefield):
        target_index = 0
    return state.players[enemy_id].battlefield[target_index]


def _build_hand_card_choices(state: MatchState, player_id: PlayerId) -> list[dict[str, Any]]:
    choices: list[dict[str, Any]] = []
    for hand_index, hand_card_id in enumerate(state.players[player_id].hand):
        card_no, level = parse_hand_card_id(hand_card_id)
        card = state.card_catalog[card_no]
        choices.append(
            {
                "kind": "discard_hand",
                "hand_index": hand_index,
                "card_no": card_no,
                "card_name": card.name,
                "level": level,
                "choice_label": f"Discard {card.name}",
                "choice_summary": f"Hand index {hand_index} / Lv.{level}",
                "choice_label_ja": f"{card.name}を捨てる",
                "choice_summary_ja": f"手札位置 {hand_index} / Lv.{level}",
            }
        )
    return choices


def _choose_hand_card_to_discard(
    state: MatchState,
    player_id: PlayerId,
    source_card_no: str,
    prompt: str,
    choice_resolver: ChoiceResolver | None,
) -> int | None:
    choices = _build_hand_card_choices(state, player_id)
    if not choices:
        return None
    selected = _request_choice(
        player_id,
        {
            "round_no": state.round_no,
            "turn_serial": state.turn_serial,
            "choice_kind": "discard_hand",
            "prompt": prompt,
            "source_card_no": source_card_no,
            "available_choices": choices,
        },
        choice_resolver,
    )
    hand_index = int(selected.get("hand_index", 0))
    if hand_index < 0 or hand_index >= len(state.players[player_id].hand):
        hand_index = 0
    return hand_index


def _deal_damage_to_unit(
    state: MatchState,
    player_id: PlayerId,
    unit: UnitState | None,
    amount: int,
    source_card_no: str | None = None,
    source_unit_id: int | None = None,
    effect_name: str | None = None,
    rng: random.Random | None = None,
    choice_resolver: ChoiceResolver | None = None,
) -> None:
    if unit is None:
        return
    unit.current_damage += amount
    _record_ability_event(
        state,
        AbilityEvent(
            type="ability_damage_dealt_to_unit",
            player_id=player_id,
            target_player_id=player_id,
            source_unit_id=source_unit_id,
            source_card_no=source_card_no,
            amount=amount,
            metadata={
                "target_card_no": unit.card_no,
                "current_damage": unit.current_damage,
                "current_bp": get_unit_current_bp(state, unit),
                "effect_name": effect_name,
            },
        ),
    )
    _destroy_broken_units(state, player_id, rng or random.Random(0), choice_resolver)


def _draw_cards_by_category(
    state: MatchState,
    player_id: PlayerId,
    category: str,
    count: int,
) -> list[str]:
    player = state.players[player_id]
    if count <= 0 or len(player.hand) >= state.regulation.hand_size_limit:
        return []
    matches: list[str] = []
    remaining: list[str] = []
    for card_no in player.draw_pile:
        if len(matches) < count and state.card_catalog[card_no].category == category:
            matches.append(card_no)
        else:
            remaining.append(card_no)
    player.draw_pile = remaining
    actual_matches = matches[: max(0, state.regulation.hand_size_limit - len(player.hand))]
    player.hand.extend(actual_matches)
    _record_draw_card_moves(state, player_id, actual_matches, reason=f"draw_by_category:{category}")
    return actual_matches


def _draw_random_cards_by_category(
    state: MatchState,
    player_id: PlayerId,
    category: str,
    count: int,
    rng: random.Random,
) -> list[str]:
    player = state.players[player_id]
    if count <= 0 or len(player.hand) >= state.regulation.hand_size_limit:
        return []

    matching_indexes = [
        index for index, card_no in enumerate(player.draw_pile) if state.card_catalog[card_no].category == category
    ]
    actual_count = min(count, len(matching_indexes), state.regulation.hand_size_limit - len(player.hand))
    if actual_count <= 0:
        return []

    selected_indexes = set(rng.sample(matching_indexes, actual_count))
    drawn_cards: list[str] = []
    remaining_cards: list[str] = []
    for index, card_no in enumerate(player.draw_pile):
        if index in selected_indexes:
            drawn_cards.append(card_no)
        else:
            remaining_cards.append(card_no)
    player.draw_pile = remaining_cards
    player.hand.extend(drawn_cards)
    _record_draw_card_moves(state, player_id, drawn_cards, reason=f"draw_random_by_category:{category}")
    return drawn_cards


def _count_drawable_cards_by_category(state: MatchState, player_id: PlayerId, category: str) -> int:
    player = state.players[player_id]
    if len(player.hand) >= state.regulation.hand_size_limit:
        return 0
    return sum(1 for card_no in player.draw_pile if state.card_catalog[card_no].category == category)


def _can_draw_any_card(state: MatchState, player_id: PlayerId) -> bool:
    player = state.players[player_id]
    return len(player.hand) < state.regulation.hand_size_limit and bool(player.draw_pile)


def _consume_trigger_card(
    state: MatchState,
    player_id: PlayerId,
    triggered_ability: dict[str, Any],
) -> bool:
    player = state.players[player_id]
    source_index = triggered_ability.get("source_index")
    card_no = triggered_ability["card_no"]
    if isinstance(source_index, int) and 0 <= source_index < len(player.trigger_zone):
        if player.trigger_zone[source_index] == card_no:
            used_card_no = player.trigger_zone.pop(source_index)
            player.discard_pile.insert(0, used_card_no)
            _record_ability_event(
                state,
                AbilityEvent(
                    type="card_moved",
                    player_id=player_id,
                    source_card_no=used_card_no,
                    metadata={"from_zone": "trigger_zone", "to_zone": "discard", "reason": "trigger_resolution"},
                ),
            )
            _record_ability_event(
                state,
                AbilityEvent(
                    type="trigger_used",
                    player_id=player_id,
                    target_player_id=player_id,
                    source_card_no=used_card_no,
                ),
            )
            return True
    if card_no in player.trigger_zone:
        player.trigger_zone.remove(card_no)
        player.discard_pile.insert(0, card_no)
        _record_ability_event(
            state,
            AbilityEvent(
                type="card_moved",
                player_id=player_id,
                source_card_no=card_no,
                metadata={"from_zone": "trigger_zone", "to_zone": "discard", "reason": "trigger_resolution"},
            ),
        )
        _record_ability_event(
            state,
            AbilityEvent(
                type="trigger_used",
                player_id=player_id,
                target_player_id=player_id,
                source_card_no=card_no,
            ),
        )
        return True
    return False


def _discard_first_card_from_hand(state: MatchState, player_id: PlayerId) -> bool:
    player = state.players[player_id]
    if not player.hand:
        return False
    hand_card_id = player.hand.pop(0)
    card_no, _level = parse_hand_card_id(hand_card_id)
    player.discard_pile.insert(0, card_no)
    _record_ability_event(
        state,
        AbilityEvent(
            type="card_moved",
            player_id=player_id,
            source_card_no=card_no,
            metadata={"from_zone": "hand", "to_zone": "discard", "reason": "discard_effect"},
        ),
    )
    return True


def _discard_hand_card_by_index(state: MatchState, player_id: PlayerId, hand_index: int) -> bool:
    player = state.players[player_id]
    if hand_index < 0 or hand_index >= len(player.hand):
        return False
    hand_card_id = player.hand.pop(hand_index)
    card_no, _level = parse_hand_card_id(hand_card_id)
    player.discard_pile.insert(0, card_no)
    _record_ability_event(
        state,
        AbilityEvent(
            type="card_moved",
            player_id=player_id,
            source_card_no=card_no,
            metadata={"from_zone": "hand", "to_zone": "discard", "reason": "discard_effect"},
        ),
    )
    return True


def _destroy_random_trigger_cards(state: MatchState, player_id: PlayerId, count: int, rng: random.Random) -> None:
    opponent = state.players[get_opponent_id(player_id)]
    for _ in range(min(count, len(opponent.trigger_zone))):
        chosen_index = rng.randrange(len(opponent.trigger_zone))
        card_no = opponent.trigger_zone.pop(chosen_index)
        opponent.discard_pile.insert(0, card_no)
        _record_ability_event(
            state,
            AbilityEvent(
                type="card_moved",
                player_id=opponent.player_id,
                source_card_no=card_no,
                metadata={"from_zone": "trigger_zone", "to_zone": "discard", "reason": "trigger_destroyed"},
            ),
        )


def _can_use_intercept_card(
    state: MatchState,
    player_id: PlayerId,
    card_no: str,
    own_unit_is_attacker: bool,
) -> bool:
    return _get_intercept_disabled_reason(state, player_id, card_no, own_unit_is_attacker) is None


def _get_intercept_disabled_reason(
    state: MatchState,
    player_id: PlayerId,
    card_no: str,
    own_unit_is_attacker: bool,
) -> str | None:
    player = state.players[player_id]
    card = state.card_catalog[card_no]
    if card.category != "intercept":
        return "not_intercept_card"
    if (card.cp or 0) > player.current_cp:
        return "not_enough_cp"
    if not _is_colorless(card.color) and not any(
        _colors_match(state.card_catalog[unit.card_no].color, card.color) for unit in player.battlefield
    ):
        return "color_requirement_not_met"
    if card_no == "1-0-081" and not own_unit_is_attacker:
        return "attacker_only"
    if card_no not in {"1-0-065", "1-0-074", "1-0-081", "1-0-091", "1-0-096"}:
        return "effect_not_implemented"
    return None


def _is_colorless(color: str) -> bool:
    return _normalize_color(color) == "colorless"


def _normalize_color(color: str) -> str:
    stripped = color.strip()
    lowered = stripped.lower()
    aliases = {
        "red": "red",
        "赤": "red",
        "blue": "blue",
        "青": "blue",
        "green": "green",
        "緑": "green",
        "yellow": "yellow",
        "黄": "yellow",
        "colorless": "colorless",
        "none": "colorless",
        "無": "colorless",
    }
    if lowered in aliases:
        return aliases[lowered]
    if stripped in aliases:
        return aliases[stripped]
    if any(ord(ch) == 28961 for ch in color):
        return "colorless"
    return lowered


def _colors_match(left: str, right: str) -> bool:
    return _normalize_color(left) == _normalize_color(right)


def _get_disabled_reason_message(disabled_reason: str) -> str:
    messages = {
        "unit_exhausted": "行動済みユニットのため選べません。",
        "not_enough_cp": "CPが足りないため使えません。",
        "color_requirement_not_met": "同属性ユニットが場にいないため使えません。",
        "attacker_only": "攻撃側のときだけ使えます。",
        "effect_not_implemented": "この効果はまだ未実装です。",
        "not_intercept_card": "インターセプトカードではありません。",
    }
    return messages.get(disabled_reason, "この選択肢は現在選べません。")


def _get_intercept_target(card_no: str, own_unit_is_attacker: bool) -> str:
    if card_no == "1-0-065":
        return "enemy_unit"
    if card_no == "1-0-081" and own_unit_is_attacker:
        return "own_unit"
    return "own_unit"


def _get_target_label_ja(target: str) -> str:
    labels = {
        "own_unit": "自分ユニット",
        "enemy_unit": "相手ユニット",
    }
    return labels.get(target, target)


def _build_battle_choice_payload(
    state: MatchState,
    own_unit: UnitState,
    enemy_unit: UnitState,
    own_unit_is_attacker: bool,
) -> dict[str, Any]:
    return {
        "own_unit": {
            "card_no": own_unit.card_no,
            "card_name": state.card_catalog[own_unit.card_no].name,
            "level": own_unit.level,
            "current_bp": get_unit_current_bp(state, own_unit),
            "current_damage": own_unit.current_damage,
            "is_attacker": own_unit_is_attacker,
        },
        "opposing_unit": {
            "card_no": enemy_unit.card_no,
            "card_name": state.card_catalog[enemy_unit.card_no].name,
            "level": enemy_unit.level,
            "current_bp": get_unit_current_bp(state, enemy_unit),
            "current_damage": enemy_unit.current_damage,
            "is_attacker": not own_unit_is_attacker,
        },
    }


def _resolve_intercept_effect(
    state: MatchState,
    player_id: PlayerId,
    card_no: str,
    own_unit: UnitState,
    enemy_unit: UnitState,
    own_unit_is_attacker: bool,
) -> None:
    if card_no == "1-0-065":
        enemy_unit.temporary_bp_modifier -= 2000
        _record_ability_event(
            state,
            AbilityEvent(
                type="unit_bp_modified",
                player_id=get_opponent_id(player_id),
                source_unit_id=enemy_unit.unit_id,
                source_card_no=card_no,
                amount=-2000,
                metadata={"target_card_no": enemy_unit.card_no, "current_bp": get_unit_current_bp(state, enemy_unit)},
            ),
        )
        return
    if card_no == "1-0-074":
        own_unit.temporary_bp_modifier += 2000
        _record_ability_event(
            state,
            AbilityEvent(
                type="unit_bp_modified",
                player_id=player_id,
                source_unit_id=own_unit.unit_id,
                source_card_no=card_no,
                amount=2000,
                metadata={"target_card_no": own_unit.card_no, "current_bp": get_unit_current_bp(state, own_unit)},
            ),
        )
        return
    if card_no == "1-0-081" and own_unit_is_attacker:
        own_unit.temporary_bp_modifier += 3000
        _record_ability_event(
            state,
            AbilityEvent(
                type="unit_bp_modified",
                player_id=player_id,
                source_unit_id=own_unit.unit_id,
                source_card_no=card_no,
                amount=3000,
                metadata={"target_card_no": own_unit.card_no, "current_bp": get_unit_current_bp(state, own_unit)},
            ),
        )
        return
    if card_no == "1-0-091":
        own_unit.temporary_bp_modifier += 7000
        _record_ability_event(
            state,
            AbilityEvent(
                type="unit_bp_modified",
                player_id=player_id,
                source_unit_id=own_unit.unit_id,
                source_card_no=card_no,
                amount=7000,
                metadata={"target_card_no": own_unit.card_no, "current_bp": get_unit_current_bp(state, own_unit)},
            ),
        )
        state.players[player_id].life -= 1
        _record_ability_event(
            state,
            AbilityEvent(
                type="life_changed",
                player_id=player_id,
                target_player_id=player_id,
                source_card_no=card_no,
                amount=-1,
            ),
        )
        _update_winner_by_life(state)
        return
    if card_no == "1-0-096":
        own_unit.temporary_bp_modifier += 3000
        _record_ability_event(
            state,
            AbilityEvent(
                type="unit_bp_modified",
                player_id=player_id,
                source_unit_id=own_unit.unit_id,
                source_card_no=card_no,
                amount=3000,
                metadata={"target_card_no": own_unit.card_no, "current_bp": get_unit_current_bp(state, own_unit)},
            ),
        )


def build_reactive_intercept_choice_payload(
    state: MatchState,
    player_id: PlayerId,
    event_type: str,
) -> dict[str, Any]:
    player = state.players[player_id]
    actions: list[dict[str, Any]] = [
        {
            "kind": "no_intercept",
            "choice_label": "Pass intercept",
            "choice_summary": "Do not use an intercept in this step.",
            "choice_label_ja": "インターセプトしない",
            "choice_summary_ja": "このタイミングではインターセプトを使いません。",
        }
    ]
    unavailable_choices: list[dict[str, Any]] = []
    for trigger_index, card_no in enumerate(player.trigger_zone):
        card = state.card_catalog[card_no]
        if card.category != "intercept":
            continue
        if not _supports_reactive_intercept_event(card_no, event_type):
            continue
        if (card.cp or 0) > player.current_cp:
            unavailable_choices.append(_build_unavailable_intercept_choice(card, trigger_index, "not_enough_cp"))
            continue
        if not _is_colorless(card.color) and not any(
            _colors_match(state.card_catalog[unit.card_no].color, card.color) for unit in player.battlefield
        ):
            unavailable_choices.append(
                _build_unavailable_intercept_choice(card, trigger_index, "color_requirement_not_met")
            )
            continue
        target_choices = _build_reactive_intercept_target_choices(state, player_id, card_no, trigger_index, event_type)
        if not target_choices:
            unavailable_choices.append(_build_unavailable_intercept_choice(card, trigger_index, "no_valid_target"))
            continue
        actions.extend(target_choices)
    return {
        "round_no": state.round_no,
        "turn_serial": state.turn_serial,
        "choice_kind": "intercept",
        "prompt": "Choose an intercept or pass.",
        "available_choices": actions,
        "unavailable_choices": unavailable_choices,
        "intercept_event_type": event_type,
    }


def apply_reactive_intercept_action(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    event_type: str,
    rng: random.Random | None = None,
    choice_resolver: ChoiceResolver | None = None,
) -> None:
    if action.get("kind") != "use_intercept":
        return
    if rng is None:
        rng = random.Random(0)
    player = state.players[player_id]
    trigger_index = int(action["trigger_index"])
    if trigger_index < 0 or trigger_index >= len(player.trigger_zone):
        raise ValueError(f"invalid trigger index: {trigger_index}")
    card_no = player.trigger_zone[trigger_index]
    if not _supports_reactive_intercept_event(card_no, event_type):
        raise ValueError(f"intercept does not support event: {card_no} {event_type}")
    card = state.card_catalog[card_no]
    if (card.cp or 0) > player.current_cp:
        raise ValueError("not enough cp")
    player.current_cp -= card.cp or 0
    used_card_no = player.trigger_zone.pop(trigger_index)
    player.discard_pile.insert(0, used_card_no)
    _record_ability_event(
        state,
        AbilityEvent(
            type="card_moved",
            player_id=player_id,
            source_card_no=used_card_no,
            metadata={"from_zone": "trigger_zone", "to_zone": "discard", "reason": "intercept_resolution"},
        ),
    )
    _record_ability_event(
        state,
        AbilityEvent(
            type="intercept_used",
            player_id=player_id,
            target_player_id=player_id,
            source_card_no=used_card_no,
        ),
    )
    _resolve_reactive_intercept_effect(state, player_id, action, event_type, rng, choice_resolver)
    _record_card_use(state, card_no)


def _resolve_happaloid_enter(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    drawn_cards = _draw_card_nos(state.players[event.player_id], 1, rng, state.regulation.hand_size_limit)
    if not drawn_cards:
        return []
    return [
        AbilityEvent(
            type="cards_drawn",
            player_id=event.player_id,
            target_player_id=event.player_id,
            source_card_no=triggered_ability["card_no"],
            amount=len(drawn_cards),
            metadata={"drawn_card_nos": list(drawn_cards)},
        )
    ]


def _resolve_ririmu_enter(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    enemy_id = get_opponent_id(event.player_id)
    target = _choose_enemy_unit(
        state,
        event.player_id,
        triggered_ability["card_no"],
        "Choose an enemy unit to deal 4000 damage.",
        choice_resolver,
    )
    _deal_damage_to_unit(state, enemy_id, target, 4000)
    return []


def _resolve_barbatos_enter(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    enemy_unit = _choose_enemy_unit(
        state,
        event.player_id,
        triggered_ability["card_no"],
        "Choose an enemy unit to reduce base BP by 4000.",
        choice_resolver,
    )
    if enemy_unit is not None:
        enemy_unit.permanent_bp_modifier -= 4000
        _destroy_broken_units(state, get_opponent_id(event.player_id))
    return []


def _resolve_swordfighter_attack(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    source = _find_unit_by_id(state, event.player_id, event.source_unit_id)
    if source is not None:
        source.temporary_bp_modifier += 2000
    return []


def _resolve_lancer_attack(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    enemy_id = get_opponent_id(event.player_id)
    target = _choose_enemy_unit(
        state,
        event.player_id,
        triggered_ability["card_no"],
        "Choose an enemy unit to deal 1000 damage.",
        choice_resolver,
    )
    _deal_damage_to_unit(
        state,
        enemy_id,
        target,
        1000,
        source_card_no=triggered_ability["card_no"],
        source_unit_id=event.source_unit_id,
        effect_name="ダメージブレイク",
        rng=rng,
        choice_resolver=choice_resolver,
    )
    return []


def _resolve_shiranui_attack(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    source = _find_unit_by_id(state, event.player_id, event.source_unit_id)
    discard_index = _choose_hand_card_to_discard(
        state,
        event.player_id,
        triggered_ability["card_no"],
        "Choose a hand card to discard for the attack bonus.",
        choice_resolver,
    )
    if source is not None and discard_index is not None and _discard_hand_card_by_index(state, event.player_id, discard_index):
        source.temporary_bp_modifier += 4000
    return []


def _resolve_shiranui_player_attack_success(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    _destroy_random_trigger_cards(state, event.player_id, 2, rng)
    return []


def _resolve_ririmu_attack_trigger_loss(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    _destroy_random_trigger_cards(state, event.player_id, 1, rng)
    return []


def _resolve_goliath_overclock(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    opponent = state.players[get_opponent_id(event.player_id)]
    opponent.life -= 1
    _update_winner_by_life(state)
    return [
        AbilityEvent(
            type="life_changed",
            player_id=opponent.player_id,
            target_player_id=opponent.player_id,
            source_card_no=triggered_ability["card_no"],
            amount=-1,
        )
    ]


def _resolve_draw_trigger_cards(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    if _count_drawable_cards_by_category(state, event.player_id, "trigger") <= 0:
        return []
    if not _consume_trigger_card(state, event.player_id, triggered_ability):
        return []
    drawn_cards = _draw_cards_by_category(state, event.player_id, "trigger", 2)
    if not drawn_cards:
        return []
    return [
        AbilityEvent(
            type="cards_drawn",
            player_id=event.player_id,
            target_player_id=event.player_id,
            source_card_no=triggered_ability["card_no"],
            amount=len(drawn_cards),
            metadata={"drawn_card_nos": list(drawn_cards)},
        )
    ]


def _resolve_draw_intercept_card(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    if _count_drawable_cards_by_category(state, event.player_id, "intercept") <= 0:
        return []
    if not _consume_trigger_card(state, event.player_id, triggered_ability):
        return []
    drawn_cards = _draw_cards_by_category(state, event.player_id, "intercept", 1)
    if not drawn_cards:
        return []
    return [
        AbilityEvent(
            type="cards_drawn",
            player_id=event.player_id,
            target_player_id=event.player_id,
            source_card_no=triggered_ability["card_no"],
            amount=len(drawn_cards),
            metadata={"drawn_card_nos": list(drawn_cards)},
        )
    ]


def _resolve_draw_any_card(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    if not _can_draw_any_card(state, event.player_id):
        return []
    if not _consume_trigger_card(state, event.player_id, triggered_ability):
        return []
    drawn_cards = _draw_card_nos(state.players[event.player_id], 1, rng, state.regulation.hand_size_limit)
    if not drawn_cards:
        return []
    return [
        AbilityEvent(
            type="cards_drawn",
            player_id=event.player_id,
            target_player_id=event.player_id,
            source_card_no=triggered_ability["card_no"],
            amount=len(drawn_cards),
            metadata={"drawn_card_nos": list(drawn_cards)},
        )
    ]


def _resolve_untiring(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    source = _find_unit_by_id(state, event.player_id, triggered_ability.get("source_unit_id"))
    if source is not None:
        source.exhausted = False
    return []


def _resolve_revive_overclock(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    chosen = _choose_discard_card(
        state,
        event.player_id,
        triggered_ability["card_no"],
        "Choose a discard pile card to return to hand.",
        choice_resolver,
        category=None,
    )
    if chosen is not None:
        _move_discard_to_hand(state, event.player_id, chosen, reason="revive")
    return []


def _resolve_revive_unit_enter(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    player = state.players[event.player_id]
    unit_indexes = [
        index
        for index, card_no in enumerate(player.discard_pile)
        if state.card_catalog[card_no].category == "unit"
    ]
    if not unit_indexes:
        return []
    chosen_index = rng.choice(unit_indexes)
    _move_discard_to_hand(state, event.player_id, chosen_index, reason="revive")
    return []


def _resolve_destroy_high_level_units(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    enemy_id = get_opponent_id(event.player_id)
    enemy = state.players[enemy_id]
    destroy_indexes = [
        index
        for index, unit in enumerate(enemy.battlefield)
        if unit.level >= 2
    ]
    for destroy_index in reversed(destroy_indexes):
        _destroy_unit_by_index(state, enemy_id, destroy_index, rng, choice_resolver)
    return []


def _resolve_charge_enter(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    player = state.players[event.player_id]
    previous_cp = player.current_cp
    player.current_cp = min(player.current_cp + 2, state.regulation.max_cp_per_round)
    gained = player.current_cp - previous_cp
    if gained <= 0:
        return []
    return [
        AbilityEvent(
            type="cp_changed",
            player_id=event.player_id,
            target_player_id=event.player_id,
            source_card_no=triggered_ability["card_no"],
            amount=gained,
        )
    ]


def _resolve_grind_draw_enter(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    source = _find_unit_by_id(state, event.player_id, event.source_unit_id)
    if source is None:
        return []
    for used_card_no in state.used_card_nos_this_turn:
        if used_card_no == source.card_no:
            continue
        used_card = state.card_catalog[used_card_no]
        if _normalize_color(used_card.color) == "green" and (used_card.cp or 0) >= 2:
            drawn_cards = _draw_card_nos(state.players[event.player_id], 1, rng, state.regulation.hand_size_limit)
            if drawn_cards:
                return [
                    AbilityEvent(
                        type="cards_drawn",
                        player_id=event.player_id,
                        target_player_id=event.player_id,
                        source_card_no=triggered_ability["card_no"],
                        amount=len(drawn_cards),
                        metadata={"drawn_card_nos": list(drawn_cards)},
                    )
                ]
            break
    return []


def _resolve_grind_beetle_enter(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    emitted: list[AbilityEvent] = []
    emitted.extend(_resolve_charge_enter(state, event, triggered_ability, rng, choice_resolver))
    emitted.extend(_resolve_grind_draw_enter(state, event, triggered_ability, rng, choice_resolver))
    return emitted


def _resolve_blocker_bonus(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    source = _find_unit_by_id(state, event.player_id, event.source_unit_id)
    if source is not None:
        source.temporary_bp_modifier += 2000
    return []


def _resolve_lost_on_destroy(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    opponent = state.players[get_opponent_id(event.player_id)]
    if not opponent.hand:
        return []
    chosen_index = rng.randrange(len(opponent.hand))
    _discard_hand_card_by_index(state, opponent.player_id, chosen_index)
    return []


def _resolve_intercept_draw_on_destroy(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> list[AbilityEvent]:
    drawn_cards = _draw_random_cards_by_category(state, event.player_id, "intercept", 1, rng)
    if not drawn_cards:
        return []
    return [
        AbilityEvent(
            type="cards_drawn",
            player_id=event.player_id,
            target_player_id=event.player_id,
            source_card_no=triggered_ability["card_no"],
            amount=len(drawn_cards),
            metadata={"drawn_card_nos": list(drawn_cards)},
        )
    ]


def _build_unavailable_intercept_choice(card: CardDefinition, trigger_index: int, reason: str) -> dict[str, Any]:
    return {
        "kind": "use_intercept",
        "trigger_index": trigger_index,
        "card_no": card.card_no,
        "card_name": card.name,
        "cost": card.cp or 0,
        "disabled_reason": reason,
        "disabled_reason_message": _get_disabled_reason_message(reason),
        "choice_label": f"Use {card.name}",
        "choice_summary": f"Unavailable: {reason}",
        "choice_label_ja": f"{card.name}を使う",
        "choice_summary_ja": _get_disabled_reason_message(reason),
    }


def _supports_reactive_intercept_event(card_no: str, event_type: str) -> bool:
    supported = {
        ("1-0-069", "unit_entered"),
        ("1-0-089", "unit_attacked"),
        ("1-0-092", "unit_destroyed"),
    }
    return (card_no, event_type) in supported


def _build_reactive_intercept_target_choices(
    state: MatchState,
    player_id: PlayerId,
    card_no: str,
    trigger_index: int,
    event_type: str,
) -> list[dict[str, Any]]:
    enemy_id = get_opponent_id(player_id)
    enemy_units = state.players[enemy_id].battlefield
    card = state.card_catalog[card_no]
    choices: list[dict[str, Any]] = []
    for target_index, unit in enumerate(enemy_units):
        if card_no == "1-0-089" and unit.level < 2:
            continue
        target_card = state.card_catalog[unit.card_no]
        choices.append(
            {
                "kind": "use_intercept",
                "trigger_index": trigger_index,
                "card_no": card_no,
                "card_name": card.name,
                "cost": card.cp or 0,
                "target_index": target_index,
                "target_card_no": unit.card_no,
                "target_card_name": target_card.name,
                "choice_label": f"Use {card.name}",
                "choice_summary": f"Target {target_card.name}",
                "choice_label_ja": f"{card.name}を使う",
                "choice_summary_ja": f"対象 {target_card.name}",
                "intercept_event_type": event_type,
            }
        )
    return choices


def _resolve_reactive_intercept_effect(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    event_type: str,
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> None:
    enemy_id = get_opponent_id(player_id)
    card_no = action["card_no"]
    if card_no == "1-0-069":
        target = _get_battlefield_unit_by_index(state, enemy_id, int(action["target_index"]))
        if target is None:
            return
        previous_level = target.level
        target.level = 3
        target.current_damage = 0
        _record_ability_event(
            state,
            AbilityEvent(
                type="unit_level_changed",
                player_id=enemy_id,
                source_unit_id=target.unit_id,
                source_card_no=target.card_no,
                metadata={"from_level": previous_level, "to_level": 3, "reason": "effect"},
            ),
        )
        return
    if card_no in {"1-0-089", "1-0-092"}:
        _destroy_unit_by_index(state, enemy_id, int(action["target_index"]), rng, choice_resolver)
        return


def _get_battlefield_unit_by_index(state: MatchState, player_id: PlayerId, index: int) -> UnitState | None:
    battlefield = state.players[player_id].battlefield
    if index < 0 or index >= len(battlefield):
        return None
    return battlefield[index]


def _destroy_unit_by_index(
    state: MatchState,
    player_id: PlayerId,
    target_index: int,
    rng: random.Random,
    choice_resolver: ChoiceResolver | None = None,
) -> None:
    player = state.players[player_id]
    if target_index < 0 or target_index >= len(player.battlefield):
        return
    target = player.battlefield.pop(target_index)
    player.discard_pile.insert(0, target.card_no)
    _record_ability_event(
        state,
        AbilityEvent(
            type="unit_sent_to_discard",
            player_id=player_id,
            source_unit_id=target.unit_id,
            source_card_no=target.card_no,
            metadata={"reason": "effect"},
        ),
    )
    resolve_ability_events(
        state,
        [
            AbilityEvent(
                type="unit_destroyed",
                player_id=player_id,
                source_unit_id=target.unit_id,
                source_card_no=target.card_no,
                target_player_id=get_opponent_id(player_id),
            )
        ],
        rng,
        choice_resolver,
    )


def _build_discard_choices(state: MatchState, player_id: PlayerId, category: str | None) -> list[dict[str, Any]]:
    choices: list[dict[str, Any]] = []
    player = state.players[player_id]
    for discard_index, card_no in enumerate(player.discard_pile):
        card = state.card_catalog[card_no]
        if category is not None and card.category != category:
            continue
        choices.append(
            {
                "kind": "choose_discard",
                "discard_index": discard_index,
                "card_no": card_no,
                "card_name": card.name,
                "choice_label": f"Return {card.name}",
                "choice_summary": f"Discard index {discard_index}",
                "choice_label_ja": f"{card.name}を回収",
                "choice_summary_ja": f"捨札位置 {discard_index}",
            }
        )
    return choices


def _choose_discard_card(
    state: MatchState,
    player_id: PlayerId,
    source_card_no: str,
    prompt: str,
    choice_resolver: ChoiceResolver | None,
    category: str | None,
) -> int | None:
    choices = _build_discard_choices(state, player_id, category)
    if not choices:
        return None
    selected = _request_choice(
        player_id,
        {
            "round_no": state.round_no,
            "turn_serial": state.turn_serial,
            "choice_kind": "discard_pile",
            "prompt": prompt,
            "source_card_no": source_card_no,
            "available_choices": choices,
        },
        choice_resolver,
    )
    discard_index = int(selected.get("discard_index", 0))
    if discard_index < 0 or discard_index >= len(state.players[player_id].discard_pile):
        return None
    return discard_index


def _move_discard_to_hand(state: MatchState, player_id: PlayerId, discard_index: int, reason: str = "recover") -> bool:
    player = state.players[player_id]
    if discard_index < 0 or discard_index >= len(player.discard_pile):
        return False
    if len(player.hand) >= state.regulation.hand_size_limit:
        return False
    card_no = player.discard_pile.pop(discard_index)
    player.hand.append(card_no)
    _record_ability_event(
        state,
        AbilityEvent(
            type="card_moved",
            player_id=player_id,
            source_card_no=card_no,
            metadata={"from_zone": "discard", "to_zone": "hand", "reason": reason},
        ),
    )
    return True


ABILITY_REGISTRY: dict[tuple[str, str], Any] = {
    ("1-0-031", "unit_overclocked"): _resolve_revive_overclock,
    ("1-0-033", "unit_entered"): _resolve_revive_unit_enter,
    ("1-0-039", "unit_entered"): _resolve_destroy_high_level_units,
    ("1-0-040", "unit_entered"): _resolve_happaloid_enter,
    ("1-0-043", "unit_entered"): _resolve_grind_beetle_enter,
    ("1-0-012", "unit_entered"): _resolve_ririmu_enter,
    ("1-0-051", "unit_entered"): _resolve_barbatos_enter,
    ("1-0-002", "unit_attacked"): _resolve_swordfighter_attack,
    ("1-0-004", "unit_attacked"): _resolve_lancer_attack,
    ("1-0-010", "unit_attacked"): _resolve_shiranui_attack,
    ("1-0-010", "player_attack_success"): _resolve_shiranui_player_attack_success,
    ("1-0-012", "unit_attacked"): _resolve_ririmu_attack_trigger_loss,
    ("1-0-007", "unit_overclocked"): _resolve_goliath_overclock,
    ("1-0-057", "unit_entered"): _resolve_draw_trigger_cards,
    ("1-0-061", "unit_entered"): _resolve_draw_intercept_card,
    ("1-0-062", "unit_entered"): _resolve_draw_any_card,
    ("1-0-045", "unit_blocked"): _resolve_blocker_bonus,
    ("1-0-027", "unit_destroyed"): _resolve_lost_on_destroy,
    ("1-0-029", "unit_destroyed"): _resolve_intercept_draw_on_destroy,
    ("1-0-044", "turn_end"): _resolve_untiring,
    ("1-0-048", "turn_end"): _resolve_untiring,
}

def parse_hand_card_id(hand_card_id: str) -> tuple[str, int]:
    if "@L" not in hand_card_id:
        return hand_card_id, 1
    card_no, level_text = hand_card_id.rsplit("@L", 1)
    return card_no, int(level_text)


def format_hand_card_id(card_no: str, level: int) -> str:
    if level <= 1:
        return card_no
    return f"{card_no}@L{level}"


def _serialize_unit(unit: UnitState, state: MatchState | None) -> dict[str, Any]:
    data = {
        "card_no": unit.card_no,
        "level": unit.level,
        "exhausted": unit.exhausted,
        "attack_restricted": unit.attack_restricted,
        "current_damage": unit.current_damage,
    }
    if state is not None:
        data["current_bp"] = get_unit_current_bp(state, unit)
    return data


def _destroy_broken_units(
    state: MatchState,
    player_id: PlayerId,
    rng: random.Random | None = None,
    choice_resolver: ChoiceResolver | None = None,
) -> None:
    player = state.players[player_id]
    survivors: list[UnitState] = []
    destroyed_units: list[UnitState] = []
    for unit in player.battlefield:
        if unit.current_damage >= get_unit_bp(state, unit):
            player.discard_pile.insert(0, unit.card_no)
            _record_ability_event(
                state,
                AbilityEvent(
                    type="unit_sent_to_discard",
                    player_id=player_id,
                    source_unit_id=unit.unit_id,
                    source_card_no=unit.card_no,
                    metadata={"reason": "battle"},
                ),
            )
            destroyed_units.append(unit)
        else:
            survivors.append(unit)
    player.battlefield = survivors
    if destroyed_units:
        resolve_ability_events(
            state,
            [
                AbilityEvent(
                    type="unit_destroyed",
                    player_id=player_id,
                    source_unit_id=unit.unit_id,
                    source_card_no=unit.card_no,
                    target_player_id=get_opponent_id(player_id),
                )
                for unit in destroyed_units
            ],
            rng or random.Random(0),
            choice_resolver,
        )


def _record_card_use(state: MatchState, card_no: str) -> None:
    state.used_card_nos_this_turn.append(card_no)


def _set_match_outcome(state: MatchState, winner: str, reason: str) -> None:
    if state.winner == winner and state.ended_reason == reason:
        return
    if state.winner is not None and state.ended_reason is not None:
        return
    state.winner = winner
    state.ended_reason = reason
    _record_ability_event(
        state,
        AbilityEvent(
            type="match_ended",
            player_id=winner if winner in {"P1", "P2"} else "P1",
            target_player_id=winner if winner in {"P1", "P2", "draw"} else None,
            metadata={"winner": winner, "reason": reason},
        ),
    )


def _update_winner_by_life(state: MatchState) -> None:
    first_life = state.players["P1"].life
    second_life = state.players["P2"].life
    if first_life <= 0 and second_life <= 0:
        _set_match_outcome(state, "draw", "life_zero")
    elif first_life <= 0:
        _set_match_outcome(state, "P2", "life_zero")
    elif second_life <= 0:
        _set_match_outcome(state, "P1", "life_zero")
