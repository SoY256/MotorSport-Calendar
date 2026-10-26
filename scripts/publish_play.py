"""Publish a signed app bundle to Google Play without a browser login.

Uses the Google Play Developer API with the "Secar Play publisher" service
account (Play Console: Secar only, "release to testing tracks"). Its key is
kept outside the repository, by default in ``%USERPROFILE%\\.secar\\play-publisher.json``
(override with ``SECAR_PLAY_KEY``).

    python scripts/publish_play.py --check
    python scripts/publish_play.py --aab release/secar-0.1.22-25.aab --notes "..."

The release goes to the closed testing track at 100% and is sent for
Google's review on commit (managed publishing is off for the app).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

PACKAGE = "secar.aab"
API = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{PACKAGE}"
UPLOAD = f"https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/{PACKAGE}"
SCOPE = "https://www.googleapis.com/auth/androidpublisher"
DEFAULT_KEY = Path(os.environ.get("USERPROFILE", Path.home())) / ".secar" / "play-publisher.json"


def session() -> requests.Session:
    key = Path(os.environ.get("SECAR_PLAY_KEY", DEFAULT_KEY))
    if not key.is_file():
        raise SystemExit(f"Service-account key not found: {key}")
    credentials = service_account.Credentials.from_service_account_file(str(key), scopes=[SCOPE])
    credentials.refresh(Request())
    http = requests.Session()
    http.headers["Authorization"] = f"Bearer {credentials.token}"
    return http


def call(http: requests.Session, method: str, url: str, **kwargs) -> dict:
    response = http.request(method, url, timeout=600, **kwargs)
    if response.status_code >= 400:
        raise SystemExit(f"{method} {url.split('?')[0]} failed ({response.status_code}): {response.text[:800]}")
    return response.json() if response.content else {}


def version_name(code: int) -> str:
    """Release name "24 (0.1.21)" from pubspec.yaml when it matches the bundle."""
    import re

    pubspec = Path(__file__).resolve().parents[1] / "pubspec.yaml"
    match = re.search(r"^version:\s*([^+\s]+)\+(\d+)", pubspec.read_text(encoding="utf-8"), re.M)
    return match.group(1) if match and int(match.group(2)) == code else ""


def upload_bundle(http: requests.Session, edit: str, aab: Path) -> int:
    size = aab.stat().st_size
    start = http.post(
        f"{UPLOAD}/edits/{edit}/bundles?uploadType=resumable",
        headers={"X-Upload-Content-Type": "application/octet-stream", "X-Upload-Content-Length": str(size)},
        timeout=120,
    )
    if start.status_code >= 400:
        raise SystemExit(f"Bundle upload could not start ({start.status_code}): {start.text[:800]}")
    location = start.headers["Location"]
    for attempt in range(3):
        with aab.open("rb") as data:
            response = http.put(location, data=data, headers={"Content-Type": "application/octet-stream"}, timeout=1800)
        if response.status_code < 400:
            return int(response.json()["versionCode"])
        time.sleep(10 * (attempt + 1))
    raise SystemExit(f"Bundle upload failed ({response.status_code}): {response.text[:800]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aab", type=Path, help="Signed .aab to publish")
    parser.add_argument("--notes", default="", help="Release notes (en-US)")
    parser.add_argument("--track", default="alpha", help="Testing track id (closed testing 'Alpha' = alpha)")
    parser.add_argument("--check", action="store_true", help="Only verify access and list the tracks")
    parser.add_argument("--no-commit", action="store_true", help="Validate the release, then discard it")
    args = parser.parse_args()

    http = session()
    edit = call(http, "POST", f"{API}/edits")["id"]
    try:
        if args.check:
            for track in call(http, "GET", f"{API}/edits/{edit}/tracks").get("tracks", []):
                releases = [
                    f"{release.get('name')} [{release.get('status')}] codes={release.get('versionCodes')}"
                    for release in track.get("releases", [])
                ]
                print(f"{track['track']}: {'; '.join(releases) or '-'}")
            return 0
        if not args.aab or not args.aab.is_file():
            raise SystemExit("--aab must point to a signed bundle")
        print(f"Uploading {args.aab.name} ({args.aab.stat().st_size / 1e6:.1f} MB)...", flush=True)
        code = upload_bundle(http, edit, args.aab)
        name = f"{code} ({version_name(code)})" if version_name(code) else str(code)
        release = {"name": name, "versionCodes": [str(code)], "status": "completed"}
        if args.notes:
            release["releaseNotes"] = [{"language": "en-US", "text": args.notes[:500]}]
        call(http, "PUT", f"{API}/edits/{edit}/tracks/{args.track}", json={"track": args.track, "releases": [release]})
        call(http, "POST", f"{API}/edits/{edit}:validate")
        if args.no_commit:
            print(f"Validated release {name} on {args.track}; discarded (--no-commit)")
            return 0
        call(http, "POST", f"{API}/edits/{edit}:commit")
        edit = ""
        print(f"Published release {name} to {args.track} (100%), sent for review")
        return 0
    finally:
        if edit:
            http.delete(f"{API}/edits/{edit}", timeout=60)


if __name__ == "__main__":
    sys.exit(main())
