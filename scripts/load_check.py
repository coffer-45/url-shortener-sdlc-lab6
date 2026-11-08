"""Local HTTP smoke/load check: 20 authenticated clients, main pages and redirects.

Run against a separate local runserver after migrate. Creates and removes temporary
users/links in the configured database; do not run against production data.
"""

import argparse
import concurrent.futures
import http.cookiejar
import os
import secrets
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from threading import Barrier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.contrib.auth import get_user_model  # noqa: E402
from links.models import ShortLink  # noqa: E402


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def status(opener, url):
    try:
        with opener.open(url, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def worker(base, username, password, code, barrier, rounds):
    cookies = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies), NoRedirect())
    if status(opener, base + "/login/") != 200:
        raise RuntimeError("Login page unavailable")
    csrf = next(cookie.value for cookie in cookies if cookie.name == "csrftoken")
    payload = urllib.parse.urlencode({
        "username": username, "password": password, "csrfmiddlewaretoken": csrf,
    }).encode()
    try:
        opener.open(urllib.request.Request(base + "/login/", payload), timeout=10)
    except urllib.error.HTTPError as exc:
        if exc.code != 302:
            raise
    if status(opener, base + "/links/") != 200:
        raise RuntimeError("Authentication failed")
    barrier.wait(timeout=30)
    samples = []
    for _ in range(rounds):
        for path, expected in (("/links/", 200), ("/links/new/", 200), (f"/{code}/", 302)):
            start = time.perf_counter()
            result = status(opener, base + path)
            samples.append((path, time.perf_counter() - start, result == expected))
    return samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--clients", type=int, default=20)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    base = args.base.rstrip("/")
    if not base.startswith(("http://127.0.0.1:", "http://localhost:")):
        parser.error("Only a local HTTP server is supported")
    if args.clients < 1 or args.rounds < 1:
        parser.error("clients and rounds must be positive")
    prefix = "load_" + secrets.token_hex(8)
    password = secrets.token_urlsafe(24)
    users = []
    try:
        for index in range(args.clients):
            users.append(get_user_model().objects.create_user(
                username=f"{prefix}_{index}", password=password
            ))
        code = secrets.token_urlsafe(8).replace("-", "a").replace("_", "b")
        ShortLink.objects.create(owner=users[0], code=code, original_url="https://example.com/")
        barrier = Barrier(args.clients)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.clients) as pool:
            futures = [pool.submit(worker, base, user.username, password, code, barrier, args.rounds)
                       for user in users]
            results = [sample for future in futures for sample in future.result()]
        durations = sorted(sample[1] for sample in results)
        failures = sum(not sample[2] for sample in results)
        p95 = durations[int((len(durations) - 1) * 0.95)]
        print(f"clients={args.clients} requests={len(results)} errors={failures} "
              f"median={statistics.median(durations):.3f}s p95={p95:.3f}s "
              f"max={durations[-1]:.3f}s")
        print("NFR-01 (<2s per request):", "PASS" if not failures and durations[-1] < 2 else "FAIL")
        return 0 if not failures and durations[-1] < 2 else 1
    finally:
        get_user_model().objects.filter(pk__in=[user.pk for user in users]).delete()


if __name__ == "__main__":
    sys.exit(main())
