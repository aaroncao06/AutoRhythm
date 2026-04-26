from __future__ import annotations

import json as _json
import os
import sys
from pathlib import Path


def _extract_json(response: str) -> str:
    start = -1
    for i, ch in enumerate(response):
        if ch in ("[", "{"):
            start = i
            break
    if start == -1:
        return "[]"
    bracket = response[start]
    closer = "]" if bracket == "[" else "}"
    end = response.rfind(closer)
    if end == -1:
        return "[]"
    return response[start : end + 1]


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

    def send(self, command: str, total_timeout: float = 120.0) -> str:
        if not self._connected or self._to_pipe is None or self._from_pipe is None:
            raise RuntimeError("Not connected to Audacity")
        os.write(self._to_pipe, (command + "\n").encode())
        response_parts: list[str] = []
        import select
        import time

        deadline = time.monotonic() + total_timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ready, _, _ = select.select(
                [self._from_pipe], [], [], min(10.0, remaining)
            )
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

    def get_tracks(self) -> list[dict]:
        resp = self.send("GetInfo: Type=Tracks Format=JSON")
        return _json.loads(_extract_json(resp))

    def export_audio(self, path: Path, num_channels: int = 1) -> bool:
        resp = self.send(f'Export2: Filename="{path}" NumChannels={num_channels}')
        return "OK" in resp

    def select_tracks(self, track: int, count: int = 1) -> bool:
        resp = self.send(
            f"SelectTracks: Track={track} TrackCount={count} Mode=Set"
        )
        return "OK" in resp

    def select_all(self) -> bool:
        resp = self.send("SelectAll:")
        return "OK" in resp

    def solo_track(self, track: int, solo: bool = True) -> bool:
        val = 1 if solo else 0
        resp = self.send(f"SetTrack: Track={track} Solo={val}")
        return "OK" in resp

    def play(self) -> bool:
        resp = self.send("Play:")
        return "OK" in resp

    def stop(self) -> bool:
        resp = self.send("Stop:")
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
