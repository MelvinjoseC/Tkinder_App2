"""
Desktop launcher that boots the Django server (if needed) and opens the
existing Marine-Ops SPA inside a PyWebView window.

Run:
    python desktop_app.py

This mirrors the experience of running ``python manage.py runserver 8000``
and visiting http://127.0.0.1:8000/ in a browser, but wraps everything in a
lightweight desktop window so no code changes are required.
"""

from __future__ import annotations

import atexit
import os
import subprocess
import sys
import time
import types
from contextlib import suppress
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", BASE_DIR))


def ensure_requests_ca_bundle() -> None:
    """Ensure Requests has a real CA file on disk."""
    try:
        import certifi
    except ImportError:
        certifi = None  # type: ignore[assignment]

    if getattr(sys, "frozen", False):
        target_dir = Path(tempfile.gettempdir()) / "marine_ops_ca"
    else:
        target_dir = BASE_DIR / "certs"
    target_dir.mkdir(parents=True, exist_ok=True)
    cert_path = target_dir / "cacert.pem"

    if not cert_path.exists():
        if certifi is None:
            debug_path = Path.home() / "MarineOps_import_error.log"
            with open(debug_path, "w", encoding="utf-8") as fh:
                fh.write("certifi not available and bundle missing\n")
            return
        try:
            # certifi.contents() returns the CA bundle text even when packaged.
            bundle_text = certifi.contents()
        except AttributeError:
            bundle_text = Path(certifi.where()).read_text(encoding="ascii")  # type: ignore[arg-type]
        cert_path.write_text(bundle_text, encoding="ascii")

    os.environ.setdefault("REQUESTS_CA_BUNDLE", str(cert_path))
    os.environ.setdefault("SSL_CERT_FILE", str(cert_path))

    if certifi is None:
        fake = types.ModuleType("certifi")
        fake.__all__ = ["where", "contents"]
        sys.modules["certifi"] = fake
        certifi = fake  # type: ignore[assignment]

    def _where() -> str:
        return str(cert_path)

    def _contents() -> str:
        return cert_path.read_text(encoding="ascii")

    certifi.where = _where  # type: ignore[attr-defined]
    certifi.contents = _contents  # type: ignore[attr-defined]

    try:
        import certifi.core as certifi_core  # type: ignore[attr-defined]
    except Exception:
        return

    certifi_core.where = _where  # type: ignore[attr-defined]
    certifi_core.contents = _contents  # type: ignore[attr-defined]
    if hasattr(certifi_core, "_CACERT_PATH"):
        certifi_core._CACERT_PATH = str(cert_path)
    if hasattr(certifi_core, "_CACERT_CTX"):
        certifi_core._CACERT_CTX = None


ensure_requests_ca_bundle()

import requests
import webview

MANAGE_PY = BASE_DIR / "manage.py"

DJANGO_HOST = os.environ.get("DESKTOP_APP_HOST", "127.0.0.1")
DJANGO_PORT = os.environ.get("DESKTOP_APP_PORT", "8000")
DJANGO_URL = f"http://{DJANGO_HOST}:{DJANGO_PORT}/"


def start_django_server() -> subprocess.Popen:
    """
    Launch ``manage.py runserver`` if the host:port is not already serving.
    """
    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "Loading_Computer.settings")
    command = [
        sys.executable,
        str(MANAGE_PY),
        "runserver",
        f"{DJANGO_HOST}:{DJANGO_PORT}",
        "--noreload",
    ]
    return subprocess.Popen(
        command,
        cwd=str(BASE_DIR),
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


def wait_for_server(url: str, timeout: float = 30.0) -> bool:
    """
    Poll the given URL until it becomes available or the timeout expires.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = requests.get(url, timeout=2)
        except requests.RequestException:
            time.sleep(0.5)
            continue

        if response.status_code < 500:
            return True
        time.sleep(0.5)

    return False


def stop_process(proc: subprocess.Popen) -> None:
    """Gracefully terminate the Django subprocess."""
    if proc.poll() is not None:
        return

    with suppress(ProcessLookupError):
        proc.terminate()

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def server_already_running() -> bool:
    try:
        requests.get(DJANGO_URL, timeout=1)
    except requests.RequestException:
        return False
    return True


def main() -> None:
    server_process = None

    if not server_already_running():
        server_process = start_django_server()
        atexit.register(stop_process, server_process)

        if not wait_for_server(DJANGO_URL):
            if server_process is not None:
                stop_process(server_process)
            raise SystemExit(
                "Django server did not start in time. Check the console output for details."
            )

    window = webview.create_window(
        title="Marine-Ops",
        url=DJANGO_URL,
        width=1280,
        height=820,
        resizable=True,
        text_select=True,
    )

    try:
        webview.start(gui="tkinter", debug=False)
    finally:
        if server_process is not None:
            stop_process(server_process)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
