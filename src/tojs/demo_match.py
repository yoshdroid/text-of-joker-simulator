from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .engine import bootstrap
from .match import play_single_action_cycle, run_boot_sequence
from .player_runner import PlayerProcess, build_python_bot_command
from .protocol import render_event_log


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local demo match with example Python bots")
    parser.add_argument("--cardpool", default="text-of-joker.cardpool.xlsx", help="Path to cardpool xlsx")
    parser.add_argument("--regulation", default="configs/regulation.default.json", help="Path to regulation json")
    parser.add_argument("--deck1", default="configs/decks/example_deck.json", help="Path to first player's deck json")
    parser.add_argument("--deck2", default="configs/decks/example_deck.json", help="Path to second player's deck json")
    parser.add_argument("--cycles", type=int, default=2, help="Number of action cycles to execute after bootstrap")
    parser.add_argument("--seed", type=int, default=7, help="Random seed")
    parser.add_argument("--hide-reqres", action="store_true", help="Hide REQ/RES transport log lines from rendered_messages")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    context = bootstrap(Path(args.cardpool), Path(args.regulation))
    card_catalog = {card.card_no: card for card in context.cardpool}
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
                    "game_events": result.match_state.event_log,
                    "rendered_messages": _render_trace_log(
                        trace_log,
                        card_catalog,
                        result.match_state.event_log,
                        show_reqres=not args.hide_reqres,
                    ),
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


def _render_trace_log(
    trace_log: list[dict[str, object]],
    card_catalog: dict[str, Any],
    game_events: list[dict[str, Any]] | None = None,
    show_reqres: bool = True,
) -> list[str]:
    rendered: list[str] = []
    latest_round_no = 0
    request_rounds: dict[str, int] = {}
    game_event_cursor = 0
    safe_game_events = [event for event in (game_events or []) if isinstance(event, dict)]
    previous_shared_state: dict[str, Any] | None = None

    for entry in trace_log:
        message = entry.get("message", {})
        if not isinstance(message, dict):
            continue
        payload = message.get("payload", {})
        if isinstance(payload, dict) and "round_no" in payload:
            latest_round_no = int(payload.get("round_no", latest_round_no))
        request_id = str(message.get("request_id", ""))
        if entry.get("direction") == "to_player" and request_id:
            request_rounds[request_id] = _extract_round_no_from_request_id(request_id) or latest_round_no
        round_no = request_rounds.get(request_id) or _extract_round_no_from_request_id(request_id) or latest_round_no
        actor = str(entry.get("player_id", "SYS"))
        direction = "REQ" if entry.get("direction") == "to_player" else "RES"

        if direction == "REQ" and message.get("type") == "state_update" and isinstance(payload, dict):
            event_log_count = payload.get("event_log_count")
            if isinstance(event_log_count, int):
                rendered.extend(_render_game_events_slice(safe_game_events, game_event_cursor, event_log_count, card_catalog))
                game_event_cursor = max(game_event_cursor, event_log_count)

        if show_reqres:
            details = _render_message_details(message, card_catalog)
            rendered.append(render_event_log(round_no, actor, direction, details))

        action_event = _render_system_event_from_message(round_no, actor, direction, message, card_catalog)
        if action_event is not None:
            rendered.append(action_event)

        if direction == "REQ" and message.get("type") == "state_update" and isinstance(payload, dict):
            current_shared_state = _build_shared_state_snapshot(payload)
            if current_shared_state is not None:
                rendered.extend(_render_state_diff_events(round_no, previous_shared_state, current_shared_state))
                previous_shared_state = current_shared_state

    rendered.extend(_render_game_events_slice(safe_game_events, game_event_cursor, len(safe_game_events), card_catalog))
    return _attach_round_event_numbers(rendered)


def _extract_round_no_from_request_id(request_id: str) -> int | None:
    if not request_id:
        return None
    parts = request_id.split("-")
    for part in parts:
        if part.isdigit():
            return int(part)
    return None


def _render_message_details(message: dict[str, object], card_catalog: dict[str, Any]) -> str:
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
        return _render_action_message(message_type, payload, card_catalog)
    if message_type == "request_action":
        actions = payload.get("available_actions", [])
        if isinstance(actions, list):
            return f"{message_type} actions=" + ",".join(str(action.get("kind", "?")) for action in actions)
    if message_type == "state_update":
        summary_parts = [
            f"{message_type} round={payload.get('round_no')} turn={payload.get('turn_serial')}",
            f"viewer={payload.get('viewer_player_id')} active={payload.get('turn_player_id')}",
        ]
        players = payload.get("players", {})
        if isinstance(players, dict):
            player_summaries = []
            for player_id, player_view in players.items():
                if isinstance(player_view, dict):
                    player_summaries.append(_render_player_summary(str(player_id), player_view))
            if player_summaries:
                summary_parts.append(" || ".join(player_summaries))
        return " | ".join(summary_parts)
    return message_type


def _render_action_message(message_type: str, payload: dict[str, Any], card_catalog: dict[str, Any]) -> str:
    kind = str(payload.get("kind", message_type))
    card_name = _get_action_card_name(payload, card_catalog)
    if kind == "drive" and card_name:
        return f"{message_type} {card_name}をユニットドライブ"
    if kind == "set_trigger" and card_name:
        return f"{message_type} トリガーゾーンに{card_name}をセット"
    if kind == "overdrive" and card_name:
        return f"{message_type} {card_name}でオーバードライブ"
    if kind == "override" and card_name:
        return f"{message_type} {card_name}をオーバーライド"
    if kind == "retreat" and card_name:
        return f"{message_type} {card_name}を撤退させる"
    if kind == "use_intercept" and card_name:
        return f"{message_type} {card_name}を使用"
    if kind == "attack":
        return f"{message_type} attack attacker_index={payload.get('attacker_index')}"
    if kind == "block":
        return f"{message_type} block blocker_index={payload.get('blocker_index')}"
    return f"{message_type} {_format_choice(payload)}"


def _get_action_card_name(payload: dict[str, Any], card_catalog: dict[str, Any]) -> str | None:
    raw_card_no = payload.get("card_no")
    if not isinstance(raw_card_no, str):
        return None
    card_no = raw_card_no.split("@L", 1)[0]
    card = card_catalog.get(card_no)
    return getattr(card, "name", None)


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


def _render_player_summary(player_id: str, player_view: dict[str, object]) -> str:
    life = player_view.get("life", "?")
    current_cp = player_view.get("current_cp", "?")
    hand_count = player_view.get("hand_count", "?")
    deck_count = player_view.get("deck_count", "?")
    battlefield = player_view.get("battlefield", [])
    trigger_zone = player_view.get("trigger_zone", [])
    battlefield_summary = _render_battlefield_summary(battlefield)
    trigger_count = len(trigger_zone) if isinstance(trigger_zone, list) else 0
    return (
        f"{player_id}: life={life} cp={current_cp} hand={hand_count} deck={deck_count} "
        f"field={battlefield_summary} trigger={trigger_count}"
    )


def _render_battlefield_summary(battlefield: object) -> str:
    if not isinstance(battlefield, list) or not battlefield:
        return "-"
    parts: list[str] = []
    for unit in battlefield:
        if not isinstance(unit, dict):
            continue
        card_no = unit.get("card_no", "?")
        level = unit.get("level", "?")
        current_bp = unit.get("current_bp", "?")
        status = "行動済み" if unit.get("exhausted") else "行動可"
        if unit.get("attack_restricted"):
            status += "/攻撃制限"
        parts.append(f"{card_no}@L{level}:{current_bp}:{status}")
    return ",".join(parts) if parts else "-"


def _render_state_diff_events(
    round_no: int,
    previous_state: dict[str, Any] | None,
    current_state: dict[str, Any],
) -> list[str]:
    if previous_state is None:
        return []

    current_players = current_state.get("players", {})
    previous_players = previous_state.get("players", {})
    if not isinstance(current_players, dict) or not isinstance(previous_players, dict):
        return []
    return _render_life_diff(round_no, previous_players, current_players)


def _render_life_diff(
    round_no: int,
    previous_players: dict[str, Any],
    current_players: dict[str, Any],
) -> list[str]:
    rendered: list[str] = []
    for player_id in current_players:
        previous_player = previous_players.get(player_id, {})
        current_player = current_players.get(player_id, {})
        if not isinstance(previous_player, dict) or not isinstance(current_player, dict):
            continue
        previous_life = previous_player.get("life")
        current_life = current_player.get("life")
        if isinstance(previous_life, int) and isinstance(current_life, int) and previous_life != current_life:
            delta = current_life - previous_life
            rendered.append(render_event_log(round_no, "SYS", "EVT", f"{player_id}のライフが{current_life}になった ({delta:+d})"))
    return rendered


def _render_game_events_slice(
    game_events: list[dict[str, Any]],
    start_index: int,
    end_index: int,
    card_catalog: dict[str, Any],
) -> list[str]:
    rendered: list[str] = []
    for event in game_events[start_index:end_index]:
        detail = _render_game_event_detail(event, card_catalog)
        if not detail:
            continue
        round_no = int(event.get("round_no", 0) or 0)
        rendered.append(render_event_log(round_no, "SYS", "EVT", detail))
    return rendered


def _build_shared_state_snapshot(payload: dict[str, Any]) -> dict[str, Any] | None:
    players = payload.get("players", {})
    if not isinstance(players, dict):
        return None
    snapshot_players: dict[str, Any] = {}
    for player_id, player_view in players.items():
        if not isinstance(player_view, dict):
            continue
        snapshot_players[str(player_id)] = {
            "life": player_view.get("life"),
            "current_cp": player_view.get("current_cp"),
            "hand_count": player_view.get("hand_count"),
            "deck_count": player_view.get("deck_count"),
            "battlefield": player_view.get("battlefield"),
            "trigger_zone": player_view.get("trigger_zone"),
        }
    return {
        "round_no": payload.get("round_no"),
        "turn_serial": payload.get("turn_serial"),
        "turn_player_id": payload.get("turn_player_id"),
        "players": snapshot_players,
    }


def _render_game_event_detail(event: dict[str, Any], card_catalog: dict[str, Any]) -> str | None:
    event_type = str(event.get("type", ""))
    player_id = str(event.get("player_id") or "SYS")
    target_player_id = event.get("target_player_id")
    amount = event.get("amount")
    source_card_no = event.get("source_card_no")
    source_card_name = _lookup_card_name(source_card_no, card_catalog)
    metadata = event.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    if event_type == "turn_start_draw" and isinstance(amount, int):
        return f"{player_id}がターン開始時に{amount}枚ドロー"
    if event_type == "turn_start_cp_set" and isinstance(amount, int):
        return f"{player_id}がターン開始時にCPを変動 {amount:+d}"
    if event_type == "turn_end":
        return f"{player_id}のターン終了"
    if event_type == "unit_driven" and source_card_name:
        return f"{player_id}が{source_card_name}をユニットドライブ"
    if event_type == "card_set_to_trigger_zone" and source_card_name:
        return f"{player_id}がトリガーゾーンに{source_card_name}をセット"
    if event_type == "unit_overdriven" and source_card_name:
        return f"{player_id}が{source_card_name}でオーバードライブ"
    if event_type == "card_overridden" and source_card_name:
        from_level = metadata.get("from_level")
        to_level = metadata.get("to_level")
        if isinstance(from_level, int) and isinstance(to_level, int):
            return f"{player_id}が{source_card_name}をオーバーライド Lv.{from_level} -> Lv.{to_level}"
        return f"{player_id}が{source_card_name}をオーバーライド"
    if event_type == "unit_retreated" and source_card_name:
        return f"{player_id}が{source_card_name}を撤退させる"
    if event_type == "attack_declared" and source_card_name:
        return f"{player_id}が{source_card_name}でアタックを宣言"
    if event_type == "block_declared" and source_card_name:
        return f"{player_id}が{source_card_name}でブロックを宣言"
    if event_type == "battle_bp_changed" and source_card_name and isinstance(amount, int):
        current_damage = metadata.get("current_damage")
        current_bp = metadata.get("current_bp")
        if isinstance(current_damage, int) and isinstance(current_bp, int):
            return f"{player_id}の{source_card_name}が{amount}ダメージを受けた (累積ダメージ {current_damage} / BP {current_bp})"
        return f"{player_id}の{source_card_name}が{amount}ダメージを受けた"
    if event_type == "ability_damage_dealt_to_unit" and source_card_name and isinstance(amount, int):
        target_name = _lookup_card_name(metadata.get("target_card_no"), card_catalog)
        effect_name = metadata.get("effect_name")
        current_damage = metadata.get("current_damage")
        current_bp = metadata.get("current_bp")
        if target_name and effect_name and isinstance(current_damage, int) and isinstance(current_bp, int):
            return (
                f"{source_card_name}の{effect_name}が{target_name}に発動 "
                f"({amount}ダメージ / 累積ダメージ {current_damage} / 現BP {current_bp})"
            )
        if target_name and effect_name:
            return f"{source_card_name}の{effect_name}が{target_name}に発動 ({amount}ダメージ)"
        if target_name:
            return f"{source_card_name}が{target_name}に{amount}ダメージ"
        return f"{source_card_name}の効果で{amount}ダメージ"
    if event_type == "unit_bp_modified" and source_card_name and isinstance(amount, int):
        target_name = _lookup_card_name(metadata.get("target_card_no"), card_catalog)
        current_bp = metadata.get("current_bp")
        if target_name and isinstance(current_bp, int):
            return f"{source_card_name}の効果で{target_name}のBPが{amount:+d} (現BP {current_bp})"
        if target_name:
            return f"{source_card_name}の効果で{target_name}のBPが{amount:+d}"
        return f"{source_card_name}の効果でBPが{amount:+d}"
    if event_type == "battle_resolved":
        result = metadata.get("result")
        attacker_name = _lookup_card_name(metadata.get("attacker_card_no"), card_catalog)
        blocker_name = _lookup_card_name(metadata.get("blocker_card_no"), card_catalog)
        if result == "attacker_win" and attacker_name and blocker_name:
            return f"戦闘結果: {attacker_name}が勝利し、{blocker_name}が敗北"
        if result == "blocker_win" and attacker_name and blocker_name:
            return f"戦闘結果: {blocker_name}が勝利し、{attacker_name}が敗北"
        if result == "draw" and attacker_name and blocker_name:
            return f"戦闘結果: {attacker_name}と{blocker_name}は相打ち"
        return "戦闘結果が解決"
    if event_type == "unit_sent_to_discard" and source_card_name:
        reason = metadata.get("reason")
        if reason == "overdrive_material":
            return f"{player_id}の{source_card_name}がオーバードライブ素材として捨札へ移動"
        if reason == "retreat":
            return f"{player_id}の{source_card_name}が撤退して捨札へ移動"
        return f"{player_id}の{source_card_name}が捨札へ移動"
    if event_type == "unit_clock_up" and source_card_name:
        from_level = metadata.get("from_level")
        to_level = metadata.get("to_level")
        if isinstance(from_level, int) and isinstance(to_level, int):
            return f"{player_id}の{source_card_name}がクロックアップ Lv.{from_level} -> Lv.{to_level}"
        return f"{player_id}の{source_card_name}がクロックアップ"
    if event_type == "unit_level_changed" and source_card_name:
        from_level = metadata.get("from_level")
        to_level = metadata.get("to_level")
        reason = metadata.get("reason")
        if isinstance(from_level, int) and isinstance(to_level, int):
            if reason == "overdrive":
                return f"{player_id}の{source_card_name}のレベルがオーバードライブで Lv.{from_level} -> Lv.{to_level}"
            return f"{player_id}の{source_card_name}のレベルが Lv.{from_level} -> Lv.{to_level}"
        return f"{player_id}の{source_card_name}のレベルが変化"
    if event_type == "card_moved" and source_card_name:
        from_zone = metadata.get("from_zone")
        to_zone = metadata.get("to_zone")
        reason = metadata.get("reason")
        if from_zone == "trigger_zone" and to_zone == "discard" and reason == "cost_reduction":
            return f"{player_id}の{source_card_name}がコスト軽減で捨札へ移動"
        if from_zone == "hand" and to_zone == "discard" and reason == "override_material":
            return f"{player_id}の{source_card_name}がオーバーライド素材として捨札へ移動"
        return f"{player_id}の{source_card_name}が{from_zone}から{to_zone}へ移動"
    if event_type == "trigger_used" and source_card_name:
        return f"{player_id}のトリガー {source_card_name} が発動"
    if event_type == "intercept_used" and source_card_name:
        return f"{player_id}が{source_card_name}をインターセプト使用"
    if event_type == "cards_drawn" and isinstance(amount, int):
        if source_card_name:
            return f"{source_card_name}の効果で{player_id}が{amount}枚ドロー"
        return f"{player_id}が{amount}枚ドロー"
    if event_type == "cp_changed" and isinstance(amount, int):
        if source_card_name:
            return f"{source_card_name}の効果で{player_id}のCPが{amount:+d}"
        return f"{player_id}のCPが{amount:+d}"
    if event_type == "life_changed" and isinstance(amount, int):
        subject = str(target_player_id) if isinstance(target_player_id, str) else player_id
        if source_card_name:
            return f"{source_card_name}の効果で{subject}のライフが{amount:+d}"
        return f"{subject}のライフが{amount:+d}"
    return None


def _lookup_card_name(card_no: object, card_catalog: dict[str, Any]) -> str | None:
    if not isinstance(card_no, str):
        return None
    card = card_catalog.get(card_no)
    return getattr(card, "name", None)


def _attach_round_event_numbers(rendered: list[str]) -> list[str]:
    numbered: list[str] = []
    round_event_numbers: dict[int, int] = {}
    for line in rendered:
        round_no = _extract_round_no_from_rendered_line(line)
        if round_no is None:
            numbered.append(line)
            continue
        event_no = round_event_numbers.get(round_no, 0) + 1
        round_event_numbers[round_no] = event_no
        prefix = f"[R{round_no:02d}]"
        numbered.append(line.replace(prefix, f"{prefix}[E{event_no:03d}]", 1))
    return numbered


def _extract_round_no_from_rendered_line(line: str) -> int | None:
    if not line.startswith("[R"):
        return None
    end = line.find("]")
    if end < 0:
        return None
    round_text = line[2:end]
    if not round_text.isdigit():
        return None
    return int(round_text)


def _render_system_event_from_message(
    round_no: int,
    actor: str,
    direction: str,
    message: dict[str, object],
    card_catalog: dict[str, Any],
) -> str | None:
    return None


if __name__ == "__main__":
    raise SystemExit(main())
