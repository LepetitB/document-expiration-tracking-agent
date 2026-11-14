"""Start the web app on http://localhost:5000

    python run.py            # default port 5000
    python run.py --port 8080
"""
from __future__ import annotations

import argparse
import os
import threading
import time
import webbrowser

from app.web.server import create_app


def _daily_checker(interval_hours: float = 24) -> None:
    from app.core.notifier import run_expiry_check

    while True:
        try:
            sent = run_expiry_check()
            if sent:
                print(f"[scheduler] sent {len(sent)} alert(s)")
        except Exception as e:  # never crash the web server
            print(f"[scheduler] error: {e}")
        time.sleep(interval_hours * 3600)


def main() -> None:
    import sys

    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")))
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--no-scheduler", action="store_true")
    args = p.parse_args()

    app = create_app()
    if not args.no_scheduler:
        threading.Thread(target=_daily_checker, daemon=True).start()
    url = f"http://localhost:{args.port}"
    print(f"\n  Document Expiration Tracking Agent → {url}\n")
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
