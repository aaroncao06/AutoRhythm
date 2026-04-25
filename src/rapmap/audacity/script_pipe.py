from __future__ import annotations

import os
import sys
from pathlib import Path


class AudacityPipe:
    def __init__(self) -> None:
        self._to_pipe: int | None = None
        self._from_pipe: int | None = None
        self._connected = False

    def connect(self, timeout: float = 2.0) -> bool:
        if sys.platform == "win32":
            to_path = r"\\.\pipe\ToSrvPipe"
            from_path = r"\\.\pipe\FromSrvPipe"
        else:
            to_path = "/tmp/audacity_script_pipe.to"
            from_path = "/tmp/audacity_script_pipe.from"

        try:
            if not Path(to_path).exists() or not Path(from_path).exists():
                return False
            self._to_pipe = os.open(to_path, os.O_WRONLY | os.O_NONBLOCK)
            self._from_pipe = os.open(from_path, os.O_RDONLY | os.O_NONBLOCK)
            self._connected = True
            return True
        except (OSError, FileNotFoundError):
            self._cleanup()
            return False

    def send(self, command: str) -> str:
        if not self._connected or self._to_pipe is None or self._from_pipe is None:
            raise RuntimeError("Not connected to Audacity")
        os.write(self._to_pipe, (command + "\n").encode())
        response_parts: list[str] = []
        import select

        while True:
            ready, _, _ = select.select([self._from_pipe], [], [], 10.0)
            if not ready:
                break
            data = os.read(self._from_pipe, 4096).decode()
            response_parts.append(data)
            if "BatchCommand finished:" in data:
                break
        return "".join(response_parts)

    def import_audio(self, path: Path) -> bool:
        resp = self.send(f'Import2: Filename="{path}"')
        return "OK" in resp

    def new_label_track(self) -> bool:
        resp = self.send("NewLabelTrack:")
        return "OK" in resp

    def set_track_name(self, track: int, name: str) -> bool:
        resp = self.send(f'SetTrack: Track={track} Name="{name}"')
        return "OK" in resp

    def import_labels(self, path: Path) -> bool:
        resp = self.send(f'Import2: Filename="{path}"')
        return "OK" in resp

    def save_project(self, path: Path) -> bool:
        resp = self.send(f'SaveProject2: Filename="{path}"')
        return "OK" in resp

    def close(self) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        if self._to_pipe is not None:
            try:
                os.close(self._to_pipe)
            except OSError:
                pass
            self._to_pipe = None
        if self._from_pipe is not None:
            try:
                os.close(self._from_pipe)
            except OSError:
                pass
            self._from_pipe = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected
