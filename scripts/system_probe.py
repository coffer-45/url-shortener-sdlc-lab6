"""Local system test: real HTTP load, server RSS, SQLite after server restart.

Uses a temporary database under /tmp/opencode; never touches the project's DB.
Requires Django and Linux /proc for RSS measurement. Not a production benchmark.
"""

import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, env):
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=env, check=True,
                          capture_output=True, text=True)


def rss_kib(pid):
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    raise RuntimeError("VmRSS not available")


def wait_ready(proc, url):
    for _ in range(100):
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early: {proc.returncode}")
        try:
            with urllib.request.urlopen(url + "/login/", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise TimeoutError("local server did not start")


def start_server(env, url, log):
    proc = subprocess.Popen([sys.executable, "manage.py", "runserver", "--noreload",
                             url.removeprefix("http://")], cwd=ROOT, env=env,
                            stdout=log, stderr=subprocess.STDOUT)
    try:
        wait_ready(proc, url)
    except BaseException:
        stop_server(proc)
        raise
    return proc


def stop_server(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def main():
    with tempfile.TemporaryDirectory(prefix="lab6-", dir="/tmp/opencode") as tmp:
        env = {**os.environ, "DJANGO_DB_PATH": str(Path(tmp) / "test.sqlite3"),
               "DJANGO_DEBUG": "1", "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1"}
        run("manage.py", "migrate", "--noinput", env=env)
        run("manage.py", "shell", "-c", (
            "from django.contrib.auth import get_user_model; "
            "from links.models import ShortLink; "
            "u=get_user_model().objects.create_user(username='persistent', password='Pass-12345!'); "
            "ShortLink.objects.create(owner=u, code='persistcode', original_url='https://example.org/persist')"
        ), env=env)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        with open(Path(tmp) / "server.log", "w") as log:
            proc = start_server(env, url, log)
            try:
                before = rss_kib(proc.pid)
                peak = [before]
                done = threading.Event()

                def sample():
                    while not done.wait(0.02):
                        try:
                            peak[0] = max(peak[0], rss_kib(proc.pid))
                        except (OSError, ValueError):
                            return

                monitor = threading.Thread(target=sample, daemon=True)
                monitor.start()
                try:
                    load = run("scripts/load_check.py", "--base", url, env=env)
                finally:
                    done.set()
                    monitor.join()
                print(load.stdout.strip())
                print(f"server RSS: before={before} KiB peak={peak[0]} KiB "
                      f"delta={peak[0] - before} KiB (Linux /proc, one runserver process)")
            finally:
                stop_server(proc)

            # Fresh server process, same database file: verify URL and retained count.
            proc = start_server(env, url, log)
            try:
                opener = urllib.request.build_opener(_NoRedirect())
                try:
                    opener.open(url + "/persistcode/", timeout=5)
                    raise AssertionError("Expected HTTP 302")
                except urllib.error.HTTPError as exc:
                    assert exc.code == 302 and exc.headers["Location"] == "https://example.org/persist"
                print("SQLite persistence after server restart: PASS (302, original URL retained)")
            finally:
                stop_server(proc)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


if __name__ == "__main__":
    main()
