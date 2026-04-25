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
        if message.type == "block_request":
            available_actions = message.payload.get("available_actions", [])
            chosen_action = {"kind": "no_block"}
            for action in available_actions:
                if action.get("kind") == "block":
                    chosen_action = action
                    break
            return Message(
                type="block_action",
                request_id=message.request_id,
                payload=chosen_action,
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
        "drive": 1,
        "attack": 2,
        "set_trigger": 3,
        "end_turn": 4,
    }
    if not available_actions:
        return {"kind": "end_turn"}
    return min(
        available_actions,
        key=lambda action: (priorities.get(str(action.get("kind")), 99), available_actions.index(action)),
    )


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
