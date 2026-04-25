from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Interval:
    xmin: float
    xmax: float
    text: str


@dataclass
class IntervalTier:
    name: str
    intervals: list[Interval] = field(default_factory=list)


def parse_textgrid(path: Path) -> dict[str, IntervalTier]:
    text = path.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines()]

    tiers: dict[str, IntervalTier] = {}
    i = 0
    while i < len(lines):
        if re.match(r'class\s*=\s*"IntervalTier"', lines[i]):
            i += 1
            name = _parse_string(lines, i, "name")
            i += 1
            while i < len(lines) and not lines[i].startswith("intervals:"):
                i += 1
            if i >= len(lines):
                break
            size = int(lines[i].split("=")[1].strip()) if "=" in lines[i] else 0
            i += 1
            tier = IntervalTier(name=name)
            for _ in range(size):
                while i < len(lines) and not re.match(r"intervals\s*\[\d+\]", lines[i]):
                    i += 1
                i += 1
                xmin = _parse_float(lines, i, "xmin")
                i += 1
                xmax = _parse_float(lines, i, "xmax")
                i += 1
                interval_text = _parse_quoted(lines, i, "text")
                i += 1
                tier.intervals.append(Interval(xmin=xmin, xmax=xmax, text=interval_text))
            tiers[name] = tier
        else:
            i += 1
    return tiers


def _parse_float(lines: list[str], idx: int, key: str) -> float:
    if idx >= len(lines):
        raise ValueError(f"Expected '{key}' at line {idx}, but file ended")
    match = re.search(r"=\s*(.+)", lines[idx])
    if not match:
        raise ValueError(f"Cannot parse float for '{key}' from: {lines[idx]}")
    return float(match.group(1).strip())


def _parse_string(lines: list[str], idx: int, key: str) -> str:
    return _parse_quoted(lines, idx, key)


def _parse_quoted(lines: list[str], idx: int, key: str) -> str:
    if idx >= len(lines):
        raise ValueError(f"Expected '{key}' at line {idx}, but file ended")
    match = re.search(r'=\s*"(.*)"', lines[idx])
    if not match:
        raise ValueError(f"Cannot parse string for '{key}' from: {lines[idx]}")
    return match.group(1)
