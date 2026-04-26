from __future__ import annotations

import platform
import subprocess


def focus_audacity() -> bool:
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["osascript", "-e", 'tell application "Audacity" to activate'],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        elif system == "Linux":
            result = subprocess.run(
                ["wmctrl", "-a", "Audacity"],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        elif system == "Windows":
            script = '(New-Object -ComObject WScript.Shell).AppActivate("Audacity")'
            result = subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return False


def launch_audacity() -> subprocess.Popen | None:
    system = platform.system()
    try:
        if system == "Darwin":
            return subprocess.Popen(["open", "-a", "Audacity"])
        elif system == "Linux":
            return subprocess.Popen(["audacity"])
        elif system == "Windows":
            return subprocess.Popen(["audacity.exe"])
    except FileNotFoundError:
        return None
    return None


def arrange_side_by_side() -> None:
    system = platform.system()
    try:
        if system == "Darwin":
            script = (
                'tell application "System Events"\n'
                "  set screenWidth to (do shell script "
                '"system_profiler SPDisplaysDataType'
                " | awk '/Resolution/{print $2; exit}'\") as integer\n"
                "  set screenHeight to (do shell script "
                '"system_profiler SPDisplaysDataType'
                " | awk '/Resolution/{print $4; exit}'\") as integer\n"
                "  set halfWidth to screenWidth div 2\n"
                '  tell process "Audacity"\n'
                "    set position of window 1 to {0, 0}\n"
                "    set size of window 1 to {halfWidth, screenHeight}\n"
                "  end tell\n"
                "end tell"
            )
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=10,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
