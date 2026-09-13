"""Cache official portraits that cannot be hot-linked reliably on Flutter web."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

from fetch_data import slugify

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"User-Agent": "MotorSport-Calendar/0.1 (+https://github.com/SoY256/MotorSport-Calendar)"}


def cache_series(series: str, *, all_remote: bool = False) -> None:
    bundled = ROOT / "assets" / "data" / series / "2026" / "standings_drivers.json"
    document = json.loads(bundled.read_text(encoding="utf-8"))
    target_dir = ROOT / "assets" / "portraits" / series
    target_dir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for driver in document["data"]:
        url = driver.get("imageUrl", "")
        if not url.startswith("http") or (not all_remote and "/FullBody/" not in url):
            continue
        driver_id = slugify(f"{driver['givenName']} {driver['familyName']}")
        target = target_dir / f"{driver_id}.jpg"
        jobs.append((driver, url, target))

    def download(job: tuple[dict, str, Path]) -> tuple[dict, Path] | None:
        driver, url, target = job
        try:
            if not target.exists():
                with urlopen(Request(url, headers=HEADERS), timeout=45) as response:
                    target.write_bytes(response.read())
        except Exception as error:
            print(f"MISS {series}/{driver['givenName']} {driver['familyName']}: {error}")
            return None
        return driver, target

    cached = 0
    with ThreadPoolExecutor(max_workers=12) as pool:
      for result in pool.map(download, jobs):
        if result is None:
          continue
        driver, target = result
        driver["imageUrl"] = f"assets/portraits/{series}/{target.name}"
        cached += 1

    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    bundled.write_text(text, encoding="utf-8")
    (ROOT / "data" / series / "2026" / "standings_drivers.json").write_text(text, encoding="utf-8")
    print(f"{series}: cached {cached} official portraits")


def main() -> None:
    cache_series("indycar")
    cache_series("indynxt")
    cache_series("imsa", all_remote=True)


if __name__ == "__main__":
    main()
