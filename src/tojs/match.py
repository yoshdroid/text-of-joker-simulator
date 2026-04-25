from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from .engine import BootstrapContext, validate_submitted_deck
from .game import (
    MatchState,
    apply_action,
    apply_attack_action,
    apply_mulligan,
    build_state_update_payload,
    create_match_state,
    list_available_actions,
    list_available_block_actions,
    start_turn,
)
from .player_runner import PlayerProcess
from .protocol import Message


@dataclass(frozen=True)
class MatchBootstrapResult:
    match_state: MatchState
    first_player_name: str
    second_player_name: str


TraceLog = list[dict[str, Any]]


def run_boot_sequence(
    context: BootstrapContext,
    first_player: PlayerProcess,
    second_player: PlayerProcess,
    seed: int = 0,
    trace_log: TraceLog | None = None,
) -> MatchBootstrapResult:
    rng = random.Random(seed)

    first_hello = _request_with_trace(
        first_player,
        "P1",
        Message(type="hello", request_id="hello-p1", payload={}),
        trace_log,
    )
    second_hello = _request_with_trace(
        second_player,
        "P2",
        Message(type="hello", request_id="hello-p2", payload={}),
        trace_log,
    )

    first_deck = _request_with_trace(
        first_player,
        "P1",
        Message(type="deck_submit", request_id="deck-p1", payload={}),
        trace_log,
    )
    second_deck = _request_with_trace(
        second_player,
        "P2",
        Message(type="deck_submit", request_id="deck-p2", payload={}),
        trace_log,
    )

    _validate_deck_payload(first_deck.payload["deck_card_nos"], context, "P1")
    _validate_deck_payload(second_deck.payload["deck_card_nos"], context, "P2")

    state = create_match_state(
        context.regulation,
        {card.card_no: card for card in context.cardpool},
        first_deck.payload["deck_card_nos"],
        second_deck.payload["deck_card_nos"],
        rng,
    )

    first_mulligan = _request_with_trace(
        first_player,
        "P1",
        Message(
            type="mulligan_decision",
            request_id="mulligan-p1",
            payload={"initial_hand_card_nos": list(state.players["P1"].hand)},
        ),
        trace_log,
    )
    second_mulligan = _request_with_trace(
        second_player,
        "P2",
        Message(
            type="mulligan_decision",
            request_id="mulligan-p2",
            payload={"initial_hand_card_nos": list(state.players["P2"].hand)},
        ),
        trace_log,
    )

    apply_mulligan(state, "P1", first_mulligan.payload["do_mulligan"], rng)
    apply_mulligan(state, "P2", second_mulligan.payload["do_mulligan"], rng)
    start_turn(state, "P1", rng)

    return MatchBootstrapResult(
        match_state=state,
        first_player_name=first_hello.payload.get("player_name", "P1"),
        second_player_name=second_hello.payload.get("player_name", "P2"),
    )


def play_single_action_cycle(
    state: MatchState,
    first_player: PlayerProcess,
    second_player: PlayerProcess,
    seed: int = 0,
    trace_log: TraceLog | None = None,
) -> MatchState:
    rng = random.Random(seed)
    players = {"P1": first_player, "P2": second_player}

    for viewer_id, process in players.items():
        payload = build_state_update_payload(state, viewer_id)
        _request_with_trace(
            process,
            viewer_id,
            Message(
                type="state_update",
                request_id=f"state-{state.turn_serial}-{viewer_id}",
                payload=payload,
            ),
            trace_log,
        )

    actor_id = state.turn_player_id
    actor = players[actor_id]
    action_response = _request_with_trace(
        actor,
        actor_id,
        Message(
            type="request_action",
            request_id=f"action-{state.turn_serial}-{actor_id}",
            payload={"available_actions": list_available_actions(state, actor_id)},
        ),
        trace_log,
    )
    if action_response.payload.get("kind") == "attack":
        defender_id = "P2" if actor_id == "P1" else "P1"
        defender = players[defender_id]
        block_response = _request_with_trace(
            defender,
            defender_id,
            Message(
                type="block_request",
                request_id=f"block-{state.turn_serial}-{defender_id}",
                payload={"available_actions": list_available_block_actions(state, defender_id)},
            ),
            trace_log,
        )
        apply_attack_action(state, actor_id, action_response.payload, block_response.payload)
    else:
        apply_action(state, actor_id, action_response.payload, rng)
    return state


def _validate_deck_payload(deck_card_nos: list[str], context: BootstrapContext, player_id: str) -> None:
    is_valid, errors = validate_submitted_deck(deck_card_nos, context)
    if not is_valid:
        joined = "; ".join(errors)
        raise ValueError(f"{player_id} submitted invalid deck: {joined}")


def _request_with_trace(
    process: PlayerProcess,
    player_id: str,
    message: Message,
    trace_log: TraceLog | None,
) -> Message:
    if trace_log is not None:
        trace_log.append(
            {
                "direction": "to_player",
                "player_id": player_id,
                "message": {
                    "type": message.type,
                    "request_id": message.request_id,
                    "payload": message.payload,
                },
            }
        )
    response = process.request(message)
    if trace_log is not None:
        trace_log.append(
            {
                "direction": "from_player",
                "player_id": player_id,
                "message": {
                    "type": response.type,
                    "request_id": response.request_id,
                    "payload": response.payload,
                },
            }
        )
    return response
