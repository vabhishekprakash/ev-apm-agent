"""Capture the 20-second hook clip as an animated GIF (issue #22).

Drives the REAL dashboard in headless Chromium while the demo fixture streams
through the detector, screenshotting each poll cycle — nothing is mocked. The
GIF appears at the top of the README.

Usage: py scripts/capture_hook_gif.py 
Output: docs/assets/hook_selfrecovery.gif
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "assets" / "hook_selfrecovery.gif"
PORT = 8055
FRAME_EVERY_S = 0.8
FRAMES = 26


# The committed GIF is captured from the real err-sequence export
# (data/interim/sequences_replay, real err1051 self-recovery) via a DATA_DIR
# override; the fixture default keeps this script runnable on a fresh clone
# where the gitignored real data is absent.
DATA_DIR = os.environ.get("DATA_DIR", str(ROOT / "tests" / "fixtures" / "demo_replay"))
SPEED = os.environ.get("REPLAY_SPEED_MULTIPLIER", "45")
# frame at which the decision trace is opened, so the clip shows the new
# "why this recommendation" panel expanding on a self-recovery row
OPEN_TRACE_AT = 8
# frame at which the view pans down to the drift chart (the degrade-then-fault
# money shot) for the closing beat. HOOK_END_ON=trace skips that pan and ends
# the clip on the decision-trace panel instead — used for the committed README
# GIF, which is captured from the REAL sequences stream (no session history,
# so there is no drift arc to show and the trace IS the closing shot).
SCROLL_TO_CHART_AT = 16
END_ON = os.environ.get("HOOK_END_ON", "chart")

# filter the queue to err1051 so the self-recovery rows surface, then click one
FILTER_JS = """() => {
  const chip = [...document.querySelectorAll('#coverage .chip:not(.dim)')]
    .find(c => c.textContent.includes('err1051'));
  if (chip) chip.click();
}"""
OPEN_TRACE_JS = """() => {
  const rows = [...document.querySelectorAll('tr.alert-row')];
  const pick = rows.find(t => t.textContent.includes('self-recovered')) || rows[0];
  if (pick) pick.click();
}"""
# keep the expanded trace centred in frame as the 2s poll re-renders
SCROLL_JS = """() => {
  const t = document.querySelector('tr.trace-row');
  if (t) t.scrollIntoView({block: 'center'});
}"""


def main() -> None:
    env = {**os.environ}
    ui = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", str(PORT),
         "--log-level", "warning"],
        cwd=ROOT / "ui", env=env)
    try:
        time.sleep(4)
        replay = subprocess.Popen(
            [sys.executable, str(ROOT / "replay" / "main.py")],
            stdout=subprocess.PIPE, env={**env,
                "DATA_DIR": DATA_DIR, "REPLAY_SPEED_MULTIPLIER": SPEED})
        detector = subprocess.Popen(
            [sys.executable, "main.py"], stdin=replay.stdout,
            cwd=ROOT / "detector", env={**env, "ALERT_SINK": "http",
                "ALERT_URL": f"http://localhost:{PORT}/alerts"})

        frames = []
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://localhost:{PORT}/")
            for i in range(FRAMES):
                time.sleep(FRAME_EVERY_S)
                if i == OPEN_TRACE_AT - 2:
                    page.evaluate(FILTER_JS)
                if i == OPEN_TRACE_AT:
                    page.evaluate(OPEN_TRACE_JS)
                if i >= OPEN_TRACE_AT and (END_ON == "trace" or i < SCROLL_TO_CHART_AT):
                    page.evaluate(SCROLL_JS)
                if i == SCROLL_TO_CHART_AT and END_ON != "trace":
                    page.evaluate("() => { const c = document.getElementById('lower');"
                                  " if (c) c.scrollIntoView({block: 'end'}); }")
                frames.append(Image.open(
                    __import__("io").BytesIO(page.screenshot())).convert("P",
                                                                         palette=Image.ADAPTIVE))
            browser.close()
        detector.terminate(), replay.terminate()

        frames[0].save(OUT, save_all=True, append_images=frames[1:],
                       duration=int(FRAME_EVERY_S * 1000), loop=0, optimize=True)
        print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(frames)} frames)")
    finally:
        ui.terminate()


if __name__ == "__main__":
    main()
