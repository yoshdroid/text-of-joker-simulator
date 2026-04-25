from __future__ import annotations

import random
from dataclasses import dataclass

from .engine import BootstrapContext, validate_submitted_deck
from .game import (
    MatchState,
    apply_action,
    apply_mulligan,
    build_state_update_payload,
    create_match_state,
    list_available_actions,
    start_turn,
)
from .player_runner import PlayerProcess
from .protocol import Message


@dataclass(frozen=True)
class MatchBootstrapResult:
    match_state: MatchState
    first_player_name: str
    second_player_name: str


def run_boot_sequence(
    context: BootstrapContext,
    first_player: PlayerProcess,
    second_player: PlayerProcess,
    seed: int = 0,
) -> MatchBootstrapResult:
    rng = random.Random(seed)

    first_hello = first_player.request(Message(type="hello", request_id="hello-p1", payload={}))
    second_hello = second_player.request(Message(type="hello", request_id="hello-p2", payload={}))

    first_deck = first_player.request(Message(type="deck_submit", request_id="deck-p1", payload={}))
    second_deck = second_player.request(Message(type="deck_submit", request_id="deck-p2", payload={}))

    _validate_deck_payload(first_deck.payload["deck_card_nos"], context, "P1")
    _validate_deck_payload(second_deck.payload["deck_card_nos"], context, "P2")

    state = create_match_state(
        context.regulation,
        first_deck.payload["deck_card_nos"],
        second_deck.payload["deck_card_nos"],
        rng,
    )

    first_mulligan = first_player.request(
        Message(
            type="mulligan_decision",
            request_id="mulligan-p1",
            payload={"initial_hand_card_nos": list(state.players["P1"].hand)},
        )
    )
    second_mulligan = second_player.request(
        Message(
            type="mulligan_decision",
            request_id="mulligan-p2",
            payload={"initial_hand_card_nos": list(state.players["P2"].hand)},
        )
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
) -> MatchState:
    rng = random.Random(seed)
    players = {"P1": first_player, "P2": second_player}

    for viewer_id, process in players.items():
        payload = build_state_update_payload(state, viewer_id)
        process.request(
            Message(
                type="state_update",
                request_id=f"state-{state.turn_serial}-{viewer_id}",
                payload=payload,
            )
        )

    actor_id = state.turn_player_id
    actor = players[actor_id]
    action_response = actor.request(
        Message(
            type="request_action",
            request_id=f"action-{state.turn_serial}-{actor_id}",
            payload={"available_actions": list_available_actions(state, actor_id)},
        )
    )
    apply_action(state, actor_id, action_response.payload, rng)
    return state


def _validate_deck_payload(deck_card_nos: list[str], context: BootstrapContext, player_id: str) -> None:
    is_valid, errors = validate_submitted_deck(deck_card_nos, context)
    if not is_valid:
        joined = "; ".join(errors)
        raise ValueError(f"{player_id} submitted invalid deck: {joined}")

