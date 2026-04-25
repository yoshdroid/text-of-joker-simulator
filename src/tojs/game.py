from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .models import CardDefinition, Regulation


PlayerId = str


@dataclass
class UnitState:
    card_no: str
    level: int = 1
    exhausted: bool = False
    attack_restricted: bool = True
    current_damage: int = 0


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
    round_no: int = 1
    turn_player_id: PlayerId = "P1"
    turn_serial: int = 0
    winner: str | None = None
    ended_reason: str | None = None


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
    for player in state.players.values():
        for unit in player.battlefield:
            unit.current_damage = 0

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
    if kind == "overdrive":
        apply_overdrive_action(state, player_id, action)
        return
    if kind == "drive":
        apply_drive_action(state, player_id, action)
        return
    if kind == "attack":
        apply_attack_action(state, player_id, action)
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
        for hand_index, card_no in enumerate(player.hand):
            if card_no not in state.card_catalog:
                continue
            actions.append(
                {
                    "kind": "set_trigger",
                    "hand_index": hand_index,
                    "card_no": card_no,
                }
            )

    if len(player.battlefield) < state.regulation.battlefield_unit_limit:
        for hand_index, card_no in enumerate(player.hand):
            card = state.card_catalog.get(card_no)
            if card is None or card.category != "unit" or card.cp is None:
                continue
            cost, reducer_index = get_drive_cost(state, player_id, card_no)
            if cost <= player.current_cp:
                actions.append(
                    {
                        "kind": "drive",
                        "hand_index": hand_index,
                        "card_no": card_no,
                        "cost": cost,
                        "trigger_reducer_index": reducer_index,
                    }
                )

    for hand_index, card_no in enumerate(player.hand):
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
                    "card_no": card_no,
                    "target_index": target_index,
                    "cost": cost,
                    "trigger_reducer_index": reducer_index,
                    "card_level": 1,
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


def apply_drive_action(state: MatchState, player_id: PlayerId, action: dict[str, Any]) -> None:
    player = state.players[player_id]
    hand_index = action["hand_index"]
    if hand_index < 0 or hand_index >= len(player.hand):
        raise ValueError(f"invalid hand index: {hand_index}")

    card_no = player.hand[hand_index]
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
            level=1,
            exhausted=False,
            attack_restricted=True,
            current_damage=0,
        )
    )


def apply_overdrive_action(state: MatchState, player_id: PlayerId, action: dict[str, Any]) -> None:
    player = state.players[player_id]
    hand_index = action["hand_index"]
    target_index = action["target_index"]
    if hand_index < 0 or hand_index >= len(player.hand):
        raise ValueError(f"invalid hand index: {hand_index}")
    if target_index < 0 or target_index >= len(player.battlefield):
        raise ValueError(f"invalid target index: {target_index}")

    card_no = player.hand[hand_index]
    card = state.card_catalog.get(card_no)
    if card is None or card.category != "evolution" or card.cp is None:
        raise ValueError(f"card is not an overdrivable evolution: {card_no}")

    target_unit = player.battlefield[target_index]
    target_card = state.card_catalog[target_unit.card_no]
    if target_card.color != card.color:
        raise ValueError("overdrive target color mismatch")

    overdrive_cost, reducer_index = get_drive_cost(state, player_id, card_no)
    if overdrive_cost > player.current_cp:
        raise ValueError("not enough cp")

    inherited_exhausted = target_unit.exhausted
    evolved_level = int(action.get("card_level", 1))

    player.current_cp -= overdrive_cost
    player.hand.pop(hand_index)
    if reducer_index is not None:
        reducer_card_no = player.trigger_zone.pop(reducer_index)
        player.discard_pile.insert(0, reducer_card_no)
    player.discard_pile.insert(0, target_unit.card_no)
    player.battlefield[target_index] = UnitState(
        card_no=card_no,
        level=evolved_level,
        exhausted=False if evolved_level >= 3 else inherited_exhausted,
        attack_restricted=False,
        current_damage=0,
    )


def apply_set_trigger_action(state: MatchState, player_id: PlayerId, action: dict[str, Any]) -> None:
    player = state.players[player_id]
    if len(player.trigger_zone) >= state.regulation.trigger_zone_limit:
        raise ValueError("trigger zone is full")

    hand_index = action["hand_index"]
    if hand_index < 0 or hand_index >= len(player.hand):
        raise ValueError(f"invalid hand index: {hand_index}")

    card_no = player.hand.pop(hand_index)
    player.trigger_zone.append(card_no)


def apply_attack_action(
    state: MatchState,
    player_id: PlayerId,
    action: dict[str, Any],
    block_action: dict[str, Any] | None = None,
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
    defender_id = get_opponent_id(player_id)
    defender = state.players[defender_id]

    if block_action is not None and block_action.get("kind") == "block":
        blocker_index = block_action["blocker_index"]
        if blocker_index < 0 or blocker_index >= len(defender.battlefield):
            raise ValueError(f"invalid blocker index: {blocker_index}")
        blocker = defender.battlefield[blocker_index]
        if blocker.exhausted:
            raise ValueError("blocker is exhausted")

        blocker.exhausted = True
        attacker.current_damage += get_unit_bp(state, blocker)
        blocker.current_damage += get_unit_bp(state, attacker)
        _destroy_broken_units(state, player_id)
        _destroy_broken_units(state, defender_id)
        _update_winner_by_life(state)
        return

    defender.life -= 1
    _update_winner_by_life(state)


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


def get_unit_bp(state: MatchState, unit: UnitState) -> int:
    card = state.card_catalog[unit.card_no]
    if not card.bp_by_level:
        return 0
    index = min(unit.level, len(card.bp_by_level)) - 1
    return card.bp_by_level[index]


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
