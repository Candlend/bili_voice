from __future__ import annotations

import socket
import threading
import time
import webbrowser
from typing import Optional, Tuple

import uvicorn

try:
    import webview  # pywebview
except Exception:
    webview = None  # type: ignore


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5176
PORT_SCAN_MAX_TRIES = 25  # try a range [DEFAULT_PORT, DEFAULT_PORT + PORT_SCAN_MAX_TRIES)


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        try:
            sock.connect((host, port))
            return True
        except Exception:
            return False


def find_free_port(host: str, base_port: int = DEFAULT_PORT, max_tries: int = PORT_SCAN_MAX_TRIES) -> int:
    # Try base_port; if occupied, increment until free or until max_tries
    for i in range(max_tries):
        port = base_port + i
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    # Fallback: 0 lets OS assign an ephemeral free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def start_uvicorn(host: str, port: int) -> None:
    # Import here to avoid side effects during PyInstaller analysis
    from backend.main import app

    config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    server.run()


def wait_for_server(host: str, port: int, timeout: float = 10.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            try:
                sock.connect((host, port))
                return True
            except Exception:
                pass
        time.sleep(0.2)
    return False


def main() -> None:
    host = DEFAULT_HOST
    # If default port is already serving, automatically pick a new free port to avoid conflicts
    port = find_free_port(host, DEFAULT_PORT, PORT_SCAN_MAX_TRIES)
    url = f"http://{host}:{port}"

    t = threading.Thread(target=start_uvicorn, args=(host, port), daemon=True)
    t.start()

    ok = wait_for_server(host, port, 15.0)
    if not ok:
        print(f"Backend did not start at {url}. Opening browser anyway.")
    if webview is not None:
        # Launch desktop window
        window = webview.create_window(
            title="BiliVoice",
            url=url,
            width=1936,
            height=1119,
            resizable=True,
        )
        # When the window closes, proactively cleanup external child processes
        try:
            def _on_closed():
                try:
                    # Ensure any tracked subprocesses (e.g., GPT-SoVITS) are terminated
                    from backend import proc_manager
                    proc_manager.cleanup_all()
                except Exception:
                    pass
        except Exception:
            _on_closed = None  # type: ignore
        # Prefer pywebview events API if available (pywebview >= 4)
        try:
            if _on_closed is not None:
                window.events.closed += _on_closed  # type: ignore[attr-defined]
        except Exception:
            # Fallback: rely on atexit hooks in proc_manager + Job Object kill-on-close
            pass
        webview.start()
    else:
        # Fallback to default browser if pywebview is unavailable
        webbrowser.open(url)
        # Keep process alive while uvicorn thread runs
        try:
            while t.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
