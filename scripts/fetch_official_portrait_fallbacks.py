"""Collect identity-safe portrait fallbacks from official championship pages."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import urljoin

from http_retry import read

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"User-Agent": "MotorSport-Calendar/0.1 (+https://github.com/SoY256/MotorSport-Calendar)"}

F3_PAGES = {
    "Louis Sharp": "https://www.fiaformula3.com/Drivers/1472/Louis-Sharp",
    "Christian Ho": "https://www.fiaformula3.com/en/latest/article/christian-ho-my-ultimate-driver.5v8AR1WRLTp6DiNqcun2Sy",
    "Patrick Heuzenroeder": "https://www.fiaformula3.com/en/drivers/patrick-heuzenroeder",
    "Woohyun Shin": "https://www.fiaformula3.com/en/drivers/michael-woohyun-shin",
}

# Individually verified driver portraits. These are kept explicit so a generic
# search result can never silently assign a different person's face.
CURATED_PORTRAITS = {
    "Louis Sharp": "https://res.cloudinary.com/prod-f2f3/image/upload/v1767549873/f3/global/drivers/2026/PreSeason/Sharp_Web026.jpg",
    "Philip Hanson": "https://upload.wikimedia.org/wikipedia/commons/0/0b/Philip_Hanson_2020_%28cropped%29.jpg",
    "Luis Felipe Derani": "https://www.cadillac.com/content/dam/cadillac/na/us/english/ux/blackwing-track-editions/pipo-derani-portrait-l.jpg?imwidth=960",
    "Thomas Fleming": "https://www.gt-world-challenge-europe.com/timthumb.php?src=%2Fimages%2Fdrivers%2Fphoto_3836.png&w=700",
    "Giammarco Levorato": "https://storage.googleapis.com/ecm-prod/assets/1/pilote/5829/giammarco-levorato_513fd8.png",
    "Rory van der Steur": "https://images.squarespace-cdn.com/content/v1/67d6dce0d010a12f9b238f7d/1773837905445-DOT3YG7XS0IXWL3F8W5F/Rory%2Bvan%2Bder%2BSteur.jpg?format=2500w",
    "Gerry Kraut": "https://storage.googleapis.com/unitedautosports-com.appspot.com/cache/images/800_450_crop_uamlmcbarcelona2021012_AnfEr4DKg9.jpg",
    "Max van der Snel": "https://images.ad.nl/N2UzNzRmYjE2MTdmY2I4OGM4N2IvZGlvLzI0MTg1OTYwMC9mb2N1cy1hbmQtZmlsbC8wLjQ2LzAuMzkvMTIwMC82MzA/de-haagse-autocoureur-max-van-der-snel-20",
    "Nico Mueller": "https://www.fiawec.com/umbrella_media/2025-nicomuller-ppm-wec-680b38d30b868183958410.jpg",
    "Nick Boulle": "https://storage.googleapis.com/ecm-prod/assets/1/pilote/5887/nick-boulle_76849a.png",
    "Johannes Zelger": "https://www.24h-en-piste.com/Pilotes/Pilote24h_4079.jpg",
}


def page(url: str) -> str:
    return read(url, HEADERS, timeout=45).decode("utf-8", "replace")


def image_from_tag(tag: str) -> str | None:
    for attribute in ("src", "data-src", "data-lazy-src"):
        match = re.search(rf'{attribute}=["\']([^"\']+)', tag, re.I)
        if match:
            return html.unescape(match.group(1))
    source = re.search(r'srcset=["\']([^"\']+)', tag, re.I)
    if source:
        return html.unescape(source.group(1).split(",")[-1].strip().split()[0])
    return None


def og_image(url: str) -> str | None:
    body = page(url)
    for tag in re.findall(r"<meta\b[^>]+>", body, re.I):
        if re.search(r'(?:property|name)=["\'](?:og:image|twitter:image)["\']', tag, re.I):
            match = re.search(r'content=["\']([^"\']+)', tag, re.I)
            if match:
                return urljoin(url, html.unescape(match.group(1)))
    return None


def imsa_portraits() -> dict[str, str]:
    result: dict[str, str] = {}
    for url in (
        "https://www.imsa.com/weathertech/drivers/",
        "https://www.imsa.com/michelinpilotchallenge/drivers/",
    ):
        try:
            body = page(url)
        except RuntimeError as error:
            print(f"Skipped unavailable IMSA page {url}: {error}")
            continue
        for tag in re.findall(r"<img\b[^>]+>", body, re.I):
            alt = re.search(r'alt=["\']Photo of ([^"\']+)', tag, re.I)
            image = image_from_tag(tag)
            if alt and image:
                result[html.unescape(alt.group(1)).strip()] = urljoin(url, image)
    return result


def main() -> None:
    found = {name: image for name, url in F3_PAGES.items() if (image := og_image(url))}
    found.update(imsa_portraits())
    found.update(CURATED_PORTRAITS)
    output = ROOT / "data" / "sources" / "official_driver_portraits.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(found, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(found)} official portrait fallbacks")


if __name__ == "__main__":
    main()
