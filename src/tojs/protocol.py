from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import IO
from typing import Any


@dataclass(frozen=True)
class Message:
    type: str
    request_id: str
    payload: dict[str, Any]


def encode_message(message: Message) -> str:
    return json.dumps(asdict(message), ensure_ascii=False, separators=(",", ":"))


def decode_message(line: str) -> Message:
    raw = json.loads(line)
    return Message(
        type=raw["type"],
        request_id=raw["request_id"],
        payload=raw.get("payload", {}),
    )


def render_event_log(round_no: int, actor: str, kind: str, details: str) -> str:
    return f"[R{round_no:02d}][{actor}][{kind}] {details}"


def write_message(stream: IO[str], message: Message) -> None:
    stream.write(encode_message(message) + "\n")
    stream.flush()


def read_message(stream: IO[str]) -> Message | None:
    line = stream.readline()
    if line == "":
        return None
    return decode_message(line.strip())

