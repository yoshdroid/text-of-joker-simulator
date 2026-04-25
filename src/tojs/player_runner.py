from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .protocol import Message, read_message, write_message


class PlayerProcess:
    def __init__(self, command: list[str], cwd: str | None = None) -> None:
        self.process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def request(self, message: Message) -> Message:
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        write_message(self.process.stdin, message)
        response = read_message(self.process.stdout)
        if response is None:
            raise RuntimeError("player process closed stdout before sending a response")
        return response

    def notify(self, message: Message) -> None:
        assert self.process.stdin is not None
        write_message(self.process.stdin, message)

    def close(self) -> None:
        if self.process.stdin is not None and not self.process.stdin.closed:
            self.process.stdin.close()
        if self.process.stdout is not None and not self.process.stdout.closed:
            self.process.stdout.close()
        if self.process.stderr is not None and not self.process.stderr.closed:
            self.process.stderr.close()
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)


def build_python_bot_command(deck_path: str | Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "tojs.bot",
        "--deck",
        str(deck_path),
    ]
