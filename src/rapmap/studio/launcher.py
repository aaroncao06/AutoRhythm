from __future__ import annotations

import time
from pathlib import Path

from rapmap.studio.window_manager import arrange_side_by_side, launch_audacity


def launch_studio(project_dir: Path, port: int = 8765) -> None:
    audacity_proc = launch_audacity()
    if audacity_proc:
        print("Launching Audacity...")
    else:
        print("Could not launch Audacity — start it manually")

    time.sleep(2)

    from rapmap.audacity.script_pipe import AudacityPipe

    pipe = AudacityPipe()
    if pipe.connect():
        pipe.close()
        print("Connected to Audacity via mod-script-pipe")
    else:
        print("Audacity mod-script-pipe not ready — enable in Edit > Preferences > Modules")

    arrange_side_by_side()

    from rapmap.editor.server import launch_editor

    launch_editor(project_dir, port=port, use_webview=True)
