"""Compose localized Play assets from real Flutter captures, never concept art."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "play_store"
CAPTURES = ROOT / ".tmp" / "marketing-captures"
SIZE = (1080, 1920)
SCENES = ("01-weekend", "02-results", "03-standings", "04-calendar", "05-seasons", "06-series")
COPY = {
    "pl-PL": {
        "labels": ("KALENDARZ", "WYNIKI", "KLASYFIKACJE", "PLAN MIESIĄCA", "SEZONY", "SERIE GT3"),
        "headlines": (
            "Twój weekend.\nW jednym miejscu.",
            "Wyniki sesji.\nBez szukania.",
            "Kierowcy i zespoły.\nWalka o punkty.",
            "Cały miesiąc.\nCzytelny plan.",
            "Sezon po sezonie.\nBez długiej listy.",
            "Twoje serie.\nTwój kalendarz.",
        ),
        "alt": (
            "Lista wyścigów z wyborem serii, odliczaniem do następnej sesji i godzinami wydarzeń.",
            "Wyniki wyścigu WEC na Monzy: pozycje, załogi, zespoły, klasy i czasy.",
            "Klasyfikacja kierowców F1 w wybranym sezonie, z punktami i stratą do lidera.",
            "Miesięczny kalendarz z wydarzeniami oznaczonymi kolorami poszczególnych serii.",
            "Przełącznik sezonów nad kalendarzem nadchodzących wydarzeń.",
            "Ustawienia wyboru GT Europe, GT International, GT America, GT Asia, GT Australia i British GT.",
        ),
        "feature": "Twój weekend.\nW jednym miejscu.",
        "feature_subtitle": "Kalendarz, wyniki i klasyfikacje",
        "feature_alt": "Secar: kalendarz motorsportu, wyniki i klasyfikacje z podglądem rzeczywistej aplikacji.",
    },
    "en-US": {
        "labels": ("RACE CALENDAR", "RESULTS", "STANDINGS", "MONTH VIEW", "SEASONS", "GT3 SERIES"),
        "headlines": (
            "Race weekends.\nAll in one place.",
            "Session results.\nWithout the search.",
            "Drivers. Teams.\nThe points battle.",
            "The whole month.\nA clearer plan.",
            "Season by season.\nNo endless lists.",
            "Your series.\nYour calendar.",
        ),
        "alt": (
            "Race event list with series selection, a countdown to the next session and event times.",
            "WEC race results at Monza showing positions, crews, teams, classes and times.",
            "F1 driver standings for the selected season, with points and gaps to the leader.",
            "Monthly calendar with events color-coded by racing series.",
            "Season switcher above the calendar of upcoming race events.",
            "Settings for GT Europe, GT International, GT America, GT Asia, GT Australia and British GT.",
        ),
        "feature": "Race weekends.\nAll in one place.",
        "feature_subtitle": "Calendars, results and standings",
        "feature_alt": "Secar motorsport calendars, results and standings with a preview of the actual app.",
    },
}


@lru_cache(maxsize=16)
def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ROOT / "assets" / "fonts" / name), size)


@lru_cache(maxsize=2)
def background(size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(size[1]):
        amount = y / max(1, size[1] - 1)
        draw.line((0, y, size[0], y), fill=(
            round(26 - 15 * amount), round(31 - 17 * amount), round(48 - 26 * amount),
        ))
    width, height = size
    draw.polygon(((width * .71, 0), (width, 0), (width, height * .37)),
                 fill=(184, 12, 27))
    draw.polygon(((width * .94, 0), (width, 0), (width, height * .08)),
                 fill=(250, 51, 56))
    draw.polygon(((0, height * .82), (width * .18, height), (0, height)),
                 fill=(97, 13, 30))
    return image


def paste_ui(canvas: Image.Image, screenshot: Image.Image, x: int, y: int, width: int) -> None:
    height = round(screenshot.height * width / screenshot.width)
    ui = screenshot.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    mask = Image.new("L", ui.size)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=22, fill=255)
    canvas.paste(ui, (x, y), mask)
    ImageDraw.Draw(canvas).rounded_rectangle(
        (x, y, x + width - 1, y + height - 1), radius=22,
        outline=(70, 77, 91), width=2,
    )


def screenshot_asset(source: Image.Image, locale: str, scene: str) -> Image.Image:
    if source.size != (1080, 2000):
        raise ValueError(f"{scene}: expected an undistorted 1080x2000 app capture, got {source.size}")
    index = SCENES.index(scene)
    canvas = background(SIZE).copy()
    draw = ImageDraw.Draw(canvas)
    draw.text((54, 35), f"SECAR / {COPY[locale]['labels'][index]}",
              font=font("Roboto-Medium.ttf", 23), fill=(255, 142, 142))
    for row, line in enumerate(COPY[locale]["headlines"][index].splitlines()):
        face = font("BarlowCondensed-Bold.ttf", 72)
        if draw.textbbox((0, 0), line, font=face)[2] > 960:
            raise ValueError(f"Headline exceeds its safe area: {line}")
        draw.text((54, 73 + row * 73), line, font=face, fill=(250, 250, 253))
    width = round(1653 * source.width / source.height)
    paste_ui(canvas, source, (SIZE[0] - width) // 2, 250, width)
    return canvas


def feature_asset(screenshot: Image.Image, locale: str) -> Image.Image:
    canvas = background((1024, 500)).copy()
    draw = ImageDraw.Draw(canvas)
    draw.text((80, 55), "SECAR", font=font("BarlowCondensed-BoldItalic.ttf", 43),
              fill=(255, 155, 155))
    for row, line in enumerate(COPY[locale]["feature"].splitlines()):
        draw.text((80, 125 + 72 * row), line,
                  font=font("BarlowCondensed-Bold.ttf", 65), fill=(252, 252, 255))
    draw.rectangle((82, 300, 225, 305), fill=(255, 72, 76))
    draw.text((82, 333), COPY[locale]["feature_subtitle"],
              font=font("Roboto-Medium.ttf", 23), fill=(224, 229, 239))
    draw.text((82, 385), "F1 / WEC / IMSA / INDYCAR / GT3",
              font=font("BarlowCondensed-SemiBold.ttf", 21), fill=(176, 187, 207))
    paste_ui(canvas, screenshot, 720, 55, 216)
    return canvas


def contact_sheet(images: list[Image.Image], locale: str) -> Image.Image:
    width, gap = 340, 24
    height = round(SIZE[1] * width / SIZE[0])
    canvas = Image.new("RGB", (width * 3 + gap * 4, height * 2 + gap * 3 + 80), (16, 20, 30))
    draw = ImageDraw.Draw(canvas)
    draw.text((gap, 18), f"SECAR / {locale} / GOOGLE PLAY",
              font=font("BarlowCondensed-Bold.ttf", 36), fill=(250, 250, 253))
    for index, image in enumerate(images):
        canvas.paste(image.resize((width, height), Image.Resampling.LANCZOS),
                     (gap + (index % 3) * (width + gap), 80 + gap + (index // 3) * (height + gap)))
    return canvas


def render_video(locale: str, ffmpeg: str) -> None:
    manifest = json.loads((CAPTURES / locale / "timeline.json").read_text(encoding="utf-8"))
    fps = manifest["fps"]
    output = OUT / "videos" / f"secar-{locale}.mp4"
    output.parent.mkdir(exist_ok=True)
    log = ROOT / ".tmp" / f"store-video-{locale}.log"
    command = [
        ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pixel_format", "rgb24",
        "-video_size", "1080x1920", "-framerate", str(fps), "-i", "pipe:0",
        "-an", "-c:v", "libx264", "-threads", "2", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ]
    with log.open("wb") as errors:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=errors)
        try:
            for entry in manifest["timeline"]:
                with Image.open(CAPTURES / locale / entry["file"]) as source:
                    frame = screenshot_asset(source, locale, entry["scene"]).tobytes()
                for _ in range(entry["frames"]):
                    process.stdin.write(frame)
        except BrokenPipeError as error:
            process.wait()
            raise RuntimeError(log.read_text(encoding="utf-8", errors="replace")) from error
        finally:
            process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError(log.read_text(encoding="utf-8", errors="replace"))
    seconds = sum(entry["frames"] for entry in manifest["timeline"]) / fps
    print(f"{locale}: {seconds:.2f}s real-app demo, {output.stat().st_size / 1e6:.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", action="store_true", help="Also encode the recorded in-app gestures")
    parser.add_argument("--ffmpeg", help="Path to an existing ffmpeg executable")
    args = parser.parse_args()
    ffmpeg = args.ffmpeg or shutil.which("ffmpeg")
    if args.video and not ffmpeg:
        raise SystemExit("ffmpeg is required for --video; provide --ffmpeg with its executable path.")
    OUT.mkdir(exist_ok=True)
    for locale, text in COPY.items():
        folder = OUT / locale
        phone = folder / "phone-screenshots"
        phone.mkdir(parents=True, exist_ok=True)
        images = []
        for scene in SCENES:
            with Image.open(CAPTURES / locale / f"{scene}.png") as source:
                image = screenshot_asset(source, locale, scene)
            image.save(phone / f"{scene}.jpg", quality=94, subsampling=0, optimize=True)
            images.append(image)
        with Image.open(CAPTURES / locale / "01-weekend.png") as source:
            feature_asset(source, locale).save(folder / "feature-graphic.jpg", quality=95, subsampling=0, optimize=True)
        descriptions = [f"featureGraphic: {text['feature_alt']}"]
        descriptions.extend(f"{scene}: {alt}" for scene, alt in zip(SCENES, text["alt"]))
        if any(len(line.split(": ", 1)[1]) > 140 for line in descriptions):
            raise ValueError(f"{locale}: alt text exceeds 140 characters")
        (folder / "alt-text.txt").write_text("\n".join(descriptions) + "\n", encoding="utf-8")
        previews = OUT / "previews"
        previews.mkdir(exist_ok=True)
        contact_sheet(images, locale).save(previews / f"{locale}.jpg", quality=92, optimize=True)
        if args.video:
            render_video(locale, ffmpeg)
        print(f"{locale}: six 1080x1920 screenshots and a 1024x500 feature graphic")


if __name__ == "__main__":
    main()
