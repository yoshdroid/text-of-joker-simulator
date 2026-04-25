from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .models import Regulation


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
    players: dict[PlayerId, PlayerState]
    round_no: int = 1
    turn_player_id: PlayerId = "P1"
    turn_serial: int = 0
    winner: str | None = None
    ended_reason: str | None = None


def create_match_state(
    regulation: Regulation,
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
    current_player = state.players[state.turn_player_id]
    for unit in current_player.battlefield:
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


def list_available_actions(state: MatchState, player_id: PlayerId) -> list[dict[str, Any]]:
    if state.winner is not None or state.turn_player_id != player_id:
        return []
    return [{"kind": "end_turn"}]


def apply_action(state: MatchState, player_id: PlayerId, action: dict[str, Any], rng: random.Random) -> None:
    if player_id != state.turn_player_id:
        raise ValueError(f"not turn player: {player_id}")
    kind = action.get("kind")
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
            viewer_id: _build_private_player_view(viewer),
            opponent.player_id: _build_public_player_view(opponent),
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


def _build_private_player_view(player: PlayerState) -> dict[str, Any]:
    return {
        "player_id": player.player_id,
        "life": player.life,
        "current_cp": player.current_cp,
        "hand_count": len(player.hand),
        "hand_card_nos": list(player.hand),
        "deck_count": len(player.draw_pile),
        "discard_top_to_bottom": list(player.discard_pile),
        "battlefield": [_serialize_unit(unit) for unit in player.battlefield],
        "trigger_zone": [{"position": index, "card_no": card_no} for index, card_no in enumerate(player.trigger_zone)],
    }


def _build_public_player_view(player: PlayerState) -> dict[str, Any]:
    return {
        "player_id": player.player_id,
        "life": player.life,
        "current_cp": player.current_cp,
        "hand_count": len(player.hand),
        "deck_count": len(player.draw_pile),
        "discard_top_to_bottom": list(player.discard_pile),
        "battlefield": [_serialize_unit(unit) for unit in player.battlefield],
        "trigger_zone": [
            {"position": index, "color": "unknown"}
            for index, _card_no in enumerate(player.trigger_zone)
        ],
    }


def _serialize_unit(unit: UnitState) -> dict[str, Any]:
    return {
        "card_no": unit.card_no,
        "level": unit.level,
        "exhausted": unit.exhausted,
        "attack_restricted": unit.attack_restricted,
        "current_damage": unit.current_damage,
    }
