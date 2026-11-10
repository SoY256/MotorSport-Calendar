"""Validate localized store copy/media and save a Google Play listing edit.

No app bundle, release track, price, country or permission is changed.
By default this only validates local files. --commit publishes the store
edit to Play Console and sends it for Google's review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "play_store"
LOCALES = ("en-US", "pl-PL")
IMAGE_TYPES = ("phoneScreenshots", "featureGraphic", "icon")
HEADERS = {
    "APP NAME": "title", "NAZWA APLIKACJI": "title",
    "SHORT DESCRIPTION": "shortDescription", "KRÓTKI OPIS": "shortDescription",
    "FULL DESCRIPTION": "fullDescription", "PEŁNY OPIS": "fullDescription",
}


def read_listing(path: Path, language: str) -> dict[str, str]:
    text = path.read_text(encoding="utf-8").strip()
    pattern = re.compile(r"^(" + "|".join(HEADERS) + r")(?:[ \t]*\([^\n)]*\))?[ \t]*$", re.M)
    marks = list(pattern.finditer(text))
    if [HEADERS[mark.group(1)] for mark in marks] != ["title", "shortDescription", "fullDescription"]:
        raise ValueError(f"{path.name}: expected title, short description and full description, in order")
    listing = {"language": language}
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        listing[HEADERS[mark.group(1)]] = text[mark.end():end].strip()
    for field, limit in (("title", 30), ("shortDescription", 80), ("fullDescription", 4000)):
        value = listing[field]
        if not value or len(value) > limit:
            raise ValueError(f"{language} {field}: {len(value)} characters, expected 1-{limit}")
        if field != "fullDescription" and "\n" in value:
            raise ValueError(f"{language} {field}: must be a single line")
    return listing


def video_url(text: str) -> str:
    value = text.strip()
    url = urlsplit(value)
    query = parse_qs(url.query)
    if url.scheme != "https" or url.fragment:
        raise ValueError("Preview video must be an HTTPS YouTube video URL without a timestamp")
    if url.netloc in ("youtube.com", "www.youtube.com") and url.path == "/watch" and set(query) == {"v"}:
        identifier = query["v"][0] if len(query["v"]) == 1 else ""
    elif url.netloc == "youtu.be" and not url.query:
        identifier = url.path.removeprefix("/")
    else:
        raise ValueError("Use a single YouTube video URL, not a playlist, channel or tracking URL")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", identifier):
        raise ValueError("Invalid YouTube video identifier")
    return value


def media_files(folder: Path) -> dict[str, list[Path]]:
    from PIL import Image

    photos = sorted((folder / "phone-screenshots").glob("*.jpg"))
    if len(photos) != 6:
        raise ValueError(f"{folder.name}: expected six ordered phone screenshots, found {len(photos)}")
    files = {"phoneScreenshots": photos, "featureGraphic": [folder / "feature-graphic.jpg"]}
    for kind, paths in files.items():
        expected = (1080, 1920) if kind == "phoneScreenshots" else (1024, 500)
        for path in paths:
            with Image.open(path) as image:
                if image.mode != "RGB" or image.size != expected or image.format != "JPEG":
                    raise ValueError(f"{path}: expected RGB JPEG {expected}, got {image.mode} {image.size} {image.format}")
                image.verify()
    alt = (folder / "alt-text.txt").read_text(encoding="utf-8").splitlines()
    if len(alt) != 7 or any(not 1 <= len(line.split(": ", 1)[-1]) <= 140 for line in alt):
        raise ValueError(f"{folder.name}: expected seven nonempty alt descriptions, at most 140 characters each")
    return files


def fingerprint(snapshot: dict) -> dict:
    return {
        "listings": sorted(snapshot["listings"], key=lambda item: item["language"]),
        "images": {
            language: {kind: [(image["id"], image["sha256"]) for image in images]
                       for kind, images in kinds.items()}
            for language, kinds in snapshot["images"].items()
        },
    }


def publish(listings: dict, media: dict, expected: Path | None) -> None:
    import publish_play as play

    http = play.session()
    edit = play.call(http, "POST", f"{play.API}/edits")["id"]

    def snapshot(edit_id: str) -> dict:
        documents = play.call(http, "GET", f"{play.API}/edits/{edit_id}/listings").get("listings", [])
        images = {
            document["language"]: {
                kind: play.call(http, "GET",
                                f"{play.API}/edits/{edit_id}/listings/{document['language']}/{kind}").get("images", [])
                for kind in IMAGE_TYPES
            }
            for document in documents
        }
        return {"listings": documents, "images": images}

    def verify(actual: dict, hashes: dict) -> None:
        by_language = {item["language"]: item for item in actual["listings"]}
        for language, listing in listings.items():
            for field, value in listing.items():
                if by_language.get(language, {}).get(field) != value:
                    raise RuntimeError(f"Google Play did not retain {language} {field}")
            for kind, expected_hashes in hashes[language].items():
                found = [item["sha256"].lower() for item in actual["images"][language][kind]]
                if found != expected_hashes:
                    raise RuntimeError(f"Google Play did not retain the expected {language} {kind} order/content")

    try:
        current = snapshot(edit)
        if expected and fingerprint(current) != fingerprint(json.loads(expected.read_text(encoding="utf-8"))):
            raise RuntimeError("The live listing changed since the backup; refusing to overwrite a concurrent edit")
        backup = ROOT / "release" / "store-backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup.mkdir(parents=True, exist_ok=False)
        (backup / "metadata.json").write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        for language, kinds in current["images"].items():
            folder = backup / language
            folder.mkdir()
            for kind, images in kinds.items():
                for index, image in enumerate(images):
                    url = urlsplit(image["url"])
                    if url.scheme != "https" or not (url.hostname or "").endswith(".googleusercontent.com"):
                        raise RuntimeError("Unexpected image backup host; refusing to send publisher credentials")
                    # Public image downloads use no authenticated API session.
                    with urlopen(image["url"], timeout=60) as response:
                        (folder / f"{kind}-{index}.image").write_bytes(response.read())
        print(f"Original copy and graphics backed up under {backup.relative_to(ROOT)}", flush=True)

        old = {item["language"]: item for item in current["listings"]}
        hashes: dict = {}
        for language, listing in listings.items():
            document = {**old.get(language, {}), **listing}
            play.call(http, "PUT", f"{play.API}/edits/{edit}/listings/{language}", json=document)
            hashes[language] = {}
            for kind, paths in media[language].items():
                desired = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
                existing = [
                    image["sha256"].lower()
                    for image in current["images"].get(language, {}).get(kind, [])
                ]
                hashes[language][kind] = desired
                if existing == desired:
                    print(f"{language}: kept unchanged {kind} ({len(paths)})", flush=True)
                    continue
                url = f"{play.API}/edits/{edit}/listings/{language}/{kind}"
                play.call(http, "DELETE", url)
                for path, digest in zip(paths, desired):
                    data = path.read_bytes()
                    result = play.call(
                        http, "POST", f"{play.UPLOAD}/edits/{edit}/listings/{language}/{kind}?uploadType=media",
                        data=data, headers={"Content-Type": "image/jpeg"},
                    )["image"]
                    if result["sha256"].lower() != digest:
                        raise RuntimeError(f"Uploaded image hash does not match {path}")
                print(f"{language}: staged {kind} ({len(paths)})", flush=True)
        verify(snapshot(edit), hashes)
        play.call(http, "POST", f"{play.API}/edits/{edit}:validate")
        play.call(http, "POST", f"{play.API}/edits/{edit}:commit")
        edit = ""

        check = play.call(http, "POST", f"{play.API}/edits")["id"]
        try:
            saved = snapshot(check)
            verify(saved, hashes)
            (backup / "published.json").write_text(
                json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8",
            )
        finally:
            response = http.delete(f"{play.API}/edits/{check}", timeout=60)
            response.raise_for_status()
        print("Store listing changes persisted and sent for Google review.")
    finally:
        if edit:
            response = http.delete(f"{play.API}/edits/{edit}", timeout=60)
            response.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true", help="Save the store edit and send it for Google review")
    parser.add_argument("--expect-backup", type=Path, help="Refuse to replace metadata/images changed since this snapshot")
    args = parser.parse_args()
    listings, media = {}, {}
    for language in LOCALES:
        listing = read_listing(STORE / f"listing-{language}.txt", language)
        video = STORE / language / "video-url.txt"
        if video.is_file():
            listing["video"] = video_url(video.read_text(encoding="utf-8"))
        listings[language] = listing
        media[language] = media_files(STORE / language)
        print(f"{language}: title {len(listing['title'])}/30, short {len(listing['shortDescription'])}/80, "
              f"full {len(listing['fullDescription'])}/4000; six screenshots + feature graphic")
    if args.commit:
        publish(listings, media, args.expect_backup)
    else:
        print("Local validation only; nothing sent to Google Play.")


if __name__ == "__main__":
    main()
