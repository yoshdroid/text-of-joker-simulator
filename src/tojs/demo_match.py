from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import bootstrap
from .match import play_single_action_cycle, run_boot_sequence
from .player_runner import PlayerProcess, build_python_bot_command
from .protocol import render_event_log


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local demo match with example Python bots")
    parser.add_argument(
        "--cardpool",
        default="text-of-joker.cardpool.xlsx",
        help="Path to cardpool xlsx",
    )
    parser.add_argument(
        "--regulation",
        default="configs/regulation.default.json",
        help="Path to regulation json",
    )
    parser.add_argument(
        "--deck1",
        default="configs/decks/example_deck.json",
        help="Path to first player's deck json",
    )
    parser.add_argument(
        "--deck2",
        default="configs/decks/example_deck.json",
        help="Path to second player's deck json",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=2,
        help="Number of action cycles to execute after bootstrap",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    context = bootstrap(Path(args.cardpool), Path(args.regulation))
    first_player = PlayerProcess(build_python_bot_command(Path(args.deck1)), cwd=".")
    second_player = PlayerProcess(build_python_bot_command(Path(args.deck2)), cwd=".")
    trace_log: list[dict[str, object]] = []

    try:
        result = run_boot_sequence(
            context,
            first_player,
            second_player,
            seed=args.seed,
            trace_log=trace_log,
        )
        snapshots = [_build_snapshot("boot", result.match_state)]
        for cycle_index in range(args.cycles):
            play_single_action_cycle(
                result.match_state,
                first_player,
                second_player,
                seed=args.seed + cycle_index,
                trace_log=trace_log,
            )
            snapshots.append(_build_snapshot(f"cycle_{cycle_index + 1}", result.match_state))

        print(
            json.dumps(
                {
                    "status": "ok",
                    "snapshots": snapshots,
                    "messages": trace_log,
                    "rendered_messages": _render_trace_log(trace_log),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        first_player.close()
        second_player.close()
    return 0


def _build_snapshot(label: str, state: object) -> dict[str, object]:
    from .game import MatchState

    assert isinstance(state, MatchState)
    return {
        "label": label,
        "round_no": state.round_no,
        "turn_serial": state.turn_serial,
        "turn_player_id": state.turn_player_id,
        "winner": state.winner,
        "players": {
            player_id: {
                "life": player.life,
                "current_cp": player.current_cp,
                "hand_count": len(player.hand),
                "deck_count": len(player.draw_pile),
                "battlefield_count": len(player.battlefield),
                "trigger_zone_count": len(player.trigger_zone),
            }
            for player_id, player in state.players.items()
        },
    }


def _render_trace_log(trace_log: list[dict[str, object]]) -> list[str]:
    rendered: list[str] = []
    latest_round_no = 0
    for entry in trace_log:
        message = entry.get("message", {})
        if not isinstance(message, dict):
            continue
        payload = message.get("payload", {})
        if isinstance(payload, dict) and "round_no" in payload:
            latest_round_no = int(payload.get("round_no", latest_round_no))
        request_id = str(message.get("request_id", ""))
        round_no = _extract_round_no_from_request_id(request_id) or latest_round_no
        actor = str(entry.get("player_id", "SYS"))
        direction = "REQ" if entry.get("direction") == "to_player" else "RES"
        details = _render_message_details(message)
        rendered.append(render_event_log(round_no, actor, direction, details))
    return rendered


def _extract_round_no_from_request_id(request_id: str) -> int | None:
    if not request_id:
        return None
    parts = request_id.split("-")
    for part in parts:
        if part.isdigit():
            return int(part)
    return None


def _render_message_details(message: dict[str, object]) -> str:
    message_type = str(message.get("type", "unknown"))
    payload = message.get("payload", {})
    if not isinstance(payload, dict):
        return message_type
    if message_type == "choice_request":
        choice_kind = str(payload.get("choice_kind", "choice"))
        prompt = str(payload.get("prompt", ""))
        lines = [f"{message_type} kind={choice_kind} prompt={prompt}"]
        available_choices = payload.get("available_choices", [])
        unavailable_choices = payload.get("unavailable_choices", [])
        if isinstance(available_choices, list) and available_choices:
            lines.append("available=" + ", ".join(_format_choice(choice) for choice in available_choices))
        if isinstance(unavailable_choices, list) and unavailable_choices:
            lines.append("unavailable=" + ", ".join(_format_choice(choice) for choice in unavailable_choices))
        return " | ".join(lines)
    if message_type in {"action", "choice_response"}:
        return f"{message_type} {_format_choice(payload)}"
    if message_type == "request_action":
        actions = payload.get("available_actions", [])
        if isinstance(actions, list):
            return f"{message_type} actions=" + ",".join(str(action.get("kind", "?")) for action in actions)
    if message_type == "state_update":
        return (
            f"{message_type} round={payload.get('round_no')} turn={payload.get('turn_serial')} "
            f"viewer={payload.get('viewer_player_id')} active={payload.get('turn_player_id')}"
        )
    return message_type


def _format_choice(choice: object) -> str:
    if not isinstance(choice, dict):
        return str(choice)
    label = choice.get("choice_label_ja") or choice.get("choice_label") or choice.get("kind", "?")
    summary = choice.get("choice_summary_ja") or choice.get("choice_summary")
    disabled = choice.get("disabled_reason_message") or choice.get("disabled_reason")
    parts = [str(label)]
    if summary:
        parts.append(str(summary))
    if disabled:
        parts.append(f"理由: {disabled}")
    return " / ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
