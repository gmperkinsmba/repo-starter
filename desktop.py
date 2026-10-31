#!/usr/bin/env python3
"""Native macOS shell for Repo Starter."""
from __future__ import annotations

import threading

import factory
import webview
from desktop_policy import install_policy


def run() -> None:
    server = factory.make_server(port=0)
    worker = threading.Thread(target=server.serve_forever, name="repo-factory-http", daemon=True)
    started = False
    try:
        worker.start()
        started = True
        origin = f"http://127.0.0.1:{server.server_port}"
        install_policy(origin)
        webview.create_window(
            "Repo Starter",
            f"{origin}/?desktop=1",
            width=1080,
            height=760,
            min_size=(800, 580),
        )
        webview.start()
    finally:
        if started:
            server.shutdown()
        server.server_close()
        if started:
            worker.join(timeout=3)


if __name__ == "__main__":
    try:
        run()
    except Exception:
        import AppKit

        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Repo Starter could not start")
        alert.setInformativeText_("The local app failed to open. Restart Repo Starter and try again.")
        alert.addButtonWithTitle_("OK")
        alert.runModal()
        raise SystemExit(1)
