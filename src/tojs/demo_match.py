from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import bootstrap
from .match import play_single_action_cycle, run_boot_sequence
from .player_runner import PlayerProcess, build_python_bot_command


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

    try:
        result = run_boot_sequence(context, first_player, second_player, seed=args.seed)
        snapshots = [_build_snapshot("boot", result.match_state)]
        for cycle_index in range(args.cycles):
            play_single_action_cycle(
                result.match_state,
                first_player,
                second_player,
                seed=args.seed + cycle_index,
            )
            snapshots.append(_build_snapshot(f"cycle_{cycle_index + 1}", result.match_state))

        print(json.dumps({"status": "ok", "snapshots": snapshots}, ensure_ascii=False, indent=2))
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
            }
            for player_id, player in state.players.items()
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())

