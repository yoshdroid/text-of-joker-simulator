from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .protocol import Message, read_message, write_message


class SimpleBot:
    def __init__(self, deck_card_nos: list[str], bot_name: str = "python-starter-bot") -> None:
        self.deck_card_nos = deck_card_nos
        self.bot_name = bot_name

    def handle(self, message: Message) -> Message:
        if message.type == "hello":
            return Message(
                type="hello",
                request_id=message.request_id,
                payload={
                    "player_name": self.bot_name,
                    "protocol_version": "1",
                },
            )
        if message.type == "deck_submit":
            return Message(
                type="deck_submit",
                request_id=message.request_id,
                payload={"deck_card_nos": self.deck_card_nos},
            )
        if message.type == "mulligan_decision":
            return Message(
                type="mulligan_decision",
                request_id=message.request_id,
                payload={"do_mulligan": False},
            )
        if message.type == "state_update":
            return Message(
                type="state_ack",
                request_id=message.request_id,
                payload={"received": True},
            )
        if message.type == "request_action":
            available_actions = message.payload.get("available_actions", [])
            chosen_action = choose_action(available_actions)
            return Message(
                type="action",
                request_id=message.request_id,
                payload=chosen_action,
            )
        if message.type == "intercept_request":
            available_actions = message.payload.get("available_actions", [])
            chosen_action = {"kind": "no_intercept"}
            for action in available_actions:
                if action.get("kind") == "use_intercept":
                    chosen_action = action
                    break
            return Message(
                type="intercept_action",
                request_id=message.request_id,
                payload=chosen_action,
            )
        if message.type == "choice_request":
            chosen_choice = choose_choice(message.payload)
            return Message(
                type="choice_response",
                request_id=message.request_id,
                payload=chosen_choice,
            )
        return Message(
            type="error",
            request_id=message.request_id,
            payload={"message": f"unsupported message type: {message.type}"},
        )


def load_deck(path: str | Path) -> list[str]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def choose_action(available_actions: list[dict[str, object]]) -> dict[str, object]:
    priorities = {
        "overdrive": 0,
        "override": 1,
        "drive": 2,
        "attack": 3,
        "set_trigger": 4,
        "end_turn": 5,
    }
    if not available_actions:
        return {"kind": "end_turn"}
    return min(
        available_actions,
        key=lambda action: (priorities.get(str(action.get("kind")), 99), available_actions.index(action)),
    )


def choose_first_option(
    available_options: list[dict[str, object]],
    fallback: dict[str, object],
) -> dict[str, object]:
    if not available_options:
        return fallback
    return available_options[0]


def choose_choice(payload: dict[str, object]) -> dict[str, object]:
    available_choices = payload.get("available_choices", [])
    if not isinstance(available_choices, list) or not available_choices:
        return {"kind": "no_choice"}
    choice_kind = payload.get("choice_kind")
    if choice_kind == "block":
        for choice in available_choices:
            if choice.get("kind") == "block":
                return choice
        return {"kind": "no_block"}
    return choose_first_option(available_choices, {"kind": "no_choice"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simple stdio bot for TOJS")
    parser.add_argument(
        "--deck",
        default="configs/decks/example_deck.json",
        help="Path to deck json",
    )
    parser.add_argument(
        "--name",
        default="python-starter-bot",
        help="Bot display name",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    bot = SimpleBot(load_deck(args.deck), bot_name=args.name)

    while True:
        message = read_message(sys.stdin)
        if message is None:
            break
        response = bot.handle(message)
        write_message(sys.stdout, response)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
