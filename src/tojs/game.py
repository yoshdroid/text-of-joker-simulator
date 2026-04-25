from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .models import CardDefinition, Regulation


PlayerId = str


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


@dataclass(frozen=True)
class AbilityEvent:
    type: str
    player_id: PlayerId
    source_unit_id: int | None = None
    target_player_id: PlayerId | None = None


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
    player = state.players[player_id]
    draw_count = get_scheduled_draw_count(state, player)
    cp_value = get_scheduled_cp(state, player)
    draw_cards(player, draw_count, rng, state.regulation.hand_size_limit)
    player.current_cp = min(cp_value, state.regulation.max_cp_per_round)
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
    if state.turn_player_id == "P2":
        state.round_no += 1

    if state.round_no > state.regulation.round_count:
        first_life = state.players["P1"].life
        second_life = state.players["P2"].life
        if first_life > second_life:
            state.winner = "P1"
        elif second_life > first_life:
            state.winner = "P2"
        else:
            state.winner = "draw"
        state.ended_reason = "round_limit"
        return

    start_turn(state, next_player_id, rng)

def apply_action(state: MatchState, player_id: PlayerId, action: dict[str, Any], rng: random.Random) -> None:
    if player_id != state.turn_player_id:
        raise ValueError(f"not turn player: {player_id}")
    kind = action.get("kind")
    if kind == "set_trigger":
        apply_set_trigger_action(state, player_id, action)
        return
    if kind == "override":
        apply_override_action(state, player_id, action, rng)
        return
    if kind == "overdrive":
        apply_overdrive_action(state, player_id, action, rng)
        return
    if kind == "drive":
        apply_drive_action(state, player_id, action, rng)
        return
    if kind == "attack":
        apply_attack_action(state, player_id, action, rng=rng)
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


def draw_cards(player: PlayerState, count: int, rng: random.Random, hand_limit: int) -> None:
    if count <= 0 or len(player.hand) >= hand_limit:
        return
    actual_count = min(count, hand_limit - len(player.hand))
    if len(player.draw_pile) < actual_count:
        rng.shuffle(player.draw_pile)
    drawn = player.draw_pile[:actual_count]
    del player.draw_pile[:actual_count]
    player.hand.extend(drawn)


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
    player = state.players[player_id]
    actions = [{"kind": "no_block"}]
    for blocker_index, unit in enumerate(player.battlefield):
        if unit.exhausted:
            continue
        actions.append(
            {
                "kind": "block",
                "blocker_index": blocker_index,
            }
        )
    return actions


def list_available_intercept_actions(
    state: MatchState,
    player_id: PlayerId,
    own_unit: UnitState,
    enemy_unit: UnitState,
    own_unit_is_attacker: bool,
) -> list[dict[str, Any]]:
    player = state.players[player_id]
    actions = [{"kind": "no_intercept"}]
    for trigger_index, card_no in enumerate(player.trigger_zone):
        card = state.card_catalog[card_no]
        if card.category != "intercept":
            continue
        if not _can_use_intercept_card(state, player_id, card_no, own_unit_is_attacker):
            continue
        actions.append(
            {
                "kind": "use_intercept",
                "trigger_index": trigger_index,
                "card_no": card_no,
                "cost": card.cp or 0,
                "target": _get_intercept_target(card_no, own_unit_is_attacker),
            }
        )
    return actions


def apply_drive_action(state: MatchState, player_id: PlayerId, action: dict[str, Any], rng: random.Random) -> None:
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
    if reducer_index is not None:
        reducer_card_no = player.trigger_zone.pop(reducer_index)
        player.discard_pile.insert(0, reducer_card_no)
    player.battlefield.append(
        UnitState(
            card_no=card_no,
            unit_id=_allocate_unit_id(state),
            level=card_level,
            exhausted=False,
            attack_restricted=True,
            current_damage=0,
        )
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
    )


def apply_overdrive_action(state: MatchState, player_id: PlayerId, action: dict[str, Any], rng: random.Random) -> None:
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

    player.current_cp -= overdrive_cost
    player.hand.pop(hand_index)
    if reducer_index is not None:
        reducer_card_no = player.trigger_zone.pop(reducer_index)
        player.discard_pile.insert(0, reducer_card_no)
    player.discard_pile.insert(0, target_unit.card_no)
    player.battlefield[target_index] = UnitState(
        card_no=card_no,
        unit_id=target_unit.unit_id,
        level=evolved_level,
        exhausted=False if evolved_level >= 3 else inherited_exhausted,
        attack_restricted=False,
        current_damage=0,
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
    resolve_ability_events(state, emitted_events, rng)


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
    draw_cards(player, 1, rng, state.regulation.hand_size_limit)


def apply_attack_action(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    block_action: dict[str, Any] | None = None,
    rng: random.Random | None = None,
) -> None:
    if rng is None:
        rng = random.Random(0)
    declare_attack_action(state, player_id, action, rng)
    resolve_declared_attack_action(state, player_id, action, block_action, rng)


def declare_attack_action(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    rng: random.Random,
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
    )


def resolve_declared_attack_action(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    block_action: dict[str, Any] | None,
    rng: random.Random,
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
        blocker.exhausted = True
        attacker.current_damage += get_unit_bp(state, blocker)
        blocker.current_damage += get_unit_bp(state, attacker)
        attacker_survives = attacker.current_damage < get_unit_bp(state, attacker)
        blocker_survives = blocker.current_damage < get_unit_bp(state, blocker)
        emitted_events: list[AbilityEvent] = []
        if attacker_survives and not blocker_survives:
            emitted_events.extend(_clock_up_unit(player_id, attacker))
        elif blocker_survives and not attacker_survives:
            emitted_events.extend(_clock_up_unit(defender_id, blocker))
        if emitted_events:
            resolve_ability_events(state, emitted_events, rng)
        _destroy_broken_units(state, player_id)
        _destroy_broken_units(state, defender_id)
        _update_winner_by_life(state)
        return

    defender.life -= 1
    resolve_ability_events(
        state,
        [
            AbilityEvent(
                type="player_attack_success",
                player_id=player_id,
                source_unit_id=attacker.unit_id,
                target_player_id=defender_id,
            )
        ],
        rng,
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
    _resolve_intercept_effect(card_no, own_unit, enemy_unit, own_unit_is_attacker)


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
        if trigger_card.color == target_card.color and trigger_card.category in {"unit", "evolution"}:
            return index
    return None


def resolve_ability_events(
    state: MatchState,
    initial_events: list[AbilityEvent],
    rng: random.Random,
) -> None:
    pending_events = list(initial_events)
    while pending_events:
        event = pending_events.pop(0)
        triggered = collect_triggered_abilities(state, event)
        for triggered_ability in triggered:
            emitted = resolve_triggered_ability(state, event, triggered_ability, rng)
            pending_events.extend(emitted)


def collect_triggered_abilities(state: MatchState, event: AbilityEvent) -> list[dict[str, Any]]:
    triggered: list[dict[str, Any]] = []
    owner = state.players[event.player_id]

    for unit in owner.battlefield:
        if unit.unit_id == 0:
            unit.unit_id = _allocate_unit_id(state)
        if unit.unit_id != event.source_unit_id:
            continue
        if supports_ability_event(unit.card_no, event.type):
            triggered.append(
                {
                    "owner_id": event.player_id,
                    "source_zone": "battlefield",
                    "source_unit_id": unit.unit_id,
                    "card_no": unit.card_no,
                }
            )

    if event.type == "unit_entered":
        for index, card_no in enumerate(owner.trigger_zone):
            if supports_ability_event(card_no, event.type):
                triggered.append(
                    {
                        "owner_id": event.player_id,
                        "source_zone": "trigger_zone",
                        "source_index": index,
                        "card_no": card_no,
                    }
                )

    if event.type == "turn_end":
        for unit in owner.battlefield:
            if unit.unit_id == 0:
                unit.unit_id = _allocate_unit_id(state)
            if supports_ability_event(unit.card_no, event.type):
                triggered.append(
                    {
                        "owner_id": event.player_id,
                        "source_zone": "battlefield",
                        "source_unit_id": unit.unit_id,
                        "card_no": unit.card_no,
                    }
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
) -> list[AbilityEvent]:
    key = (
        triggered_ability["card_no"],
        event.type,
    )
    resolver = ABILITY_REGISTRY.get(key)
    if resolver is None:
        return []
    return resolver(state, event, triggered_ability, rng)


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


def _clock_up_unit(player_id: PlayerId, unit: UnitState) -> list[AbilityEvent]:
    if unit.level >= 3:
        return []
    unit.level += 1
    unit.current_damage = 0
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


def _find_first_enemy_unit(state: MatchState, player_id: PlayerId) -> UnitState | None:
    enemy_id = get_opponent_id(player_id)
    enemy_units = state.players[enemy_id].battlefield
    return enemy_units[0] if enemy_units else None


def _deal_damage_to_unit(state: MatchState, player_id: PlayerId, unit: UnitState | None, amount: int) -> None:
    if unit is None:
        return
    unit.current_damage += amount
    _destroy_broken_units(state, player_id)


def _draw_cards_by_category(
    state: MatchState,
    player_id: PlayerId,
    category: str,
    count: int,
) -> int:
    player = state.players[player_id]
    if count <= 0 or len(player.hand) >= state.regulation.hand_size_limit:
        return 0
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
    return len(actual_matches)


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
            return True
    if card_no in player.trigger_zone:
        player.trigger_zone.remove(card_no)
        player.discard_pile.insert(0, card_no)
        return True
    return False


def _discard_first_card_from_hand(state: MatchState, player_id: PlayerId) -> bool:
    player = state.players[player_id]
    if not player.hand:
        return False
    hand_card_id = player.hand.pop(0)
    card_no, _level = parse_hand_card_id(hand_card_id)
    player.discard_pile.insert(0, card_no)
    return True


def _destroy_random_trigger_cards(state: MatchState, player_id: PlayerId, count: int, rng: random.Random) -> None:
    opponent = state.players[get_opponent_id(player_id)]
    for _ in range(min(count, len(opponent.trigger_zone))):
        chosen_index = rng.randrange(len(opponent.trigger_zone))
        card_no = opponent.trigger_zone.pop(chosen_index)
        opponent.discard_pile.insert(0, card_no)


def _can_use_intercept_card(
    state: MatchState,
    player_id: PlayerId,
    card_no: str,
    own_unit_is_attacker: bool,
) -> bool:
    player = state.players[player_id]
    card = state.card_catalog[card_no]
    if card.category != "intercept":
        return False
    if (card.cp or 0) > player.current_cp:
        return False
    if card.color != "無" and not any(
        state.card_catalog[unit.card_no].color == card.color for unit in player.battlefield
    ):
        return False
    if card_no == "1-0-081" and not own_unit_is_attacker:
        return False
    return card_no in {"1-0-065", "1-0-074", "1-0-081", "1-0-096"}


def _get_intercept_target(card_no: str, own_unit_is_attacker: bool) -> str:
    if card_no == "1-0-065":
        return "enemy_unit"
    if card_no == "1-0-081" and own_unit_is_attacker:
        return "own_unit"
    return "own_unit"


def _resolve_intercept_effect(
    card_no: str,
    own_unit: UnitState,
    enemy_unit: UnitState,
    own_unit_is_attacker: bool,
) -> None:
    if card_no == "1-0-065":
        enemy_unit.temporary_bp_modifier -= 2000
        return
    if card_no == "1-0-074":
        own_unit.temporary_bp_modifier += 2000
        return
    if card_no == "1-0-081" and own_unit_is_attacker:
        own_unit.temporary_bp_modifier += 3000
        return
    if card_no == "1-0-096":
        own_unit.temporary_bp_modifier += 3000


def _resolve_happaloid_enter(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
) -> list[AbilityEvent]:
    draw_cards(state.players[event.player_id], 1, rng, state.regulation.hand_size_limit)
    return []


def _resolve_ririmu_enter(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
) -> list[AbilityEvent]:
    enemy_id = get_opponent_id(event.player_id)
    _deal_damage_to_unit(state, enemy_id, _find_first_enemy_unit(state, event.player_id), 4000)
    return []


def _resolve_barbatos_enter(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
) -> list[AbilityEvent]:
    enemy_unit = _find_first_enemy_unit(state, event.player_id)
    if enemy_unit is not None:
        enemy_unit.permanent_bp_modifier -= 4000
        _destroy_broken_units(state, get_opponent_id(event.player_id))
    return []


def _resolve_swordfighter_attack(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
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
) -> list[AbilityEvent]:
    enemy_id = get_opponent_id(event.player_id)
    _deal_damage_to_unit(state, enemy_id, _find_first_enemy_unit(state, event.player_id), 1000)
    return []


def _resolve_shiranui_attack(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
) -> list[AbilityEvent]:
    source = _find_unit_by_id(state, event.player_id, event.source_unit_id)
    if source is not None and _discard_first_card_from_hand(state, event.player_id):
        source.temporary_bp_modifier += 4000
    return []


def _resolve_shiranui_player_attack_success(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
) -> list[AbilityEvent]:
    _destroy_random_trigger_cards(state, event.player_id, 2, rng)
    return []


def _resolve_ririmu_attack_trigger_loss(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
) -> list[AbilityEvent]:
    _destroy_random_trigger_cards(state, event.player_id, 1, rng)
    return []


def _resolve_goliath_overclock(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
) -> list[AbilityEvent]:
    opponent = state.players[get_opponent_id(event.player_id)]
    opponent.life -= 1
    _update_winner_by_life(state)
    return []


def _resolve_draw_trigger_cards(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
) -> list[AbilityEvent]:
    if _count_drawable_cards_by_category(state, event.player_id, "trigger") <= 0:
        return []
    if not _consume_trigger_card(state, event.player_id, triggered_ability):
        return []
    _draw_cards_by_category(state, event.player_id, "trigger", 2)
    return []


def _resolve_draw_intercept_card(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
) -> list[AbilityEvent]:
    if _count_drawable_cards_by_category(state, event.player_id, "intercept") <= 0:
        return []
    if not _consume_trigger_card(state, event.player_id, triggered_ability):
        return []
    _draw_cards_by_category(state, event.player_id, "intercept", 1)
    return []


def _resolve_draw_any_card(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
) -> list[AbilityEvent]:
    if not _can_draw_any_card(state, event.player_id):
        return []
    if not _consume_trigger_card(state, event.player_id, triggered_ability):
        return []
    draw_cards(state.players[event.player_id], 1, rng, state.regulation.hand_size_limit)
    return []


def _resolve_untiring(
    state: MatchState,
    event: AbilityEvent,
    triggered_ability: dict[str, Any],
    rng: random.Random,
) -> list[AbilityEvent]:
    source = _find_unit_by_id(state, event.player_id, triggered_ability.get("source_unit_id"))
    if source is not None:
        source.exhausted = False
    return []


ABILITY_REGISTRY: dict[tuple[str, str], Any] = {
    ("1-0-040", "unit_entered"): _resolve_happaloid_enter,
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
        data["current_bp"] = get_unit_bp(state, unit)
    return data


def _destroy_broken_units(state: MatchState, player_id: PlayerId) -> None:
    player = state.players[player_id]
    survivors: list[UnitState] = []
    for unit in player.battlefield:
        if unit.current_damage >= get_unit_bp(state, unit):
            player.discard_pile.insert(0, unit.card_no)
        else:
            survivors.append(unit)
    player.battlefield = survivors


def _update_winner_by_life(state: MatchState) -> None:
    first_life = state.players["P1"].life
    second_life = state.players["P2"].life
    if first_life <= 0 and second_life <= 0:
        state.winner = "draw"
        state.ended_reason = "life_zero"
    elif first_life <= 0:
        state.winner = "P2"
        state.ended_reason = "life_zero"
    elif second_life <= 0:
        state.winner = "P1"
        state.ended_reason = "life_zero"
